"""Owner-only Unix IPC and command line for the vanilla director."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import queue
import signal
import socket
import socketserver
import stat
import struct
import sys
import threading
import time

from .bridge import GameBridge
from .config import Config
from .engine import Engine

MAX_REQUEST = 16_384
MAX_REPLY = 2_097_152
ADMIN_ACTIONS = frozenset({"doctor", "register_chest", "unregister_chest", "pause", "resume", "start", "start_override", "cancel", "history", "rewards", "review", "quarantine", "resolve", "confirm", "reload_config"})


def log(event: str, **details):
    print(json.dumps({"time": time.time(), "event": event, **details}, ensure_ascii=False, separators=(",", ":")), flush=True)


class OwnerLock:
    def __init__(self, database: Path):
        self.path = database.with_suffix(database.suffix + ".lock")
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        self.handle = os.fdopen(descriptor, "r+")
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.handle.close()
            self.handle = None
            raise RuntimeError("Another director already owns this database; refusing a second writer") from exc
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(str(os.getpid()))
        self.handle.flush()
        return self

    def __exit__(self, *args):
        if self.handle is not None:
            self.handle.close()
            self.handle = None


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(30)
        _, uid, _ = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != os.getuid():
            return
        try:
            raw = self.rfile.readline(MAX_REQUEST + 1)
            if len(raw) > MAX_REQUEST or not raw.endswith(b"\n"):
                raise ValueError("Administrative request is oversized or incomplete")
            request = json.loads(raw)
            if not isinstance(request, dict) or set(request) != {"protocol", "action", "args"} or type(request["protocol"]) is not int or request["protocol"] != 1 or not isinstance(request["action"], str) or request["action"] not in ADMIN_ACTIONS or not isinstance(request["args"], dict):
                raise ValueError("Invalid typed administrative request")
            result = queue.Queue(maxsize=1)
            self.server.requests.put_nowait((request["action"], request["args"], f"uid:{uid}", result))
            try:
                response = result.get(timeout=25)
            except queue.Empty:
                response = {"ok": False, "error": "Administrative result timed out; inspect doctor/review before repeating a mutation"}
        except (ValueError, UnicodeError, RecursionError, queue.Full) as exc:
            response = {"ok": False, "error": str(exc)}
        except OSError:
            return
        try:
            encoded = json.dumps(response, ensure_ascii=False).encode() + b"\n"
            if len(encoded) > MAX_REPLY:
                encoded = b'{"ok":false,"error":"Administrative reply exceeds limit; query one quest/operation at a time"}\n'
            self.wfile.write(encoded)
        except OSError:
            pass  # The owner finishes/journals the action even if its CLI disconnects.


class AdminServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, path: Path):
        self.path = path
        self.requests = queue.Queue(maxsize=64)
        if len(os.fsencode(path)) > 100:
            raise ValueError("DIRECTOR_SOCKET path is too long for a Unix socket; select a shorter private path")
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.exists() or path.is_symlink():
            if not stat.S_ISSOCK(path.lstat().st_mode):
                raise RuntimeError("Administrative socket path contains a non-socket file; preserving it")
            # OwnerLock is already held. Do not unlink another live socket.
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                probe.settimeout(0.2)
                probe.connect(str(path))
            except (ConnectionRefusedError, FileNotFoundError):
                path.unlink()
            else:
                raise RuntimeError("Administrative socket is already served by another owner")
            finally:
                probe.close()
        super().__init__(str(path), _Handler)
        os.chmod(path, 0o600)
        self.thread = threading.Thread(target=self.serve_forever, name="keeper-admin", daemon=True)
        self.thread.start()

    def finish(self):
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=2)
        self.path.unlink(missing_ok=True)


def admin_call(config: Config, action: str, args: dict) -> dict:
    encoded = json.dumps({"protocol": 1, "action": action, "args": args}).encode() + b"\n"
    if len(encoded) > MAX_REQUEST:
        raise ValueError("Administrative request exceeds the size limit")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(30)
            client.connect(str(config.socket_path))
            client.sendall(encoded)
            result = bytearray()
            while not result.endswith(b"\n"):
                piece = client.recv(min(65_536, MAX_REPLY + 1 - len(result)))
                if not piece:
                    raise RuntimeError("Director disconnected; inspect state before repeating a mutation")
                result.extend(piece)
                if len(result) > MAX_REPLY:
                    raise RuntimeError("Administrative response exceeds the size limit")
            response = json.loads(result)
            if not isinstance(response, dict) or type(response.get("ok")) is not bool:
                raise RuntimeError("Invalid director IPC reply")
            if not response["ok"]:
                raise RuntimeError(response.get("error", "Administrative action rejected"))
            return response["result"]
    except FileNotFoundError as exc:
        raise RuntimeError("Director is not running at the configured socket; start the owner service first") from exc
    except socket.timeout as exc:
        raise RuntimeError("Administrative result unknown after timeout; use doctor/review, not blind mutation retries") from exc


def run(config: Config) -> int:
    if not config.rcon_password:
        raise ValueError("RCON_PASSWORD is required to run the director")
    if Path("director_state.json").exists():
        raise ValueError("Archive the prototype director_state.json before cutover; it is not imported or discarded automatically")
    obsolete = {"SPAWN_X", "SPAWN_Y", "SPAWN_Z", "SPAWN_RADIUS", "DIRECTOR_STATE"} & os.environ.keys()
    if obsolete:
        raise ValueError("Remove obsolete prototype settings: " + ", ".join(sorted(obsolete)) + "; register the delivery chest explicitly")
    os.umask(0o077)
    stopping = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopping.set())
    with OwnerLock(config.db_path):
        engine = Engine(config, GameBridge(config))
        server = None
        try:
            started = engine.start()
            server = AdminServer(config.socket_path)
            log("Director ready", socket=str(config.socket_path), version="26.3", **started)
            cursor = engine.store.one("SELECT COALESCE(MAX(sequence),0) AS sequence FROM audit_events")["sequence"]
            last_status = None
            while not stopping.is_set():
                # Network worker threads only queue requests. Engine/SQLite/RCON always
                # run on this single owner thread, including all operator mutations.
                for _ in range(8):
                    try:
                        action, arguments, actor, response = server.requests.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        result = engine.admin(action, arguments, actor=actor)
                        response.put_nowait({"ok": True, "result": result})
                    except Exception as exc:
                        response.put_nowait({"ok": False, "error": str(exc)})
                engine.tick()
                status = (engine.connected, engine.pause_reason, engine.quest["status"] if engine.quest else "IDLE")
                if status != last_status:
                    log("state", connected=status[0], pause_reason=status[1], quest_state=status[2])
                    last_status = status
                for event in engine.store.all("SELECT * FROM audit_events WHERE sequence>? ORDER BY sequence LIMIT 64", (cursor,)):
                    cursor = event["sequence"]
                    log("audit", sequence=cursor, action=event["action"], target=event["target"], actor=event["actor"], reason=event["reason"], details=json.loads(event["details"]))
                stopping.wait(0.05)
        finally:
            if server is not None:
                server.finish()
            try:
                engine.shutdown()
            except Exception as exc:
                log("shutdown_checkpoint_unavailable", error=str(exc), instruction="Inspect unresolved operations before resuming")
        log("Director stopped")
    return 0


def parser():
    result = argparse.ArgumentParser(description="Cooperative AI quests for vanilla Minecraft Java 26.3")
    result.add_argument("--config", type=Path, help="Validated JSON config; credentials remain environment-only")
    command = result.add_subparsers(dest="command")
    command.add_parser("run", help="Run the single owner service (default)")
    admin = command.add_parser("admin", help="Owner-only local administration")
    actions = admin.add_subparsers(dest="action", required=True)
    actions.add_parser("doctor")
    actions.add_parser("resume")
    actions.add_parser("reload-config")
    chest = actions.add_parser("chest").add_subparsers(dest="chest_action", required=True)
    register = chest.add_parser("register")
    for name in ("x", "y", "z"):
        register.add_argument(name, type=int)
    unregister = chest.add_parser("unregister")
    unregister.add_argument("--reason", required=True)
    pause = actions.add_parser("pause")
    pause.add_argument("--reason", required=True)
    for name in ("start", "start-override"):
        start = actions.add_parser(name)
        start.add_argument("item")
        start.add_argument("quantity", type=int)
        if name == "start-override":
            start.add_argument("--reason", required=True)
    cancel = actions.add_parser("cancel")
    cancel.add_argument("quest_id")
    cancel.add_argument("--reason", required=True)
    history = actions.add_parser("history")
    history.add_argument("quest_id", nargs="?")
    rewards = actions.add_parser("rewards")
    rewards.add_argument("player_uuid")
    review = actions.add_parser("review")
    review.add_argument("operation_id")
    quarantine = actions.add_parser("quarantine", help="Quarantine committed issuance after an independently restored player file")
    quarantine.add_argument("operation_id")
    quarantine.add_argument("--reason", required=True)
    resolve = actions.add_parser("resolve")
    resolve.add_argument("operation_id")
    resolve.add_argument("resolution", choices=("commit", "abort", "compensate", "void"))
    resolve.add_argument("--reason", required=True)
    correction = resolve.add_mutually_exclusive_group()
    correction.add_argument("--count", type=int, help="Explicit corrective Ender Chest payout amount")
    correction.add_argument("--quantity", type=int, help="Explicit corrective chest-consumption amount")
    confirm = actions.add_parser("confirm")
    confirm.add_argument("token")
    return result


def main(argv=None) -> int:
    arguments = parser().parse_args(argv)
    try:
        config = Config.load(arguments.config)
        if arguments.command != "admin":
            return run(config)
        action = arguments.action.replace("-", "_")
        payload = {key: value for key, value in vars(arguments).items() if key not in ("command", "action", "config", "chest_action", "count", "quantity") and value is not None}
        if action == "chest":
            action = arguments.chest_action + "_chest"
        if action in ("start", "start_override"):
            payload["quantity"] = arguments.quantity
        if action == "resolve":
            if arguments.count is not None:
                payload["correction"] = {"kind": "PAY", "count": arguments.count}
            elif arguments.quantity is not None:
                payload["correction"] = {"kind": "COMPLETE", "quantity": arguments.quantity}
            if arguments.resolution != "compensate" and "correction" in payload:
                raise ValueError("Correction amounts are only valid for compensate")
        result = admin_call(config, action, payload)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        domain = result.get("status")
        return 0 if domain is None or domain in ("OK", "PAUSED", "DEFERRED", "CONFIRMATION_REQUIRED", "CANCELLED") or (domain == "REVIEW_REQUIRED" and result.get("operator_paused") is True) else 1
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"director: {exc}", file=sys.stderr)
        return 2
