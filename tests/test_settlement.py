import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from settlement import BuildingError, StructureManager
from tests.support import FakeMinecraft, config_files, read_template


class SettlementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.paths = config_files(self.temp.name)
        self.world = FakeMinecraft()
        self.now = 1000.0
        self.manager = self.open()
        self.manager.grant_xp(100)

    def open(self, *, dry_run=False):
        manager = StructureManager(*self.paths, self.world.command, dry_run=dry_run, clock=lambda: self.now)
        self.addCleanup(manager.close)
        return manager

    def finish(self, result, manager=None):
        manager = manager or self.manager
        for _ in range(6):
            self.now += 10
            manager.tick()
        return next(p for p in manager.list_plots() if p["id"] == result["plot_id"])

    def update_config(self, change):
        data = json.loads(self.paths[1].read_text())
        change(data)
        self.paths[1].write_text(json.dumps(data))

    def reject(self, structure, plot=None, **kwargs):
        with self.assertRaises(BuildingError):
            self.manager.place(structure, plot, **kwargs)
        self.assertEqual(self.world.placements, [])

    def test_all_rotations_keep_actual_blocks_inside_plot(self):
        cases = {
            "north": ("none", 110, -25),
            "east": ("clockwise_90", 116, -25),
            "south": ("clockwise_180", 114, -19),
            "west": ("counterclockwise_90", 110, -21),
        }
        for facing, (rotation, x, z) in cases.items():
            with self.subTest(facing=facing), tempfile.TemporaryDirectory() as directory:
                paths = config_files(directory)
                config = json.loads(paths[1].read_text())
                config["plots"]["residential_1"]["facing"] = facing
                paths[1].write_text(json.dumps(config))
                world = FakeMinecraft()
                manager = StructureManager(*paths, world.command)
                try:
                    manager.grant_xp(100)
                    manager.place("cottage_tier_1", "residential_1", owner="Rob")
                    manager.tick()
                    self.assertIn(f" {x} 67 {z} {rotation} none", world.placements[0])
                    for bx, by, bz in world.blocks:
                        self.assertTrue(110 <= bx < 119 and 67 <= by < 73 and -25 <= bz < -18)
                finally:
                    manager.close()

    def test_unknown_plot_rejected(self):
        self.reject("workshop_tier_1", "imaginary_plot")

    def test_unknown_structure_rejected(self):
        self.reject("../evil")

    def test_incompatible_plot_rejected(self):
        self.reject("workshop_tier_1", "residential_1")

    def test_footprint_too_large_rejected(self):
        self.reject("workshop_tier_1", "commercial_1")

    def test_plot_selection_rotation_ownership_restart_and_capabilities(self):
        result = self.manager.place("workshop_tier_1", owner="CheekyHambone", reason="Trial of Iron", quest_id="trial-1")
        self.assertEqual(result["plot_id"], "workshop_east")
        plot = self.finish(result)
        self.assertEqual(plot["status"], "occupied")
        self.assertEqual(plot["owner_player"], "CheekyHambone")
        # west rotates +z to +x and +x to -z: translate z by width - 1.
        self.assertIn("director:workshop_tier_1 145 67 -32 counterclockwise_90 none", self.world.placements[0])
        self.assertIn("tool_rewards", self.manager.context()["capabilities"])
        restarted = self.open()
        self.assertEqual(next(p for p in restarted.list_plots() if p["id"] == "workshop_east")["current_structure"], "workshop_tier_1")
        self.assertIn("CheekyHambone", json.dumps(restarted.context()))
        self.assertIn("Trial of Iron", json.dumps(restarted.context()))
        with self.assertRaises(BuildingError):
            restarted.place("workshop_tier_1", "workshop_east", owner="SomeoneElse")
        self.assertEqual(len(self.world.placements), 1)

    def test_level_unlock_and_idempotent_xp(self):
        events = self.manager.grant_xp(250, quest_id="xp-quest")
        self.assertTrue(any(e["type"] == "settlement_level_up" and e["new_level"] == 3 for e in events))
        self.assertEqual(self.manager.show_settlement()["xp"], 350)
        self.manager.grant_xp(250, quest_id="xp-quest")
        self.assertEqual(self.manager.show_settlement()["xp"], 350)
        self.assertIn("house_tier_2", self.manager.context()["unlocked_structures"])
        with self.assertRaises(BuildingError):
            self.manager.grant_xp(-1)

    def test_locked_structure_rejected(self):
        self.reject("house_tier_2", "residential_1")

    def test_initialization_disabled_is_nonmutating(self):
        self.assertEqual(self.manager.initialize(), [])
        self.assertFalse(self.manager.show_settlement()["initialization_started"])
        self.assertEqual(self.world.placements, [])

    def test_unsafe_starter_area_does_not_claim_initialization(self):
        self.world.blocks[(130, 67, -40)] = "minecraft:barrel"
        with self.assertRaises(BuildingError):
            self.manager.initialize(force=True)
        self.assertFalse(self.manager.show_settlement()["initialization_started"])
        self.assertEqual(self.world.placements, [])
        self.assertTrue(all(p["status"] == "available" for p in self.manager.list_plots()))

    def test_repeatable_houses_are_limited_to_one_per_owner(self):
        self.manager.place("cottage_tier_1", "residential_1", owner="Rob")
        with self.assertRaises(BuildingError):
            self.manager.place("cottage_tier_1", "residential_2", owner="Rob")
        self.manager.place("cottage_tier_1", "residential_2", owner="CheekyHambone")
        self.assertEqual(len(self.world.placements), 2)

    def test_initialization_not_repeated_after_restart(self):
        self.manager.close()
        self.update_config(lambda c: c["settlement"].update(initialize_on_first_run=True))
        initial = self.open()
        initial.initialize()
        self.now += 10
        initial.tick()
        self.assertEqual(len(self.world.placements), 2)
        initial.close()
        restarted = self.open()
        restarted.initialize()
        restarted.tick()
        self.assertEqual(len(self.world.placements), 2)
        self.assertTrue(restarted.show_settlement()["initialized"])

    def test_owned_upgrade_and_player_edits_protected(self):
        result = self.manager.place("cottage_tier_1", "residential_1", owner="CheekyHambone")
        self.finish(result)
        self.manager.grant_xp(200)
        with self.assertRaises(BuildingError):
            self.manager.upgrade("residential_1", "house_tier_2", owner="Rob")
        upgraded = self.manager.upgrade("residential_1", "house_tier_2", owner="CheekyHambone")
        plot = self.finish(upgraded)
        self.assertEqual(plot["current_structure"], "house_tier_2")
        self.assertEqual(plot["owner_player"], "CheekyHambone")
        with self.assertRaises(BuildingError):
            self.manager.upgrade("residential_1", "cottage_tier_1")

    def test_upgrade_rejects_modified_build(self):
        result = self.manager.place("cottage_tier_1", "residential_1", owner="Rob")
        self.finish(result)
        self.manager.grant_xp(200)
        self.world.blocks[(110, 68, -25)] = "minecraft:chest"
        with self.assertRaises(BuildingError):
            self.manager.upgrade("residential_1", "house_tier_2", owner="Rob")
        self.assertEqual(len(self.world.placements), 1)

    def test_wrong_acknowledgement_protects_successfully_placed_building(self):
        original = self.manager.command

        def wrong_ack(command):
            response = original(command)
            if " run place template " in command:
                return 'Loaded template "director:storehouse_tier_1" at 120, 67, -40'
            return response

        self.manager.command = wrong_ack
        with self.assertRaises(BuildingError):
            self.manager.place("keeper_shrine", "civic_center", quest_id="wrong-ack")
        plot = next(p for p in self.manager.list_plots() if p["id"] == "civic_center")
        self.assertEqual(plot["status"], "protected")
        self.assertEqual(self.world.blocks[(120, 67, -40)], "minecraft:cobblestone")
        with self.assertRaises(BuildingError):
            self.manager.place("keeper_shrine", "civic_center", quest_id="wrong-ack")
        self.assertEqual(len(self.world.placements), 1)

    def test_invalid_llm_actions_never_reach_rcon(self):
        invalid = [
            {"action": "rcon", "command": "fill 0 0 0 100 100 100 air"},
            {"action": "construct_building", "structure_id": "unknown", "owner": "Rob", "reason": "test"},
            {"action": "construct_building", "structure_id": "workshop_tier_1", "owner": "Rob", "reason": "test", "x": 0},
            {"action": "construct_building", "structure_id": "workshop_tier_1", "owner": "@a", "reason": "test"},
            {"action": "upgrade_building", "plot_id": "unknown", "target_structure": "house_tier_2", "owner": "Rob", "reason": "test"},
        ]
        before = len(self.world.commands)
        for action in invalid:
            with self.subTest(action=action), self.assertRaises(BuildingError):
                self.manager.execute_action(action, ["Rob"])
        self.assertEqual(len(self.world.commands), before)

    def test_dry_run_preserves_existing_database_bytes_and_world(self):
        self.manager.close()
        before = hashlib.sha256(self.paths[2].read_bytes()).digest()
        dry = self.open(dry_run=True)
        result = dry.place("workshop_tier_1", owner="Rob")
        self.assertTrue(result["dry_run"])
        self.assertTrue(any("place template director:workshop_tier_1" in cmd for cmd in result["commands"]))
        dry.grant_xp(500)
        dry.close()
        self.assertEqual(hashlib.sha256(self.paths[2].read_bytes()).digest(), before)
        self.assertEqual(self.world.placements, [])
        self.assertEqual(self.world.blocks, {})

    def test_dry_run_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = config_files(directory)
            dry = StructureManager(*paths, self.world.command, dry_run=True)
            try:
                dry.place("keeper_shrine", "civic_center")
            finally:
                dry.close()
            self.assertFalse(paths[2].exists())

    def test_placement_failure_never_marks_occupied_or_retries(self):
        self.world.fail_place = True
        try:
            self.manager.place("workshop_tier_1", "workshop_east")
        except BuildingError:
            pass
        self.manager.tick()
        plot = next(p for p in self.manager.list_plots() if p["id"] == "workshop_east")
        self.assertNotEqual(plot["status"], "occupied")
        attempts = sum("place template" in c for c in self.world.commands)
        self.open().tick()
        self.assertEqual(sum("place template" in c for c in self.world.commands), attempts)

    def test_players_containers_unloaded_and_unknown_response_fail_closed(self):
        scenarios = [
            lambda: self.world.players.append((146, 68, -37)),
            lambda: self.world.blocks.update({(145, 67, -38): "minecraft:chest"}),
            lambda: setattr(self.world, "loaded", False),
            lambda: setattr(self.world, "respond", False),
        ]
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                self.world.players.clear()
                self.world.blocks.clear()
                self.world.loaded = True
                self.world.respond = True
                scenario()
                self.reject("workshop_tier_1", "workshop_east")

    def test_protected_region_rejected(self):
        self.manager.close()
        self.update_config(lambda c: c.update(protected_regions=[{"min": {"x": 145, "y": 67, "z": -38}, "max": {"x": 146, "y": 68, "z": -37}}]))
        try:
            protected = self.open()
        except BuildingError:
            pass
        else:
            with self.assertRaises(BuildingError):
                protected.place("workshop_tier_1", "workshop_east")
        self.assertEqual(self.world.placements, [])

    def test_remove_rejects_player_edits_then_removes_only_verified_building(self):
        result = self.manager.place("keeper_shrine", "civic_center")
        self.finish(result)
        old = self.world.blocks[(120, 68, -40)]
        self.world.blocks[(120, 68, -40)] = "minecraft:chest"
        with self.assertRaises(BuildingError):
            self.manager.remove("civic_center")
        self.assertEqual(self.world.blocks[(120, 68, -40)], "minecraft:chest")
        self.world.blocks[(120, 68, -40)] = old
        self.manager.remove("civic_center")
        self.assertEqual(next(p for p in self.manager.list_plots() if p["id"] == "civic_center")["status"], "available")
        self.assertTrue(all(b == "minecraft:air" for b in self.world.blocks.values()))
        self.assertFalse(any(c.startswith(("fill ", "setblock ")) for c in self.world.commands))

    def test_stages_survive_restart(self):
        self.manager.close()
        config_files(self.temp.name, stages=True)
        staged = self.open()
        result = staged.place("workshop_tier_1", "workshop_east", owner="Rob")
        self.assertTrue(result["pending"])
        staged.close()
        resumed = self.open()
        plot = self.finish(result, resumed)
        self.assertEqual(plot["status"], "occupied")
        self.assertEqual(len(self.world.placements), 3)
        self.assertEqual(self.world.blocks[(145, 67, -38)], "minecraft:cobblestone")

    def test_stage_edit_protects_plot_without_replacing_player_block(self):
        self.manager.close()
        config_files(self.temp.name, stages=True)
        staged = self.open()
        result = staged.place("workshop_tier_1", "workshop_east")
        self.world.blocks[(145, 68, -38)] = "minecraft:barrel"
        self.now += 10
        staged.tick()
        plot = next(p for p in staged.list_plots() if p["id"] == result["plot_id"])
        self.assertEqual(plot["status"], "protected")
        self.assertEqual(self.world.blocks[(145, 68, -38)], "minecraft:barrel")
        self.assertEqual(len(self.world.placements), 1)

    def test_second_manager_cannot_claim_reserved_plot(self):
        self.manager.close()
        config_files(self.temp.name, stages=True)
        staged = self.open()
        staged.place("workshop_tier_1", "workshop_east", owner="Rob")
        other = self.open()
        with self.assertRaises(BuildingError):
            other.place("workshop_tier_1", "workshop_east", owner="CheekyHambone")
        self.assertEqual(len(self.world.placements), 1)

    def test_player_entering_after_preflight_blocks_actual_placement(self):
        original = self.manager.command

        def entering(command):
            if "place template" in command:
                self.world.players.append((145, 68, -38))
            return original(command)

        self.manager.command = entering
        try:
            self.manager.place("workshop_tier_1", "workshop_east")
        except BuildingError:
            pass
        self.assertEqual(self.world.placements, [])
        self.assertNotEqual(next(p for p in self.manager.list_plots() if p["id"] == "workshop_east")["status"], "occupied")

    def test_partial_removal_protects_plot_and_never_replays(self):
        self.manager.place("keeper_shrine", "civic_center")
        original = self.manager.command
        attempts = []

        def partial(command):
            if " run setblock " in command:
                attempts.append(command)
                if len(attempts) == 2:
                    raise OSError("Lost removal response")
            return original(command)

        self.manager.command = partial
        with self.assertRaises(BuildingError):
            self.manager.remove("civic_center")
        self.assertEqual(next(p for p in self.manager.list_plots() if p["id"] == "civic_center")["status"], "protected")
        with self.assertRaises(BuildingError):
            self.manager.remove("civic_center")
        self.assertEqual(len(attempts), 2)

    def test_dry_run_upgrade_and_removal_leave_world_and_database_unchanged(self):
        self.manager.place("cottage_tier_1", "residential_1", owner="Rob")
        self.manager.grant_xp(200)
        self.manager.close()
        before = self.paths[2].read_bytes()
        world_before = dict(self.world.blocks)
        dry = self.open(dry_run=True)
        preview = dry.upgrade("residential_1", "house_tier_2", owner="Rob")
        self.assertTrue(preview["dry_run"])
        self.assertTrue(any("house_tier_2" in c for c in preview["commands"]))
        removal = dry.remove("residential_1")
        self.assertTrue(any(" run setblock " in c for c in removal["commands"]))
        dry.close()
        self.assertEqual(self.paths[2].read_bytes(), before)
        self.assertEqual(self.world.blocks, world_before)
        self.assertEqual(len(self.world.placements), 1)

    def test_failed_initialization_is_not_completed_or_repeated(self):
        self.world.fail_place = True
        results = self.manager.initialize(force=True)
        self.assertTrue(any(not r["success"] for r in results))
        self.assertTrue(self.manager.show_settlement()["initialization_started"])
        self.assertFalse(self.manager.show_settlement()["initialized"])
        before = sum(" run place template " in c for c in self.world.commands)
        restarted = self.open()
        restarted.initialize(force=True)
        restarted.tick()
        self.assertEqual(sum(" run place template " in c for c in self.world.commands), before)

    def test_announcement_failure_does_not_undo_durable_placement(self):
        self.world.fail_announce = True
        result = self.manager.place("keeper_shrine", "civic_center")
        self.assertEqual(self.finish(result)["status"], "occupied")

    def test_live_geometry_cannot_be_changed_in_config(self):
        self.finish(self.manager.place("keeper_shrine", "civic_center"))
        self.manager.close()
        self.update_config(lambda c: c["plots"]["civic_center"]["position"].update(x=999))
        with self.assertRaises(BuildingError):
            self.open()


class TemplateTests(unittest.TestCase):
    def test_templates_have_bounded_geometry_and_no_block_entities(self):
        registry = json.loads((Path(__file__).resolve().parents[1] / "config/structures.json").read_text())["structures"]
        for definition in registry.values():
            templates = [definition["template"]] + [s["template"] for s in definition.get("stages", [])]
            for template in templates:
                with self.subTest(template=template):
                    data = read_template(template.split(":")[1])
                    fp = definition["footprint"]
                    self.assertEqual(data["size"], [fp["width"], fp["height"], fp["depth"]])
                    self.assertEqual(data["entities"], [])
                    for block in data["blocks"]:
                        self.assertNotIn("nbt", block)
                        self.assertTrue(all(0 <= n < size for n, size in zip(block["pos"], data["size"])))


if __name__ == "__main__":
    unittest.main()
