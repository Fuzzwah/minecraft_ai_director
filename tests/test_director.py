import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import director
from settlement import StructureManager
from quest_supply import PlayerProfile, SupplySnapshot, parse_inventory_slots
from tests.support import FakeMinecraft, config_files


class DirectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.paths = config_files(self.temp.name)
        self.world = FakeMinecraft()
        self.manager = StructureManager(*self.paths, self.world.command)
        self.world.ender_items["CheekyHambone"] = [(0, "minecraft:diamond", 3), (1, "minecraft:stick", 2)]
        self.addCleanup(self.manager.close)
        for key, value in {
            "STATE_PATH": Path(self.temp.name) / "quest.json",
            "SETTLEMENT_PATH": self.paths[1],
            "SETTLEMENT_ENABLED": True,
            "DRY_RUN": False,
            "OFFERING_CHEST": self.world.chest_position,
            "rcon": self.world.command,
        }.items():
            p = patch.object(director, key, value)
            p.start()
            self.addCleanup(p.stop)

    def quest(self, rewards=None):
        return director.Quest("CheekyHambone", "minecraft:diamond", 1, 3, "Trial of Diamond", "Bring diamond", 1234.0,
                              rewards=rewards or [], quest_id="trial-diamond", lane="private",
                              candidate_band="established", submission="ender_chest")

    def test_legacy_quest_state_loads_stable_id(self):
        old = asdict(self.quest())
        old.pop("rewards")
        old.pop("quest_id")
        director.STATE_PATH.write_text(json.dumps({"active_quest": old, "last_quest_at": 1234.0}))
        a = director.load_state()
        b = director.load_state()
        self.assertEqual(a.active_quest.quest_id, b.active_quest.quest_id)
        self.assertEqual(a.active_quest.rewards, [])
        self.assertEqual(a.active_quest.item, "minecraft:diamond")

    def test_quest_validation_bounds_existing_items_and_configured_rewards(self):
        valid = {"player": "CheekyHambone", "item": "minecraft:diamond", "quantity": 1,
                 "reward_tier": 3, "title": "Trial", "announcement": "Bring diamond",
                 "rewards": [{"type": "structure", "structure_id": "workshop_tier_1"}]}
        quest = director.validate_quest(valid, ["CheekyHambone"], self.manager)
        self.assertEqual(quest.rewards, [{"type": "settlement_xp", "amount": 30},
                                       {"type": "structure", "structure_id": "workshop_tier_1"}])
        for change in [
            {"quantity": 100}, {"player": "@a"}, {"item": "minecraft:tnt"},
            {"rewards": [{"type": "settlement_xp", "amount": 9999}]},
            {"rewards": [{"type": "structure", "structure_id": "house_tier_2"}]},
            {"command": "setblock 0 64 0 lava"},
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                director.validate_quest(valid | change, ["CheekyHambone"], self.manager)

    def test_quest_unlocks_constructs_and_persists_workshop_after_restart(self):
        self.manager.grant_xp(70)
        quest = self.quest([{"type": "settlement_xp", "amount": 30},
                            {"type": "structure", "structure_id": "workshop_tier_1"}])
        state = director.State(active_quest=quest)
        events = director.complete_quest(state, quest, self.manager)
        self.manager.tick()
        director.process_pending_rewards(state, self.manager)
        self.assertTrue(any(e["type"] == "settlement_level_up" and e["new_level"] == 2 for e in events))
        self.assertEqual(self.manager.show_settlement()["xp"], 100)
        self.assertEqual(len(self.world.placements), 1)
        self.assertEqual(state.pending_settlement_rewards, [])
        self.assertIsNone(director.load_state().active_quest)
        restarted = StructureManager(*self.paths, self.world.command)
        try:
            context = restarted.context()
            self.assertIn("workshop_tier_1", json.dumps(context["buildings"]))
            self.assertIn("CheekyHambone", json.dumps(context["buildings"]))
            self.assertIn("Trial of Diamond", json.dumps(context["recent_quests"]))
        finally:
            restarted.close()
        self.assertEqual(sum(c.startswith("give ") for c in self.world.commands), 1)
        self.assertEqual(sum(c.startswith(("data remove entity", "data modify entity")) for c in self.world.commands), 1)

    def test_blocked_structure_reward_survives_restart_without_double_pay(self):
        self.manager.grant_xp(100)
        self.world.blocks[(145, 67, -38)] = "minecraft:chest"
        quest = self.quest([{"type": "settlement_xp", "amount": 30},
                            {"type": "structure", "structure_id": "workshop_tier_1"}])
        state = director.State(active_quest=quest)
        director.complete_quest(state, quest, self.manager)
        self.assertEqual(len(state.pending_settlement_rewards), 1)
        restarted_state = director.load_state()
        self.world.blocks.clear()
        director.process_pending_rewards(restarted_state, self.manager)
        self.manager.tick()
        director.process_pending_rewards(restarted_state, self.manager)
        self.assertEqual(restarted_state.pending_settlement_rewards, [])
        self.assertEqual(self.manager.show_settlement()["xp"], 130)
        self.assertEqual(len(self.world.placements), 1)
        self.assertEqual(sum(c.startswith("give ") for c in self.world.commands), 1)
        self.assertEqual(sum(c.startswith(("data remove entity", "data modify entity")) for c in self.world.commands), 1)

    def test_dry_run_quest_never_consumes_grants_or_saves(self):
        quest = self.quest([{"type": "settlement_xp", "amount": 30}])
        state = director.State(active_quest=quest)
        with patch.object(director, "DRY_RUN", True):
            director.complete_quest(state, quest, self.manager)
        self.assertIs(state.active_quest, quest)
        self.assertFalse(director.STATE_PATH.exists())
        self.assertEqual(self.manager.show_settlement()["xp"], 0)
        self.assertFalse(any(c.startswith(("clear ", "give ", "experience ", "title ")) for c in self.world.commands))

    def test_uncertain_consumption_is_not_replayed_after_restart(self):
        quest = self.quest([{"type": "settlement_xp", "amount": 30}])
        state = director.State(active_quest=quest)
        original = self.world.command

        def uncertain(command):
            if command.startswith(("data remove entity", "data modify entity")):
                self.world.commands.append(command)
                raise OSError("Lost response after consuming items")
            return original(command)

        with patch.object(director, "rcon", uncertain):
            director.complete_quest(state, quest, self.manager)
        restarted = director.load_state()
        director.process_pending_rewards(restarted, self.manager)
        self.assertEqual(sum(c.startswith(("data remove entity", "data modify entity")) for c in self.world.commands), 1)
        self.assertEqual(self.manager.show_settlement()["xp"], 0)
        self.assertEqual(restarted.pending_settlement_rewards[0].consumption, "uncertain")

    def test_java_inventory_field_order_is_parsed_without_losing_metadata(self):
        response = ('block data: {Items: [{count: 3, id: "minecraft:pumpkin", '
                    'components: {"minecraft:custom_name": "Keeper"}, Slot: 0b}, '
                    '{count: 2, id: "minecraft:stick", Slot: 1b}]}')
        self.assertEqual(parse_inventory_slots(response)[0]["id"], "minecraft:pumpkin")
        self.assertEqual(parse_inventory_slots(response)[0]["count"], 3)
        self.assertEqual(parse_inventory_slots(response)[1]["slot"], 1)

    def test_lane_filtering_uses_pumpkin_supply_and_progression_boundaries(self):
        snapshot = SupplySnapshot({"minecraft:pumpkin": 4}, {"minecraft:pumpkin": {"spawn_blocks"}}, True, "complete")
        novice = PlayerProfile("Novice", 0, frozenset(), frozenset(), frozenset(), 0)
        private = director.candidate_items("private", novice, snapshot, 0)
        self.assertEqual([candidate["item"] for candidate in private], ["minecraft:pumpkin"])
        self.assertNotIn("minecraft:carrot", [candidate["item"] for candidate in private])
        self.assertEqual(director.progression_band(11), "spawn_local")
        self.assertEqual(director.progression_band(12), "early")
        self.assertEqual(director.progression_band(115), "endgame")
        self.assertEqual(director.candidate_items("communal", None,
                                                  SupplySnapshot({}, {}, False, "unknown"), 0), [])

    def test_private_and_communal_strength_are_distinct(self):
        novice = PlayerProfile("Novice", 0, frozenset(), frozenset(), frozenset(), 0)
        advanced = PlayerProfile("Advanced", 0, frozenset({"minecraft:diamond"}), frozenset(),
                                 frozenset({"minecraft:netherite_chestplate"}), 100)
        self.assertEqual(director.average_strength({"Novice": novice, "Advanced": advanced}), 50)
        self.assertEqual(director.progression_band(novice.score), "spawn_local")
        self.assertEqual(director.progression_band(advanced.score), "nether_end")

    def test_empty_candidates_and_malformed_model_decline_safely(self):
        with self.assertRaises(ValueError):
            director.fallback_quest(["CheekyHambone"], candidates=[])
        candidate = [{"item": "minecraft:pumpkin", "min": 2, "max": 8,
                      "band": "spawn_local", "sources": ["spawn_blocks"]}]
        with self.assertRaises(ValueError):
            director.validate_quest({"player": "CheekyHambone", "item": "minecraft:carrot",
                                     "quantity": 5, "reward_tier": 1, "title": "x",
                                     "announcement": "x", "rewards": []},
                                    ["CheekyHambone"], candidates=candidate)

    def test_legacy_state_migrates_to_private_map(self):
        old = asdict(self.quest())
        old.pop("rewards")
        old.pop("quest_id")
        director.STATE_PATH.write_text(json.dumps({"active_quest": old, "last_quest_at": 1234.0}))
        state = director.load_state()
        self.assertIn("CheekyHambone", state.private_quests)
        self.assertEqual(state.private_quests["CheekyHambone"].quest_id, state.active_quest.quest_id)

    def test_communal_chest_rewards_all_online_players_once(self):
        self.world.players[:] = ["CheekyHambone", "Alex"]
        self.world.blocks[self.world.chest_position] = "minecraft:chest"
        self.world.chest_items[:] = [(0, "minecraft:pumpkin", 4), (1, "minecraft:stick", 2)]
        quest = director.Quest("_communal", "minecraft:pumpkin", 2, 1, "Temple", "Offer pumpkin", 1,
                              quest_id="communal", lane="communal", candidate_band="spawn_local",
                              submission="offering_chest")
        state = director.State(communal_quest=quest)
        director.complete_quest(state, quest, self.manager)
        gives = [command for command in self.world.commands if command.startswith("give ")]
        self.assertEqual(len(gives), 2)
        self.assertTrue(any("give CheekyHambone" in command for command in gives))
        self.assertTrue(any("give Alex" in command for command in gives))
        self.assertEqual(self.world.chest_items, [(0, "minecraft:pumpkin", 2), (1, "minecraft:stick", 2)])
        before = len(gives)
        director.process_pending_rewards(state, self.manager)
        self.assertEqual(len([command for command in self.world.commands if command.startswith("give ")]), before)

    def test_private_ender_rewards_only_target(self):
        self.world.ender_items["CheekyHambone"] = [(0, "minecraft:pumpkin", 3), (1, "minecraft:stick", 2)]
        self.world.ender_items["Alex"] = [(0, "minecraft:pumpkin", 3)]
        quest = director.Quest("CheekyHambone", "minecraft:pumpkin", 2, 1, "Private", "Offer pumpkin", 1,
                              quest_id="private", lane="private", candidate_band="spawn_local",
                              submission="ender_chest")
        state = director.State(private_quests={"CheekyHambone": quest})
        director.complete_quest(state, quest, self.manager)
        gives = [command for command in self.world.commands if command.startswith("give ")]
        self.assertEqual(len(gives), 1)
        self.assertTrue(gives[0].startswith("give CheekyHambone"))
        self.assertEqual(self.world.ender_items["Alex"], [(0, "minecraft:pumpkin", 3)])

    def test_ai_decision_cannot_escape_high_level_validation(self):
        with patch.object(director, "request_llm_json", return_value={"action": "construct_building", "structure_id": "workshop_tier_1", "owner": "CheekyHambone", "reason": "test", "command": "fill 0 0 0 9 9 9 air"}):
            with self.assertRaises(ValueError):
                director.make_settlement_decision(self.manager, ["CheekyHambone"], [{"type": "quest_completed"}])
        self.assertEqual(self.world.commands, [])

    def test_log_tail_continues_tracking_rotation(self):
        log = Path(self.temp.name) / "latest.log"
        log.write_text("old log\n")
        tail = director.LogTail(log)
        try:
            self.assertEqual(tail.read_new(), [])
            with log.open("a") as handle:
                handle.write("Rob joined the game\n")
            self.assertEqual(tail.read_new(), ["Rob joined the game"])
            log.rename(log.with_suffix(".old"))
            log.write_text("rotated old\n")
            self.assertEqual(tail.read_new(), [])
            with log.open("a") as handle:
                handle.write("Rob has made the advancement [Stone Age]\n")
            self.assertTrue(director.interesting(tail.read_new()[0]))
        finally:
            tail.close()


if __name__ == "__main__":
    unittest.main()
