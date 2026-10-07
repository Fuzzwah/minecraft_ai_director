"""Isolated Java 26.3 Anvil fixtures; never inspect or mutate a live world."""

import copy
import math
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from quest_supply import AnvilWorldReader, SupplySnapshot
from tools import nbt


AIR = "minecraft:air"
DIRT = "minecraft:dirt"
FARMLAND = {"id": "minecraft:farmland", "properties": {"moisture": "7"}}


def crop(name, age):
    return {"id": "minecraft:" + name, "properties": {"age": str(age)}}


def section(section_y, blocks=(), *, filler=0):
    """Encode native homogeneous/mixed-codec palettes in padded long words."""
    palette = [AIR]
    cells = [0] * 4096
    for x, y, z, state in blocks:
        if state not in palette:
            palette.append(state)
        cells[(y & 15) * 256 + (z & 15) * 16 + (x & 15)] = palette.index(state)
    for index in range(filler):
        palette.append("minecraft:fixture_" + str(index))
    if any(isinstance(state, dict) for state in palette):
        palette = [state if isinstance(state, dict) else {"": state} for state in palette]
    states = {"palette": palette}
    if len(palette) > 1:
        bits = max(4, (len(palette) - 1).bit_length())
        entries_per_long = 64 // bits
        words = []
        for start in range(0, 4096, entries_per_long):
            word = sum(value << (offset * bits) for offset, value in enumerate(cells[start:start + entries_per_long]))
            words.append(word if word < 2 ** 63 else word - 2 ** 64)
        states["data"] = nbt.LongArray(words)
    return {"Y": nbt.Byte(section_y), "block_states": states}


