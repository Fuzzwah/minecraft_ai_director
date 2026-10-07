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
from typing import Callable

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
    """Read complete, stable Java 26.3 overworld observations without writes."""

    _DATA_VERSION = 5023
    _SECTION_Y = range(-4, 20)
    _AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
    _CROPS = {
        "minecraft:wheat": ("minecraft:wheat", "7"),
        "minecraft:carrots": ("minecraft:carrot", "7"),
        "minecraft:potatoes": ("minecraft:potato", "7"),
        "minecraft:beetroots": ("minecraft:beetroot", "3"),
    }
    _CONTAINERS = {"minecraft:chest", "minecraft:trapped_chest", "minecraft:barrel"}

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
    def _region_file(directory: Path, chunk_x: int, chunk_z: int) -> Path:
        return directory / f"r.{chunk_x // 32}.{chunk_z // 32}.mca"

    @staticmethod
    def _identity(path: Path) -> tuple | None:
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    @staticmethod
    def _chunk_from_region(payload: bytes, chunk_x: int, chunk_z: int) -> dict | None:
        if len(payload) < 8192:
            raise ValueError("invalid Anvil region size")
        index = 4 * ((chunk_x & 31) + (chunk_z & 31) * 32)
        location = int.from_bytes(payload[index:index + 4], "big")
        offset, sectors = location >> 8, location & 255
        if not offset and not sectors:
            return None
        if offset < 2 or not sectors or offset * 4096 + 5 > len(payload):
            raise ValueError("invalid Anvil chunk allocation")
        start = offset * 4096
        length = int.from_bytes(payload[start:start + 4], "big")
        if length < 1 or length + 4 > sectors * 4096 or start + 4 + length > len(payload):
            raise ValueError("invalid Anvil chunk length")
        compression = payload[start + 4]
        raw = payload[start + 5:start + 4 + length]
        if compression == 1:
            raw = gzip.decompress(raw)
        elif compression == 2:
            inflater = zlib.decompressobj()
            raw = inflater.decompress(raw)
            if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
                raise ValueError("invalid compressed Anvil record length")
        elif compression != 3:
            raise ValueError(f"unsupported Anvil compression {compression}")
        return nbt.loads(raw)

    @classmethod
    def _normalize_state(cls, state: dict | str, version: int) -> tuple[str, dict[str, str]]:
        if version != cls._DATA_VERSION:
            raise ValueError(f"unsupported block-state DataVersion {version}")
        if isinstance(state, str):
            block_id, properties = state, {}
        elif isinstance(state, dict):
            # Java 26.3's heterogeneous codec list wraps its string alternative
            # in an empty-name compound. Keep the trusted NBT types intact.
            if set(state) == {""}:
                block_id, properties = state[""], {}
            elif "id" in state and set(state) <= {"id", "properties"}:
                block_id, properties = state["id"], state.get("properties", {})
            elif "Name" in state and set(state) <= {"Name", "Properties"}:
                block_id, properties = state["Name"], state.get("Properties", {})
            else:
                raise ValueError("unsupported block-state palette representation")
        else:
            raise ValueError("invalid block-state palette entry")
        if not isinstance(block_id, str) or not re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9_./-]+", block_id):
            raise ValueError("invalid block-state id")
        if not isinstance(properties, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in properties.items()
        ):
            raise ValueError("invalid block-state properties")
        return block_id, properties

    @classmethod
    def _decode_section(cls, section: dict, version: int) -> tuple[list, list[int]]:
        if not isinstance(section, dict):
            raise ValueError("invalid section")
        states = section.get("block_states")
        if not isinstance(states, dict) or set(states) - {"palette", "data"}:
            raise ValueError("unsupported block-state layout")
        palette = states.get("palette")
        if not isinstance(palette, (list, tuple)) or not 1 <= len(palette) <= 4096:
            raise ValueError("invalid block-state palette length")
        normalized = [cls._normalize_state(state, version) for state in palette]
        packed = states.get("data")
        if len(palette) == 1:
            if packed is not None:
                raise ValueError("single-state section has unexpected packed data")
            return normalized, [0] * 4096
        if not isinstance(packed, nbt.LongArray):
            raise ValueError("block states require an NBT long array")
        bits = max(4, (len(palette) - 1).bit_length())
        per_word = 64 // bits
        if len(packed) != (4096 + per_word - 1) // per_word:
            raise ValueError("invalid padded block-state array length")
        mask = (1 << bits) - 1
        indices = []
        # Since Java 1.16 entries do not cross word boundaries. Actual 5023
        # five-bit palettes have 342 words, not the continuous layout's 320.
        for word_index, signed_word in enumerate(packed):
            if not isinstance(signed_word, int) or not -(1 << 63) <= signed_word < (1 << 63):
                raise ValueError("invalid packed block-state word")
            word = signed_word & ((1 << 64) - 1)
            entries = min(per_word, 4096 - word_index * per_word)
            for slot in range(entries):
                index = (word >> (slot * bits)) & mask
                if index >= len(palette):
                    raise ValueError("block-state palette index out of range")
                indices.append(index)
        return normalized, indices

    @staticmethod
    def _integer(value, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"invalid {label}")
        return value

    @classmethod
    def _decode_chunk(cls, chunk: dict, chunk_x: int, chunk_z: int) -> dict:
        version = cls._integer(chunk.get("DataVersion"), "DataVersion")
        if version != cls._DATA_VERSION or chunk.get("Status") != "minecraft:full":
            raise ValueError("unsupported or unfinished saved chunk")
        if (cls._integer(chunk.get("xPos"), "xPos"), cls._integer(chunk.get("zPos"), "zPos")) != (chunk_x, chunk_z):
            raise ValueError("saved chunk coordinates mismatch")
        if cls._integer(chunk.get("yPos"), "yPos") != -4:
            raise ValueError("unsupported overworld vertical layout")
        sections = chunk.get("sections")
        if not isinstance(sections, (list, tuple)):
            raise ValueError("missing sections")
        decoded = {}
        for section in sections:
            if not isinstance(section, dict):
                raise ValueError("invalid section")
            section_y = cls._integer(section.get("Y"), "section Y")
            if section_y not in cls._SECTION_Y or section_y in decoded:
                raise ValueError("invalid or duplicate section Y")
            decoded[section_y] = cls._decode_section(section, version)
        if set(decoded) != set(cls._SECTION_Y):
            raise ValueError("incomplete saved column sections")
        return decoded

    @staticmethod
    def _block(decoded: dict, x: int, y: int, z: int) -> tuple[str, dict]:
        palette, indices = decoded[y // 16]
        return palette[indices[(y & 15) * 256 + (z & 15) * 16 + (x & 15)]]

    @classmethod
    def _top(cls, decoded: dict, x: int, z: int) -> int | None:
        for section_y in reversed(cls._SECTION_Y):
            palette, indices = decoded[section_y]
            if len(palette) == 1 and palette[0][0] in cls._AIR:
                continue
            for local_y in range(15, -1, -1):
                if palette[indices[local_y * 256 + z * 16 + x]][0] not in cls._AIR:
                    return section_y * 16 + local_y
        return None

    @classmethod
    def _stack(cls, stack: dict) -> tuple[str, int]:
        if not isinstance(stack, dict):
            raise ValueError("invalid item stack")
        item = stack.get("id")
        count = cls._integer(stack.get("count"), "stack count")
        if not isinstance(item, str) or not re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9_./-]+", item) or count <= 0:
            raise ValueError("invalid item stack id/count")
        return item, count

    @classmethod
    def _observe_blocks(cls, snapshot: SupplySnapshot, chunk: dict, decoded: dict,
                        chunk_x: int, chunk_z: int, inside: Callable, warmup: bool) -> None:
        tops = {}
        for local_z in range(16):
            for local_x in range(16):
                world_x, world_z = chunk_x * 16 + local_x, chunk_z * 16 + local_z
                if not inside(world_x, world_z):
                    continue
                top = cls._top(decoded, local_x, local_z)
                tops[local_x, local_z] = top
                if top is None or top <= -64:
                    continue
                block, properties = cls._block(decoded, local_x, top, local_z)
                support = cls._block(decoded, local_x, top - 1, local_z)[0]
                if block in cls._CROPS:
                    item, age = cls._CROPS[block]
                    if properties.get("age") == age and support == "minecraft:farmland":
                        snapshot.add(item, 1, "spawn_blocks")
                elif support not in cls._AIR and support not in {"minecraft:water", "minecraft:lava"}:
                    if block == "minecraft:pumpkin":
                        snapshot.add("minecraft:pumpkin", 1, "spawn_blocks")
                    elif block == "minecraft:hay_block":
                        snapshot.add("minecraft:wheat", 9, "spawn_blocks")
                    elif not warmup and block == "minecraft:oak_log":
                        snapshot.add("minecraft:oak_log", 1, "spawn_blocks")
        containers = chunk.get("block_entities")
        if not isinstance(containers, (list, tuple)):
            raise ValueError("missing block entities")
        seen = set()
        for container in containers:
            if not isinstance(container, dict):
                raise ValueError("invalid block entity")
            if container.get("id") not in cls._CONTAINERS:
                continue
            cx, cy, cz = (cls._integer(container.get(axis), f"container {axis}") for axis in ("x", "y", "z"))
            if cx // 16 != chunk_x or cz // 16 != chunk_z or not -64 <= cy < 320:
                raise ValueError("container coordinates outside chunk")
            if (cx, cy, cz) in seen:
                raise ValueError("duplicate container")
            seen.add((cx, cy, cz))
            if not inside(cx, cz):
                continue
            if cls._block(decoded, cx & 15, cy, cz & 15)[0] != container["id"]:
                raise ValueError("container block mismatch")
            if "LootTable" in container:
                if not isinstance(container["LootTable"], str) or "Items" in container:
                    raise ValueError("ambiguous saved container inventory")
                # An unopened loot-table chest has no realized item stacks.
                # Observing it must not generate loot or invent its contents.
                continue
            stacks = container.get("Items")
            if not isinstance(stacks, (list, tuple)):
                raise ValueError("invalid container inventory")
            parsed = [cls._stack(stack) for stack in stacks]
            if tops[cx & 15, cz & 15] == cy:
                for item, count in parsed:
                    snapshot.add(item, count, "spawn_containers")

    @classmethod
    def _observe_entities(cls, snapshot: SupplySnapshot, root: dict, chunk_x: int,
                          chunk_z: int, inside: Callable, decoded: dict) -> None:
        if cls._integer(root.get("DataVersion"), "entity DataVersion") != cls._DATA_VERSION:
            raise ValueError("unsupported entity DataVersion")
        position = root.get("Position")
        if not isinstance(position, nbt.IntArray) or list(position) != [chunk_x, chunk_z]:
            raise ValueError("entity chunk coordinates mismatch")
        entities = root.get("Entities")
        if not isinstance(entities, (list, tuple)):
            raise ValueError("invalid entities")
        for entity in entities:
            if not isinstance(entity, dict):
                raise ValueError("invalid saved entity")
            if entity.get("id") != _ITEM_ENTITY_ID:
                continue
            pos = entity.get("Pos")
            if not isinstance(pos, (list, tuple)) or len(pos) != 3 or any(
                not isinstance(value, (int, float)) or not math.isfinite(value) for value in pos
            ):
                raise ValueError("invalid item entity position")
            if math.floor(pos[0]) // 16 != chunk_x or math.floor(pos[2]) // 16 != chunk_z:
                raise ValueError("item entity coordinates outside chunk")
            if inside(pos[0], pos[2]):
                item, count = cls._stack(entity.get("Item"))
                top = cls._top(decoded, math.floor(pos[0]) & 15, math.floor(pos[2]) & 15)
                if top is not None and pos[1] >= top + 1:
                    snapshot.add(item, count, "nearby_drops")

    def snapshot(self, x: float, y: float, z: float, radius: int = 64, *,
                 warmup: bool = False, loaded: Callable[[int, int], bool] | None = None) -> SupplySnapshot:
        """Observe a horizontal disk; absent ``loaded`` is an offline copied-world read."""
        snapshot = SupplySnapshot()
        cache = {}
        identities = {}
        try:
            if any(not math.isfinite(value) for value in (x, y, z)) or not isinstance(radius, int) or radius < 0:
                raise ValueError("invalid snapshot coordinates/radius")
            inside = lambda bx, bz: (bx - x) ** 2 + (bz - z) ** 2 <= radius ** 2
            chunks = []
            for chunk_x in range(math.floor(x - radius) // 16, math.floor(x + radius) // 16 + 1):
                for chunk_z in range(math.floor(z - radius) // 16, math.floor(z + radius) // 16 + 1):
                    near_x = min(max(x, chunk_x * 16), chunk_x * 16 + 16)
                    near_z = min(max(z, chunk_z * 16), chunk_z * 16 + 16)
                    if inside(near_x, near_z):
                        chunks.append((chunk_x, chunk_z))
            if loaded is not None and any(loaded(cx, cz) is not True for cx, cz in chunks):
                raise ValueError("relevant chunks are not verifiably loaded")

            def region(directory, cx, cz, required):
                path = self._region_file(directory, cx, cz)
                if path not in cache:
                    identities[path] = self._identity(path)
                    cache[path] = path.read_bytes() if identities[path] is not None else None
                payload = cache[path]
                if payload is None:
                    if required:
                        raise ValueError("missing saved terrain region")
                    return None
                root = self._chunk_from_region(payload, cx, cz)
                if root is None and required:
                    raise ValueError("missing saved terrain chunk")
                return root

            for cx, cz in chunks:
                chunk = region(self.region_dir, cx, cz, True)
                decoded = self._decode_chunk(chunk, cx, cz)
                self._observe_blocks(snapshot, chunk, decoded, cx, cz, inside, warmup)
                entities = region(self.entities_dir, cx, cz, False)
                if entities is not None:
                    self._observe_entities(snapshot, entities, cx, cz, inside, decoded)
            if loaded is not None and any(loaded(cx, cz) is not True for cx, cz in chunks):
                raise ValueError("relevant chunks unloaded during observation")
            if any(self._identity(path) != identity for path, identity in identities.items()):
                raise ValueError("saved region changed during observation")
        except (OSError, ValueError, EOFError, TypeError, KeyError, zlib.error) as error:
            # Partial positive evidence must not escape even to an incautious caller.
            return SupplySnapshot(reason=f"unavailable: {error}")
        snapshot.complete = True
        snapshot.reason = "complete"
        return snapshot


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
