#!/usr/bin/env python3
"""
Minecraft AI Director - small working prototype for a Java Edition server.

What it does:
  * tails latest.log and keeps a short history of interesting events
  * uses RCON to discover online players
  * periodically asks an OpenAI-compatible LLM for a constrained collect quest
  * announces the quest in-game
  * detects when the player brings the requested items to world spawn
  * consumes the items and grants a reward from a server-controlled reward table

The LLM NEVER emits commands. It only chooses from validated quest fields.

No Python packages are required; this file uses only the standard library.
"""

from __future__ import annotations

import json
import os
import random
import re
import socket
import struct
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


# ----------------------------- configuration -----------------------------

RCON_HOST = os.getenv("RCON_HOST", "127.0.0.1")
RCON_PORT = int(os.getenv("RCON_PORT", "25575"))
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "")

LOG_PATH = Path(os.getenv("MINECRAFT_LOG", "./logs/latest.log"))
STATE_PATH = Path(os.getenv("DIRECTOR_STATE", "./director_state.json"))

SPAWN_X = float(os.getenv("SPAWN_X", "0"))
SPAWN_Y = float(os.getenv("SPAWN_Y", "64"))
SPAWN_Z = float(os.getenv("SPAWN_Z", "0"))
SPAWN_RADIUS = float(os.getenv("SPAWN_RADIUS", "6"))

POLL_SECONDS = float(os.getenv("POLL_SECONDS", "5"))
QUEST_INTERVAL_SECONDS = int(os.getenv("QUEST_INTERVAL_SECONDS", "600"))

# OpenAI-compatible Chat Completions endpoint. Examples:
#   OpenRouter: https://openrouter.ai/api/v1/chat/completions
#   Ollama:     http://127.0.0.1:11434/v1/chat/completions
LLM_URL = os.getenv("LLM_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")

# Set to 1 to prove the game loop works without making an LLM request.
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"

ALLOWED_ITEMS = {
    "minecraft:iron_ingot": (3, 12),
    "minecraft:copper_ingot": (4, 16),
    "minecraft:gold_ingot": (2, 8),
    "minecraft:coal": (6, 20),
    "minecraft:redstone": (6, 20),
    "minecraft:lapis_lazuli": (4, 16),
    "minecraft:oak_log": (6, 20),
    "minecraft:bread": (3, 10),
    "minecraft:carrot": (5, 16),
    "minecraft:cooked_beef": (3, 10),
}

# The model selects only a tier. Your code owns the actual economy.
REWARDS = {
    1: [
        ("give {player} minecraft:emerald 3", "3 emeralds"),
        ("give {player} minecraft:gold_ingot 4", "4 gold ingots"),
    ],
    2: [
        ("give {player} minecraft:diamond 2", "2 diamonds"),
        ("give {player} minecraft:emerald 8", "8 emeralds"),
    ],
    3: [
        ("give {player} minecraft:diamond 4", "4 diamonds"),
        ("give {player} minecraft:ancient_debris 1", "1 ancient debris"),
    ],
}

PLAYER_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")
COUNT_RE = re.compile(r"\b(\d+)\b")


# ----------------------------- RCON client -----------------------------

class RconError(RuntimeError):
    pass


