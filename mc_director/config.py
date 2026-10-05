"""Validated configuration for the single supported vanilla release."""
from __future__ import annotations

import copy
import hashlib
import ipaddress
import json
import math
import os
import re
import uuid
from dataclasses import dataclass, field, fields
from pathlib import Path
from urllib.parse import urlsplit

from .snbt import IntArray

MINECRAFT_VERSION = "26.3"
SERVER_SHA1 = "33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c"
ITEM_IDS = (
    "minecraft:iron_ingot", "minecraft:copper_ingot", "minecraft:gold_ingot",
    "minecraft:coal", "minecraft:redstone", "minecraft:lapis_lazuli",
    "minecraft:oak_log", "minecraft:bread", "minecraft:carrot", "minecraft:cooked_beef",
    "minecraft:emerald", "minecraft:diamond", "minecraft:ancient_debris",
)
DEFAULT_CATALOG = {
    item: {"code": code, "base": base, "min": low, "max": high, "weight": weight, "enabled": True}
    for code, (item, base, low, high, weight) in enumerate(zip(
        ITEM_IDS[:10], (6, 8, 4, 12, 12, 8, 12, 6, 10, 6),
        (6, 8, 4, 12, 12, 8, 12, 6, 10, 6),
        (48, 64, 24, 96, 96, 64, 96, 48, 80, 48),
        (3, 1, 6, 1, 1, 2, 1, 2, 1, 3),
    ))
}
DEFAULT_REWARDS = {
    1: [{"item": ITEM_IDS[10], "count": 3, "code": 10}, {"item": ITEM_IDS[2], "count": 4, "code": 2}],
    2: [{"item": ITEM_IDS[11], "count": 2, "code": 11}, {"item": ITEM_IDS[10], "count": 8, "code": 10}],
    3: [{"item": ITEM_IDS[11], "count": 4, "code": 11}, {"item": ITEM_IDS[12], "count": 1, "code": 12}],
}


def _positive(value, name: str, maximum: float, *, integer: bool = False, allow_zero: bool = False):
    sign = "nonnegative" if allow_zero else "positive"
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite {sign} {'integer' if integer else 'number'}")
    if value < 0 or (value == 0 and not allow_zero) or value > maximum or (integer and not isinstance(value, int)):
        lower = "at least zero" if allow_zero else "greater than zero"
        raise ValueError(f"{name} must be {'an integer ' if integer else ''}{lower} and at most {maximum:g}")
    return value


def _boolean(value: str, name: str) -> bool:
    normalized = value.lower()
    if normalized not in ("0", "1", "true", "false"):
        raise ValueError(f"{name} must be 0/1 or true/false")
    return normalized in ("1", "true")


