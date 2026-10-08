import copy
import gzip
import json
import shutil
import tempfile
import unittest
import zlib
from pathlib import Path

from tools import nbt
from tools import village_temples as temples


PACK = temples.DEFAULT_OUTPUT


class NBTTests(unittest.TestCase):
    def test_all_java_tags_and_modified_utf8_round_trip_preserve_wire_types(self):
        document = nbt.Compound({
            "byte": nbt.Byte(-128), "short": nbt.Short(-32768),
            "int": nbt.Int(-2147483648), "long": nbt.Long(-9223372036854775808),
            "float": nbt.Float(1.25), "double": nbt.Double(-2.5),
            "bytes": nbt.ByteArray(b"\x00\x80\xff"),
            "string": "Keeper\x00\U0001f3db\ud800",
            "list": nbt.List([nbt.Short(2), nbt.Short(3)], item_tag=2),
            "empty": nbt.List([], item_tag=10),
            "compound": {"nested": nbt.Byte(1)},
            "ints": nbt.IntArray([-2147483648, 0, 2147483647]),
            "longs": nbt.LongArray([-9223372036854775808, 9223372036854775807]),
        }, name="named\x00root")
        raw = nbt.dumps(document, compressed=False)
        for payload in (raw, gzip.compress(raw, mtime=0), zlib.compress(raw)):
            with self.subTest(compression=payload[:2]):
                decoded = nbt.loads(payload)
                self.assertEqual(decoded, document)
                self.assertEqual(decoded.name, document.name)
                self.assertEqual(nbt.dumps(decoded, compressed=False), raw)
                self.assertIsInstance(decoded["long"], nbt.Long)
                self.assertIsInstance(decoded["bytes"], nbt.ByteArray)
                self.assertIsInstance(decoded["ints"], nbt.IntArray)
                self.assertIsInstance(decoded["longs"], nbt.LongArray)
                self.assertEqual(decoded["empty"].item_tag, 10)

    def test_rejects_truncation_trailing_bytes_and_mixed_lists(self):
        raw = nbt.dumps({"name": "Keeper", "value": nbt.IntArray([1, 2])}, compressed=False)
        for bad in (raw[:-1], raw + b"x", b"\x01\x00\x00\x01"):
            with self.subTest(payload=bad), self.assertRaises(ValueError):
                nbt.loads(bad)
        with self.assertRaises(ValueError):
            nbt.dumps({"mixed": [nbt.Short(1), nbt.Int(2)]})


class VillageTempleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((PACK / "manifest.json").read_bytes())
        cls.roots = {resource: nbt.loads((PACK / temples.resource_path(resource)).read_bytes())
                     for resource in cls.manifest["roots"]}

    def first(self):
        resource = next(iter(self.roots))
        return copy.deepcopy(self.roots[resource]), self.manifest["roots"][resource]

    @staticmethod
    def change_block(root, position, state):
        if isinstance(state, str):
            state = {"id": state}
        if state not in root["palette"]:
            root["palette"].append(state)
        block = next(b for b in root["blocks"] if list(b["pos"]) == list(position))
        block["state"] = root["palette"].index(state)
        block.pop("nbt", None)

    def test_every_effective_weighted_boundary_covers_normal_and_abandoned_assets(self):
        seen = set()
        for style in temples.STYLES:
            pool = json.loads((PACK / temples.pool_path(style)).read_bytes())
            boundary = 0
            abandoned_weights = []
            for entry in pool["elements"]:
                resource = entry["element"]["location"]
                for ticket in (boundary, boundary + entry["weight"] - 1):
                    with self.subTest(style=style, ticket=ticket):
                        selected = temples.choose_weighted(pool, ticket)
                        self.assertEqual(selected, resource)
                        temples.validate_root(self.roots[selected], self.manifest["roots"][selected])
                        seen.add(selected)
                if "/zombie/" in resource:
                    abandoned_weights.append(entry["weight"])
                boundary += entry["weight"]
            self.assertTrue(abandoned_weights)
            self.assertLess(sum(abandoned_weights), boundary // 10)
            for invalid in (-1, boundary):
                with self.assertRaises(ValueError):
                    temples.choose_weighted(pool, invalid)
        self.assertEqual(len(seen), 32)
        self.assertEqual(sum("/zombie/" in resource for resource in seen), 16)

    def test_real_roots_have_one_roofed_altar_clear_entry_supported_paths_in_all_rotations(self):
        for resource, root in self.roots.items():
            record = self.manifest["roots"][resource]
            for rotation in range(4):
                with self.subTest(resource=resource, rotation=rotation):
                    temples.validate_root(root, record, rotations=(rotation,))
                    dimensions = root["size"] if rotation % 2 == 0 else [root["size"][2], root["size"][1], root["size"][0]]
                    for block in root["blocks"]:
                        p = temples.rotate(block["pos"], root["size"], rotation)
                        self.assertTrue(all(0 <= coordinate < bound for coordinate, bound in zip(p, dimensions)))
                    for joint in record["jigsaws"]:
                        orientation = joint["state"]["properties"]["orientation"]
                        rotated = temples.rotated_state(joint["state"], rotation)["properties"]["orientation"]
                        facing = orientation.split("_")[0]
                        if facing in ("north", "east", "south", "west"):
                            directions = ("north", "east", "south", "west")
                            self.assertEqual(rotated.split("_")[0], directions[(directions.index(facing) + rotation) % 4])

    def test_landmarks_have_four_tall_columns_obelisks_stairs_and_one_offering_source(self):
        for resource, root in self.roots.items():
            record = self.manifest["roots"][resource]
            with self.subTest(resource=resource):
                temples.validate_root(root, record)
                blocks = temples.block_map(root)
                floor = record["floor_y"]
                self.assertEqual(root["size"][::2], [25, 25])
                for x in (6, 9, 15, 18):
                    for y in range(floor + 5, floor + 10):
                        self.assertEqual(blocks[x, y, 10]["id"], "minecraft:sandstone")
                for x in (4, 20):
                    for y in range(floor + 5, floor + 16):
                        self.assertIn(blocks[x, y, 7]["id"],
                                      {"minecraft:sandstone", "minecraft:smooth_sandstone", "minecraft:chiseled_sandstone"})
                for z in range(4, 7):
                    for x in range(9, 16):
                        state = blocks[x, floor + z - 3, z]
                        self.assertTrue(state["id"].endswith("_stairs"))
                        self.assertEqual(state["properties"]["facing"], "south")
                self.assertEqual(set(record["containers"]), {"offering_chest"})
                self.assertNotIn("minecraft:ender_chest", {state["id"] for state in root["palette"]})

    def test_abandoned_processors_cannot_change_altar_roof_floor_or_clearance(self):
        for resource, root in self.roots.items():
            record = self.manifest["roots"][resource]
            reference = record["processors"]
            processors = self.manifest["processor_lists"][reference] if isinstance(reference, str) else reference
            with self.subTest(resource=resource):
                temples.validate_processors(root, record, processors, self.manifest["processor_tags"])

    def test_roads_face_outward_and_all_connector_metadata_survives_expansion(self):
        for resource, record in self.manifest["roots"].items():
            with self.subTest(resource=resource):
                source = record["source_jigsaws"]
                moves = {adjustment["index"]: adjustment for adjustment in record["connector_adjustments"]}
                for index, (original, authored) in enumerate(zip(source, record["jigsaws"])):
                    self.assertEqual(original["nbt"], authored["nbt"])
                    self.assertEqual(original["state"], authored["state"])
                    if original["nbt"]["pool"].endswith("/streets"):
                        x, y, z = authored["pos"]
                        facing = authored["state"]["properties"]["orientation"].split("_")[0]
                        self.assertEqual(y, original["pos"][1])
                        self.assertTrue({"west": x == 0, "east": x == 24,
                                         "north": z == 0, "south": z == 24}[facing])
                    if original["pos"] != authored["pos"]:
                        self.assertEqual(moves[index]["from"], original["pos"])
                        self.assertEqual(moves[index]["to"], authored["pos"])

    def test_pack_contains_only_mandatory_roots_and_unchanged_selection_contract(self):
        report = temples.validate_pack(PACK)
        self.assertEqual(report["roots"], 32)
        self.assertEqual(report["rotations"], 128)
        self.assertEqual(report["styles"], {"plains": 8, "desert": 6, "savanna": 8, "snowy": 6, "taiga": 4})

    def test_missing_rare_abandoned_root_is_rejected(self):
        resource = next(r for r in self.roots if "/zombie/" in r)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pack"
            shutil.copytree(PACK, output)
            (output / temples.resource_path(resource)).unlink()
            with self.assertRaises(ValueError):
                temples.validate_pack(output)

    def test_obstructed_or_implicit_air_entry_is_rejected(self):
        for defect in ("solid", "missing"):
            root, record = self.first()
            with self.subTest(defect=defect):
                if defect == "solid":
                    self.change_block(root, record["entry"], "minecraft:smooth_stone")
                else:
                    root["blocks"][:] = [b for b in root["blocks"] if list(b["pos"]) != record["entry"]]
                with self.assertRaises(ValueError):
                    temples.validate_root(root, record)

    def test_damaged_architecture_floor_altar_and_clearance_are_rejected(self):
        root, record = self.first()
        floor = record["floor_y"]
        positions = [[5, record["roof_y"], 12], [5, floor + 6, 14],
                     [6, floor, 13], record["altar"]["base"],
                     record["altar"]["approach"], [12, floor + 5, 16],
                     [12, floor + 2, 5], [4, floor + 12, 7]]
        for position in positions:
            damaged = copy.deepcopy(root)
            old = temples.block_map(root)[tuple(position)]["id"]
            self.change_block(damaged, position, "minecraft:smooth_stone" if old == "minecraft:air" else "minecraft:air")
            with self.subTest(position=position), self.assertRaises(ValueError):
                temples.validate_root(damaged, record)
        damaged = copy.deepcopy(root)
        self.change_block(damaged, [0, floor, 0], temples.ALTAR_BASE)
        with self.assertRaises(ValueError):
            temples.validate_root(damaged, record)

    def test_stair_access_does_not_assume_players_can_jump_up_a_wall(self):
        root, record = self.first()
        blocks = temples.block_map(root)
        start = record["altar"]["approach"]
        road = next(j["pos"] for j in record["jigsaws"] if j["nbt"]["pool"].endswith("/streets"))
        self.assertIn(tuple(road), temples.reachable(blocks, start))
        for defect in ("missing", "reversed", "full_cube"):
            changed = copy.deepcopy(blocks)
            for x in range(9, 16):
                p = (x, record["floor_y"] + 2, 5)
                if defect == "reversed":
                    changed[p]["properties"]["facing"] = "north"
                else:
                    changed[p] = {"id": "minecraft:air" if defect == "missing" else "minecraft:sandstone"}
            with self.subTest(defect=defect):
                self.assertNotIn(tuple(road), temples.reachable(changed, start))

    def test_preserved_road_can_still_be_obstructed_and_is_rejected(self):
        root, record = self.first()
        road = next(j for j in record["jigsaws"] if j["nbt"]["pool"].endswith("/streets"))
        x, y, z = road["pos"]
        for px, pz in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)):
            if 0 <= px < root["size"][0] and 0 <= pz < root["size"][2]:
                for height in range(y, y + 3):
                    self.change_block(root, [px, height, pz], "minecraft:smooth_stone")
        with self.assertRaises(ValueError):
            temples.validate_root(root, record)

    def test_trusted_jigsaw_changes_are_rejected(self):
        for defect in ("position", "metadata", "orientation"):
            root, record = self.first()
            road = next(b for b in temples.joints(root) if temples.is_road(b))
            if defect == "position":
                road["pos"][0] += 1
            elif defect == "metadata":
                road["nbt"]["pool"] = "minecraft:empty"
            else:
                root["palette"][road["state"]]["properties"]["orientation"] = "up_north"
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                temples.validate_root(root, record)

    def test_processor_that_can_damage_altar_is_rejected_without_random_sampling(self):
        root, record = self.first()
        processor = {"processors": [{"processor_type": "minecraft:rule", "rules": [{
            "input_predicate": {"predicate_type": "minecraft:random_block_match", "block": temples.ALTAR_BASE,
                                "probability": 0.00001},
            "location_predicate": {"predicate_type": "minecraft:always_true"},
            "output_state": "minecraft:cobweb"}]}]}
        with self.assertRaises(ValueError):
            temples.validate_processors(root, record, processor, {})

    def test_real_generated_nbt_has_only_approved_container_payloads_and_is_stable(self):
        for resource, root in self.roots.items():
            with self.subTest(resource=resource):
                record = self.manifest["roots"][resource]
                self.assertFalse(root["entities"])
                payloads = []
                for block in root["blocks"]:
                    if "nbt" not in block:
                        continue
                    block_id = root["palette"][block["state"]]["id"]
                    self.assertIn(block_id, {"minecraft:jigsaw", *temples.CONTAINER_IDS.values()})
                    if block_id != "minecraft:jigsaw":
                        payloads.append((tuple(block["pos"]), block_id, block["nbt"]))
                self.assertEqual({item[0] for item in payloads},
                                 {tuple(position) for position in record["containers"].values()})
                self.assertEqual({item[1] for item in payloads}, {"minecraft:chest"})
                self.assertNotIn("minecraft:ender_chest", {state["id"] for state in root["palette"]})
                offering = next(item for item in payloads if item[1] == "minecraft:chest")
                self.assertEqual(len(offering[2]["Items"]), 0)
                self.assertNotIn("LootTable", offering[2])
                payload = (PACK / temples.resource_path(resource)).read_bytes()
                self.assertEqual(nbt.dumps(root), payload)


if __name__ == "__main__":
    unittest.main()
