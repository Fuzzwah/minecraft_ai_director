#!/usr/bin/env python3
"""Manage the isolated itzg/Podman vanilla server without touching mc_do_not_die.

Uses the reference server's rootless `podman run`, named /data volume, UID/GID,
VANILLA type and restart=no lifecycle. Game and RCON ports are loopback-only.
Offline mode requires --offline-fixtures and is never a production default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
NAME = "mc_ai_director_test"
VOLUME = "mc_ai_director_test_data"
IMAGE = "docker.io/itzg/minecraft-server@sha256:783d2712019a3996b4168752517a08d3448ef8995879b200316c3888f98dc394"


def podman(*args, capture=False, check=True):
    return subprocess.run(["podman", *args], check=check, text=True, capture_output=capture)


def inspect():
    result = podman("container", "inspect", NAME, capture=True, check=False)
    if result.returncode:
        return None
    value = json.loads(result.stdout)[0]
    settings = dict(item.split("=", 1) for item in value["Config"]["Env"] if "=" in item)
    mounts = value.get("Mounts", [])
    if settings.get("TYPE") != "VANILLA" or settings.get("VERSION") != "26.3" or not any(item.get("Name") == VOLUME and item.get("Destination") == "/data" for item in mounts):
        raise RuntimeError("Existing test container does not match this project's isolated vanilla26.3 volume/configuration")
    return value


def env_file(path):
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value
    return result


def private_file(path, text):
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(text)
    path.chmod(0o600)


def write_director_env(password, game_port, rcon_port):
    path = RUNTIME / "director-test.env"
    settings = {
        "RCON_HOST": "127.0.0.1", "RCON_PORT": str(rcon_port), "RCON_PASSWORD": password,
        "MINECRAFT_HOST": "127.0.0.1", "MINECRAFT_PORT": str(game_port),
        "DIRECTOR_DB": str(RUNTIME / "test-director.sqlite3"),
        "DIRECTOR_SOCKET": str(RUNTIME / "test-director.sock"), "DEMO_MODE": "1",
        "MINECRAFT_SERVER_JAR": str(RUNTIME / "official26.3.jar"),
    }
    private_file(path, "".join(f"{key}={value}\n" for key, value in settings.items()))
    print(f"Private director environment: {path} (credentials are not printed)")


def start(args):
    existing = inspect()
    if existing is not None:
        settings = dict(item.split("=", 1) for item in existing["Config"]["Env"] if "=" in item)
        offline = settings.get("ONLINE_MODE", "true").lower() == "false"
        if offline != args.offline_fixtures:
            raise RuntimeError("Existing test container's online mode differs; use its explicit mode flag. Configuration is not silently replaced.")
        if existing["State"]["Status"] != "running":
            podman("start", NAME)
        ports = existing["HostConfig"]["PortBindings"]
        write_director_env(settings["RCON_PASSWORD"], int(ports["25565/tcp"][0]["HostPort"]), int(ports["25575/tcp"][0]["HostPort"]))
        print(f"{NAME} running; follow `python3 tools/test_server.py logs` for readiness")
        return
    approved = os.environ.get("EULA", "").upper()
    if approved not in ("TRUE", "1"):
        raise RuntimeError("Server owner must explicitly accept the Minecraft EULA: set EULA=TRUE before start")
    saved = env_file(RUNTIME / "test-server.env")
    password = os.environ.get("RCON_PASSWORD") or saved.get("RCON_PASSWORD") or secrets.token_hex(32)
    if any(char in password for char in "\r\n\x00"):
        raise RuntimeError("RCON password contains invalid environment-file characters")
    settings = {
        "EULA": "TRUE", "TYPE": "VANILLA", "VERSION": "26.3", "UID": str(os.getuid()), "GID": str(os.getgid()),
        "MEMORY": "2G", "ENABLE_RCON": "true", "RCON_PASSWORD": password, "RCON_PORT": "25575",
        "OVERRIDE_SERVER_PROPERTIES": "true",
        "ONLINE_MODE": "false" if args.offline_fixtures else "true",
        "ENABLE_WHITELIST": "false" if args.offline_fixtures else "true",
        "ENFORCE_WHITELIST": "false" if args.offline_fixtures else "true",
        "MODE": "survival", "DIFFICULTY": "normal", "SPAWN_PROTECTION": "0",
        "VIEW_DISTANCE": "4", "SIMULATION_DISTANCE": "4", "MAX_PLAYERS": "20",
        "PAUSE_WHEN_EMPTY_SECONDS": "0",
        "MOTD": "Minecraft AI Director isolated vanilla26.3 test server",
    }
    private_file(RUNTIME / "test-server.env", "".join(f"{key}={value}\n" for key, value in settings.items()))
    podman("run", "--detach", "--name", NAME, "--env-file", str(RUNTIME / "test-server.env"),
           "--volume", f"{VOLUME}:/data", "--publish", f"127.0.0.1:{args.game_port}:25565",
           "--publish", f"127.0.0.1:{args.rcon_port}:25575", "--restart", "no", args.image)
    write_director_env(password, args.game_port, args.rcon_port)
    if args.offline_fixtures:
        print("OFFLINE FIXTURES: loopback-only unauthenticated clients; never use this configuration publicly")
    print(f"Started {NAME}; game localhost:{args.game_port}, RCON localhost:{args.rcon_port}. Existing servers/volumes untouched.")


def status():
    value = inspect()
    if value is None:
        print(json.dumps({"container": NAME, "state": "absent", "volume": VOLUME}))
        return
    print(json.dumps({"container": NAME, "state": value["State"]["Status"], "image": value["Config"]["Image"],
                      "volume": VOLUME, "restart": value["HostConfig"]["RestartPolicy"]["Name"],
                      "ports": value["HostConfig"]["PortBindings"]}, indent=2))


def install_pack():
    if inspect() is None:
        raise RuntimeError("Start the test container before installing the pack")
    state = podman("exec", NAME, "rcon-cli", "data get storage keeper:runtime", capture=True)
    if "{" in state.stdout:
        sys.path.insert(0, str(ROOT))
        from mc_director.snbt import extract
        if extract(state.stdout).get("enabled"):
            raise RuntimeError("Pause the director before replacing/reloading its datapack")
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    source = ROOT / "datapack"
    if not (source / "pack.mcmeta").is_file():
        raise RuntimeError("Repository datapack is absent; no placeholder is installed")
    target = RUNTIME / "keeper.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source))
    target.chmod(0o644)
    podman("exec", "--user", "0", NAME, "mkdir", "-p", "/data/world/datapacks")
    podman("cp", str(target), f"{NAME}:/data/world/datapacks/keeper.zip")
    podman("exec", "--user", "0", NAME, "chown", "1000:1000", "/data/world/datapacks/keeper.zip")
    podman("exec", NAME, "rcon-cli", "reload")
    jar = RUNTIME / "official26.3.jar"
    podman("cp", f"{NAME}:/data/minecraft_server.26.3.jar", str(jar))
    with jar.open("rb") as handle:
        if hashlib.file_digest(handle, "sha1").hexdigest() != "33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c":
            raise RuntimeError("Running server jar is not Mojang's official vanilla26.3 artifact")
    print("Installed repository datapack as keeper.zip; reload disables mutations pending director handshake")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    launch = commands.add_parser("start")
    launch.add_argument("--offline-fixtures", action="store_true", help="Explicit loopback-only unauthenticated test clients")
    launch.add_argument("--game-port", type=int, default=25566)
    launch.add_argument("--rcon-port", type=int, default=25576)
    launch.add_argument("--image", default=IMAGE)
    commands.add_parser("stop")
    commands.add_parser("restart")
    commands.add_parser("logs")
    commands.add_parser("status")
    commands.add_parser("install-pack")
    director = commands.add_parser("director", help="Run the director or its admin CLI with the private test environment")
    director.add_argument("command", nargs=argparse.REMAINDER)
    rcon = commands.add_parser("rcon")
    rcon.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == "start":
        if not 1 <= args.game_port <= 65535 or not 1 <= args.rcon_port <= 65535 or args.game_port == args.rcon_port:
            parser.error("Game/RCON ports must be distinct valid ports")
        start(args)
    elif args.action == "status":
        status()
    elif args.action == "install-pack":
        install_pack()
    elif args.action == "director":
        path = RUNTIME / "director-test.env"
        if not path.is_file():
            raise RuntimeError("Start the managed test server before running its director")
        environment = os.environ | env_file(path)
        if "DEMO_MODE" in os.environ:
            environment["DEMO_MODE"] = os.environ["DEMO_MODE"]
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        os.chdir(ROOT)
        os.execve(sys.executable, [sys.executable, str(ROOT / "director.py"), *command], environment)
    elif args.action == "rcon":
        if not args.command:
            parser.error("rcon requires an operator command")
        if inspect() is None:
            raise RuntimeError("Test container is absent")
        podman("exec", NAME, "rcon-cli", " ".join(args.command))
    elif args.action == "logs":
        podman("logs", "--follow", NAME)
    else:
        if inspect() is None:
            raise RuntimeError("Test container is absent")
        podman(args.action, NAME)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"test-server: {exc}", file=sys.stderr)
        raise SystemExit(2)