@dataclass
class Config:
    config_path: Path = Path("director_config.json")
    db_path: Path = Path(".runtime/director.sqlite3")
    socket_path: Path = Path(".runtime/director.sock")
    rcon_host: str = "127.0.0.1"
    rcon_port: int = 25575
    rcon_password: str = field(default="", repr=False)
    game_host: str = "127.0.0.1"
    game_port: int = 25565
    version: str = MINECRAFT_VERSION
    poll_seconds: float = 5.0
    quest_expiry_seconds: float = 7200.0
    cooldown_seconds: float = 600.0
    reward_retry_seconds: float = 60.0
    generation_deadline_seconds: float = 45.0
    llm_timeout_seconds: float = 30.0
    max_quests_per_day: int = 12
    max_ai_calls_per_day: int = 12
    max_recipients: int = 20
    max_payout_batch: int = 8
    heartbeat_ticks: int = 600
    excluded_uuids: tuple[str, ...] = ()
    catalog: dict = field(default_factory=lambda: copy.deepcopy(DEFAULT_CATALOG))
    rewards: dict = field(default_factory=lambda: copy.deepcopy(DEFAULT_REWARDS))
    demo_mode: bool = False
    llm_url: str = ""
    llm_model: str = ""
    llm_api_key: str = field(default="", repr=False)
    share_events: bool = True
    share_chat: bool = False
    flavor_enabled: bool = True
    log_path: Path | None = None
    server_jar: Path | None = None
    _file_required: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self):
        for name in ("config_path", "db_path", "socket_path"):
            setattr(self, name, Path(getattr(self, name)).expanduser().resolve())
        for name in ("log_path", "server_jar"):
            if getattr(self, name) is not None:
                setattr(self, name, Path(getattr(self, name)).expanduser().resolve())
        if self.version != MINECRAFT_VERSION:
            raise ValueError("Only official vanilla Minecraft Java 26.3 is supported")
        for name in ("rcon_host", "game_host"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or len(value) > 255 or re.search(r"[\s/\x00]", value):
                raise ValueError(f"{name} must be a hostname or IP address")
        for name in ("rcon_port", "game_port"):
            _positive(getattr(self, name), name, 65535, integer=True)
        for name in ("poll_seconds", "reward_retry_seconds", "generation_deadline_seconds", "llm_timeout_seconds"):
            _positive(getattr(self, name), name, 3600)
        _positive(self.quest_expiry_seconds, "quest_expiry_seconds", 604800)
        _positive(self.cooldown_seconds, "cooldown_seconds", 604800, allow_zero=True)
        if self.poll_seconds > 5:
            raise ValueError("poll_seconds must be at most 5 to maintain the heartbeat")
        if self.llm_timeout_seconds >= self.generation_deadline_seconds:
            raise ValueError("LLM timeout must be shorter than the generation deadline")
        for name in ("max_quests_per_day", "max_ai_calls_per_day"):
            _positive(getattr(self, name), name, 1000, integer=True)
        _positive(self.max_recipients, "max_recipients", 128, integer=True)
        _positive(self.max_payout_batch, "max_payout_batch", 8, integer=True)
        _positive(self.heartbeat_ticks, "heartbeat_ticks", 600, integer=True)
        if self.heartbeat_ticks < 20:
            raise ValueError("heartbeat_ticks must allow at least one second of server ticks")
        if self.heartbeat_ticks < self.poll_seconds * 40:
            raise ValueError("heartbeat_ticks must allow at least two poll intervals")
        for name in ("demo_mode", "share_events", "share_chat", "flavor_enabled"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean")
        if not isinstance(self.excluded_uuids, (tuple, list)):
            raise ValueError("excluded_uuids must be a list of UUID strings")
        try:
            self.excluded_uuids = tuple(str(uuid.UUID(value)) for value in self.excluded_uuids)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("Invalid excluded player UUID") from exc
        if len(set(self.excluded_uuids)) != len(self.excluded_uuids) or len(self.excluded_uuids) > 128:
            raise ValueError("Excluded UUIDs must be unique and at most 128")
        self.catalog = self._catalog(self.catalog)
        self.rewards = self._rewards(self.rewards)
        if not any(item["enabled"] for item in self.catalog.values()):
            raise ValueError("At least one collection item must be enabled")
        for name in ("rcon_password", "llm_api_key", "llm_url", "llm_model"):
            value = getattr(self, name)
            if not isinstance(value, str) or "\x00" in value or "\n" in value or "\r" in value:
                raise ValueError(f"Invalid {name}")
        if self.llm_model and not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,120}", self.llm_model):
            raise ValueError("LLM_MODEL must be an exact provider model identifier")
        if self.llm_url:
            parsed = urlsplit(self.llm_url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
                raise ValueError("LLM_URL must be an HTTP(S) endpoint without embedded credentials or fragment")
            if parsed.scheme == "http":
                loopback = parsed.hostname == "localhost"
                try:
                    loopback = loopback or ipaddress.ip_address(parsed.hostname).is_loopback
                except ValueError:
                    pass
                if not loopback:
                    raise ValueError("Plain HTTP LLM endpoints must be loopback; use HTTPS or a local tunnel")

    @staticmethod
    def _catalog(raw: dict) -> dict:
        if not isinstance(raw, dict) or any(key not in DEFAULT_CATALOG for key in raw):
            raise ValueError("Catalog contains an unsupported 26.3 item ID")
        result = copy.deepcopy(DEFAULT_CATALOG)
        for item, entry in raw.items():
            if not isinstance(entry, dict) or set(entry) - {"code", "base", "min", "max", "weight", "enabled"}:
                raise ValueError("Invalid catalog entry")
            result[item].update(entry)
        for item, entry in result.items():
            if entry["code"] != DEFAULT_CATALOG[item]["code"] or type(entry["code"]) is not int:
                raise ValueError("Catalog item codes are fixed by the datapack")
            for name in ("base", "min", "max", "weight"):
                _positive(entry[name], f"catalog {item} {name}", 4096 if name == "weight" else 1728, integer=True)
            if not entry["min"] <= entry["base"] <= entry["max"]:
                raise ValueError("Catalog requires min <= base <= max")
            if type(entry["enabled"]) is not bool:
                raise ValueError("Catalog enabled must be boolean")
        return result

    @staticmethod
    def _rewards(raw: dict) -> dict:
        if not isinstance(raw, dict):
            raise ValueError("Rewards must be a tier table")
        if set(map(str, raw)) != {"1", "2", "3"}:
            raise ValueError("Rewards require exactly tiers 1, 2, and 3")
        result = {}
        for tier, entries in raw.items():
            if not isinstance(entries, list) or not 1 <= len(entries) <= 8:
                raise ValueError("Each tier requires 1–8 reward choices")
            choices = []
            for entry in entries:
                if not isinstance(entry, dict) or set(entry) - {"item", "count", "code"} or not {"item", "count"} <= set(entry):
                    raise ValueError("Rewards must be a plain item/count stack")
                item = entry["item"]
                if item not in ITEM_IDS:
                    raise ValueError("Reward item is not supported by this datapack release")
                count = _positive(entry["count"], "reward count", 64, integer=True)
                code = ITEM_IDS.index(item)
                if "code" in entry and (type(entry["code"]) is not int or entry["code"] != code):
                    raise ValueError("Reward item codes are fixed by the datapack")
                choices.append({"item": item, "count": count, "code": code})
            result[int(tier)] = choices
        return result

    @classmethod
    def load(cls, config_path: Path | str | None = None, *, environ=None) -> Config:
        env = os.environ if environ is None else environ
        path = Path(config_path or env.get("DIRECTOR_CONFIG", "director_config.json"))
        data = {}
        source_exists = path.exists()
        if source_exists:
            if path.stat().st_size > 65_536:
                raise ValueError("Configuration exceeds 64 KiB")
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ValueError("Cannot read valid director configuration") from exc
            if not isinstance(data, dict):
                raise ValueError("Director configuration must be an object")
        elif config_path is not None or "DIRECTOR_CONFIG" in env:
            raise ValueError("Explicit director configuration file does not exist")
        allowed = {entry.name for entry in fields(cls) if not entry.name.startswith("_")} - {"config_path", "rcon_password", "llm_api_key"}
        if set(data) - allowed:
            raise ValueError("Unknown configuration keys; secrets belong in environment variables")
        values = {**data, "config_path": path, "_file_required": source_exists or config_path is not None or "DIRECTOR_CONFIG" in env}
        mapping = {
            "DIRECTOR_DB": ("db_path", str), "DIRECTOR_SOCKET": ("socket_path", str),
            "RCON_HOST": ("rcon_host", str), "RCON_PORT": ("rcon_port", int), "RCON_PASSWORD": ("rcon_password", str),
            "MINECRAFT_HOST": ("game_host", str), "MINECRAFT_PORT": ("game_port", int), "MINECRAFT_VERSION": ("version", str),
            "POLL_SECONDS": ("poll_seconds", float), "QUEST_INTERVAL_SECONDS": ("cooldown_seconds", float),
            "LLM_URL": ("llm_url", str), "LLM_MODEL": ("llm_model", str), "LLM_API_KEY": ("llm_api_key", str),
            "MINECRAFT_LOG": ("log_path", str), "MINECRAFT_SERVER_JAR": ("server_jar", str),
        }
        for key, (name, convert) in mapping.items():
            if key in env:
                try:
                    values[name] = convert(env[key])
                except ValueError as exc:
                    raise ValueError(f"Invalid numeric environment setting {key}") from exc
        if "RCON_HOST" in env and "MINECRAFT_HOST" not in env and "game_host" not in data:
            values["game_host"] = env["RCON_HOST"]
        for key, name in (("DEMO_MODE", "demo_mode"), ("SHARE_EVENTS", "share_events"), ("SHARE_CHAT", "share_chat"), ("FLAVOR_ENABLED", "flavor_enabled")):
            if key in env:
                values[name] = _boolean(env[key], key)
        return cls(**values)

    def reload(self) -> Config:
        return type(self).load(self.config_path if self._file_required or self.config_path.exists() else None)

    def public(self) -> dict:
        result = {}
        for entry in fields(self):
            if entry.name.startswith("_") or entry.name in ("rcon_password", "llm_api_key"):
                continue
            value = getattr(self, entry.name)
            result[entry.name] = str(value) if isinstance(value, Path) else copy.deepcopy(value)
        return result

    def pack_config(self) -> dict:
        excluded = []
        for value in self.excluded_uuids:
            integer = uuid.UUID(value).int
            parts = [(integer >> shift) & 0xFFFFFFFF for shift in (96, 64, 32, 0)]
            excluded.append({"uuid": IntArray([part if part < 2**31 else part - 2**32 for part in parts])})
        result = {
            "protocol": 1, "build": 1, "version": self.version,
            "catalog": [{"code": entry["code"], "item": item, "min": entry["min"], "max": entry["max"], "enabled": int(entry["enabled"])} for item, entry in self.catalog.items()],
            "items": [{"code": code, "item": item} for code, item in enumerate(ITEM_IDS)],
            "excluded": excluded, "max_recipients": self.max_recipients, "heartbeat_ticks": self.heartbeat_ticks,
        }
        result["config_hash"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return result