class MinecraftRcon:
    """Minimal Minecraft/Source RCON client using only the stdlib."""

    SERVERDATA_RESPONSE_VALUE = 0
    SERVERDATA_EXECCOMMAND = 2
    SERVERDATA_AUTH_RESPONSE = 2
    SERVERDATA_AUTH = 3

    def __init__(self, host: str, port: int, password: str, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self.request_id = random.randint(1, 2_000_000_000)

    def __enter__(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)
        self._send_packet(self.request_id, self.SERVERDATA_AUTH, self.password)
        rid, ptype, _ = self._recv_packet()
        if rid == -1 or ptype != self.SERVERDATA_AUTH_RESPONSE:
            raise RconError("RCON authentication failed")
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.sock:
            self.sock.close()
            self.sock = None

    def command(self, command: str) -> str:
        if not self.sock:
            raise RconError("RCON is not connected")
        self.request_id += 1
        rid = self.request_id
        self._send_packet(rid, self.SERVERDATA_EXECCOMMAND, command)
        response_id, _ptype, payload = self._recv_packet()
        if response_id != rid:
            raise RconError(f"Unexpected RCON response id {response_id}; expected {rid}")
        return payload

    def _send_packet(self, request_id: int, packet_type: int, payload: str) -> None:
        assert self.sock is not None
        body = struct.pack("<ii", request_id, packet_type) + payload.encode("utf-8") + b"\x00\x00"
        packet = struct.pack("<i", len(body)) + body
        self.sock.sendall(packet)

    def _recv_exact(self, size: int) -> bytes:
        assert self.sock is not None
        chunks = []
        received = 0
        while received < size:
            chunk = self.sock.recv(size - received)
            if not chunk:
                raise RconError("RCON connection closed unexpectedly")
            chunks.append(chunk)
            received += len(chunk)
        return b"".join(chunks)

    def _recv_packet(self) -> tuple[int, int, str]:
        raw_len = self._recv_exact(4)
        (length,) = struct.unpack("<i", raw_len)
        if length < 10 or length > 4_194_304:
            raise RconError(f"Invalid RCON packet length: {length}")
        body = self._recv_exact(length)
        request_id, packet_type = struct.unpack("<ii", body[:8])
        payload = body[8:-2].decode("utf-8", errors="replace")
        return request_id, packet_type, payload


def rcon(command: str) -> str:
    if not RCON_PASSWORD:
        raise RconError("RCON_PASSWORD is not set")
    with MinecraftRcon(RCON_HOST, RCON_PORT, RCON_PASSWORD) as client:
        response = client.command(command)
    print(f"[RCON] {command} -> {response!r}")
    return response


# ----------------------------- quests -----------------------------

@dataclass
class Quest:
    player: str
    item: str
    quantity: int
    reward_tier: int
    title: str
    announcement: str
    created_at: float


@dataclass
class State:
    active_quest: Optional[Quest] = None
    last_quest_at: float = 0.0


def save_state(state: State) -> None:
    data = {
        "active_quest": asdict(state.active_quest) if state.active_quest else None,
        "last_quest_at": state.last_quest_at,
    }
    tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)


def load_state() -> State:
    if not STATE_PATH.exists():
        return State()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        quest_data = data.get("active_quest")
        quest = Quest(**quest_data) if quest_data else None
        return State(active_quest=quest, last_quest_at=float(data.get("last_quest_at", 0)))
    except Exception as exc:
        print(f"[WARN] Could not load state: {exc}")
        return State()


def online_players() -> list[str]:
    response = rcon("list")
    if ":" not in response:
        return []
    names = response.split(":", 1)[1].strip()
    if not names:
        return []
    players = [name.strip() for name in names.split(",") if name.strip()]
    return [p for p in players if PLAYER_RE.fullmatch(p)]


def json_text(text: str) -> str:
    return json.dumps({"text": text, "color": "gold"}, separators=(",", ":"))


def announce(text: str) -> None:
    rcon(f"tellraw @a {json_text('[The Keeper] ' + text)}")


def parse_first_int(text: str) -> int:
    match = COUNT_RE.search(text)
    return int(match.group(1)) if match else 0


def items_at_spawn(quest: Quest) -> int:
    # Run clear ... 0 only if the named player is within SPAWN_RADIUS of the configured spawn.
    # In Java Edition maxCount=0 counts matching items without removing them.
    selector = f"@a[name={quest.player},distance=..{SPAWN_RADIUS:g},limit=1]"
    command = (
        f"execute in minecraft:overworld positioned {SPAWN_X:g} {SPAWN_Y:g} {SPAWN_Z:g} "
        f"as {selector} run clear @s {quest.item} 0"
    )
    return parse_first_int(rcon(command))


