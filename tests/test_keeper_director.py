"""Consumer-visible Keeper credit/reward recovery through the real Director API."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import director
from keeper import KeeperController, KeeperError, KeeperUncertain, keeper_id, rank
from tests.support import FakeMinecraft, ROOT


class KeeperDirectorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "quests.json"
        self.world = FakeMinecraft()
        self.world.players = ["Alice", "Bob"]
        choice = patch.object(director.random, "randrange", return_value=0)
        choice.start()
        self.addCleanup(choice.stop)
        self.state = director.State()
        manifest = json.loads((ROOT / "config/keeper_temples.json").read_text())
        self.resource = next(iter(manifest["roots"]))
        definition = manifest["roots"][self.resource]
        minimum = [100, 64, 100]
        chest = [minimum[i] + definition["chest"][i] for i in range(3)]
        self.world.chest_position = tuple(chest)
        for cell in definition["invariants"] + definition["access"] + definition["mutable_baseline"]:
            position = tuple(minimum[i] + cell["pos"][i] for i in range(3))
            properties = cell["state"].get("properties", {})
            block = cell["state"]["id"]
            if properties:
                block += "[" + ",".join(f"{k}={v}" for k, v in sorted(properties.items())) + "]"
            self.world.blocks[position] = block
        for key, value in {"STATE_PATH": self.path, "KEEPER_ENABLED": True,
                           "DRY_RUN": False, "OFFERING_CHEST": tuple(chest),
                           "rcon": self.world.command}.items():
            change = patch.object(director, key, value)
            change.start()
            self.addCleanup(change.stop)
        self.controller = KeeperController(
            ROOT / "config/keeper_temples.json", "keeper-unit-world", self.resource,
            minimum, "north", chest, self.world.command, lambda: director.save_state(self.state))
        self.controller.enroll(self.state.keepers)
        self.key = self.controller.keeper_id
        self.record = self.state.keepers[self.key]

    def quest(self, identity, *, lane="private", item="minecraft:pumpkin", quantity=2):
        quest = director.Quest(
            "Alice" if lane == "private" else director.COMMUNAL_PLAYER,
            item, quantity, 1, "Offering", "Bring an offering", 1234.0,
            quest_id=identity, lane=lane, candidate_band="spawn_local", submission="offering_chest",
            policy_version=director.QUEST_POLICY_VERSION, mode="warmup", reference_band="spawn_local")
        director.bind_quest(self.state, quest)
        return quest

    def activate(self, quest):
        if quest.lane == "private":
            self.state.private_quests[quest.player] = quest
        else:
            self.state.communal_quest = quest
        self.world.chest_items[:] = [(0, quest.item, quest.quantity), (1, "minecraft:stick", 5)]
        return quest

    def seed_credit(self, count):
        self.record["progression"]["credited_quest_ids"][:] = [f"history-{i}" for i in range(count)]

    def pending(self, quest, recipients=None):
        reward = director.PendingReward(quest, 0, consumption="done", recipients=recipients or ["Alice"])
        director.freeze_pending_reward(reward, self.state)
        self.state.pending_settlement_rewards.append(reward)
        return reward

    def test_both_lanes_credit_once_without_multiplying_recipients_or_other_keeper(self):
        other = copy.deepcopy(self.record)
        other["binding"]["minimum"][0] += 100
        other["binding"]["chest"][0] += 100
        other["evolution"]["enabled"] = False
        other_key = keeper_id(other["binding"])
        self.state.keepers[other_key] = other
        self.activate(self.quest("private"))
        director.complete_quest(self.state, self.state.private_quests["Alice"])
        communal = self.activate(self.quest("communal", lane="communal"))
        director.complete_quest(self.state, communal)
        loaded = director.load_state()
        self.assertEqual(loaded.keepers[self.key]["progression"]["credited_quest_ids"], ["private", "communal"])
        self.assertEqual(loaded.keepers[other_key]["progression"]["credited_quest_ids"], [])
        self.assertEqual(self.world.player_levels, {"Alice": 4, "Bob": 2})
        self.assertEqual(self.world.chest_items, [(1, "minecraft:stick", 5)])
        inventory = copy.deepcopy(self.world.player_rewards)
        director.complete_quest(loaded, communal)
        director.process_pending_rewards(loaded, None)
        self.assertEqual(self.world.player_rewards, inventory)
        self.assertEqual(loaded.keepers[self.key]["progression"]["credited_quest_ids"], ["private", "communal"])

    def test_crossing_quest_uses_old_rank_and_subsequent_offering_gets_new_benefits(self):
        self.seed_credit(2)
        crossing = self.activate(self.quest("awakening"))
        director.complete_quest(self.state, crossing)
        self.assertEqual(rank(self.record), 2)
        self.assertEqual(self.world.player_xp_total, {})
        self.assertEqual(self.world.player_effects, {})
        subsequent = self.activate(self.quest("awakened-offering"))
        director.complete_quest(self.state, subsequent)
        self.assertEqual(self.world.player_xp_total, {"Alice": 5})
        self.assertEqual(self.world.player_effects["Alice"]["haste"], {"amplifier": 0, "duration": 600})
        self.assertEqual(self.world.player_rewards["Alice"], {"minecraft:emerald": 6})
        self.assertNotIn("Bob", self.world.player_effects)

    def test_frozen_plan_survives_restart_and_later_rank_advancement(self):
        self.seed_credit(9)
        pending = self.pending(self.quest("frozen"))
        self.record["progression"]["credited_quest_ids"].append("concurrent-success")
        director.save_state(self.state)
        loaded = director.load_state()
        director.process_pending_rewards(loaded, None)
        self.assertEqual(rank(loaded.keepers[self.key]), 3)
        self.assertEqual(self.world.player_xp_total["Alice"], 5)
        self.assertEqual(self.world.player_effects["Alice"]["haste"]["duration"], 600)
        self.assertNotIn("resistance", self.world.player_effects["Alice"])
        self.assertEqual(pending.reward_rank, 2)

    def test_lost_bonus_reply_preserves_exact_debt_without_credit_or_replay(self):
        self.seed_credit(10)
        quest = self.activate(self.quest("lost-points"))
        command = self.world.command
        def lose_reply(value):
            response = command(value)
            if value == "experience add Alice 10 points":
                raise OSError("Reply lost after points were granted")
            return response
        with patch.object(director, "rcon", side_effect=lose_reply):
            director.complete_quest(self.state, quest)
        loaded = director.load_state()
        self.assertTrue(loaded.pending_settlement_rewards[0].vanilla_uncertain)
        self.assertEqual(len(loaded.keepers[self.key]["progression"]["credited_quest_ids"]), 10)
        self.assertEqual(self.world.player_xp_total["Alice"], 10)
        rewards = copy.deepcopy(self.world.player_rewards)
        director.process_pending_rewards(loaded, None)
        self.assertEqual(self.world.player_xp_total["Alice"], 10)
        self.assertEqual(self.world.player_rewards, rewards)
        with self.assertRaises(KeeperUncertain):
            director.ensure_writer_safe(loaded)

    def test_lost_effect_reply_keeps_debt_without_reapplication_or_credit(self):
        self.seed_credit(3)
        quest = self.activate(self.quest("lost-effect"))
        command = self.world.command
        def lose_reply(value):
            response = command(value)
            if value == "effect give Alice minecraft:haste 30 0 true":
                raise OSError("Reply lost after Haste was applied")
            return response
        with patch.object(director, "rcon", side_effect=lose_reply):
            director.complete_quest(self.state, quest)
        loaded = director.load_state()
        self.assertTrue(loaded.pending_settlement_rewards[0].vanilla_uncertain)
        self.assertEqual(self.world.player_effects["Alice"]["haste"], {"amplifier": 0, "duration": 600})
        self.world.player_effects["Alice"]["haste"]["duration"] = 200
        director.process_pending_rewards(loaded, None)
        self.assertEqual(self.world.player_effects["Alice"]["haste"]["duration"], 200)
        self.assertEqual(len(loaded.keepers[self.key]["progression"]["credited_quest_ids"]), 3)
        with self.assertRaises(KeeperUncertain):
            director.ensure_writer_safe(loaded)

    def test_existing_stronger_effect_is_preserved_without_clear(self):
        self.seed_credit(10)
        self.world.player_effects["Alice"] = {"haste": {"amplifier": 1, "duration": 2400}}
        director.complete_quest(self.state, self.activate(self.quest("stronger")))
        self.assertEqual(self.world.player_effects["Alice"]["haste"], {"amplifier": 1, "duration": 2400})
        self.assertEqual(self.world.player_effects["Alice"]["resistance"], {"amplifier": 0, "duration": 600})
        self.assertIn("stronger", self.record["progression"]["credited_quest_ids"])

    def test_stronger_infinite_effect_remains_while_other_benefits_complete(self):
        self.seed_credit(10)
        for amplifier in (0, 1):
            with self.subTest(amplifier=amplifier):
                self.world.player_effects["Alice"] = {"haste": {"amplifier": amplifier, "duration": -1}}
                identity = f"infinite-{amplifier}"
                director.complete_quest(self.state, self.activate(self.quest(identity)))
                self.assertEqual(self.world.player_effects["Alice"]["haste"], {"amplifier": amplifier, "duration": -1})
                self.assertEqual(self.world.player_effects["Alice"]["resistance"], {"amplifier": 0, "duration": 600})
                self.assertEqual(self.world.player_xp_total["Alice"], 10 * (amplifier + 1))
                self.assertIn(identity, self.record["progression"]["credited_quest_ids"])

    def test_disabled_progression_preserves_record_and_finishes_prepared_benefits(self):
        self.seed_credit(10)
        pending = self.pending(self.quest("disabled"))
        with patch.object(director, "KEEPER_ENABLED", False):
            director.process_pending_rewards(self.state, None)
        self.assertEqual(len(self.record["progression"]["credited_quest_ids"]), 10)
        self.assertEqual(self.world.player_xp_total["Alice"], 10)
        self.assertEqual(self.state.pending_settlement_rewards, [])
        self.assertEqual(pending.reward_rank, 3)

    def test_malformed_reward_action_and_duplicate_json_cannot_overwrite_state(self):
        self.seed_credit(10)
        self.pending(self.quest("tampered"))
        director.save_state(self.state)
        data = json.loads(self.path.read_text())
        data["pending_settlement_rewards"][0]["reward_plan"][2]["amount"] = 9999
        self.path.write_text(json.dumps(data))
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            director.load_state()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.world.player_xp_total, {})
        self.path.write_text('{"keepers": {}, "keepers": {}}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            director.load_state()
        self.assertEqual(self.path.read_text(), '{"keepers": {}, "keepers": {}}')

    def test_boolean_numeric_action_is_rejected_before_dispatch(self):
        self.seed_credit(10)
        pending = self.pending(self.quest("bad-amplifier"))
        effect = next(a for a in pending.reward_plan if a["kind"] == "effect")
        effect["amplifier"] = False
        with self.assertRaises(ValueError):
            director.process_pending_rewards(self.state, None)
        self.assertEqual(self.world.player_rewards, {})

    def test_legacy_reward_indices_and_recipients_do_not_change_on_migration(self):
        quest = self.quest("legacy")
        raw = director.asdict(director.PendingReward(quest, 0, consumption="done", vanilla_step=2,
                                                     recipients=["Alice"]))
        for key in ("reward_plan", "reward_rank", "keeper_id", "source"):
            raw.pop(key)
        raw["consumption_commands"] = [f"data remove block {' '.join(map(str, self.world.chest_position))} Items[{{Slot:0b}}]"]
        self.path.write_text(json.dumps({"pending_settlement_rewards": [raw], "keepers": self.state.keepers}))
        loaded = director.load_state()
        pending = loaded.pending_settlement_rewards[0]
        self.assertEqual(pending.vanilla_step, 2)
        director.process_pending_rewards(loaded, None)
        self.assertEqual(self.world.player_rewards, {})
        self.assertEqual(self.world.player_xp_total, {})
        self.assertEqual(self.world.player_levels, {})
        self.assertEqual(len(loaded.keepers[self.key]["progression"]["credited_quest_ids"]), 1)

    def test_final_save_failure_stops_writer_after_rewards_without_repeating_them(self):
        quest = self.activate(self.quest("save-failure"))
        save = director.save_state
        def failing_save(state):
            if not state.pending_settlement_rewards and "save-failure" in self.record["progression"]["credited_quest_ids"]:
                raise director.StatePersistenceError("Final rename unavailable")
            return save(state)
        with patch.object(director, "save_state", side_effect=failing_save):
            with self.assertRaises(director.StatePersistenceError):
                director.complete_quest(self.state, quest)
        loaded = director.load_state()
        self.assertEqual(loaded.pending_settlement_rewards[0].vanilla_step,
                         len(loaded.pending_settlement_rewards[0].reward_plan))
        rewards = copy.deepcopy(self.world.player_rewards)
        director.process_pending_rewards(loaded, None)
        self.assertEqual(self.world.player_rewards, rewards)
        self.assertEqual(loaded.keepers[self.key]["progression"]["credited_quest_ids"], ["save-failure"])

    def test_dry_run_does_not_save_or_consume_or_credit(self):
        self.seed_credit(10)
        quest = self.activate(self.quest("preview"))
        director.save_state(self.state)
        before = self.path.read_bytes()
        items = list(self.world.chest_items)
        with patch.object(director, "DRY_RUN", True):
            director.complete_quest(self.state, quest)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.world.chest_items, items)
        self.assertEqual(self.world.player_rewards, {})
        self.assertEqual(len(self.record["progression"]["credited_quest_ids"]), 10)

    def test_invalid_binding_stops_startup_before_offering_mutation(self):
        self.activate(self.quest("startup"))
        director.save_state(self.state)
        before = self.path.read_bytes()
        binding = self.record["binding"]
        environment = {
            "KEEPER_WORLD_ID": binding["world_id"], "KEEPER_TEMPLE_RESOURCE": binding["resource"],
            "KEEPER_TEMPLE_FACING": "south",
            **{f"KEEPER_TEMPLE_MIN_{axis}": str(value) for axis, value in zip("XYZ", binding["minimum"])},
        }
        with patch.dict("os.environ", environment), patch.object(director, "RCON_PASSWORD", "unit-only"):
            self.assertEqual(director.main(), 2)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.world.chest_items, [(0, "minecraft:pumpkin", 2), (1, "minecraft:stick", 5)])
        self.assertEqual(self.world.player_rewards, {})
        self.assertEqual(self.record["progression"]["credited_quest_ids"], [])

    def test_read_only_legacy_enrollment_does_not_backfill_or_persist(self):
        self.path.write_text(json.dumps({
            "communal_completions": 3, "private_completions": {"Alice": 2},
            "private_issued": {"Alice": 7}, "last_quest_at": 11,
        }))
        before = self.path.read_bytes()
        binding = self.record["binding"]
        environment = {
            "KEEPER_WORLD_ID": binding["world_id"], "KEEPER_TEMPLE_RESOURCE": binding["resource"],
            "KEEPER_TEMPLE_FACING": binding["facing"],
            **{f"KEEPER_TEMPLE_MIN_{axis}": str(value) for axis, value in zip("XYZ", binding["minimum"])},
        }
        with patch.dict("os.environ", environment), patch.object(director, "DRY_RUN", True):
            legacy = director.load_state()
            previewer = director.keeper_controller(legacy, persist=True)
            preview = previewer.preview(legacy.keepers)
        self.assertEqual((preview["xp"], preview["rank"], preview["registered"]), (0, 1, True))
        self.assertEqual(legacy.keepers[self.key]["progression"]["credited_quest_ids"], [])
        self.assertEqual((legacy.communal_completions, legacy.private_completions,
                          legacy.private_issued, legacy.last_quest_at),
                         (3, {"Alice": 2}, {"Alice": 7}, 11))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.world.player_rewards, {})

    def test_admin_malformed_state_returns_json_error_without_rewriting(self):
        self.path.write_text('{"keepers":{"invalid":{}}}')
        before = self.path.read_bytes()
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "keeper_admin.py"), "--state", str(self.path), "show"],
            cwd=ROOT, capture_output=True, text=True, timeout=15)
        response = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(response["success"])
        self.assertTrue(response["dry_run"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_admin_reads_earned_and_delayed_appearance_without_rewriting(self):
        self.seed_credit(3)
        director.save_state(self.state)
        before = self.path.read_bytes()
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "keeper_admin.py"), "--state", str(self.path),
             "show", "--keeper-id", self.key], cwd=ROOT, capture_output=True, text=True, timeout=15)
        response = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        selected = response["selected"]
        self.assertEqual((selected["xp"], selected["rank"], selected["installed_rank"], selected["due_rank"]),
                         (3, 2, 1, 2))
        self.assertEqual(self.path.read_bytes(), before)


    def test_ambiguous_legacy_source_blocks_rewards_even_when_levels_disabled(self):
        quest = self.quest("ambiguous")
        quest.keeper_id = None
        quest.source = {}
        pending = director.PendingReward(quest, 0, consumption="done", recipients=["Alice"],
            consumption_commands=["data remove block 10 64 10 Items[{Slot:0b}]",
                                  "data remove block 20 64 20 Items[{Slot:0b}]"])
        director.freeze_pending_reward(pending, self.state, legacy=True)
        self.state.pending_settlement_rewards.append(pending)
        director.save_state(self.state)
        before = self.path.read_bytes()
        with patch.object(director, "KEEPER_ENABLED", False), self.assertRaises(KeeperError):
            director.process_pending_rewards(self.state, None)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.world.player_rewards, {})
        self.assertEqual(director.reserved_items(self.state), {"minecraft:pumpkin"})
        self.assertEqual(self.record["progression"]["credited_quest_ids"], [])

    def test_policy_retirement_does_not_consume_or_credit_either_lane(self):
        for lane in ("private", "communal"):
            quest = self.activate(self.quest("retire-" + lane, lane=lane))
            quest.policy_version = 0
            quest.mode = "legacy"
            quest.reference_band = None
            director.revalidate_legacy_quests(
                self.state, snapshots={True: director.SupplySnapshot({}, {}, True, "verified absent supply")})
            self.assertNotIn(quest, director.active_quests(self.state))
            self.assertEqual(self.world.chest_items, [(0, "minecraft:pumpkin", 2), (1, "minecraft:stick", 5)])
        self.assertEqual(self.record["progression"]["credited_quest_ids"], [])
        self.assertEqual(self.world.player_rewards, {})
        self.assertEqual((self.state.private_completions, self.state.communal_completions), ({}, 0))


    def test_pinned_source_and_issuer_rank_ignore_later_global_chest_setting(self):
        quest = self.activate(self.quest("pinned"))
        other = copy.deepcopy(self.record)
        other["binding"]["minimum"][0] += 100
        other["binding"]["chest"][0] += 100
        other["progression"]["credited_quest_ids"] = [f"other-{i}" for i in range(50)]
        other["evolution"]["enabled"] = False
        other_key = keeper_id(other["binding"])
        self.state.keepers[other_key] = other
        with patch.object(director, "OFFERING_CHEST", tuple(other["binding"]["chest"])):
            director.complete_quest(self.state, quest)
        self.assertEqual(self.world.chest_items, [(1, "minecraft:stick", 5)])
        self.assertEqual(self.world.player_rewards["Alice"], {"minecraft:emerald": 3})
        self.assertEqual(self.world.player_levels["Alice"], 2)
        self.assertEqual(self.world.player_points.get("Alice", 0), 0)
        self.assertEqual(self.world.player_effects.get("Alice", {}), {})
        self.assertEqual(self.record["progression"]["credited_quest_ids"], ["pinned"])
        self.assertEqual(len(other["progression"]["credited_quest_ids"]), 50)


if __name__ == "__main__":
    unittest.main()
