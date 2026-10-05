import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import director
from settlement import StructureManager
from tests.support import FakeMinecraft, config_files


class DirectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.paths = config_files(self.temp.name)
        self.world = FakeMinecraft()
        self.manager = StructureManager(*self.paths, self.world.command)
        self.addCleanup(self.manager.close)
        for key, value in {
            "STATE_PATH": Path(self.temp.name) / "quest.json",
            "SETTLEMENT_PATH": self.paths[1],
            "SETTLEMENT_ENABLED": True,
            "DRY_RUN": False,
            "rcon": self.world.command,
        }.items():
            p = patch.object(director, key, value)
            p.start()
            self.addCleanup(p.stop)

    def quest(self, rewards=None):
        return director.Quest("CheekyHambone", "minecraft:iron_ingot", 3, 3, "Trial of Iron", "Bring iron", 1234.0,
                              rewards=rewards or [], quest_id="trial-iron")

    def test_legacy_quest_state_loads_stable_id(self):
        old = asdict(self.quest())
        old.pop("rewards")
        old.pop("quest_id")
        director.STATE_PATH.write_text(json.dumps({"active_quest": old, "last_quest_at": 1234.0}))
        a = director.load_state()
        b = director.load_state()
        self.assertEqual(a.active_quest.quest_id, b.active_quest.quest_id)
        self.assertEqual(a.active_quest.rewards, [])
        self.assertEqual(a.active_quest.item, "minecraft:iron_ingot")

    def test_quest_validation_bounds_existing_items_and_configured_rewards(self):
        valid = {"player": "CheekyHambone", "item": "minecraft:iron_ingot", "quantity": 5,
                 "reward_tier": 3, "title": "Trial", "announcement": "Bring iron",
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
            self.assertIn("Trial of Iron", json.dumps(context["recent_quests"]))
        finally:
            restarted.close()
        self.assertEqual(sum(c.startswith("give ") for c in self.world.commands), 1)
        self.assertEqual(sum(c.startswith("clear ") for c in self.world.commands), 1)

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
        self.assertEqual(sum(c.startswith("clear ") for c in self.world.commands), 1)

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
            if command.startswith("clear "):
                self.world.commands.append(command)
                raise OSError("Lost response after consuming items")
            return original(command)

        with patch.object(director, "rcon", uncertain):
            director.complete_quest(state, quest, self.manager)
        restarted = director.load_state()
        director.process_pending_rewards(restarted, self.manager)
        self.assertEqual(sum(c.startswith("clear ") for c in self.world.commands), 1)
        self.assertEqual(self.manager.show_settlement()["xp"], 0)
        self.assertEqual(restarted.pending_settlement_rewards[0].consumption, "uncertain")

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