def complete_quest(state: State, quest: Quest) -> None:
    # Re-check and then consume only the required quantity.
    found = items_at_spawn(quest)
    if found < quest.quantity:
        return

    removed = parse_first_int(rcon(f"clear {quest.player} {quest.item} {quest.quantity}"))
    if removed < quest.quantity:
        print(f"[WARN] Expected to remove {quest.quantity}, but server reported {removed}")
        return

    reward_cmd, reward_name = random.choice(REWARDS[quest.reward_tier])
    rcon(reward_cmd.format(player=quest.player))
    rcon(f"experience add {quest.player} {quest.reward_tier * 2} levels")
    rcon(
        f"title {quest.player} title "
        + json.dumps({"text": "QUEST COMPLETE", "color": "green", "bold": True}, separators=(",", ":"))
    )
    rcon(f"playsound minecraft:ui.toast.challenge_complete master {quest.player}")
    announce(f"{quest.player} completed '{quest.title}' and received {reward_name}!")

    state.active_quest = None
    state.last_quest_at = time.time()
    save_state(state)


# ----------------------------- log tail -----------------------------

INTERESTING_PATTERNS = (
    "joined the game",
    "left the game",
    "has made the advancement",
    "has completed the challenge",
    "was slain by",
    "was shot by",
    "blew up",
    "drowned",
    "fell from a high place",
    "tried to swim in lava",
    "was blown up by",
    "went up in flames",
    "hit the ground too hard",
    "was killed by",
)


class LogTail:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None
        self.inode = None

    def open_at_end(self) -> None:
        self.close()
        self.handle = self.path.open("r", encoding="utf-8", errors="replace")
        self.handle.seek(0, os.SEEK_END)
        try:
            self.inode = self.path.stat().st_ino
        except OSError:
            self.inode = None

    def close(self) -> None:
        if self.handle:
            self.handle.close()
            self.handle = None

    def read_new(self) -> list[str]:
        if not self.path.exists():
            return []

        if self.handle is None:
            self.open_at_end()
            return []

        # Re-open after log rotation/recreation.
        try:
            inode = self.path.stat().st_ino
            if self.inode is not None and inode != self.inode:
                self.open_at_end()
                return []
        except OSError:
            return []

        lines = self.handle.readlines()
        return [line.rstrip("\n") for line in lines]


# ----------------------------- LLM -----------------------------

def strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def validate_quest(raw: dict, players: list[str]) -> Quest:
    player = str(raw.get("player", ""))
    item = str(raw.get("item", ""))
    title = str(raw.get("title", "A Small Favour"))[:60]
    announcement = str(raw.get("announcement", "Bring the requested offering to world spawn."))[:220]

    if player not in players or not PLAYER_RE.fullmatch(player):
        raise ValueError("LLM selected an invalid/offline player")
    if item not in ALLOWED_ITEMS:
        raise ValueError("LLM selected an item outside the allow-list")

    low, high = ALLOWED_ITEMS[item]
    quantity = int(raw.get("quantity", low))
    if not low <= quantity <= high:
        raise ValueError(f"quantity must be between {low} and {high} for {item}")

    reward_tier = int(raw.get("reward_tier", 1))
    if reward_tier not in REWARDS:
        raise ValueError("invalid reward tier")

    return Quest(
        player=player,
        item=item,
        quantity=quantity,
        reward_tier=reward_tier,
        title=title,
        announcement=announcement,
        created_at=time.time(),
    )


def fallback_quest(players: list[str]) -> Quest:
    """Useful for DEMO_MODE and as a graceful fallback if the LLM call fails."""
    player = random.choice(players)
    item = random.choice(list(ALLOWED_ITEMS))
    low, high = ALLOWED_ITEMS[item]
    quantity = random.randint(low, min(high, low + 5))
    pretty_item = item.split(":", 1)[1].replace("_", " ")
    return Quest(
        player=player,
        item=item,
        quantity=quantity,
        reward_tier=1 if quantity <= 6 else 2,
        title="Tribute at Spawn",
        announcement=f"{player}, bring me {quantity} {pretty_item} at world spawn. I will know when you arrive.",
        created_at=time.time(),
    )