def terrain(cx=0, cz=0, blocks=(), containers=(), *, filler=0):
    sections = []
    for sy in range(-4, 20):
        relevant = [block for block in blocks if block[1] // 16 == sy]
        sections.append(section(sy, relevant, filler=filler if relevant else 0))
    return {
        "DataVersion": nbt.Int(5023), "Status": "minecraft:full",
        "xPos": nbt.Int(cx), "zPos": nbt.Int(cz), "yPos": nbt.Int(-4),
        "sections": sections, "block_entities": list(containers),
    }


def chest(x, y, z, item, count):
    return {"id": "minecraft:chest", "x": nbt.Int(x), "y": nbt.Int(y), "z": nbt.Int(z),
            "Items": [{"Slot": nbt.Byte(0), "id": "minecraft:" + item, "count": nbt.Int(count)}]}


def drop(x, y, z, item, count):
    return {"id": "minecraft:item", "Pos": [nbt.Double(x), nbt.Double(y), nbt.Double(z)],
            "Item": {"id": "minecraft:" + item, "count": nbt.Int(count)}}


def entity_chunk(cx, cz, entities):
    return {"DataVersion": nbt.Int(5023), "Position": nbt.IntArray([cx, cz]), "Entities": entities}


def write_regions(directory, chunks, *, trailing_padding=True):
    grouped = {}
    for (cx, cz), root in chunks.items():
        grouped.setdefault((cx // 32, cz // 32), []).append((cx, cz, root))
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for (rx, rz), roots in grouped.items():
        header = bytearray(8192)
        records = []
        offset = 2
        for cx, cz, root in roots:
            compressed = zlib.compress(nbt.dumps(root, compressed=False))
            record = (len(compressed) + 1).to_bytes(4, "big") + b"\x02" + compressed
            sectors = math.ceil(len(record) / 4096)
            index = 4 * ((cx & 31) + (cz & 31) * 32)
            header[index:index + 4] = ((offset << 8) | sectors).to_bytes(4, "big")
            records.append(record + bytes(sectors * 4096 - len(record)))
            offset += sectors
        if not trailing_padding:
            records[-1] = records[-1][:4 + int.from_bytes(records[-1][:4], "big")]
        path = directory / f"r.{rx}.{rz}.mca"
        path.write_bytes(header + b"".join(records))
        paths.append(path)
    return paths


class SupplyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.world = Path(self.temporary.name)
        self.regions = self.world / "region"
        self.entities = self.world / "entities"

    def save(self, chunks, entities=None, **kwargs):
        paths = write_regions(self.regions, chunks, **kwargs)
        if entities is not None:
            write_regions(self.entities, entities)
        self.reader = AnvilWorldReader(self.world)
        return paths

    def observe(self, x=8, z=8, radius=7, **kwargs):
        return self.reader.snapshot(x, 65, z, radius, warmup=kwargs.pop("warmup", True), **kwargs)

    def assertUnavailable(self, result):
        self.assertFalse(result.complete)
        self.assertEqual(result.items, {})
        self.assertEqual(result.sources, {})
        self.assertIn("unavailable", result.reason)

    def test_mature_crop_age_and_conservative_yields(self):
        blocks = []
        for x, name, age in [(2, "wheat", 7), (3, "carrots", 6), (4, "potatoes", 7),
                              (5, "beetroots", 3), (6, "beetroots", 2), (7, "carrots", 7)]:
            blocks += [(x, 64, 8, FARMLAND), (x, 65, 8, crop(name, age))]
        blocks += [(8, 64, 8, DIRT), (8, 65, 8, "minecraft:pumpkin"),
                   (9, 64, 8, DIRT), (9, 65, 8, "minecraft:hay_block"),
                   (10, 64, 8, DIRT), (10, 65, 8, "minecraft:melon")]
        self.save({(0, 0): terrain(blocks=blocks)})
        result = self.observe()
        self.assertTrue(result.complete)
        self.assertEqual(result.items, {"minecraft:wheat": 10, "minecraft:potato": 1,
                                      "minecraft:beetroot": 1, "minecraft:carrot": 1, "minecraft:pumpkin": 1})
        self.assertEqual(result.sources["minecraft:wheat"], {"spawn_blocks"})

    def test_missing_growth_buried_and_unsupported_crops_are_not_supply(self):
        blocks = [(4, 64, 8, FARMLAND), (4, 65, 8, "minecraft:carrots"),
                  (5, 64, 8, FARMLAND), (5, 65, 8, crop("carrots", 7)), (5, 66, 8, DIRT),
                  (6, 65, 8, crop("wheat", 7)),
                  (7, 64, 8, DIRT), (7, 65, 8, crop("wheat", 7)),
                  (8, -32, 8, DIRT), (8, -31, 8, "minecraft:pumpkin"), (8, 64, 8, DIRT)]
        self.save({(0, 0): terrain(blocks=blocks)})
        result = self.observe()
        self.assertTrue(result.complete)
        self.assertEqual(result.items, {})

    def test_one_pumpkin_and_five_wheat_do_not_become_catalog_minimum(self):
        blocks = [(8, 64, 8, DIRT), (8, 65, 8, "minecraft:pumpkin")]
        for x in range(3, 8):
            blocks += [(x, 64, 8, FARMLAND), (x, 65, 8, crop("wheat", 7))]
        self.save({(0, 0): terrain(blocks=blocks)})
        result = self.observe()
        self.assertTrue(result.complete)
        self.assertEqual(result.items, {"minecraft:pumpkin": 1, "minecraft:wheat": 5})
        self.assertLess(result.items["minecraft:pumpkin"], 2)
        self.assertLess(result.items["minecraft:wheat"], 6)

    def test_actual_disk_edge_not_intersecting_section_or_square(self):
        blocks = []
        for x, z in [(13, 8), (14, 8), (12, 12), (3, 8), (8, 13)]:
            blocks += [(x, 64, z, DIRT), (x, 65, z, "minecraft:pumpkin")]
        self.save({(0, 0): terrain(blocks=blocks)})
        result = self.observe(radius=5)
        self.assertTrue(result.complete)
        self.assertEqual(result.items, {"minecraft:pumpkin": 3})
        fractional = self.observe(x=8.25, radius=5)
        self.assertTrue(fractional.complete)
        self.assertEqual(fractional.items, {"minecraft:pumpkin": 1})

    def test_mixed_native_palette_padded_boundaries_have_exact_positions(self):
        # Five bits: cell 395 ends word 32, cell 396 starts word 33.
        blocks = [(11, 64, 8, FARMLAND), (11, 65, 8, crop("wheat", 7)),
                  (12, 64, 8, FARMLAND), (12, 65, 8, crop("carrots", 7)),
                  (15, 64, 15, FARMLAND), (15, 65, 15, crop("carrots", 7))]
        root = terrain(blocks=blocks, filler=17)
        self.save({(0, 0): root})
        for x, item in [(11, "minecraft:wheat"), (12, "minecraft:carrot")]:
            with self.subTest(x=x):
                result = self.observe(x=x, z=8, radius=0)
                self.assertTrue(result.complete)
                self.assertEqual(result.items, {item: 1})
        self.assertIsInstance(root["sections"][8]["block_states"]["data"], nbt.LongArray)
        self.assertEqual(len(root["sections"][8]["block_states"]["data"]), 342)

    def test_each_axis_and_section_y_is_positional(self):
        blocks = [(2, 79, 3, DIRT), (2, 80, 3, "minecraft:pumpkin"),
                  (3, 79, 2, FARMLAND), (3, 80, 2, crop("carrots", 7))]
        self.save({(0, 0): terrain(blocks=blocks)})
        result = self.observe(x=2, z=3, radius=0)
        self.assertTrue(result.complete)
        self.assertEqual(result.items, {"minecraft:pumpkin": 1})

    def test_negative_chunks_regions_and_entity_coordinates(self):
        blocks = [(-5, 64, -5, DIRT), (-5, 65, -5, "minecraft:pumpkin"),
                  (-6, 64, -5, DIRT), (-6, 65, -5, "minecraft:chest"), (-6, 64, -6, DIRT)]
        root = terrain(-1, -1, blocks, [chest(-6, 65, -5, "melon", 3)])
        entities = entity_chunk(-1, -1, [drop(-5.25, 65, -5.25, "carrot", 4)])
        self.save({(-1, -1): root}, {(-1, -1): entities})
        result = self.observe(x=-6, z=-6, radius=1)
        self.assertTrue(result.complete)
        self.assertEqual(result.items, {"minecraft:melon": 3})
        result = self.observe(x=-6, z=-6, radius=2)
        self.assertTrue(result.complete)
        self.assertEqual(result.items, {"minecraft:pumpkin": 1, "minecraft:melon": 3, "minecraft:carrot": 4})

    def test_chests_and_drops_obey_radius_and_exact_stacks_without_recipes(self):
        blocks = []
        containers = []
        for x in [8, 13, 14]:
            blocks += [(x, 64, 8, DIRT), (x, 65, 8, "minecraft:chest")]
            containers.append(chest(x, 65, 8, "melon", 2))
        containers.append(chest(9, 60, 8, "diamond", 64))
        blocks += [(9, 60, 8, "minecraft:chest"), (9, 65, 8, DIRT)]
        entities = entity_chunk(0, 0, [drop(8, 66, 8, "raw_iron", 7), drop(13, 66, 8, "oak_log", 3),
                                     drop(13.01, 66, 8, "diamond", 99), drop(9, 60, 8, "diamond", 99)])
        self.save({(0, 0): terrain(blocks=blocks, containers=containers)}, {(0, 0): entities})
        result = self.observe(radius=5)
        self.assertTrue(result.complete)
        self.assertEqual(result.items, {"minecraft:melon": 4, "minecraft:raw_iron": 7, "minecraft:oak_log": 3})
        self.assertEqual(result.sources["minecraft:melon"], {"spawn_containers"})
        self.assertEqual(result.sources["minecraft:oak_log"], {"nearby_drops"})
        self.assertNotIn("minecraft:iron_ingot", result.items)

    def test_warmup_excludes_building_logs_but_not_exact_stacks(self):
        blocks = [(8, 64, 8, DIRT), (8, 65, 8, "minecraft:oak_log"),
                  (9, 65, 8, "minecraft:chest")]
        self.save({(0, 0): terrain(blocks=blocks, containers=[chest(9, 65, 8, "oak_log", 4)])})
        warm = self.observe()
        later = self.observe(warmup=False)
        self.assertTrue(warm.complete)
        self.assertTrue(later.complete)
        self.assertEqual(warm.items, {"minecraft:oak_log": 4})
        self.assertEqual(later.items, {"minecraft:oak_log": 5})

    def test_single_state_strings_and_empty_name_wrappers(self):
        for state in ["minecraft:pumpkin", {"": "minecraft:pumpkin"}, {"Name": "minecraft:pumpkin"}]:
            with self.subTest(state=state):
                root = terrain()
                root["sections"][8] = {"Y": nbt.Byte(4), "block_states": {"palette": [state]}}
                self.save({(0, 0): root})
                result = self.observe(radius=0)
                self.assertTrue(result.complete)
                self.assertEqual(result.items, {"minecraft:pumpkin": 1})

    def test_malformed_lengths_indices_types_and_single_state_data_fail_closed(self):
        blocks = [(8, 64, 8, DIRT), (8, 65, 8, "minecraft:pumpkin")]
        root = terrain(blocks=blocks, filler=17)
        mutations = {
            "truncated": lambda states: states["data"].pop(),
            "extra word": lambda states: states["data"].append(nbt.Long(0)),
            "continuous layout": lambda states: states.update(data=nbt.LongArray([0] * 320)),
            "invalid index outside radius": lambda states: states["data"].__setitem__(0, nbt.Long(31)),
            "wrong NBT type": lambda states: states.update(data=nbt.IntArray([0] * 342)),
            "unknown layout": lambda states: states.update(bits=5),
            "unknown palette schema": lambda states: states.update(
                palette=[{"name": AIR}] + [{"": state} for state in states["palette"][1:]]),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                bad = copy.deepcopy(root)
                mutate(bad["sections"][8]["block_states"])
                self.save({(0, 0): bad})
                self.assertUnavailable(self.observe(radius=0))
        bad = terrain(blocks=blocks)
        bad["sections"][0]["block_states"]["data"] = nbt.LongArray([0] * 256)
        self.save({(0, 0): bad})
        self.assertUnavailable(self.observe())

    def test_unsupported_version_incomplete_sections_wrong_coordinates_and_status(self):
        for field, value in [("DataVersion", 9999), ("xPos", 1), ("zPos", -1),
                             ("yPos", 0), ("Status", "minecraft:noise")]:
            with self.subTest(field=field):
                root = terrain()
                root[field] = value
                self.save({(0, 0): root})
                self.assertUnavailable(self.observe())
        for alteration in [lambda sections: sections.pop(), lambda sections: sections.append(sections[0])]:
            root = terrain()
            alteration(root["sections"])
            self.save({(0, 0): root})
            self.assertUnavailable(self.observe())

    def test_no_partial_positive_evidence_if_another_chunk_is_missing(self):
        blocks = [(15, 64, 8, DIRT), (15, 65, 8, "minecraft:pumpkin")]
        self.save({(0, 0): terrain(blocks=blocks)})
        self.assertUnavailable(self.observe(x=15, z=8, radius=2))

    def test_unloaded_initial_and_final_probes_fail_closed(self):
        self.save({(0, 0): terrain(blocks=[(8, 64, 8, DIRT), (8, 65, 8, "minecraft:pumpkin")])})
        with patch.object(Path, "read_bytes", side_effect=AssertionError("unloaded chunk must not be read")):
            self.assertUnavailable(self.observe(loaded=lambda cx, cz: False))
        answers = iter([True, False])
        self.assertUnavailable(self.observe(loaded=lambda cx, cz: next(answers)))
        calls = []
        result = self.observe(loaded=lambda cx, cz: calls.append((cx, cz)) or True)
        self.assertTrue(result.complete)
        self.assertEqual(calls, [(0, 0), (0, 0)])

    def test_region_read_once_and_identity_checked_before_after(self):
        self.save({(0, 0): terrain(), (1, 0): terrain(1, 0)})
        reads = []
        original = Path.read_bytes
        def read_once(path):
            reads.append(path)
            return original(path)
        with patch.object(Path, "read_bytes", read_once):
            result = self.observe(x=15, z=8, radius=2)
        self.assertTrue(result.complete)
        self.assertEqual(reads, [self.regions / "r.0.0.mca"])
        self.assertEqual(result.items, {})

    def test_changing_region_rejects_all_supply(self):
        paths = self.save({(0, 0): terrain(blocks=[(8, 64, 8, DIRT), (8, 65, 8, "minecraft:pumpkin")])})
        original = Path.read_bytes
        def changing(path):
            payload = original(path)
            if path == paths[0]:
                path.write_bytes(payload + b"\0")
            return payload
        with patch.object(Path, "read_bytes", changing):
            self.assertUnavailable(self.observe())

    def test_creating_previously_absent_entity_region_rejects_snapshot(self):
        self.save({(0, 0): terrain()})
        original = self.reader._identity
        calls = {}
        def create_after_first_stat(path):
            calls[path] = calls.get(path, 0) + 1
            if path.parent == self.entities and calls[path] == 2:
                write_regions(self.entities, {(0, 0): entity_chunk(0, 0, [drop(8, 65, 8, "diamond", 64)])})
            return original(path)
        with patch.object(self.reader, "_identity", create_after_first_stat):
            self.assertUnavailable(self.observe())

    def test_malformed_entities_and_chest_data_fail_closed(self):
        blocks = [(8, 64, 8, DIRT), (8, 65, 8, "minecraft:pumpkin"), (9, 65, 8, "minecraft:chest")]
        noninteger = chest(9, 65, 8, "melon", 2)
        noninteger["Items"][0]["count"] = nbt.Double(2.0)
        for malformed in [chest(9, 65, 8, "melon", 0), noninteger]:
            self.save({(0, 0): terrain(blocks=blocks, containers=[malformed])})
            self.assertUnavailable(self.observe())
        good = terrain(blocks=blocks, containers=[chest(9, 65, 8, "melon", 2)])
        for mutate in [lambda root: root.update(DataVersion=1), lambda root: root.update(Position=nbt.IntArray([1, 0])),
                       lambda root: root["Entities"][0].update(Pos=[nbt.Double(float("nan"))] * 3),
                       lambda root: root["Entities"][0].update(Item={"id": "minecraft:carrot", "count": 0})]:
            bad = entity_chunk(0, 0, [drop(8, 65, 8, "carrot", 3)])
            mutate(bad)
            self.save({(0, 0): good}, {(0, 0): bad})
            self.assertUnavailable(self.observe())

    def test_record_truncation_and_unsupported_compression_are_unavailable(self):
        paths = self.save({(0, 0): terrain()})
        payload = paths[0].read_bytes()
        for malformed in [payload[:8192], payload[:8196] + b"\x04" + payload[8197:]]:
            paths[0].write_bytes(malformed)
            self.assertUnavailable(self.observe())

    def test_compressed_record_declared_length_must_match_the_stream(self):
        paths = self.save({(0, 0): terrain()})
        payload = paths[0].read_bytes()
        length = int.from_bytes(payload[8192:8196], "big")
        for declared in [0, length - 1, length + 1, 4096]:
            with self.subTest(declared=declared):
                paths[0].write_bytes(payload[:8192] + declared.to_bytes(4, "big") + payload[8196:])
                self.assertUnavailable(self.observe())

    def test_region_need_not_have_unused_trailing_sector_padding(self):
        self.save({(0, 0): terrain()}, trailing_padding=False)
        self.assertTrue(self.observe().complete)

    def test_unopened_native_loot_table_chest_has_no_realized_supply(self):
        blocks = [(8, 64, 8, DIRT), (8, 65, 8, "minecraft:pumpkin"), (9, 65, 8, "minecraft:chest")]
        unopened = {"id": "minecraft:chest", "x": nbt.Int(9), "y": nbt.Int(65), "z": nbt.Int(8),
                    "LootTable": "minecraft:chests/village/village_plains_house", "LootTableSeed": nbt.Long(123)}
        self.save({(0, 0): terrain(blocks=blocks, containers=[unopened])})
        result = self.observe()
        self.assertTrue(result.complete)
        self.assertEqual(result.items, {"minecraft:pumpkin": 1})

    def test_negative_section_y_and_topmost_surface_are_not_section_totals(self):
        blocks = [(8, -33, 8, FARMLAND), (8, -32, 8, crop("wheat", 7))]
        self.save({(0, 0): terrain(blocks=blocks)})
        result = self.observe(radius=0)
        self.assertTrue(result.complete)
        self.assertEqual(result.items, {"minecraft:wheat": 1})

    def test_replaced_region_with_identical_bytes_is_unstable(self):
        paths = self.save({(0, 0): terrain(blocks=[(8, 64, 8, DIRT), (8, 65, 8, "minecraft:pumpkin")])})
        original = Path.read_bytes
        def replacing(path):
            payload = original(path)
            replacement = path.with_suffix(".replacement")
            replacement.write_bytes(payload)
            replacement.replace(path)
            return payload
        with patch.object(Path, "read_bytes", replacing):
            self.assertUnavailable(self.observe())

    def test_snapshot_positional_dataclass_and_add_contract_remain_unchanged(self):
        snapshot = SupplySnapshot({"minecraft:wheat": 1}, {"minecraft:wheat": {"spawn_blocks"}}, True, "complete")
        snapshot.add("minecraft:wheat", 2, "nearby_drops")
        self.assertEqual(snapshot.items, {"minecraft:wheat": 3})
        self.assertEqual(snapshot.sources["minecraft:wheat"], {"spawn_blocks", "nearby_drops"})


if __name__ == "__main__":
    unittest.main()
