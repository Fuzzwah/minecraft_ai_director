import copy
import hashlib
import json
import unittest

from tools import keeper_patches as patches
from tools import nbt
from tools import village_temples as temples

import keeper
from tests.test_keeper import TempleWorld, block

class KeeperPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((temples.DEFAULT_OUTPUT / "manifest.json").read_bytes())
        cls.definitions = json.loads(patches.DEFAULT_DEFINITIONS.read_bytes())
        cls.resource = "minecraft:village/plains/town_centers/plains_fountain_01"
        cls.root = nbt.loads((temples.DEFAULT_OUTPUT / temples.resource_path(cls.resource)).read_bytes())
        cls.record = cls.manifest["roots"][cls.resource]
        cls.definition = cls.definitions["roots"][cls.resource]

    def blocks_at(self, rank, turns=0):
        blocks = {temples.rotate(p, self.root["size"], turns): temples.rotated_state(s, turns)
                  for p, s in temples.block_map(self.root).items()}
        definition = patches.rotated_definition(self.definition, turns)
        for stage in range(2, rank + 1):
            for cell in definition["milestones"][str(stage)]:
                blocks[tuple(cell["pos"])] = cell["target"]
        return blocks

    def test_real_root_matrix_all_prefixes_is_read_only(self):
        paths = [patches.DEFAULT_DEFINITIONS, temples.DEFAULT_OUTPUT / "manifest.json"] + list(
            (temples.DEFAULT_OUTPUT / "data").rglob("*"))
        before = {p: hashlib.sha256(p.read_bytes()).digest() for p in paths if p.is_file()}
        result = patches.check_patches()
        self.assertEqual(result["roots"], 32)
        self.assertEqual(result["rotations"], 128)
        self.assertEqual(result["cumulative_states"], 640)
        self.assertEqual(result["prefixes"], 8448)
        for path, digest in before.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), digest, str(path))
        self.assertEqual({r["style"] for r in self.manifest["roots"].values()}, set(temples.STYLES))
        for style in temples.STYLES:
            roots = [r for r, v in self.manifest["roots"].items() if v["style"] == style]
            self.assertTrue(any("/zombie/" in r for r in roots))
            self.assertTrue(any("/zombie/" not in r for r in roots))

    def test_golems_have_paired_feet_shoulders_face_nose_and_antenna(self):
        # Behavioral silhouette assertions are grounded in the real chest/altar
        # geometry, not a second copy of the transition list.
        chest = self.record["containers"]["offering_chest"]
        for turns in range(4):
            blocks = self.blocks_at(3, turns)
            for center in (chest[0] - 4, chest[0] + 4):
                for dx in (-1, 1):
                    foot = temples.rotate((center + dx, chest[1], chest[2]), self.root["size"], turns)
                    leg = temples.rotate((center + dx, chest[1] + 1, chest[2]), self.root["size"], turns)
                    shoulder = temples.rotate((center + dx, chest[1] + 2, chest[2]), self.root["size"], turns)
                    self.assertEqual(blocks[foot]["id"], "minecraft:waxed_cut_copper_stairs")
                    self.assertEqual(blocks[foot]["properties"]["facing"], ("north", "east", "south", "west")[turns])
                    self.assertEqual(blocks[leg]["id"], "minecraft:waxed_cut_copper")
                    self.assertEqual(blocks[shoulder]["id"], "minecraft:waxed_cut_copper_stairs")
                    inward = ("east", "south", "west", "north")[turns] if dx == -1 else (
                        "west", "north", "east", "south")[turns]
                    self.assertEqual(blocks[shoulder]["properties"]["facing"], inward)
                face = temples.rotate((center, chest[1] + 3, chest[2]), self.root["size"], turns)
                nose = temples.rotate((center, chest[1] + 3, chest[2] - 1), self.root["size"], turns)
                antenna = temples.rotate((center, chest[1] + 4, chest[2]), self.root["size"], turns)
                self.assertEqual(blocks[face]["id"], "minecraft:waxed_chiseled_copper")
                for p in (nose, antenna):
                    self.assertEqual(blocks[p]["id"], "minecraft:waxed_cut_copper_slab")
                    self.assertEqual(blocks[p]["properties"]["type"], "bottom")

    def test_intended_idol_and_sun_changes_preserve_stone_and_old_lights(self):
        floor = self.record["floor_y"]
        original = temples.block_map(self.root)
        final = self.blocks_at(5)
        for y in range(4, 11):
            self.assertEqual(final[(12, floor + y, 19)], original[(12, floor + y, 19)])
        for cell in self.record["features"]["lighting"]:
            self.assertEqual(final[tuple(cell["pos"])], cell["state"])
        self.assertEqual(final[(11, floor + 5, 19)]["id"], "minecraft:chiseled_sandstone")
        self.assertEqual(final[(11, floor + 8, 19)]["id"], "minecraft:waxed_cut_copper")
        self.assertEqual(final[(11, floor + 9, 19)]["id"], "minecraft:gold_block")
        self.assertEqual(final[(11, floor + 14, 7)]["id"], "minecraft:glowstone")
        # Baseline feature equality is deliberately not an evolution validator.
        patches.validate_geometry(self.root, self.record, self.definition, final)
        chest = tuple(self.record["containers"]["offering_chest"])
        self.assertEqual(final[chest], original[chest])
        self.assertEqual(final[(chest[0], chest[1] + 1, chest[2])], {"id": "minecraft:air"})
        payloads = [b for b in self.root["blocks"] if "nbt" in b and b["nbt"].get("id") == "minecraft:chest"]
        self.assertEqual(len(payloads), 1)
        self.assertEqual(list(payloads[0]["nbt"]["Items"]), [])

    def test_obstructed_entrance_and_chest_lid_are_rejected(self):
        for position in (self.record["entry"], [self.record["containers"]["offering_chest"][0],
                         self.record["containers"]["offering_chest"][1] + 1,
                         self.record["containers"]["offering_chest"][2]]):
            blocks = self.blocks_at(5)
            blocks[tuple(position)] = {"id": "minecraft:gold_block"}
            with self.subTest(position=position), self.assertRaisesRegex(ValueError, "access|lid"):
                patches.validate_geometry(self.root, self.record, self.definition, blocks)

    def test_missing_chain_support_rejects_completed_geometry(self):
        blocks = self.blocks_at(5)
        blocks[(9, self.record["floor_y"] + 10, 14)] = {"id": "minecraft:air"}
        with self.assertRaisesRegex(ValueError, "Unsupported hanging"):
            patches.validate_geometry(self.root, self.record, self.definition, blocks)

    def test_golem_without_its_feet_is_an_unsupported_component(self):
        blocks = self.blocks_at(3)
        chest = self.record["containers"]["offering_chest"]
        for x in (chest[0] - 5, chest[0] - 3, chest[0] + 3, chest[0] + 5):
            blocks[(x, chest[1], chest[2])] = {"id": "minecraft:air"}
        with self.assertRaisesRegex(ValueError, "Unsupported sculpture"):
            patches.validate_geometry(self.root, self.record, self.definition, blocks)

    def test_untouched_generated_road_fringe_preserves_enrollment_but_not_obstructions(self):
        # Same-seed untouched Java 26.3 generation produced these four cells,
        # unlike raw template placement. Streets/terrain own this outer fringe.
        generated = {(1, 0, 12): {"id": "minecraft:dirt_path"},
                     (2, 0, 11): {"id": "minecraft:grass_block", "properties": {"snowy": "false"}},
                     (2, 0, 12): {"id": "minecraft:dirt_path"},
                     (2, 1, 11): {"id": "minecraft:short_grass"}}
        minimum = (100, 60, 100)
        for turns, facing in enumerate(("north", "east", "south", "west")):
            with self.subTest(facing=facing):
                world = TempleWorld()
                for pos, state in {**temples.block_map(self.root), **generated}.items():
                    actual = tuple(a + b for a, b in zip(
                        temples.rotate(pos, self.root["size"], turns), minimum))
                    world.blocks[actual] = block(temples.rotated_state(state, turns))
                chest = [a + b for a, b in zip(
                    temples.rotate(self.definition["chest"], self.root["size"], turns), minimum)]
                controller = keeper.KeeperController(
                    patches.DEFAULT_DEFINITIONS, "generated-fringe-fixture", self.resource,
                    minimum, facing, chest, world.command, lambda: None)
                records = {}
                identity = controller.enroll(records)
                self.assertEqual(records[identity]["progression"]["credited_quest_ids"], [])
                for ordinal in range(3):
                    keeper.credit(records[identity], f"offering-{ordinal}")
                self.assertEqual(controller.tick(records)[0]["installed_rank"], 2)
                for pos, state in generated.items():
                    actual = tuple(a + b for a, b in zip(
                        temples.rotate(pos, self.root["size"], turns), minimum))
                    self.assertEqual(world.blocks[actual], block(state))
                entry = self.definition["entry"]
                for local in (entry, [entry[0], entry[1] - 1, entry[2]],
                              [self.definition["chest"][0], self.definition["chest"][1] + 1,
                               self.definition["chest"][2]]):
                    actual = tuple(a + b for a, b in zip(
                        temples.rotate(local, self.root["size"], turns), minimum))
                    prior = world.blocks[actual]
                    world.blocks[actual] = "minecraft:air" if local[1] < entry[1] else "minecraft:chest"
                    with self.assertRaises(keeper.KeeperError):
                        controller.verify_source(records)
                    world.blocks[actual] = prior


    def test_skipped_ancillary_jigsaws_cannot_be_literal_world_probes(self):
        ancillary_seen = False
        for resource, record in self.manifest["roots"].items():
            root = nbt.loads((temples.DEFAULT_OUTPUT / temples.resource_path(resource)).read_bytes())
            definition = self.definitions["roots"][resource]
            skipped = {p for p, state in temples.block_map(root).items()
                       if state["id"] == "minecraft:structure_void"}
            probes = {tuple(cell["pos"]) for group in ("invariants", "access", "mutable_baseline")
                      for cell in definition[group]}
            self.assertFalse(skipped & probes, resource)
            interior = [p for p in skipped if 0 < p[0] < root["size"][0] - 1
                        and 0 < p[2] < root["size"][2] - 1]
            if interior and not ancillary_seen:
                ancillary_seen = True
                invalid = copy.deepcopy(definition)
                invalid["access"].append({"pos": list(interior[0]), "state": {"id": "minecraft:structure_void"}})
                with self.assertRaises(ValueError):
                    patches.validate_definition(root, record, invalid)
        self.assertTrue(ancillary_seen)

    def test_standing_lantern_before_pedestal_rejects_intermediate_prefix(self):
        definition = copy.deepcopy(self.definition)
        stage = definition["milestones"]["2"]
        stage[0], stage[1] = stage[1], stage[0]
        with self.assertRaisesRegex(ValueError, "Unsupported standing"):
            patches.validate_definition(self.root, self.record, definition)

    def test_bottom_up_chain_dispatch_rejects_intermediate_prefix(self):
        definition = copy.deepcopy(self.definition)
        stage = definition["milestones"]["5"]
        stage[0], stage[2] = stage[2], stage[0]
        with self.assertRaisesRegex(ValueError, "Unsupported hanging"):
            patches.validate_definition(self.root, self.record, definition)

    def test_unrotated_stair_states_in_rotated_map_are_rejected(self):
        blocks = self.blocks_at(3, 1)
        for cell in self.record["features"]["approach_steps"]:
            p = temples.rotate(cell["pos"], self.root["size"], 1)
            blocks[p] = copy.deepcopy(cell["state"])
        with self.assertRaisesRegex(ValueError, "access|Unsupported|obstructed"):
            patches.validate_geometry(self.root, self.record, self.definition, blocks, turns=1)

    def test_wrong_predecessor_and_incomplete_state_are_rejected(self):
        wrong = copy.deepcopy(self.definition)
        wrong["milestones"]["2"][0]["expected"] = {"id": "minecraft:gold_block"}
        with self.assertRaisesRegex(ValueError, "predecessor"):
            patches.validate_definition(self.root, self.record, wrong)
        wrong = copy.deepcopy(self.definition)
        del wrong["milestones"]["3"][0]["target"]["properties"]["waterlogged"]
        with self.assertRaisesRegex(ValueError, "properties"):
            patches.validate_definition(self.root, self.record, wrong)

    def test_sensitive_payload_access_and_out_of_bounds_targets_are_rejected(self):
        cases = []
        wrong = copy.deepcopy(self.definition)
        wrong["milestones"]["2"][0]["target"] = {"id": "minecraft:chest"}
        cases.append((wrong, "sensitive"))
        wrong = copy.deepcopy(self.definition)
        wrong["milestones"]["2"][0]["target"]["nbt"] = {"Items": []}
        cases.append((wrong, "sensitive"))
        wrong = copy.deepcopy(self.definition)
        wrong["milestones"]["2"][0]["pos"][0] = self.root["size"][0]
        cases.append((wrong, "bounds"))
        wrong = copy.deepcopy(self.definition)
        wrong["milestones"]["2"][0]["pos"] = list(self.record["containers"]["offering_chest"])
        cases.append((wrong, "forbidden"))
        for definition, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                patches.validate_definition(self.root, self.record, definition)

    def test_processor_changed_air_is_not_enrollable(self):
        processor = {"processors": [{"processor_type": "minecraft:rule", "rules": [{
            "input_predicate": {"predicate_type": "minecraft:block_match", "block": "minecraft:air"},
            "location_predicate": {"predicate_type": "minecraft:always_true"},
            "output_state": "minecraft:cobweb"}]}]}
        with self.assertRaisesRegex(ValueError, "Processor-unstable"):
            patches.validate_definition(self.root, self.record, self.definition, processors=(processor,))


if __name__ == "__main__":
    unittest.main()