def make_quest_with_llm(players: list[str], recent_events: list[str]) -> Quest:
    if DEMO_MODE:
        return fallback_quest(players)
    if not (LLM_URL and LLM_MODEL):
        raise RuntimeError("Set LLM_URL and LLM_MODEL, or set DEMO_MODE=1")

    allowed = {
        item: {"min": limits[0], "max": limits[1]}
        for item, limits in ALLOWED_ITEMS.items()
    }
    system = (
        "You are The Keeper, a playful Minecraft game master on a private family server. "
        "Create ONE small collect-and-return quest. The player must bring items to world spawn. "
        "Keep it fun, concise, age-appropriate, and achievable in normal survival play. "
        "Do not invent commands, items, players, coordinates, or rewards. "
        "Return JSON only with keys: player, item, quantity, reward_tier, title, announcement. "
        "reward_tier must be 1, 2, or 3."
    )
    user = {
        "online_players": players,
        "allowed_items_and_quantities": allowed,
        "recent_server_events": recent_events[-20:],
        "instruction": "Choose an online player and create one quest. Use an exact allowed item id.",
    }

    payload = json.dumps(
        {
            "model": LLM_MODEL,
            "temperature": 0.8,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user)},
            ],
        }
    ).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    request = urllib.request.Request(LLM_URL, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP {exc.code}: {body[:500]}") from exc

    content = result["choices"][0]["message"]["content"]
    raw = json.loads(strip_code_fence(content))
    return validate_quest(raw, players)


# ----------------------------- main loop -----------------------------

def interesting(line: str) -> bool:
    return any(pattern in line for pattern in INTERESTING_PATTERNS)


def main() -> int:
    print("Minecraft AI Director starting")
    print(f"  log:   {LOG_PATH}")
    print(f"  rcon:  {RCON_HOST}:{RCON_PORT}")
    print(f"  spawn: {SPAWN_X:g}, {SPAWN_Y:g}, {SPAWN_Z:g} radius {SPAWN_RADIUS:g}")
    print(f"  mode:  {'DEMO' if DEMO_MODE else 'LLM'}")

    if not RCON_PASSWORD:
        print("ERROR: RCON_PASSWORD is required", file=sys.stderr)
        return 2

    state = load_state()
    recent_events: deque[str] = deque(maxlen=40)
    tail = LogTail(LOG_PATH)

    try:
        # Fail fast if RCON details are wrong.
        print(f"Online players: {online_players()}")
    except Exception as exc:
        print(f"ERROR: Cannot talk to Minecraft RCON: {exc}", file=sys.stderr)
        return 2

    try:
        while True:
            for line in tail.read_new():
                if interesting(line):
                    recent_events.append(line)
                    print(f"[EVENT] {line}")

            try:
                players = online_players()

                if state.active_quest:
                    quest = state.active_quest
                    # Cancel cleanly if the target is offline; keep the quest persisted for next login.
                    if quest.player in players:
                        found = items_at_spawn(quest)
                        if found >= quest.quantity:
                            print(f"[QUEST] Completion detected: {quest.player} has {found} {quest.item} at spawn")
                            complete_quest(state, quest)

                elif players and time.time() - state.last_quest_at >= QUEST_INTERVAL_SECONDS:
                    try:
                        quest = make_quest_with_llm(players, list(recent_events))
                    except Exception as exc:
                        print(f"[WARN] LLM quest generation failed: {exc}")
                        quest = fallback_quest(players)

                    state.active_quest = quest
                    state.last_quest_at = time.time()
                    save_state(state)
                    announce(quest.announcement)
                    print(f"[QUEST] {quest}")

            except (OSError, RconError) as exc:
                print(f"[WARN] RCON problem: {exc}")
            except Exception as exc:
                print(f"[WARN] Director tick failed: {exc}")

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        print("\nDirector stopped.")
        return 0
    finally:
        tail.close()


if __name__ == "__main__":
    raise SystemExit(main())
