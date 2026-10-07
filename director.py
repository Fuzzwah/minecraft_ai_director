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
import logging
import os
import random
import re
import socket
import struct
import sys
import time
import urllib.error
import urllib.request
import hashlib
import math
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from quest_supply import (AnvilWorldReader, PlayerProfile, SupplySnapshot, build_profile,
                          parse_inventory_slots, parse_player_items)


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
SPAWN_SUPPLY_RADIUS = int(os.getenv("SPAWN_SUPPLY_RADIUS", "64"))
WORLD_DATA_PATH = Path(os.getenv("MINECRAFT_WORLD", "/minecraft/world"))


def optional_coordinate(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


OFFERING_CHEST = tuple(optional_coordinate(name) for name in (
    "OFFERING_CHEST_X", "OFFERING_CHEST_Y", "OFFERING_CHEST_Z"))

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

SETTLEMENT_ENABLED = os.getenv("DIRECTOR_SETTLEMENT_ENABLED", "0") == "1"
DRY_RUN = os.getenv("DIRECTOR_DRY_RUN", "0") == "1"
STRUCTURES_PATH = Path(os.getenv("DIRECTOR_STRUCTURES", "config/structures.json"))
SETTLEMENT_PATH = Path(os.getenv("DIRECTOR_SETTLEMENT", "config/settlement.json"))
DATABASE_PATH = Path(os.getenv("DIRECTOR_DATABASE", "director_settlement.sqlite3"))

QUEST_CATALOG = {
    # Warm-up uses verified nearby yield; later bands are progression-gated.
    "minecraft:wheat": {"min": 6, "max": 20, "band": "spawn_local"},
    "minecraft:carrot": {"min": 5, "max": 16, "band": "spawn_local"},
    "minecraft:potato": {"min": 5, "max": 16, "band": "spawn_local"},
    "minecraft:beetroot": {"min": 5, "max": 16, "band": "spawn_local"},
    "minecraft:pumpkin": {"min": 2, "max": 8, "band": "spawn_local"},
    "minecraft:melon": {"min": 2, "max": 8, "band": "spawn_local"},
    "minecraft:oak_log": {"min": 6, "max": 20, "band": "spawn_local"},
    "minecraft:bread": {"min": 3, "max": 10, "band": "spawn_local"},
    "minecraft:cooked_beef": {"min": 3, "max": 10, "band": "spawn_local"},
    "minecraft:coal": {"min": 6, "max": 20, "band": "early"},
    "minecraft:copper_ingot": {"min": 4, "max": 16, "band": "early"},
    "minecraft:iron_ingot": {"min": 3, "max": 12, "band": "early"},
    "minecraft:gold_ingot": {"min": 2, "max": 8, "band": "established"},
    "minecraft:redstone": {"min": 6, "max": 20, "band": "established"},
    "minecraft:lapis_lazuli": {"min": 4, "max": 16, "band": "established"},
    "minecraft:diamond": {"min": 1, "max": 4, "band": "established"},
    "minecraft:emerald": {"min": 1, "max": 6, "band": "established"},
    "minecraft:quartz": {"min": 4, "max": 16, "band": "nether_end"},
    "minecraft:blaze_rod": {"min": 1, "max": 6, "band": "nether_end"},
    "minecraft:nether_wart": {"min": 4, "max": 16, "band": "nether_end"},
    "minecraft:ender_pearl": {"min": 1, "max": 4, "band": "nether_end"},
    "minecraft:shulker_shell": {"min": 1, "max": 4, "band": "endgame"},
    "minecraft:netherite_scrap": {"min": 1, "max": 2, "band": "endgame"},
    "minecraft:ancient_debris": {"min": 1, "max": 2, "band": "endgame"},
}
ALLOWED_ITEMS = {item: (data["min"], data["max"]) for item, data in QUEST_CATALOG.items()}
BAND_ORDER = ("spawn_local", "early", "established", "nether_end", "endgame")
BAND_THRESHOLDS = {"spawn_local": 0, "early": 12, "established": 35, "nether_end": 70, "endgame": 115}
PRIVATE_PLAYER = "_private"
COMMUNAL_PLAYER = "_communal"
QUEST_POLICY_VERSION = 1

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
    rewards: list[dict] = field(default_factory=list)
    quest_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    lane: str = "private"
    candidate_band: str = "spawn_local"
    submission: str = "offering_chest"
    availability: list[str] = field(default_factory=list)
    policy_version: int = 0
    mode: str = "legacy"
    reference_band: str | None = None


@dataclass
class PendingReward:
    quest: Quest
    vanilla_choice: int
    consumption: str = "prepared"
    consumption_step: int = 0
    consumption_uncertain: bool = False
    consumption_commands: list[str] = field(default_factory=list)
    vanilla_step: int = 0
    vanilla_uncertain: bool = False
    recorded: bool = False
    xp_done: bool = False
    structures_done: int = 0
    last_error: str = ""
    recipients: list[str] = field(default_factory=list)
    source_snapshot: dict = field(default_factory=dict)


@dataclass
class State:
    # active_quest remains a legacy compatibility view for old state files.
    active_quest: Optional[Quest] = None
    communal_quest: Optional[Quest] = None
    private_quests: dict[str, Quest] = field(default_factory=dict)
    last_quest_at: float = 0.0
    last_communal_quest_at: float = 0.0
    private_quest_at: dict[str, float] = field(default_factory=dict)
    pending_settlement_rewards: list[PendingReward] = field(default_factory=list)
    communal_completions: int = 0
    private_completions: dict[str, int] = field(default_factory=dict)
    private_issued: dict[str, int] = field(default_factory=dict)


def save_state(state: State) -> None:
    data = {
        "active_quest": asdict(state.active_quest) if state.active_quest else None,
        "communal_quest": asdict(state.communal_quest) if state.communal_quest else None,
        "private_quests": {player: asdict(quest) for player, quest in state.private_quests.items()},
        "last_quest_at": state.last_quest_at,
        "last_communal_quest_at": state.last_communal_quest_at,
        "private_quest_at": state.private_quest_at,
        "pending_settlement_rewards": [asdict(pending) for pending in state.pending_settlement_rewards],
        "communal_completions": state.communal_completions,
        "private_completions": state.private_completions,
        "private_issued": state.private_issued,
    }
    tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # Atomic rename alone is not durable across a host crash.
    with tmp.open("r+") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(STATE_PATH)
    directory_fd = os.open(STATE_PATH.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def load_state() -> State:
    if not STATE_PATH.exists():
        return State()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("state must be an object")
        communal_completions = load_counter(data.get("communal_completions", 0), maximum=3)
        private_completions = load_counter_map(data.get("private_completions", {}), maximum=3)
        private_issued = load_counter_map(data.get("private_issued", {}))
        legacy_data = data.get("active_quest")
        legacy = load_saved_quest(legacy_data) if legacy_data is not None else None
        communal_data = data.get("communal_quest")
        communal = load_saved_quest(communal_data) if communal_data is not None else None
        private_data = data.get("private_quests", {})
        if not isinstance(private_data, dict):
            raise ValueError("private quests must be an object")
        private = {player: load_saved_quest(raw) for player, raw in private_data.items()}
        pending_ids = set()
        if legacy is not None and communal is None and not private:
            # Preserve old saves and their stable quest ID while assigning the
            # old inventory quest to the named player's private lane.
            private[legacy.player] = legacy
        pending = []
        pending_data = data.get("pending_settlement_rewards", [])
        if not isinstance(pending_data, list):
            raise ValueError("pending settlement rewards must be a list")
        for entry in pending_data:
            if not isinstance(entry, dict):
                raise ValueError("invalid pending reward")
            entry = dict(entry)
            entry["quest"] = load_saved_quest(entry["quest"])
            reward = PendingReward(**entry)
            if reward.quest.quest_id in pending_ids:
                raise ValueError("duplicate pending quest ID")
            pending_ids.add(reward.quest.quest_id)
            if type(reward.vanilla_choice) is not int or not 0 <= reward.vanilla_choice < len(REWARDS[reward.quest.reward_tier]):
                raise ValueError("invalid pending vanilla reward")
            if reward.consumption not in {"prepared", "uncertain", "done"}:
                raise ValueError("invalid pending consumption status")
            if type(reward.consumption_step) is not int or not 0 <= reward.consumption_step <= 256:
                raise ValueError("invalid pending consumption progress")
            if not isinstance(reward.consumption_commands, list) or any(not isinstance(command, str) for command in reward.consumption_commands):
                raise ValueError("invalid pending consumption commands")
            if reward.consumption_step > len(reward.consumption_commands):
                raise ValueError("pending consumption progress exceeds commands")
            if type(reward.vanilla_step) is not int or not 0 <= reward.vanilla_step <= 256:
                raise ValueError("invalid pending vanilla progress")
            if any(type(value) is not bool for value in (reward.consumption_uncertain, reward.vanilla_uncertain, reward.recorded, reward.xp_done)):
                raise ValueError("invalid pending reward flags")
            structures = sum(item["type"] == "structure" for item in reward.quest.rewards)
            if type(reward.structures_done) is not int or not 0 <= reward.structures_done <= structures:
                raise ValueError("invalid pending structure progress")
            if not isinstance(reward.last_error, str) or not isinstance(reward.recipients, list):
                raise ValueError("invalid pending reward metadata")
            pending.append(reward)
        last_quest_at = float(data.get("last_quest_at", 0))
        last_communal_quest_at = float(data.get("last_communal_quest_at", last_quest_at))
        private_quest_at = data.get("private_quest_at", {})
        if not isinstance(private_quest_at, dict):
            raise ValueError("private quest timestamps must be an object")
        private_quest_at = {str(player): float(value) for player, value in private_quest_at.items()}
        if not all(math.isfinite(value) for value in (last_quest_at, last_communal_quest_at, *private_quest_at.values())):
            raise ValueError("invalid quest timestamp")
        state = State(active_quest=legacy, communal_quest=communal, private_quests=private,
                      last_quest_at=last_quest_at, last_communal_quest_at=last_communal_quest_at,
                      private_quest_at=private_quest_at, pending_settlement_rewards=pending,
                      communal_completions=communal_completions,
                      private_completions=private_completions, private_issued=private_issued)
        migrated = (legacy_private_submission(legacy_data)
                    or legacy_private_submission(communal_data)
                    or any(legacy_private_submission(raw) for raw in private_data.values())
                    or any(legacy_private_submission(entry.get("quest")) for entry in pending_data))
        if migrated and not DRY_RUN:
            save_state(state)
        return state
    except Exception as exc:
        print(f"[WARN] Could not load state: {exc}")
        # Never discard durable reward debt or overwrite an unreadable save.
        raise ValueError(f"Cannot safely load director state: {exc}") from exc


def load_counter(value: object, *, maximum: int | None = None) -> int:
    if type(value) is not int or value < 0 or (maximum is not None and value > maximum):
        raise ValueError("invalid quest progression counter")
    return value


def load_counter_map(value: object, *, maximum: int | None = None) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError("quest progression counters must be an object")
    for player, count in value.items():
        if not isinstance(player, str) or not PLAYER_RE.fullmatch(player) or player in {COMMUNAL_PLAYER, PRIVATE_PLAYER}:
            raise ValueError("invalid quest progression player")
        load_counter(count, maximum=maximum)
    return dict(value)


def validate_reward_shape(reward: dict) -> dict:
    if not isinstance(reward, dict):
        raise ValueError("reward must be an object")
    if reward.get("type") == "settlement_xp" and set(reward) == {"type", "amount"}:
        if type(reward["amount"]) is int and reward["amount"] >= 0:
            return dict(reward)
    if reward.get("type") == "structure" and set(reward) == {"type", "structure_id"}:
        if isinstance(reward["structure_id"], str) and re.fullmatch(r"[a-z0-9_]+", reward["structure_id"]):
            return dict(reward)
    raise ValueError("invalid settlement reward")


def legacy_private_submission(raw: object) -> bool:
    return (isinstance(raw, dict) and raw.get("lane", "private") == "private"
            and raw.get("submission") == "ender_chest")


def load_saved_quest(raw: dict) -> Quest:
    if not isinstance(raw, dict):
        raise ValueError("quest must be an object")
    data = dict(raw)
    if "quest_id" not in data:
        # Old quests receive the same ID on every load, even before migration is saved.
        data["quest_id"] = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
    quest = Quest(**data)
    if legacy_private_submission(data):
        quest.submission = "offering_chest"
    if not isinstance(quest.player, str) or not PLAYER_RE.fullmatch(quest.player):
        raise ValueError("invalid saved quest player")
    if quest.lane not in {"private", "communal", "legacy"}:
        raise ValueError("invalid saved quest lane")
    if quest.lane == "communal" and quest.player != COMMUNAL_PLAYER:
        raise ValueError("invalid communal quest owner")
    if quest.lane == "private" and quest.player in {COMMUNAL_PLAYER, PRIVATE_PLAYER}:
        raise ValueError("invalid private quest owner")
    if quest.candidate_band not in BAND_ORDER:
        raise ValueError("invalid quest candidate band")
    if type(quest.policy_version) is not int or not 0 <= quest.policy_version <= QUEST_POLICY_VERSION:
        raise ValueError("invalid quest policy version")
    if quest.mode not in {"legacy", "warmup", "communal", "long_term", "aspirational"}:
        raise ValueError("invalid quest policy mode")
    if quest.reference_band is not None and quest.reference_band not in BAND_ORDER:
        raise ValueError("invalid quest reference band")
    if quest.policy_version and (quest.mode == "legacy" or quest.reference_band is None):
        raise ValueError("missing quest policy metadata")
    if quest.policy_version:
        band_index = BAND_ORDER.index(quest.candidate_band)
        reference_index = BAND_ORDER.index(quest.reference_band)
        if (quest.mode == "warmup" and (band_index != 0 or reference_index != 0)
                or quest.mode == "communal" and (quest.lane != "communal" or band_index != reference_index)
                or quest.mode in {"long_term", "aspirational"} and (
                    quest.lane != "private"
                    or band_index - reference_index != (2 if quest.mode == "aspirational" else 1))):
            raise ValueError("inconsistent quest policy metadata")
    if quest.submission not in {"offering_chest", "ender_chest", "player_inventory"}:
        raise ValueError("invalid quest submission")
    if not isinstance(quest.availability, list) or any(not isinstance(item, str) for item in quest.availability):
        raise ValueError("invalid quest availability")
    if quest.item not in ALLOWED_ITEMS or type(quest.quantity) is not int or quest.quantity <= 0:
        raise ValueError("invalid saved quest items")
    if type(quest.reward_tier) is not int or quest.reward_tier not in REWARDS:
        raise ValueError("invalid saved reward tier")
    if not isinstance(quest.title, str) or not isinstance(quest.announcement, str):
        raise ValueError("invalid saved quest text")
    if type(quest.created_at) not in (int, float) or not math.isfinite(quest.created_at):
        raise ValueError("invalid saved quest timestamp")
    if not isinstance(quest.quest_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", quest.quest_id):
        raise ValueError("invalid saved quest ID")
    if not isinstance(quest.rewards, list) or len(quest.rewards) > 32:
        raise ValueError("invalid saved rewards")
    quest.rewards = [validate_reward_shape(reward) for reward in quest.rewards]
    return quest


def configured_rewards(manager, tier: int) -> list[dict]:
    if manager is None:
        return []
    config = json.loads(SETTLEMENT_PATH.read_text(encoding="utf-8"))
    table = config.get("quest_rewards", {})
    if not isinstance(table, dict):
        raise ValueError("quest_rewards must be an object")
    rewards = table.get(str(tier), [])
    if not isinstance(rewards, list) or len(rewards) > 32:
        raise ValueError("invalid configured rewards")
    result = [validate_reward_shape(reward) for reward in rewards]
    for reward in result:
        if reward["type"] == "structure" and reward["structure_id"] not in manager.registry:
            raise ValueError("configured reward references an unknown structure")
    if len({json.dumps(reward, sort_keys=True) for reward in result}) != len(result):
        raise ValueError("duplicate configured reward")
    return result


def online_players() -> list[str]:
    response = rcon("list")
    if ":" not in response:
        return []
    names = response.split(":", 1)[1].strip()
    if not names:
        return []
    players = [name.strip() for name in names.split(",") if name.strip()]
    return [p for p in players if PLAYER_RE.fullmatch(p)]


def player_profile(player: str) -> PlayerProfile:
    """Read bounded progression facts; malformed facts conservatively score zero."""
    try:
        def checked(command: str) -> str:
            response = rcon(command)
            if response.startswith(("No ", "Unknown ", "Expected ")):
                raise ValueError(response)
            return response
        levels = parse_first_int(checked(f"experience query {player} levels"))
        inventory = parse_player_items(checked(f"data get entity {player} Inventory"))
        equipment = parse_player_items(checked(f"data get entity {player} ArmorItems"))
        equipment.update(parse_player_items(checked(f"data get entity {player} HandItems")))
        return build_profile(player, levels, inventory, {}, equipment)
    except (OSError, RconError, ValueError):
        return build_profile(player, 0, {}, {}, {}, confidence="limited")


def profiles_for(players: list[str]) -> dict[str, PlayerProfile]:
    return {player: player_profile(player) for player in players}


def supply_snapshot(*, warmup: bool = False) -> SupplySnapshot:
    if not DRY_RUN:
        # Establish a server save boundary before reading the mounted Anvil files.
        rcon("save-all flush")
    def loaded(chunk_x: int, chunk_z: int) -> bool:
        response = rcon(f"execute if loaded {chunk_x * 16} {int(SPAWN_Y)} {chunk_z * 16} run time query gametime")
        return bool(re.fullmatch(r"The game time is \d+ tick\(s\)", response.strip()))
    return AnvilWorldReader(WORLD_DATA_PATH).snapshot(
        SPAWN_X, SPAWN_Y, SPAWN_Z, 32 if warmup else SPAWN_SUPPLY_RADIUS,
        warmup=warmup, loaded=loaded)


def progression_band(score: int) -> str:
    result = BAND_ORDER[0]
    for band in BAND_ORDER:
        if score >= BAND_THRESHOLDS[band]:
            result = band
    return result


def active_quests(state: State) -> list[Quest]:
    ordered = ([state.communal_quest] if state.communal_quest else [])
    ordered.extend(state.private_quests[player] for player in sorted(state.private_quests))
    if state.active_quest:
        ordered.append(state.active_quest)
    seen = set()
    return [quest for quest in ordered if not (quest.quest_id in seen or seen.add(quest.quest_id))]


def reserved_items(state: State, *, exclude_id: str | None = None) -> set[str]:
    records = active_quests(state) + [entry.quest for entry in state.pending_settlement_rewards]
    return {quest.item for quest in records if quest.quest_id != exclude_id}


def lane_warmup(state: State, lane: str, player: str | None = None) -> bool:
    return (state.communal_completions if lane == "communal"
            else state.private_completions.get(player, 0)) < 3


def communal_reference(state: State, score: int) -> str:
    if state.communal_quest:
        return state.communal_quest.candidate_band
    return "spawn_local" if lane_warmup(state, "communal") else progression_band(score)


def candidate_items(lane: str, profile: PlayerProfile | None, snapshot: SupplySnapshot,
                    score: int, *, state: State | None = None, communal_score: int = 0,
                    exclude_id: str | None = None) -> list[dict]:
    if lane not in {"communal", "private"} or (lane == "private" and profile is None):
        raise ValueError("invalid quest candidate lane or profile")
    state = state if state is not None else State()
    player = profile.player if profile else None
    warmup = lane_warmup(state, lane, player)
    reference = communal_reference(state, communal_score)
    reserved = reserved_items(state, exclude_id=exclude_id)
    if warmup:
        bands = [("spawn_local", "warmup")]
        reference = "spawn_local"
    elif lane == "communal":
        bands = [(progression_band(score), "communal")]
        reference = progression_band(score)
    else:
        if profile.confidence != "complete":
            return []
        ceiling = BAND_ORDER.index(progression_band(profile.score))
        normal = BAND_ORDER.index(reference) + 1
        bands = []
        if (state.private_issued.get(player, 0) + 1) % 5 == 0 and normal + 1 <= ceiling:
            bands.append((BAND_ORDER[normal + 1], "aspirational"))
        if normal <= ceiling and normal < len(BAND_ORDER):
            bands.append((BAND_ORDER[normal], "long_term"))
    for selected_band, mode in bands:
        candidates = []
        for item, definition in QUEST_CATALOG.items():
            if item in reserved or definition["band"] != selected_band:
                continue
            if (warmup or selected_band == "spawn_local") and (
                    not snapshot.complete or type(snapshot.items.get(item)) is not int
                    or snapshot.items[item] < definition["min"]):
                continue
            candidates.append({
                "item": item, "min": definition["min"],
                "max": definition["min"] if warmup else definition["max"],
                "band": selected_band, "sources": sorted(snapshot.sources.get(item, set())),
                "mode": mode, "reference_band": reference,
            })
        if candidates:
            return candidates
    return []


def average_strength(profiles: dict[str, PlayerProfile]) -> int:
    return round(sum(profile.score for profile in profiles.values()) / len(profiles)) if profiles else 0


def json_text(text: str) -> str:
    return json.dumps({"text": text, "color": "gold"}, separators=(",", ":"))


def announce(text: str) -> None:
    rcon(f"tellraw @a {json_text('[The Keeper] ' + text)}")


def parse_first_int(text: str) -> int:
    match = COUNT_RE.search(text)
    return int(match.group(1)) if match else 0


def source_slots(quest: Quest) -> list[dict]:
    if quest.submission == "offering_chest":
        if any(value is None for value in OFFERING_CHEST):
            raise ValueError("offering chest coordinates are not configured")
        x, y, z = OFFERING_CHEST
        block_id = rcon(f"execute if loaded {x} {y} {z} run data get block {x} {y} {z} id")
        if "Test failed" in block_id or "minecraft:chest" not in block_id or "ender_chest" in block_id:
            raise ValueError("configured offering source is not a loaded normal chest")
        response = rcon(f"data get block {x} {y} {z} Items")
    else:
        raise ValueError("shared offering chest is the only supported quest source")
    return parse_inventory_slots(response)


def items_in_source(quest: Quest, slots: list[dict] | None = None) -> int:
    slots = source_slots(quest) if slots is None else slots
    return sum(slot["count"] for slot in slots if slot["id"] == quest.item)


def source_descriptor(quest: Quest) -> tuple[str, str] | None:
    if quest.submission == "offering_chest":
        if any(value is None for value in OFFERING_CHEST):
            return None
        x, y, z = OFFERING_CHEST
        return f"block {x} {y} {z}", "Items"
    return None


def source_fingerprint(slots: list[dict]) -> list[dict]:
    return [{key: slot[key] for key in ("slot", "id", "count", "raw")} for slot in slots]


def offering_source_commands(quest: Quest, slots: list[dict]) -> list[str]:
    descriptor = source_descriptor(quest)
    if descriptor is None:
        raise ValueError("quest offering source is not configured")
    target, path = descriptor
    remaining = quest.quantity
    commands = []
    for slot in slots:
        if slot["id"] != quest.item or remaining <= 0:
            continue
        take = min(remaining, slot["count"])
        if take == slot["count"]:
            commands.append(f"data remove {target} {path}[{{Slot:{slot['slot']}b}}]")
        else:
            new_count = slot["count"] - take
            commands.append(f"data modify {target} {path}[{{Slot:{slot['slot']}b}}].count set value {new_count}")
        remaining -= take
    if remaining:
        raise ValueError("offering quantity is no longer available")
    return commands


def _clear_quest_lane(state: State, quest: Quest) -> None:
    if state.communal_quest and state.communal_quest.quest_id == quest.quest_id:
        state.communal_quest = None
    if state.private_quests.get(quest.player, None) and state.private_quests[quest.player].quest_id == quest.quest_id:
        state.private_quests.pop(quest.player, None)
    if state.active_quest and state.active_quest.quest_id == quest.quest_id:
        state.active_quest = None


def revalidate_legacy_quests(state: State, *, profiles: dict[str, PlayerProfile] | None = None,
                             snapshots: dict[bool, SupplySnapshot] | None = None) -> set[str]:
    """Retire only untouched, provably invalid work; return suspended quest IDs."""
    pending_ids = {entry.quest.quest_id for entry in state.pending_settlement_rewards}
    occupied = {entry.quest.item: entry.quest.quest_id for entry in state.pending_settlement_rewards}
    # Resolve reliable record-level conflicts before supply filtering, so a later
    # duplicate cannot make its higher-priority communal winner appear invalid.
    for quest in active_quests(state):
        if quest.quest_id in pending_ids:
            continue
        winner = occupied.setdefault(quest.item, quest.quest_id)
        if winner != quest.quest_id and quest.policy_version != QUEST_POLICY_VERSION and not DRY_RUN:
            _clear_quest_lane(state, quest)
            save_state(state)
            announce(f"Retired {quest.title!r}: {quest.item} is reserved by an earlier quest or pending operation. "
                     "No offerings consumed, rewards granted, or completions counted.")
    occupied = {entry.quest.item: entry.quest.quest_id for entry in state.pending_settlement_rewards}
    suspended = set()
    profiles = profiles if profiles is not None else {}
    snapshots = dict(snapshots) if snapshots is not None else {}
    group_score = average_strength(profiles)
    for quest in active_quests(state):
        if quest.quest_id in pending_ids:
            continue
        conflict = quest.item in occupied and occupied[quest.item] != quest.quest_id
        occupied.setdefault(quest.item, quest.quest_id)
        if quest.policy_version == QUEST_POLICY_VERSION:
            continue
        candidate = None
        reason = "its item is reserved by an earlier quest or pending operation"
        if not conflict:
            lane = "communal" if quest.lane == "communal" else "private"
            warmup = lane_warmup(state, lane, quest.player)
            profile = profiles.get(quest.player)
            if not warmup and lane == "private" and (
                    profile is None or profile.confidence != "complete"):
                suspended.add(quest.quest_id)
                continue
            if not warmup and (not profiles or any(p.confidence != "complete" for p in profiles.values())):
                suspended.add(quest.quest_id)
                continue
            if warmup not in snapshots:
                try:
                    snapshots[warmup] = supply_snapshot(warmup=warmup)
                except (OSError, RconError, ValueError):
                    snapshots[warmup] = SupplySnapshot({}, {}, False, "observation unavailable")
            snapshot = snapshots[warmup]
            if not snapshot.complete:
                suspended.add(quest.quest_id)
                continue
            if profile is None and lane == "private":
                profile = build_profile(quest.player, 0, {}, {}, {}, confidence="limited")
            candidates = candidate_items(
                lane, profile, snapshot, group_score if lane == "communal" else profile.score,
                state=state, communal_score=group_score, exclude_id=quest.quest_id)
            candidate = next((entry for entry in candidates if entry["item"] == quest.item
                              and entry["min"] <= quest.quantity <= entry["max"]), None)
            reason = ("it does not meet the verified nearby warm-up catalog-minimum policy"
                      if warmup else "it does not meet the progression-safe personal/communal policy")
        if candidate is None:
            suspended.add(quest.quest_id)
            if DRY_RUN:
                continue
            _clear_quest_lane(state, quest)
            save_state(state)
            announce(f"Retired {quest.title!r} for {'the group' if quest.lane == 'communal' else quest.player}: "
                     f"{reason}. No offerings were consumed, rewards granted, or completions counted.")
        elif not DRY_RUN:
            quest.policy_version = QUEST_POLICY_VERSION
            quest.mode = candidate["mode"]
            quest.reference_band = candidate["reference_band"]
            quest.candidate_band = candidate["band"]
            save_state(state)
    return suspended


def completion_allowed(state: State, quest: Quest) -> bool:
    if quest.policy_version != QUEST_POLICY_VERSION:
        profiles = profiles_for(online_players())
        if quest.quest_id in revalidate_legacy_quests(state, profiles=profiles):
            return False
    return (any(active.quest_id == quest.quest_id for active in active_quests(state))
            and quest.item not in reserved_items(state, exclude_id=quest.quest_id))


def complete_quest(state: State, quest: Quest, manager=None) -> list[dict]:
    if any(entry.quest.quest_id == quest.quest_id for entry in state.pending_settlement_rewards):
        return complete_settlement_quest(state, quest, manager)
    if not completion_allowed(state, quest):
        return []
    try:
        slots = source_slots(quest)
    except (OSError, RconError, ValueError) as exc:
        print(f"[WARN] Quest {quest.quest_id}: offering source unavailable: {exc}")
        return []
    if items_in_source(quest, slots) < quest.quantity:
        return []
    if DRY_RUN:
        print(f"[DRY_RUN] Quest {quest.quest_id}: would consume {quest.quantity} {quest.item} from "
              f"{quest.submission}, grant tier {quest.reward_tier} to its eligible recipients, "
              f"and settlement rewards {quest.rewards}")
        return []
    return complete_settlement_quest(state, quest, manager, slots)


def vanilla_commands(pending: PendingReward) -> list[str]:
    quest = pending.quest
    reward_cmd, reward_name = REWARDS[quest.reward_tier][pending.vanilla_choice]
    recipients = pending.recipients or ([quest.player] if quest.lane == "private" else [])
    commands = []
    for player in recipients:
        commands.extend([
            reward_cmd.format(player=player),
            f"experience add {player} {quest.reward_tier * 2} levels",
            f"title {player} title " + json.dumps(
                {"text": "QUEST COMPLETE", "color": "green", "bold": True}, separators=(",", ":")),
            f"playsound minecraft:ui.toast.challenge_complete master {player}",
        ])
    names = ", ".join(recipients)
    commands.append(f"tellraw @a {json_text('[The Keeper] ' + names + ' completed ' + repr(quest.title) + ' and received ' + reward_name + '!')}")
    return commands


def complete_settlement_quest(state: State, quest: Quest, manager, slots: list[dict] | None = None) -> list[dict]:
    if DRY_RUN:
        return []
    pending = next((entry for entry in state.pending_settlement_rewards
                    if entry.quest.quest_id == quest.quest_id), None)
    if pending is None:
        if not completion_allowed(state, quest):
            return []
        slots = source_slots(quest) if slots is None else slots
        commands = offering_source_commands(quest, slots)
        recipients = (online_players() if quest.lane == "communal" else [quest.player])
        recipients = [player for player in recipients if PLAYER_RE.fullmatch(player)]
        if not recipients:
            return []
        pending = PendingReward(
            quest, random.randrange(len(REWARDS[quest.reward_tier])),
            recipients=recipients,
            source_snapshot={"slots": source_fingerprint(slots), "commands": commands},
        )
        state.pending_settlement_rewards.append(pending)
        save_state(state)
    if pending.consumption == "done":
        return process_pending_rewards(state, manager)
    if pending.consumption == "uncertain":
        return []
    if any(entry.quest.quest_id != quest.quest_id and entry.quest.item == quest.item
           for entry in state.pending_settlement_rewards):
        return []
    # Persist a prepared intent, then mark each external mutation uncertain before
    # dispatch. An unknown response is never replayed automatically.
    pending.consumption = "uncertain"
    _clear_quest_lane(state, quest)
    state.last_quest_at = time.time()
    save_state(state)
    try:
        current = source_slots(quest)
        if source_fingerprint(current) != pending.source_snapshot.get("slots"):
            raise RconError("offering inventory changed after intent preparation")
        commands = pending.source_snapshot.get("commands", pending.consumption_commands)
        pending.consumption_commands = list(commands)
        save_state(state)
        while pending.consumption_step < len(pending.consumption_commands):
            pending.consumption_uncertain = True
            save_state(state)
            rcon(pending.consumption_commands[pending.consumption_step])
            pending.consumption_uncertain = False
            pending.consumption_step += 1
            save_state(state)
    except Exception as exc:
        pending.last_error = f"Offering consumption requires reconciliation: {exc}"
        save_state(state)
        print(f"[WARN] Quest {quest.quest_id}: {pending.last_error}")
        return []
    pending.consumption = "done"
    save_state(state)
    return process_pending_rewards(state, manager)


def process_pending_rewards(state: State, manager) -> list[dict]:
    events = []
    if DRY_RUN:
        return events
    for pending in list(state.pending_settlement_rewards):
        if pending.consumption != "done" or pending.consumption_uncertain:
            continue
        quest = pending.quest
        if not pending.vanilla_uncertain:
            commands = vanilla_commands(pending)
            while pending.vanilla_step < len(commands):
                command = commands[pending.vanilla_step]
                pending.vanilla_step += 1
                pending.vanilla_uncertain = True
                save_state(state)
                try:
                    rcon(command)
                except Exception as exc:
                    pending.last_error = f"Vanilla reward requires reconciliation: {exc}"
                    save_state(state)
                    print(f"[WARN] Quest {quest.quest_id}: {pending.last_error}")
                    break
                pending.vanilla_uncertain = False
                save_state(state)
        try:
            owner = (pending.recipients or [quest.player])[0]
            if manager is not None and not pending.recorded:
                manager.record_quest(quest.quest_id, owner, quest.title)
                pending.recorded = True
                save_state(state)
                events.append({"type": "quest_completed", "quest_id": quest.quest_id,
                               "player": owner, "recipients": pending.recipients, "title": quest.title})
            if manager is not None and not pending.xp_done:
                amount = sum(reward["amount"] for reward in quest.rewards
                             if reward["type"] == "settlement_xp")
                if amount:
                    events.extend(manager.grant_xp(amount, quest_id=quest.quest_id))
                pending.xp_done = True
                save_state(state)
            structures = [reward["structure_id"] for reward in quest.rewards if reward["type"] == "structure"]
            while manager is not None and pending.structures_done < len(structures):
                index = pending.structures_done
                result = manager.place(structures[index], owner=owner,
                                       reason=f"Quest reward: {quest.title}",
                                       quest_id=f"{quest.quest_id}:structure:{index}")
                if result.get("pending"):
                    break
                if not result.get("success"):
                    raise ValueError("Settlement placement was not accepted")
                pending.structures_done += 1
                save_state(state)
            vanilla_done = (not pending.vanilla_uncertain
                            and pending.vanilla_step == len(vanilla_commands(pending)))
            xp_required = any(reward["type"] == "settlement_xp" and reward["amount"]
                              for reward in quest.rewards)
            obligations_done = (pending.structures_done == len(structures)
                                and (not xp_required or pending.xp_done)
                                and (manager is None or pending.recorded))
            if vanilla_done and obligations_done:
                if quest.lane == "communal":
                    state.communal_completions = min(3, state.communal_completions + 1)
                else:
                    state.private_completions[quest.player] = min(
                        3, state.private_completions.get(quest.player, 0) + 1)
                _clear_quest_lane(state, quest)
                state.pending_settlement_rewards.remove(pending)
                save_state(state)
        except Exception as exc:
            error = str(exc)[:500]
            if pending.last_error != error:
                print(f"[WARN] Pending settlement reward {quest.quest_id}: {error}")
                pending.last_error = error
                save_state(state)
    return events


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


def _candidate_map(candidates: list[dict] | None) -> dict[str, dict]:
    if candidates is None:
        raise ValueError("policy-constrained quest candidates are required")
    return {candidate["item"]: candidate for candidate in candidates}


def validate_quest(raw: dict, players: list[str], manager=None, offered_rewards=None, *,
                   lane: str = "private", candidates: list[dict] | None = None,
                   state: State) -> Quest:
    if lane not in {"private", "communal"}:
        raise ValueError("invalid quest lane")
    if not isinstance(raw, dict) or set(raw) - {
        "player", "item", "quantity", "reward_tier", "title", "announcement", "rewards"
    }:
        raise ValueError("invalid quest JSON keys")
    for key in ("quantity", "reward_tier"):
        if key in raw and type(raw[key]) is not int:
            raise ValueError(f"{key} must be an integer")
    player = COMMUNAL_PLAYER if lane == "communal" else str(raw.get("player", ""))
    item = str(raw.get("item", ""))
    title = str(raw.get("title", "A Small Favour"))[:60]

    if lane == "private" and (player not in players or not PLAYER_RE.fullmatch(player)):
        raise ValueError("LLM selected an invalid/offline player")
    candidate = _candidate_map(candidates).get(item)
    if candidate is None or item in reserved_items(state):
        raise ValueError("LLM selected an unavailable or reserved item")

    low, high = candidate["min"], candidate["max"]
    quantity = int(raw.get("quantity", low))
    if not low <= quantity <= high:
        raise ValueError(f"quantity must be between {low} and {high} for {item}")

    reward_tier = int(raw.get("reward_tier", 1))
    if reward_tier not in REWARDS:
        raise ValueError("invalid reward tier")
    allowed_rewards = (offered_rewards[str(reward_tier)] if offered_rewards is not None
                       else configured_rewards(manager, reward_tier))
    requested = raw.get("rewards", [])
    if not isinstance(requested, list) or len(requested) > len(allowed_rewards):
        raise ValueError("invalid requested rewards")
    requested = [validate_reward_shape(reward) for reward in requested]
    if any(reward not in allowed_rewards for reward in requested):
        raise ValueError("LLM requested a reward outside the configured choices")
    if len({json.dumps(reward, sort_keys=True) for reward in requested}) != len(requested):
        raise ValueError("duplicate requested rewards")
    rewards = [reward for reward in allowed_rewards if reward["type"] == "settlement_xp"]
    rewards.extend(reward for reward in requested if reward["type"] == "structure")
    submission = "offering_chest"
    return Quest(player=player, item=item, quantity=quantity, reward_tier=reward_tier,
                 title=title, announcement=quest_announcement(player, item, quantity, candidate["mode"]),
                 created_at=time.time(), rewards=rewards,
                 lane=lane, candidate_band=candidate["band"], submission=submission,
                 availability=list(candidate.get("sources", [])), policy_version=QUEST_POLICY_VERSION,
                 mode=candidate["mode"], reference_band=candidate["reference_band"])


def fallback_quest(players: list[str], manager=None, *, lane: str = "private",
                   candidates: list[dict] | None = None, state: State) -> Quest:
    """Code-owned fallback constrained by the same candidate list as the LLM."""
    if lane == "private" and not players:
        raise ValueError("private quest requires an online player")
    reserved = reserved_items(state)
    available = [entry for entry in _candidate_map(candidates).values() if entry["item"] not in reserved]
    if not available:
        raise ValueError("no quest candidates available")
    candidate = random.choice(available)
    item, low, high = candidate["item"], candidate["min"], candidate["max"]
    quantity = random.randint(low, min(high, low + 5))
    player = random.choice(players) if lane == "private" else COMMUNAL_PLAYER
    tier = min(3, 1 + BAND_ORDER.index(candidate["band"]) // 2)
    return Quest(player=player, item=item, quantity=quantity, reward_tier=tier,
                 title="Temple Offering",
                 announcement=quest_announcement(player, item, quantity, candidate["mode"]),
                 created_at=time.time(), rewards=[reward for reward in configured_rewards(manager, tier)
                 if reward["type"] == "settlement_xp"], lane=lane,
                 candidate_band=candidate["band"], submission="offering_chest",
                 availability=list(candidate.get("sources", [])), policy_version=QUEST_POLICY_VERSION,
                 mode=candidate["mode"], reference_band=candidate["reference_band"])


def quest_announcement(player: str, item: str, quantity: int, mode: str) -> str:
    target = "Everyone" if player == COMMUNAL_PLAYER else player
    label = {"warmup": "Nearby warm-up", "communal": "Communal offering",
             "long_term": "Longer-term personal goal", "aspirational": "Aspirational longer-term personal goal"}[mode]
    pretty = item.split(":", 1)[1].replace("_", " ")
    return f"{target}: {label} — bring {quantity} {pretty} to the shared normal temple offering chest."


def assign_quest(state: State, quest: Quest, candidates: list[dict]) -> bool:
    """Commit only a still-unreserved policy choice, with its issued sequence."""
    candidate = _candidate_map(candidates).get(quest.item)
    if lane_warmup(state, quest.lane, quest.player) != (quest.mode == "warmup"):
        return False
    if (candidate is None or quest.item in reserved_items(state)
            or not candidate["min"] <= quest.quantity <= candidate["max"]
            or quest.policy_version != QUEST_POLICY_VERSION
            or (quest.mode, quest.reference_band, quest.candidate_band) != (
                candidate["mode"], candidate["reference_band"], candidate["band"])):
        return False
    if quest.lane == "communal":
        if state.communal_quest is not None:
            return False
    elif quest.player in state.private_quests or quest.lane != "private":
        return False
    if DRY_RUN:
        print(f"[DRY_RUN] Would announce: {quest.announcement}")
        return False
    now = time.time()
    if quest.lane == "communal":
        state.communal_quest = quest
        state.last_communal_quest_at = now
    else:
        state.private_quests[quest.player] = quest
        state.private_quest_at[quest.player] = now
        if quest.mode != "warmup":
            state.private_issued[quest.player] = state.private_issued.get(quest.player, 0) + 1
    state.last_quest_at = now
    save_state(state)
    announce(quest.announcement)
    return True


def schedule_quests(state: State, players: list[str], recent_events: list[str], manager=None, *,
                    profiles: dict[str, PlayerProfile] | None = None,
                    snapshots: dict[bool, SupplySnapshot] | None = None) -> list[Quest]:
    """Communal-first, stable personal scheduling using the same frozen policy."""
    now = time.time()
    due = []
    if state.communal_quest is None and players and now - state.last_communal_quest_at >= QUEST_INTERVAL_SECONDS:
        due.append(("communal", None))
    due.extend(("private", player) for player in sorted(set(players))
               if player not in state.private_quests
               and now - state.private_quest_at.get(player, 0) >= QUEST_INTERVAL_SECONDS)
    if not due:
        return []
    profiles = profiles if profiles is not None else profiles_for(players)
    snapshots = dict(snapshots) if snapshots is not None else {}
    score = average_strength(profiles)
    assigned = []
    for lane, player in due:
        if not DRY_RUN:
            if lane == "communal":
                state.last_communal_quest_at = now
            else:
                state.private_quest_at[player] = now
        profile = profiles.get(player) if player else None
        if lane == "private" and profile is None:
            continue
        warmup = lane_warmup(state, lane, player)
        if warmup not in snapshots:
            snapshots[warmup] = supply_snapshot(warmup=warmup)
        snapshot = snapshots[warmup]
        strength = score if lane == "communal" else profile.score
        candidates = candidate_items(lane, profile, snapshot, strength,
                                     state=state, communal_score=score)
        if not candidates:
            print(f"[QUEST] {lane} lane declined for {player or 'the group'}: no safe unreserved candidates")
            continue
        targets = players if lane == "communal" else [player]
        try:
            quest = make_quest_with_llm(targets, recent_events, manager, lane=lane,
                                       candidates=candidates, strength=strength, state=state)
        except Exception as exc:
            print(f"[WARN] {lane} LLM quest generation failed: {exc}")
            try:
                quest = fallback_quest(targets, manager, lane=lane, candidates=candidates, state=state)
            except ValueError:
                continue
        # Model latency may leave the original candidate list stale.
        current = candidate_items(lane, profile, snapshot, strength,
                                  state=state, communal_score=score)
        if assign_quest(state, quest, current):
            assigned.append(quest)
    return assigned


def make_quest_with_llm(players: list[str], recent_events: list[str], manager=None, *,
                        lane: str = "private", candidates: list[dict] | None = None,
                        strength: int = 0, state: State) -> Quest:
    if DEMO_MODE:
        return fallback_quest(players, manager, lane=lane, candidates=candidates, state=state)
    if not (LLM_URL and LLM_MODEL):
        raise RuntimeError("Set LLM_URL and LLM_MODEL, or set DEMO_MODE=1")
    candidate_map = _candidate_map(candidates)
    if not candidate_map:
        raise ValueError("no quest candidates available")
    allowed = {item: {"min": value["min"], "max": value["max"], "band": value["band"]}
               for item, value in candidate_map.items()}
    system = (
        "You are The Keeper, a playful Minecraft game master on a private family server. "
        "Create ONE concise collect-and-return quest. Every lane submits to the shared normal temple offering chest; "
        "private quests reward only their named target player. "
        "Do not invent commands, items, players, coordinates, or rewards. Return JSON only with "
        "keys: player, item, quantity, reward_tier, title, announcement."
    )
    user = {"quest_lane": lane, "online_players": players, "strength_score": strength,
            "allowed_items_and_quantities": allowed, "recent_server_events": recent_events[-20:],
            "instruction": "Choose only an exact candidate item and quantity; use an online player for private lane."}
    offered_rewards = None
    if manager is not None:
        offered_rewards = {str(tier): configured_rewards(manager, tier) for tier in REWARDS}
        system += (" Settlement XP is fixed by configuration. Select only exact offered structure "
                   "rewards in the requested tier; never invent XP amounts or structure IDs.")
        user["settlement_context"] = compact_settlement_context(manager)
        user["configured_reward_choices"] = offered_rewards
    raw = request_llm_json(system, user)
    return validate_quest(raw, players, manager, offered_rewards, lane=lane, candidates=candidates, state=state)


def request_llm_json(system: str, user: dict):
    payload = json.dumps({
        "model": LLM_MODEL,
        "temperature": 0.8,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user)},
        ],
    }).encode("utf-8")

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
    return json.loads(strip_code_fence(content))


def compact_settlement_context(manager) -> dict:
    context = manager.context()
    return {
        "settlement": context.get("settlement", {}),
        "buildings": context.get("buildings", [])[:16],
        "available_plots": context.get("available_plots", [])[:16],
        "categories": context.get("categories", []),
        "unlocked_structures": context.get("unlocked_structures", []),
        "capabilities": context.get("capabilities", {}),
        "recent_quests": context.get("recent_quests", [])[:5],
        "events": context.get("events", [])[:8],
    }


def make_settlement_decision(manager, players: list[str], events: list[dict]):
    system = (
        "You are The Keeper planning one safe improvement for a Minecraft settlement. "
        "Return null if no appropriate action is available; otherwise return exactly ONE JSON object. "
        "Allowed forms: {action:construct_building,structure_id,owner,reason} or "
        "{action:upgrade_building,plot_id,target_structure,owner,reason}. "
        "Use exact configured unlocked structure IDs and existing plot IDs from context. "
        "owner must be one online player. reason is a short plain description. "
        "Never return commands, templates, blocks, coordinates, extra keys, or XP rewards. "
        "Respect existing ownership and choose a genuinely useful improvement prompted by these events."
    )
    raw = request_llm_json(system, {
        "online_players": players,
        "settlement_context": compact_settlement_context(manager),
        "trigger_events": events[-8:],
    })
    if raw is None:
        return None
    # Core validates the complete high-level action before any RCON mutation.
    return manager.execute_action(raw, players)


# ----------------------------- main loop -----------------------------

def interesting(line: str) -> bool:
    return any(pattern in line for pattern in INTERESTING_PATTERNS)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("Minecraft AI Director starting")
    print(f"  log:   {LOG_PATH}")
    print(f"  rcon:  {RCON_HOST}:{RCON_PORT}")
    print(f"  spawn: {SPAWN_X:g}, {SPAWN_Y:g}, {SPAWN_Z:g} radius {SPAWN_RADIUS:g}")
    print(f"  mode:  {'DEMO' if DEMO_MODE else 'LLM'}")

    if not RCON_PASSWORD:
        print("ERROR: RCON_PASSWORD is required", file=sys.stderr)
        return 2

    try:
        state = load_state()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    recent_events: deque[str] = deque(maxlen=40)
    tail = LogTail(LOG_PATH)
    manager = None
    decision_events: deque[dict] = deque(maxlen=12)
    last_decision_at = time.time()

    try:
        # Fail fast if RCON details are wrong.
        print(f"Online players: {online_players()}")
        if SETTLEMENT_ENABLED:
            from settlement import StructureManager
            manager = StructureManager(
                STRUCTURES_PATH, SETTLEMENT_PATH, DATABASE_PATH, rcon, dry_run=DRY_RUN)
            settlement = manager.show_settlement()
            if not settlement["enabled"] or settlement["world_id"].startswith("CHANGE_ME"):
                raise ValueError("Enable settlement config and assign its unique world_id before enabling Director integration")
            for result in manager.initialize():
                print(f"[SETTLEMENT] Initialization: {json.dumps(result)}")
    except Exception as exc:
        print(f"ERROR: Director startup failed: {exc}", file=sys.stderr)
        tail.close()
        if manager is not None:
            manager.close()
        return 2

    try:
        while True:
            for line in tail.read_new():
                if interesting(line):
                    recent_events.append(line)
                    print(f"[EVENT] {line}")

            try:
                if manager is not None:
                    for event in manager.tick():
                        print(f"[SETTLEMENT] {json.dumps(event)}")
                        if event["type"] in ("settlement_level_up", "construction_complete"):
                            decision_events.append(event)
                decision_events.extend(process_pending_rewards(state, manager))
                players = online_players()
                pending_ids = {entry.quest.quest_id for entry in state.pending_settlement_rewards}
                suspended = set()
                if any(quest.policy_version != QUEST_POLICY_VERSION and quest.quest_id not in pending_ids
                       for quest in active_quests(state)):
                    suspended = revalidate_legacy_quests(state, profiles=profiles_for(players))
                for quest in active_quests(state):
                    if quest.quest_id not in suspended and (quest.lane == "communal" or quest.player in players):
                        decision_events.extend(complete_quest(state, quest, manager))
                schedule_quests(state, players, list(recent_events), manager)

                if (manager is not None and players and decision_events and not DEMO_MODE
                        and LLM_URL and LLM_MODEL
                        and time.time() - last_decision_at >= max(60, QUEST_INTERVAL_SECONDS)):
                    triggers = list(decision_events)
                    decision_events.clear()
                    last_decision_at = time.time()
                    try:
                        result = make_settlement_decision(manager, players, triggers)
                        print(f"[SETTLEMENT] AI decision: {json.dumps(result)}")
                    except Exception as exc:
                        print(f"[WARN] Settlement AI decision rejected/failed: {exc}")

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
        if manager is not None:
            manager.close()


if __name__ == "__main__":
    raise SystemExit(main())
