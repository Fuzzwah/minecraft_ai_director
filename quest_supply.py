"""Read-only Minecraft Anvil supply and player progression helpers.

The observer intentionally fails closed. A missing, malformed, or incomplete
spawn-area snapshot never becomes evidence that an item is available.
"""

from __future__ import annotations

import gzip
import math
import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from tools import nbt


_ITEM_ENTITY_ID = "minecraft:item"


@dataclass
class SupplySnapshot:
    items: dict[str, int] = field(default_factory=dict)
    sources: dict[str, set[str]] = field(default_factory=dict)
    complete: bool = False
    reason: str = ""

    def add(self, item: str, count: int, source: str) -> None:
        if not isinstance(item, str) or not item.startswith("minecraft:") or count <= 0:
            return
        self.items[item] = self.items.get(item, 0) + int(count)
        self.sources.setdefault(item, set()).add(source)


@dataclass(frozen=True)
class PlayerProfile:
    player: str
    experience_levels: int
    inventory_items: frozenset[str]
    ender_items: frozenset[str]
    equipment_items: frozenset[str]
    score: int
    confidence: str = "complete"


class AnvilWorldReader:
    """Read saved overworld chunks without mutating them."""

    def __init__(self, world_path: Path):
        self.world_path = Path(world_path)
        candidates = (
            self.world_path / "dimensions/minecraft/overworld",
            self.world_path,
            self.world_path / "world",
        )
        self.overworld = next((path for path in candidates if (path / "region").is_dir()), candidates[0])
        self.region_dir = self.overworld / "region"
        self.entities_dir = self.overworld / "entities"

    @staticmethod
    def _region_coordinate(chunk: int) -> int:
        return chunk // 32

    @staticmethod
    def _region_file(directory: Path, rx: int, rz: int) -> Path:
        return directory / f"r.{rx}.{rz}.mca"

    @staticmethod
    def _header_entry(header: bytes, local_x: int, local_z: int) -> tuple[int, int]:
        offset = 4 * (local_x + local_z * 32)
        value = int.from_bytes(header[offset:offset + 4], "big")
        return value >> 8, value & 0xFF

    @classmethod
    def _read_chunk(cls, path: Path, chunk_x: int, chunk_z: int):
        if not path.is_file():
            raise FileNotFoundError(path)
        payload = path.read_bytes()
        if len(payload) < 8192:
            raise ValueError("truncated Anvil header")
        offset, sectors = cls._header_entry(payload[:4096], chunk_x & 31, chunk_z & 31)
        if offset == 0 or sectors == 0:
            raise FileNotFoundError(f"missing chunk {chunk_x},{chunk_z}")
        start = offset * 4096
        if start + 5 > len(payload):
            raise ValueError("chunk offset outside region")
        length = int.from_bytes(payload[start:start + 4], "big")
        if length < 1 or start + 4 + length > len(payload):
            raise ValueError("invalid chunk length")
        compression = payload[start + 4]
        compressed = payload[start + 5:start + 4 + length]
        if compression == 1:
            raw = gzip.decompress(compressed)
        elif compression == 2:
            raw = zlib.decompress(compressed)
        elif compression == 3:
            raw = compressed
        else:
            raise ValueError(f"unsupported Anvil compression {compression}")
        return nbt.loads(raw)

    @staticmethod
    def _sections(chunk: dict) -> Iterable[dict]:
        sections = chunk.get("sections", chunk.get("Level", {}).get("Sections", []))
        return sections if isinstance(sections, (list, tuple)) else []

    @staticmethod
    def _palette(section: dict):
        states = section.get("block_states", section.get("BlockStates"))
        if not isinstance(states, dict):
            return (), ()
        palette = states.get("palette", states.get("Palette", []))
        data = states.get("data", states.get("Data", []))
        if not isinstance(palette, (list, tuple)):
            return (), ()
        return palette, data if isinstance(data, (list, tuple)) else ()

    @staticmethod
    def _palette_counts(palette, packed) -> Iterable[tuple[dict, int]]:
        if not palette:
            return ()
        if len(palette) == 1:
            return ((palette[0], 4096),)
        if not packed:
            raise ValueError("palette has no packed block-state data")
        bits = max(4, (len(palette) - 1).bit_length())
        mask = (1 << bits) - 1
        words = [int(word) & ((1 << 64) - 1) for word in packed]
        counts = [0] * len(palette)
        for index in range(4096):
            bit = index * bits
            word = bit // 64
            shift = bit % 64
            value = words[word] >> shift
            used = 64 - shift
            if used < bits and word + 1 < len(words):
                value |= words[word + 1] << used
            palette_index = value & mask
            if palette_index < len(counts):
                counts[palette_index] += 1
        return tuple((state, count) for state, count in zip(palette, counts) if count)

    @staticmethod
    def _state_id(state: dict | str) -> str:
        if isinstance(state, str):
            return state
        if not isinstance(state, dict):
            return ""
        return state.get("Name", state.get("name", state.get("id", "")))

    @staticmethod
    def _item_id(stack: dict) -> str:
        return stack.get("id", stack.get("Id", ""))

    @staticmethod
    def _item_count(stack: dict) -> int:
        value = stack.get("count", stack.get("Count", 0))
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _supply_item(block_id: str) -> str | None:
        direct = {
            "minecraft:carrots": "minecraft:carrot",
            "minecraft:wheat": "minecraft:wheat",
            "minecraft:potatoes": "minecraft:potato",
            "minecraft:beetroots": "minecraft:beetroot",
            "minecraft:pumpkin": "minecraft:pumpkin",
            "minecraft:melon": "minecraft:melon",
            "minecraft:oak_log": "minecraft:oak_log",
            "minecraft:hay_block": "minecraft:wheat",
        }
        return direct.get(block_id)

    @staticmethod
    def _position(entity: dict) -> tuple[float, float, float] | None:
        position = entity.get("Pos", entity.get("pos"))
        if not isinstance(position, (list, tuple)) or len(position) != 3:
            return None
        try:
            return tuple(float(value) for value in position)
        except (TypeError, ValueError):
            return None

    def snapshot(self, x: float, y: float, z: float, radius: int = 64) -> SupplySnapshot:
        snapshot = SupplySnapshot()
        center_x, center_z = int(math.floor(x)), int(math.floor(z))
        min_chunk_x = (center_x - radius) // 16
        max_chunk_x = (center_x + radius) // 16
        min_chunk_z = (center_z - radius) // 16
        max_chunk_z = (center_z + radius) // 16
        expected = 0
        readable = 0
        for chunk_x in range(min_chunk_x, max_chunk_x + 1):
            for chunk_z in range(min_chunk_z, max_chunk_z + 1):
                expected += 1
                region = self._region_file(self.region_dir, self._region_coordinate(chunk_x),
                                           self._region_coordinate(chunk_z))
                try:
                    chunk = self._read_chunk(region, chunk_x, chunk_z)
                except (FileNotFoundError, OSError, ValueError, EOFError, zlib.error, gzip.BadGzipFile):
                    continue
                try:
                    for section in self._sections(chunk):
                        palette, packed = self._palette(section)
                        for state, count in self._palette_counts(palette, packed):
                            item = self._supply_item(self._state_id(state))
                            if item:
                                snapshot.add(item, count, "spawn_blocks")
                    for block_entity in chunk.get("block_entities", chunk.get("Level", {}).get("TileEntities", [])):
                        if not isinstance(block_entity, dict):
                            continue
                        for stack in block_entity.get("Items", []):
                            if isinstance(stack, dict):
                                snapshot.add(self._item_id(stack), self._item_count(stack), "spawn_containers")
                except (TypeError, ValueError, KeyError):
                    continue
                readable += 1
        entities_complete = self._read_item_entities(snapshot, center_x, center_z, radius)
        snapshot.complete = readable == expected and entities_complete and expected > 0
        snapshot.reason = "complete" if snapshot.complete else f"read {readable}/{expected} spawn chunks"
        return snapshot

    def _read_item_entities(self, snapshot: SupplySnapshot, center_x: int, center_z: int, radius: int) -> bool:
        # An absent entity region is the normal Anvil representation for no
        # saved entities. Existing entity regions must still decode fully.
        if not self.entities_dir.is_dir():
            return True
        min_chunk_x = (center_x - radius) // 16
        max_chunk_x = (center_x + radius) // 16
        min_chunk_z = (center_z - radius) // 16
        max_chunk_z = (center_z + radius) // 16
        expected = 0
        readable = 0
        for chunk_x in range(min_chunk_x, max_chunk_x + 1):
            for chunk_z in range(min_chunk_z, max_chunk_z + 1):
                region = self._region_file(self.entities_dir, self._region_coordinate(chunk_x),
                                           self._region_coordinate(chunk_z))
                if not region.exists():
                    continue
                try:
                    root = self._read_chunk(region, chunk_x, chunk_z)
                except FileNotFoundError:
                    continue
                except (OSError, ValueError, EOFError, zlib.error, gzip.BadGzipFile):
                    return False
                expected += 1
                readable += 1
                for entity in root.get("Entities", root.get("entities", [])):
                    if not isinstance(entity, dict) or entity.get("id") != _ITEM_ENTITY_ID:
                        continue
                    position = self._position(entity)
                    if position is None or math.hypot(position[0] - center_x, position[2] - center_z) > radius:
                        continue
                    stack = entity.get("Item", entity.get("item", {}))
                    if isinstance(stack, dict):
                        snapshot.add(self._item_id(stack), self._item_count(stack), "nearby_drops")
        return readable == expected


