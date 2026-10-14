"""Observable Keeper safety/progression tests; no authoring tooling at runtime."""
import copy
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

import keeper

ROOT = Path(__file__).resolve().parents[1]
AIR = {"id": "minecraft:air"}
GOLD = {"id": "minecraft:gold_block"}
CHEST = {"id": "minecraft:chest", "properties": {"facing": "north", "type": "single", "waterlogged": "false"}}


def block(state):
    properties = state.get("properties", {})
    return state["id"] + ("[" + ",".join(f"{k}={v}" for k, v in sorted(properties.items())) + "]" if properties else "")


def rotate(pos, size, facing):
    x, y, z = pos
    w, _, d = size
    return {"north": (x, y, z), "east": (d - 1 - z, y, x),
            "south": (w - 1 - x, y, d - 1 - z), "west": (z, y, w - 1 - x)}[facing]


def manifest(stage_size=17):
    positions = [[x, 2, z] for z in range(2, 8) for x in range(2, 8)][:stage_size + 3]
    stages = {"2": [{"pos": p, "expected": copy.deepcopy(AIR), "target": copy.deepcopy(GOLD)} for p in positions[:stage_size]]}
    for milestone, pos in zip((3, 4, 5), positions[stage_size:]):
        stages[str(milestone)] = [{"pos": pos, "expected": copy.deepcopy(AIR), "target": {"id": "minecraft:glowstone"}}]
    definition = {"size": [9, 7, 9], "floor_y": 0, "chest": [1, 2, 1], "entry": [1, 2, 0],
                  "mutable_baseline": [{"pos": p, "state": copy.deepcopy(AIR)} for p in positions],
                  "invariants": [{"pos": [1, 2, 1], "state": copy.deepcopy(CHEST)},
                                 {"pos": [0, 2, 1], "state": {"id": "minecraft:sandstone"}}],
                  "access": [{"pos": [1, 3, 1], "state": copy.deepcopy(AIR)},
                             {"pos": [1, 2, 0], "state": copy.deepcopy(AIR)},
                             {"pos": [1, 3, 0], "state": copy.deepcopy(AIR)},
                             {"pos": [1, 1, 0], "state": {"id": "minecraft:smooth_stone"}}],
                  "milestones": stages}
    return {"version": 1, "minecraft_version": "26.3", "roots": {"fixture:temple": definition}}


class TempleWorld:
    """Small deterministic adapter using observed 26.3 list/setblock replies."""

    def __init__(self):
        self.blocks = {}
        self.commands = []
        self.mutations = []
        self.loaded = True
        self.unloaded_chunks = set()
        self.player = False
        self.before_dispatch = None
        self.after_dispatch = None
        self.on_probe = None
        self.reply = None
        self.lost_reply = False

    def place(self, definition, minimum, facing="north"):
        turns = ("north", "east", "south", "west").index(facing)
        for name in ("mutable_baseline", "invariants", "access"):
            for cell in definition[name]:
                pos = tuple(a + b for a, b in zip(rotate(cell["pos"], definition["size"], facing), minimum))
                state = copy.deepcopy(cell["state"])
                properties = state.get("properties", {})
                if "facing" in properties:
                    directions = ("north", "east", "south", "west")
                    properties["facing"] = directions[(directions.index(properties["facing"]) + turns) % 4]
                if turns % 2 and properties.get("axis") in ("x", "z"):
                    properties["axis"] = "z" if properties["axis"] == "x" else "x"
                self.blocks[pos] = block(state)

    def command(self, command):
        self.commands.append(command)
        mutation = re.search(r" run setblock (-?\d+) (-?\d+) (-?\d+) (\S+) replace$", command)
        if mutation and self.before_dispatch:
            self.before_dispatch(command)
        if not mutation and self.on_probe:
            self.on_probe(command)
        for x, _, z in re.findall(r"if loaded (-?\d+) (-?\d+) (-?\d+)", command):
            if not self.loaded or (int(x) // 16, int(z) // 16) in self.unloaded_chunks:
                return ""
        if "unless entity @a[" in command and self.player:
            return ""
        for x, y, z, state in re.findall(r"if block (-?\d+) (-?\d+) (-?\d+) (\S+)", command):
            if self.blocks.get((int(x), int(y), int(z)), "minecraft:air") != state:
                return ""
        if mutation:
            x, y, z, state = mutation.groups()
            pos = (int(x), int(y), int(z))
            self.blocks[pos] = state
            self.mutations.append((pos, state, command))
            if self.after_dispatch:
                self.after_dispatch(command)
            if self.lost_reply:
                raise OSError("Injected lost setblock reply")
            return self.reply if self.reply is not None else f"Changed the block at {x}, {y}, {z}"
        if command.endswith(" run list"):
            return "There are 0 of a max of 20 players online: "
        raise AssertionError("Unexpected Keeper command: " + command)


class KeeperTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "keeper.json"
        self.manifest = manifest()
        self.path.write_text(json.dumps(self.manifest))
        self.definition = self.manifest["roots"]["fixture:temple"]
        self.minimum = (10, 64, 10)
        self.world = TempleWorld()
        self.world.place(self.definition, self.minimum)
        self.keepers = {}
        self.saves = []
        self.fail_save = False
        self.controller = self.make_controller()

    def make_controller(self, **changes):
        values = {"definitions_path": self.path, "world_id": "fixture-world", "resource": "fixture:temple",
                  "minimum": self.minimum, "facing": "north", "offering_chest": (11, 66, 11),
                  "command": self.world.command, "persist": self.save}
        values.update(changes)
        return keeper.KeeperController(**values)

    def save(self):
        if self.fail_save:
            raise OSError("Injected save failure")
        self.saves.append(copy.deepcopy(self.keepers))

    def enroll(self, count=0):
        identity = self.controller.enroll(self.keepers)
        record = self.keepers[identity]
        for i in range(count):
            keeper.credit(record, f"quest-{i}")
        return record

    def target(self, index=0, milestone="2"):
        local = self.definition["milestones"][milestone][index]["pos"]
        return tuple(a + b for a, b in zip(local, self.minimum))

    def test_rank_boundaries_and_complete_policy(self):
        record = self.enroll()
        expected = {0: 1, 2: 1, 3: 2, 9: 2, 10: 3, 24: 3, 25: 4, 49: 4, 50: 5, 75: 5}
        for count in range(76):
            if count in expected:
                self.assertEqual(keeper.rank(record), expected[count])
            if count < 75:
                self.assertTrue(keeper.credit(record, f"boundary-{count}"))
        self.assertEqual(len(record["progression"]["credited_quest_ids"]), 75)
        self.assertEqual(keeper.policy(3), {"name": "Warden", "minimum": 10, "bonus_points": 10,
                                          "haste_seconds": 60, "resistance_seconds": 30})
        for bad in (0, 6, True, "3", None):
            with self.subTest(bad=bad), self.assertRaises(keeper.KeeperError):
                keeper.policy(bad)

    def test_credit_is_once_per_record_and_independent(self):
        a = self.enroll(2)
        b = copy.deepcopy(a)
        b["binding"]["minimum"][0] += 100
        b["binding"]["chest"][0] += 100
        b["progression"]["credited_quest_ids"] = []
        b["evolution"]["enabled"] = False
        identity = keeper.keeper_id(b["binding"])
        self.keepers[identity] = b
        self.assertTrue(keeper.credit(a, "personal"))
        self.assertFalse(keeper.credit(a, "personal"))
        self.assertTrue(keeper.credit(a, "communal"))
        self.assertEqual(keeper.rank(a), 2)
        self.assertEqual(keeper.rank(b), 1)
        self.assertEqual(b["progression"]["credited_quest_ids"], [])
        keeper.validate_records(json.loads(json.dumps(self.keepers)))

    def test_identity_uses_only_world_dimension_and_original_minimum(self):
        binding = copy.deepcopy(self.controller.binding)
        expected = "keeper:" + hashlib.sha256(json.dumps(["fixture-world", "minecraft:overworld", 10, 64, 10],
                                                         separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        self.assertEqual(keeper.keeper_id(binding), expected)
        binding.update(resource="fixture:other", facing="south", definition_digest="a" * 64)
        self.assertEqual(keeper.keeper_id(binding), expected)
        binding["minimum"][0] += 1
        self.assertNotEqual(keeper.keeper_id(binding), expected)

    def test_record_validation_fails_closed(self):
        self.enroll()
        corruptions = (
            lambda r: r.update(version=2),
            lambda r: r.update(extra=True),
            lambda r: r["binding"].update(minimum=[True, 64, 10]),
            lambda r: r["binding"].update(dimension="minecraft:the_nether"),
            lambda r: r["progression"].update(credited_quest_ids=["same", "same"]),
            lambda r: r["progression"].update(last_announced_rank=2),
            lambda r: r["evolution"].update(installed_rank=2),
            lambda r: r["evolution"].update(enabled=1),
            lambda r: r["evolution"].update(upgrade={"version": 2}),
        )
        for corruption in corruptions:
            values = copy.deepcopy(self.keepers)
            corruption(values[self.controller.keeper_id])
            with self.subTest(corruption=corruption), self.assertRaises(keeper.KeeperError):
                keeper.validate_records(values)
        with self.assertRaises(keeper.KeeperError):
            keeper.validate_records({"wrong-id": next(iter(self.keepers.values()))})
        with self.assertRaises(keeper.KeeperError):
            keeper.rank({"progression": []})

    def test_duplicate_manifest_keys_and_future_version_rejected_before_probes(self):
        for content in ('{"version":1,"version":1}', json.dumps({**self.manifest, "version": 2})):
            self.path.write_text(content)
            with self.assertRaises(keeper.KeeperError):
                self.make_controller()
        self.assertEqual(self.world.commands, [])

    def test_manifest_forbids_sensitive_unknown_incomplete_and_no_touch_states(self):
        corruptions = (
            lambda d: d["milestones"]["2"][0].update(target=copy.deepcopy(CHEST)),
            lambda d: d["milestones"]["2"][0].update(target={"id": "minecraft:command_block"}),
            lambda d: d["milestones"]["2"][0].update(target={"id": "minecraft:lantern"}),
            lambda d: d["milestones"]["2"][0].update(target=copy.deepcopy(AIR)),
            lambda d: d["milestones"]["2"][0].update(pos=d["chest"]),
            lambda d: d["mutable_baseline"][0].update(pos=d["access"][0]["pos"]),
            lambda d: d["milestones"]["2"][0].update(pos=[999, 2, 2]),
            lambda d: d["milestones"]["3"][0].update(expected=copy.deepcopy(GOLD)),
            lambda d: d["invariants"][0].update(state={**copy.deepcopy(CHEST), "nbt": {"Items": []}}),
        )
        for corruption in corruptions:
            values = copy.deepcopy(self.manifest)
            corruption(values["roots"]["fixture:temple"])
            self.path.write_text(json.dumps(values))
            with self.subTest(corruption=corruption), self.assertRaises(keeper.KeeperError):
                self.make_controller()
        self.assertEqual(self.world.mutations, [])

    def test_chest_transform_and_state_rotation_in_all_facings(self):
        for facing in ("north", "east", "south", "west"):
            world = TempleWorld()
            world.place(self.definition, self.minimum, facing)
            chest = tuple(a + b for a, b in zip(rotate(self.definition["chest"], self.definition["size"], facing), self.minimum))
            controller = self.make_controller(facing=facing, offering_chest=chest, command=world.command, persist=lambda: None)
            records = {}
            identity = controller.enroll(records)
            controller.verify_source(records)
            self.assertEqual(records[identity]["binding"]["chest"], list(chest))
            self.assertEqual(records[identity]["evolution"]["installed_rank"], 1)
        with self.assertRaises(keeper.KeeperError):
            self.make_controller(offering_chest=(10, 64, 10))

    def test_binding_digest_conflict_and_world_rebind_never_reset_progress(self):
        record = self.enroll(3)
        original = copy.deepcopy(self.keepers)
        changed_world = self.make_controller(world_id="replacement-world")
        with self.assertRaises(keeper.KeeperError):
            changed_world.enroll(self.keepers)
        changed = copy.deepcopy(self.manifest)
        changed["roots"]["fixture:temple"]["invariants"][1]["state"] = copy.deepcopy(GOLD)
        self.path.write_text(json.dumps(changed))
        changed_definition = self.make_controller()
        self.assertEqual(changed_definition.keeper_id, self.controller.keeper_id)
        with self.assertRaises(keeper.KeeperError):
            changed_definition.enroll(self.keepers)
        self.assertEqual(self.keepers, original)
        self.assertEqual(keeper.rank(record), 2)
        self.assertEqual(self.world.mutations, [])

    def test_new_registration_requires_baseline_but_existing_source_does_not(self):
        self.world.blocks[self.target()] = "minecraft:barrel"
        with self.assertRaises(keeper.KeeperError):
            self.controller.enroll(self.keepers)
        self.assertEqual(self.keepers, {})
        self.world.blocks[self.target()] = "minecraft:air"
        record = self.enroll(3)
        self.world.blocks[self.target()] = "minecraft:barrel"
        self.controller.enroll(self.keepers)
        self.controller.verify_source(self.keepers)
        events = self.controller.tick(self.keepers)
        self.assertTrue(events[-1]["blocked"])
        self.assertTrue(record["evolution"]["last_error"])
        self.assertTrue(keeper.credit(record, "independent-safe-quest"))
        self.assertEqual(self.world.blocks[self.target()], "minecraft:barrel")
        self.assertEqual(self.world.mutations, [])

    def test_source_access_failures_are_not_ordinary_decoration_events(self):
        record = self.enroll(3)
        self.world.blocks[(11, 67, 11)] = "minecraft:stone_bricks"
        with self.assertRaises(keeper.KeeperError):
            self.controller.verify_source(self.keepers)
        with self.assertRaises(keeper.KeeperError):
            self.controller.tick(self.keepers)
        self.assertEqual(record["evolution"]["installed_rank"], 1)
        self.assertEqual(self.world.mutations, [])

    def test_max_sixteen_mutations_and_resume_only_unsent_suffix(self):
        record = self.enroll(3)
        self.controller.tick(self.keepers)
        upgrade = record["evolution"]["upgrade"]
        self.assertEqual(len(self.world.mutations), 16)
        self.assertEqual(upgrade["step"], 16)
        self.assertFalse(upgrade["uncertain"])
        self.assertEqual(record["evolution"]["installed_rank"], 1)
        self.keepers = json.loads(json.dumps(self.saves[-1]))
        restarted = self.make_controller()
        restarted.enroll(self.keepers)
        self.assertEqual(restarted.tick(self.keepers)[-1]["installed_rank"], 2)
        self.assertEqual(len(self.world.mutations), 17)
        self.assertEqual(len({pos for pos, _, _ in self.world.mutations}), 17)
        self.assertIsNone(self.keepers[restarted.keeper_id]["evolution"]["upgrade"])
        self.assertEqual(restarted.tick(self.keepers), [])

    def test_stage_order_cannot_skip_to_highest_earned_rank(self):
        record = self.enroll(50)
        events = []
        while record["evolution"]["installed_rank"] < 5:
            before = len(self.world.mutations)
            events.extend(self.controller.tick(self.keepers))
            self.assertLessEqual(len(self.world.mutations) - before, 16)
        self.assertEqual([e["installed_rank"] for e in events], [2, 3, 4, 5])
        self.assertEqual(len(self.world.mutations), 20)
        self.assertEqual(keeper.rank(record), 5)

    def test_saved_snapshot_tampering_fails_closed(self):
        self.enroll(3)
        self.controller.tick(self.keepers)
        changes = (
            lambda u: u.update(step=18),
            lambda u: u.update(target_rank=3),
            lambda u: u["binding"].update(facing="east"),
            lambda u: u["transitions"][0].update(target={"id": "minecraft:glowstone"}),
            lambda u: u["definition"]["milestones"]["2"][0].update(target={"id": "minecraft:glowstone"}),
            lambda u: u.update(uncertain=True, status="ready"),
        )
        for change in changes:
            records = copy.deepcopy(self.keepers)
            change(records[self.controller.keeper_id]["evolution"]["upgrade"])
            before = len(self.world.mutations)
            with self.subTest(change=change), self.assertRaises(keeper.KeeperError):
                self.controller.tick(records)
            self.assertEqual(len(self.world.mutations), before)

    def test_resume_checks_acknowledged_prefix_and_all_remaining_states(self):
        record = self.enroll(3)
        self.controller.tick(self.keepers)
        first = self.target()
        self.world.blocks[first] = "minecraft:barrel"
        self.assertTrue(self.controller.tick(self.keepers)[-1]["blocked"])
        self.assertEqual(len(self.world.mutations), 16)
        self.world.blocks[first] = "minecraft:gold_block"
        remaining = self.target(16)
        self.world.blocks[remaining] = "minecraft:chest"
        self.assertTrue(self.controller.tick(self.keepers)[-1]["blocked"])
        self.assertEqual(record["evolution"]["upgrade"]["step"], 16)
        self.assertEqual(len(self.world.mutations), 16)

    def test_lost_reply_is_durable_uncertain_and_never_replayed_after_load(self):
        self.enroll(3)
        self.world.lost_reply = True
        with self.assertRaises(keeper.KeeperUncertain):
            self.controller.tick(self.keepers)
        saved = self.saves[-1]
        upgrade = saved[self.controller.keeper_id]["evolution"]["upgrade"]
        self.assertTrue(upgrade["uncertain"])
        self.assertEqual(upgrade["step"], 0)
        self.assertEqual(self.world.blocks[self.target()], "minecraft:gold_block")
        self.keepers = json.loads(json.dumps(saved))
        self.world.lost_reply = False
        restarted = self.make_controller()
        for action in (restarted.enroll, restarted.verify_source, restarted.tick):
            with self.assertRaises(keeper.KeeperUncertain):
                action(self.keepers)
        self.assertEqual(len(self.world.mutations), 1)
        preview = restarted.preview(self.keepers)
        self.assertTrue(preview["uncertain"])
        self.assertEqual(len(preview["transitions"]), 17)
        self.assertEqual(preview["next_step"], 0)

    def test_uncertainty_is_saved_before_world_dispatch(self):
        self.enroll(3)
        observed = []

        def before(command):
            saved = self.saves[-1][self.controller.keeper_id]["evolution"]["upgrade"]
            observed.append((saved["step"], saved["uncertain"], saved["status"]))

        self.world.before_dispatch = before
        self.controller.tick(self.keepers)
        self.assertEqual(observed, [(step, True, "uncertain") for step in range(16)])

    def test_empty_generic_wrong_coordinate_and_wrong_state_acknowledgements_are_uncertain(self):
        for response in ("", "Success", "Changed the block at 999, 66, 12"):
            with self.subTest(response=response):
                self.keepers = {}
                self.saves = []
                self.world = TempleWorld()
                self.world.place(self.definition, self.minimum)
                self.controller = self.make_controller()
                self.enroll(3)
                self.world.reply = response
                with self.assertRaises(keeper.KeeperUncertain):
                    self.controller.tick(self.keepers)
                self.assertTrue(self.saves[-1][self.controller.keeper_id]["evolution"]["upgrade"]["uncertain"])
                self.assertEqual(self.keepers[self.controller.keeper_id]["evolution"]["installed_rank"], 1)
        self.keepers = {}
        self.world = TempleWorld()
        self.world.place(self.definition, self.minimum)
        self.controller = self.make_controller()
        self.enroll(3)
        self.world.after_dispatch = lambda _: self.world.blocks.update({self.target(): "minecraft:barrel"})
        with self.assertRaises(keeper.KeeperUncertain):
            self.controller.tick(self.keepers)

    def test_player_or_chunk_preflight_blocks_without_dispatch(self):
        self.enroll(3)
        self.world.player = True
        self.assertTrue(self.controller.tick(self.keepers)[-1]["blocked"])
        self.assertEqual(self.world.mutations, [])
        self.world.player = False
        # The temple spans two chunks; this one does not contain its source probes.
        self.world.unloaded_chunks.add((1, 1))
        self.assertTrue(self.controller.tick(self.keepers)[-1]["blocked"])
        self.assertEqual(self.world.mutations, [])
        self.world.unloaded_chunks.clear()
        self.controller.tick(self.keepers)
        for _, _, command in self.world.mutations:
            self.assertIn("execute in minecraft:overworld", command)
            self.assertIn("if loaded 0 64 0", command)
            self.assertIn("if loaded 16 64 16", command)
            self.assertIn("unless entity @a[x=10,y=64,z=10,dx=8,dy=6,dz=8]", command)
            self.assertIn("if block", command)

    def test_player_entering_or_chunk_unloading_at_dispatch_stays_uncertain(self):
        for setting in ("player", "chunk"):
            with self.subTest(setting=setting):
                self.keepers = {}
                self.saves = []
                self.world = TempleWorld()
                self.world.place(self.definition, self.minimum)
                self.controller = self.make_controller()
                self.enroll(3)
                if setting == "player":
                    self.world.before_dispatch = lambda _: setattr(self.world, "player", True)
                else:
                    self.world.before_dispatch = lambda _: self.world.unloaded_chunks.add((1, 1))
                with self.assertRaises(keeper.KeeperUncertain):
                    self.controller.tick(self.keepers)
                self.assertEqual(self.world.mutations, [])
                self.assertTrue(self.saves[-1][self.controller.keeper_id]["evolution"]["upgrade"]["uncertain"])

    def test_protected_regions_are_dimension_aware(self):
        self.enroll(3)
        region = {"min": {"x": 10, "y": 64, "z": 10}, "max": {"x": 18, "y": 70, "z": 18}}
        protected = self.make_controller(protected_regions=[region])
        self.assertTrue(protected.tick(self.keepers)[-1]["blocked"])
        self.assertEqual(self.world.mutations, [])
        other_dimension = self.make_controller(protected_regions=[{**region, "dimension": "minecraft:the_nether"}])
        other_dimension.tick(self.keepers)
        self.assertEqual(len(self.world.mutations), 16)

    def test_final_verification_preserves_all_acknowledged_progress_without_repair(self):
        record = self.enroll(3)
        self.controller.tick(self.keepers)
        edited = False

        def edit_at_final_probe(command):
            nonlocal edited
            upgrade = record["evolution"]["upgrade"]
            if not edited and upgrade and upgrade["step"] == 17 and not upgrade["uncertain"]:
                self.world.blocks[self.target()] = "minecraft:barrel"
                edited = True

        self.world.on_probe = edit_at_final_probe
        events = self.controller.tick(self.keepers)
        self.assertTrue(events[-1]["blocked"])
        self.assertEqual(record["evolution"]["installed_rank"], 1)
        self.assertEqual(record["evolution"]["upgrade"]["step"], 17)
        self.assertFalse(record["evolution"]["upgrade"]["uncertain"])
        self.assertEqual(len(self.world.mutations), 17)
        self.controller.tick(self.keepers)
        self.assertEqual(len(self.world.mutations), 17)
        self.world.blocks[self.target()] = "minecraft:gold_block"
        self.assertEqual(self.controller.tick(self.keepers)[-1]["installed_rank"], 2)
        self.assertEqual(len(self.world.mutations), 17)

    def test_completed_decoration_is_not_replayed_or_baseline_enrolled(self):
        record = self.enroll(3)
        self.controller.tick(self.keepers)
        self.controller.tick(self.keepers)
        self.world.blocks[self.target()] = "minecraft:barrel"
        restarted = self.make_controller()
        restarted.enroll(self.keepers)
        restarted.verify_source(self.keepers)
        self.assertEqual(restarted.tick(self.keepers), [])
        self.assertEqual(self.world.blocks[self.target()], "minecraft:barrel")
        for i in range(3, 10):
            keeper.credit(record, f"quest-{i}")
        self.assertTrue(restarted.tick(self.keepers)[-1]["blocked"])
        self.assertEqual(record["evolution"]["installed_rank"], 2)
        self.assertEqual(len(self.world.mutations), 17)

    def test_disabled_selected_record_and_other_keepers_cannot_authorize_mutation(self):
        record = self.enroll(50)
        record["evolution"]["enabled"] = False
        other = copy.deepcopy(record)
        other["binding"]["minimum"][0] += 100
        other["binding"]["chest"][0] += 100
        other["evolution"]["enabled"] = True
        self.keepers[keeper.keeper_id(other["binding"])] = other
        self.controller.enroll(self.keepers)
        self.assertFalse(record["evolution"]["enabled"])
        self.assertEqual(self.controller.tick(self.keepers), [])
        self.assertEqual(self.world.mutations, [])

    def test_dry_run_enrollment_preview_and_tick_never_change_records_or_world(self):
        dry = self.make_controller(dry_run=True)
        before = copy.deepcopy(self.world.blocks)
        dry.enroll(self.keepers)
        self.assertEqual(self.keepers, {})
        self.assertEqual(self.saves, [])
        prospective = dry.preview(self.keepers)
        self.assertEqual(prospective["rank"], 1)
        self.assertEqual(prospective["xp"], 0)
        self.assertEqual(self.keepers, {})
        record = self.enroll(3)
        original = copy.deepcopy(self.keepers)
        saved_count = len(self.saves)
        for action in (dry.preview, dry.tick, self.controller.preview):
            result = action(self.keepers)
            result = result[0] if isinstance(result, list) else result
            self.assertEqual(len(result["transitions"]), 17)
            self.assertEqual(result["due_rank"], 2)
            self.assertEqual(self.keepers, original)
        self.assertEqual(len(self.saves), saved_count)
        self.assertEqual(self.world.blocks, before)
        self.assertEqual(self.world.mutations, [])
        self.assertEqual(record["evolution"]["last_error"], "")

    def test_preview_blocker_and_status_results_do_not_alias_saved_records(self):
        self.enroll(3)
        original = copy.deepcopy(self.keepers)
        self.world.blocks[self.target()] = "minecraft:barrel"
        result = self.controller.preview(self.keepers)
        self.assertTrue(result["blocked"])
        self.assertEqual(result["rank"], 2)
        self.assertEqual(result["installed_rank"], 1)
        self.assertEqual(self.keepers, original)
        shown = keeper.status(self.keepers, self.controller.keeper_id)
        shown["selected"]["binding"]["minimum"][0] = 999
        self.assertEqual(self.keepers, original)

    def test_save_failure_stops_before_dispatch(self):
        self.enroll(3)
        self.fail_save = True
        with self.assertRaises(keeper.KeeperUncertain):
            self.controller.tick(self.keepers)
        self.assertEqual(self.world.mutations, [])

    def test_authored_patches_evolve_all_ranks_in_each_facing_with_exact_readback(self):
        path = ROOT / "config/keeper_temples.json"
        definitions = json.loads(path.read_text())
        resource, definition = next(iter(definitions["roots"].items()))
        for facing in ("north", "east", "south", "west"):
            with self.subTest(facing=facing):
                world = TempleWorld()
                world.place(definition, (0, 64, 0), facing)
                untouched = (-1, 64, -1)
                world.blocks[untouched] = "minecraft:barrel"
                chest = tuple(a + b for a, b in zip(rotate(definition["chest"], definition["size"], facing), (0, 64, 0)))
                chest_before = world.blocks[chest]
                records = {}
                saved = []
                controller = keeper.KeeperController(path, "authored-world", resource, (0, 64, 0), facing,
                                                    chest, world.command, lambda: saved.append(copy.deepcopy(records)))
                identity = controller.enroll(records)
                for i in range(50):
                    keeper.credit(records[identity], f"authored-{i}")
                installed = []
                for _ in range(8):
                    before = len(world.mutations)
                    events = controller.tick(records)
                    self.assertLessEqual(len(world.mutations) - before, 16)
                    self.assertFalse(any(event.get("blocked") for event in events))
                    installed.extend(event["installed_rank"] for event in events)
                    if records[identity]["evolution"]["installed_rank"] == 5:
                        break
                self.assertEqual(installed, [2, 3, 4, 5])
                self.assertEqual(len(world.mutations), sum(len(cells) for cells in definition["milestones"].values()))
                self.assertEqual(world.blocks[chest], chest_before)
                self.assertEqual(world.blocks[untouched], "minecraft:barrel")
                keeper.validate_records(json.loads(json.dumps(saved[-1])))
                controller.enroll(records)
                self.assertEqual(controller.tick(records), [])


if __name__ == "__main__":
    unittest.main()