def parse_inventory_slots(response: str) -> list[dict]:
    """Parse Java 26.3 inventory compounds regardless of field ordering."""
    slots = []
    start = response.find("[")
    if start < 0:
        return slots
    chunks = []
    depth = 0
    token_start = start + 1
    for index in range(start + 1, len(response)):
        char = response[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            chunks.append(response[token_start:index])
            token_start = index + 1
    chunks.append(response[token_start:])
    for chunk in chunks:
        slot_match = re.search(r"(?:Slot|slot)\s*:\s*(-?\d+)b", chunk)
        item_match = re.search(r"(?:id|Id)\s*:\s*\"?(minecraft:[a-z0-9_/.-]+)\"?", chunk)
        count_match = re.search(r"(?:count|Count)\s*:\s*(-?\d+)", chunk)
        if not slot_match or not item_match or not count_match:
            continue
        slots.append({"slot": int(slot_match.group(1)), "id": item_match.group(1),
                      "count": max(0, int(count_match.group(1))), "raw": chunk.strip()})
    return slots


def parse_player_items(response: str) -> dict[str, int]:
    """Parse item IDs/counts from Java `data get entity` output."""
    result: dict[str, int] = {}
    for slot in parse_inventory_slots(response):
        result[slot["id"]] = result.get(slot["id"], 0) + slot["count"]
    return result


def strength_score(levels: int, inventory: dict[str, int], ender: dict[str, int], equipment: dict[str, int],
                   confidence: str = "complete") -> tuple[int, str]:
    progression_items = {
        "minecraft:iron_ingot": 3, "minecraft:diamond": 12, "minecraft:netherite_ingot": 25,
        "minecraft:blaze_rod": 15, "minecraft:ender_pearl": 18, "minecraft:shulker_shell": 28,
        "minecraft:ancient_debris": 32, "minecraft:netherite_scrap": 30,
    }
    score = max(0, min(100, int(levels)))
    for item, weight in progression_items.items():
        if item in inventory or item in ender:
            score += weight
    for item in equipment:
        if item.startswith("minecraft:diamond_"):
            score += 10
        elif item.startswith("minecraft:netherite_"):
            score += 20
        elif item.startswith("minecraft:iron_"):
            score += 3
    score = min(200, score)
    if levels < 0:
        confidence = "limited"
    return score, confidence


def build_profile(player: str, levels: int, inventory: dict[str, int], ender: dict[str, int],
                  equipment: dict[str, int], confidence: str = "complete") -> PlayerProfile:
    score, confidence = strength_score(levels, inventory, ender, equipment, confidence)
    return PlayerProfile(player, levels, frozenset(inventory), frozenset(ender), frozenset(equipment), score, confidence)
