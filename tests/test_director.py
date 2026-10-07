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
        self.world.blocks[self.world.chest_position] = "minecraft:chest"
        self.world.chest_items[:] = [(0, "minecraft:diamond", 3)]
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
                              candidate_band="established", submission="offering_chest",
                              policy_version=director.QUEST_POLICY_VERSION,
                              mode="long_term", reference_band="early")

    def test_legacy_quest_state_loads_stable_id(self):
        old = asdict(self.quest())
        old["submission"] = "ender_chest"
        old.pop("rewards")
        old.pop("quest_id")
        director.STATE_PATH.write_text(json.dumps({"active_quest": old, "last_quest_at": 1234.0}))
        a = director.load_state()
        b = director.load_state()
        self.assertEqual(a.active_quest.quest_id, b.active_quest.quest_id)
        self.assertEqual(a.active_quest.rewards, [])
        self.assertEqual(a.active_quest.item, "minecraft:diamond")
        self.assertEqual(a.active_quest.submission, "offering_chest")
        persisted = json.loads(director.STATE_PATH.read_text())
        self.assertEqual(persisted["active_quest"]["submission"], "offering_chest")

    def test_pending_legacy_reward_migrates_without_losing_intent(self):
        quest = self.quest()
        quest.submission = "ender_chest"
        pending = director.PendingReward(
            quest, vanilla_choice=0, consumption="uncertain", last_error="reconcile",
            recipients=["CheekyHambone"], source_snapshot={"slots": [{"slot": 0}]})
        state = director.State(pending_settlement_rewards=[pending])
        director.save_state(state)
        loaded = director.load_state()
        migrated = loaded.pending_settlement_rewards[0]
        self.assertEqual(migrated.quest.quest_id, quest.quest_id)
        self.assertEqual(migrated.quest.player, quest.player)
        self.assertEqual(migrated.quest.item, quest.item)
        self.assertEqual(migrated.quest.quantity, quest.quantity)
        self.assertEqual(migrated.quest.submission, "offering_chest")
        self.assertEqual(migrated.consumption, "uncertain")
        self.assertEqual(migrated.last_error, "reconcile")
        self.assertEqual(migrated.recipients, ["CheekyHambone"])

    def test_quest_validation_bounds_existing_items_and_configured_rewards(self):
        valid = {"player": "CheekyHambone", "item": "minecraft:diamond", "quantity": 1,
                 "reward_tier": 3, "title": "Trial", "announcement": "Bring diamond",
                 "rewards": [{"type": "structure", "structure_id": "workshop_tier_1"}]}
        profile = PlayerProfile("CheekyHambone", 0, frozenset(), frozenset(), frozenset(), 35)
        state = director.State(communal_completions=3, private_completions={"CheekyHambone": 3})
        candidates = director.candidate_items("private", profile, SupplySnapshot({}, {}, True), 35,
                                             state=state, communal_score=12)
        quest = director.validate_quest(valid, ["CheekyHambone"], self.manager, candidates=candidates, state=state)
        self.assertEqual(quest.rewards, [{"type": "settlement_xp", "amount": 30},
                                       {"type": "structure", "structure_id": "workshop_tier_1"}])
        self.assertEqual(quest.submission, "offering_chest")
        self.assertIn("offering chest", quest.announcement.lower())
        for change in [
            {"quantity": 100}, {"player": "@a"}, {"item": "minecraft:tnt"},
            {"rewards": [{"type": "settlement_xp", "amount": 9999}]},
            {"rewards": [{"type": "structure", "structure_id": "house_tier_2"}]},
            {"command": "setblock 0 64 0 lava"},
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                director.validate_quest(valid | change, ["CheekyHambone"], self.manager,
                                        candidates=candidates, state=state)

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
        self.assertEqual(sum(c.startswith(("data remove block", "data modify block")) for c in self.world.commands), 1)

    def test_blocked_structure_reward_survives_restart_without_double_pay(self):
        self.manager.grant_xp(100)
        self.world.blocks[(145, 67, -38)] = "minecraft:chest"
        quest = self.quest([{"type": "settlement_xp", "amount": 30},
                            {"type": "structure", "structure_id": "workshop_tier_1"}])
        state = director.State(active_quest=quest)
        director.complete_quest(state, quest, self.manager)
        self.assertEqual(len(state.pending_settlement_rewards), 1)
        self.assertEqual(state.private_completions, {})
        restarted_state = director.load_state()
        self.world.blocks.clear()
        director.process_pending_rewards(restarted_state, self.manager)
        self.manager.tick()
        director.process_pending_rewards(restarted_state, self.manager)
        self.assertEqual(restarted_state.pending_settlement_rewards, [])
        self.assertEqual(restarted_state.private_completions, {"CheekyHambone": 1})
        self.assertEqual(self.manager.show_settlement()["xp"], 130)
        self.assertEqual(len(self.world.placements), 1)
        self.assertEqual(sum(c.startswith("give ") for c in self.world.commands), 1)
        self.assertEqual(sum(c.startswith(("data remove block", "data modify block")) for c in self.world.commands), 1)

    def test_dry_run_quest_never_consumes_grants_or_saves(self):
        quest = self.quest([{"type": "settlement_xp", "amount": 30}])
        state = director.State(active_quest=quest)
        with patch.object(director, "DRY_RUN", True):
            director.complete_quest(state, quest, self.manager)
        self.assertIs(state.active_quest, quest)
        self.assertFalse(director.STATE_PATH.exists())
        self.assertEqual(self.manager.show_settlement()["xp"], 0)
        self.assertEqual(state.private_completions, {})
        self.assertEqual(state.private_issued, {})
        self.assertFalse(any(c.startswith(("clear ", "give ", "experience ", "title ")) for c in self.world.commands))

    def test_uncertain_consumption_is_not_replayed_after_restart(self):
        quest = self.quest([{"type": "settlement_xp", "amount": 30}])
        state = director.State(active_quest=quest)
        original = self.world.command

        def uncertain(command):
            if command.startswith(("data remove block", "data modify block")):
                self.world.commands.append(command)
                raise OSError("Lost response after consuming items")
            return original(command)

        with patch.object(director, "rcon", uncertain):
            director.complete_quest(state, quest, self.manager)
        restarted = director.load_state()
        director.process_pending_rewards(restarted, self.manager)
        self.assertEqual(sum(c.startswith(("data remove block", "data modify block")) for c in self.world.commands), 1)
        self.assertEqual(self.manager.show_settlement()["xp"], 0)
        self.assertEqual(restarted.pending_settlement_rewards[0].consumption, "uncertain")
        self.assertEqual(restarted.private_completions, {})

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
            director.fallback_quest(["CheekyHambone"], candidates=[], state=director.State())
        novice = PlayerProfile("CheekyHambone", 0, frozenset(), frozenset(), frozenset(), 0)
        candidate = director.candidate_items("private", novice, self.local_supply(), 0)
        with self.assertRaises(ValueError):
            director.validate_quest({"player": "CheekyHambone", "item": "minecraft:carrot",
                                     "quantity": 5, "reward_tier": 1, "title": "x",
                                     "announcement": "x", "rewards": []},
                                    ["CheekyHambone"], candidates=candidate, state=director.State())

    def test_legacy_state_migrates_to_private_map(self):
        old = asdict(self.quest())
        old["submission"] = "ender_chest"
        old.pop("rewards")
        old.pop("quest_id")
        director.STATE_PATH.write_text(json.dumps({"active_quest": old, "last_quest_at": 1234.0}))
        state = director.load_state()
        self.assertIn("CheekyHambone", state.private_quests)
        self.assertEqual(state.private_quests["CheekyHambone"].quest_id, state.active_quest.quest_id)
        self.assertEqual(state.private_quests["CheekyHambone"].submission, "offering_chest")

    def test_communal_chest_rewards_all_online_players_once(self):
        self.world.players[:] = ["CheekyHambone", "Alex"]
        self.world.blocks[self.world.chest_position] = "minecraft:chest"
        self.world.chest_items[:] = [(0, "minecraft:pumpkin", 4), (1, "minecraft:stick", 2)]
        quest = director.Quest("_communal", "minecraft:pumpkin", 2, 1, "Temple", "Offer pumpkin", 1,
                              quest_id="communal", lane="communal", candidate_band="spawn_local",
                              submission="offering_chest", policy_version=director.QUEST_POLICY_VERSION,
                              mode="warmup", reference_band="spawn_local")
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

    def test_private_shared_chest_rewards_only_target(self):
        self.world.players[:] = ["CheekyHambone", "Alex"]
        self.world.blocks[self.world.chest_position] = "minecraft:chest"
        self.world.chest_items[:] = [(0, "minecraft:pumpkin", 3), (1, "minecraft:stick", 2)]
        self.world.ender_items["CheekyHambone"] = [(0, "minecraft:pumpkin", 3)]
        self.world.ender_items["Alex"] = [(0, "minecraft:pumpkin", 3)]
        quest = director.Quest("CheekyHambone", "minecraft:pumpkin", 2, 1, "Private", "Offer pumpkin", 1,
                              quest_id="private", lane="private", candidate_band="spawn_local",
                              submission="offering_chest", policy_version=director.QUEST_POLICY_VERSION,
                              mode="warmup", reference_band="spawn_local")
        state = director.State(private_quests={"CheekyHambone": quest})
        director.complete_quest(state, quest, self.manager)
        gives = [command for command in self.world.commands if command.startswith("give ")]
        self.assertEqual(len(gives), 1)
        self.assertTrue(gives[0].startswith("give CheekyHambone"))
        self.assertEqual(self.world.chest_items, [(0, "minecraft:pumpkin", 1), (1, "minecraft:stick", 2)])
        self.assertEqual(self.world.ender_items["Alex"], [(0, "minecraft:pumpkin", 3)])
        self.assertFalse(any("EnderItems" in command for command in self.world.commands))

    def test_player_profile_does_not_read_ender_inventory(self):
        director.player_profile("CheekyHambone")
        self.assertFalse(any("EnderItems" in command for command in self.world.commands))

    def test_ender_only_private_supply_does_not_complete(self):
        self.world.ender_items["CheekyHambone"] = [(0, "minecraft:pumpkin", 3)]
        quest = director.Quest("CheekyHambone", "minecraft:pumpkin", 2, 1, "Private", "Offer pumpkin", 1,
                              quest_id="ender-only", lane="private", candidate_band="spawn_local",
                              submission="offering_chest", policy_version=director.QUEST_POLICY_VERSION,
                              mode="warmup", reference_band="spawn_local")
        state = director.State(private_quests={"CheekyHambone": quest})
        director.complete_quest(state, quest, self.manager)
        self.assertFalse(any(command.startswith("give ") for command in self.world.commands))
        self.assertEqual(self.world.ender_items["CheekyHambone"], [(0, "minecraft:pumpkin", 3)])
        self.assertFalse(any("EnderItems" in command for command in self.world.commands))

    def local_supply(self, items=None, complete=True):
        items = {"minecraft:pumpkin": 4, "minecraft:wheat": 12} if items is None else items
        return SupplySnapshot(items, {item: {"spawn_blocks"} for item in items}, complete,
                              "complete" if complete else "unknown")

    def profile(self, player="CheekyHambone", score=100, confidence="complete"):
        return PlayerProfile(player, 0, frozenset({"minecraft:carrot"}), frozenset(),
                             frozenset(), score, confidence)

    def opening(self, *, player="CheekyHambone", item="minecraft:pumpkin",
                quest_id="opening", lane="private", quantity=None, legacy=False):
        return director.Quest(
            director.COMMUNAL_PLAYER if lane == "communal" else player,
            item, director.QUEST_CATALOG[item]["min"] if quantity is None else quantity,
            1, "Opening offering", "Offer pumpkin", 1,
            quest_id=quest_id, lane=lane, candidate_band="spawn_local",
            policy_version=0 if legacy else director.QUEST_POLICY_VERSION,
            mode="legacy" if legacy else "warmup",
            reference_band=None if legacy else "spawn_local")

    def test_warmup_overrides_strength_requires_minimum_local_yield(self):
        profile = self.profile(score=200)
        snapshot = self.local_supply({"minecraft:pumpkin": 1, "minecraft:wheat": 6})
        for lane in ("private", "communal"):
            with self.subTest(lane=lane):
                candidates = director.candidate_items(lane, profile if lane == "private" else None,
                                                      snapshot, 200)
                self.assertEqual([(c["item"], c["min"], c["max"], c["mode"]) for c in candidates],
                                 [("minecraft:wheat", 6, 6, "warmup")])
        self.assertEqual(director.candidate_items("private", profile, self.local_supply({}), 200), [])
        self.assertEqual(director.candidate_items("private", profile,
                                                  self.local_supply(complete=False), 200), [])

    def test_model_and_fallback_share_exact_warmup_bounds(self):
        state = director.State()
        candidates = director.candidate_items("private", self.profile(), self.local_supply(), 100, state=state)
        raw = {"player": "CheekyHambone", "item": "minecraft:pumpkin", "quantity": 3, "reward_tier": 1}
        with self.assertRaises(ValueError):
            director.validate_quest(raw, ["CheekyHambone"], candidates=candidates, state=state)
        quest = director.validate_quest(raw | {"quantity": 2}, ["CheekyHambone"],
                                        candidates=candidates, state=state)
        self.assertEqual((quest.quantity, quest.mode, quest.reference_band), (2, "warmup", "spawn_local"))
        fallback = director.fallback_quest(["CheekyHambone"], candidates=candidates, state=state)
        self.assertEqual(fallback.quantity, director.QUEST_CATALOG[fallback.item]["min"])
        for factory in (director.validate_quest, director.fallback_quest):
            with self.subTest(factory=factory.__name__), self.assertRaises(ValueError):
                if factory is director.validate_quest:
                    factory(raw, ["CheekyHambone"], state=state)
                else:
                    factory(["CheekyHambone"], state=state)

    def test_state_round_trip_counters_and_strict_legacy_defaults(self):
        quest = self.quest()
        pending = director.PendingReward(quest, 0, consumption="uncertain",
                                         consumption_commands=["data remove block 0 64 0 Items[0]"],
                                         recipients=["CheekyHambone"], source_snapshot={"slots": [{"raw": "{id:x}"}]})
        state = director.State(private_quests={quest.player: quest}, pending_settlement_rewards=[pending],
                               communal_completions=2, private_completions={quest.player: 3},
                               private_issued={quest.player: 9})
        director.save_state(state)
        self.assertEqual(asdict(director.load_state()), asdict(state))
        raw = json.loads(director.STATE_PATH.read_text())
        for key in ("communal_completions", "private_completions", "private_issued"):
            raw.pop(key)
        for key in ("policy_version", "mode", "reference_band"):
            raw["private_quests"][quest.player].pop(key)
            raw["pending_settlement_rewards"][0]["quest"].pop(key)
        director.STATE_PATH.write_text(json.dumps(raw))
        loaded = director.load_state()
        self.assertEqual((loaded.communal_completions, loaded.private_completions, loaded.private_issued), (0, {}, {}))
        self.assertEqual(loaded.private_quests[quest.player].policy_version, 0)
        self.assertEqual(loaded.pending_settlement_rewards[0].source_snapshot, pending.source_snapshot)
        self.assertEqual(loaded.pending_settlement_rewards[0].consumption_commands, pending.consumption_commands)

    def test_invalid_state_progress_is_never_reset_without_settlements(self):
        for value in (-1, 4, True, "2", None):
            with self.subTest(value=value), patch.object(director, "SETTLEMENT_ENABLED", False):
                director.STATE_PATH.write_text(json.dumps({"communal_completions": value}))
                with self.assertRaises(ValueError):
                    director.load_state()
        for key, value in (("private_completions", {"Alex": True}),
                           ("private_completions", {"@a": 1}), ("private_issued", {"Alex": -1}),
                           ("private_issued", [])):
            with self.subTest(key=key, value=value):
                director.STATE_PATH.write_text(json.dumps({key: value}))
                with self.assertRaises(ValueError):
                    director.load_state()
        for change in ({"policy_version": True}, {"policy_version": 99}, {"mode": "easy"},
                       {"reference_band": "unknown"}, {"reference_band": None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                director.load_saved_quest(asdict(self.quest()) | change)

    def test_third_completion_transitions_only_its_lane_once_after_restart(self):
        quest = self.opening()
        self.world.chest_items[:] = [(0, "minecraft:pumpkin", 2)]
        state = director.State(private_quests={quest.player: quest}, communal_completions=1,
                               private_completions={quest.player: 2, "Alex": 0})
        director.complete_quest(state, quest)
        loaded = director.load_state()
        self.assertEqual(loaded.private_completions, {"CheekyHambone": 3, "Alex": 0})
        self.assertEqual(loaded.communal_completions, 1)
        director.process_pending_rewards(loaded, None)
        director.complete_quest(loaded, quest)
        self.assertEqual(loaded.private_completions[quest.player], 3)
        next_candidates = director.candidate_items("private", self.profile(), self.local_supply(), 100, state=loaded)
        self.assertEqual({candidate["band"] for candidate in next_candidates}, {"early"})
        alex = director.candidate_items("private", self.profile("Alex"), self.local_supply(), 100, state=loaded)
        self.assertEqual({candidate["mode"] for candidate in alex}, {"warmup"})

    def test_pending_success_credits_communal_with_no_settlement_manager(self):
        quest = self.opening(lane="communal")
        pending = director.PendingReward(quest, 0, consumption="done", recipients=["CheekyHambone"])
        state = director.State(communal_completions=2, pending_settlement_rewards=[pending])
        director.save_state(state)
        loaded = director.load_state()
        director.process_pending_rewards(loaded, None)
        self.assertEqual(loaded.communal_completions, 3)
        self.assertEqual(director.load_state().pending_settlement_rewards, [])
        director.process_pending_rewards(director.load_state(), None)
        self.assertEqual(director.load_state().communal_completions, 3)

    def test_pending_uncertainty_dryrun_and_disabled_settlement_debt_do_not_credit(self):
        for status, uncertain in (("prepared", False), ("uncertain", True), ("done", True)):
            quest = self.opening()
            pending = director.PendingReward(quest, 0, consumption=status, consumption_uncertain=uncertain)
            state = director.State(pending_settlement_rewards=[pending])
            director.process_pending_rewards(state, None)
            self.assertEqual(state.private_completions, {})
            self.assertEqual(state.pending_settlement_rewards, [pending])
        quest = self.opening()
        pending = director.PendingReward(quest, 0, consumption="done", recipients=[quest.player])
        state = director.State(pending_settlement_rewards=[pending])
        with patch.object(director, "DRY_RUN", True):
            director.process_pending_rewards(state, None)
        self.assertEqual(state.private_completions, {})
        quest.rewards = [{"type": "settlement_xp", "amount": 30}]
        director.process_pending_rewards(state, None)
        self.assertEqual(state.private_completions, {})
        self.assertEqual(state.pending_settlement_rewards, [pending])

    def test_lost_vanilla_response_never_advances_completion(self):
        quest = self.opening()
        pending = director.PendingReward(quest, 0, consumption="done", recipients=[quest.player])
        state = director.State(pending_settlement_rewards=[pending])
        with patch.object(director, "rcon", side_effect=OSError("lost reward response")):
            director.process_pending_rewards(state, None)
        loaded = director.load_state()
        director.process_pending_rewards(loaded, None)
        self.assertTrue(loaded.pending_settlement_rewards[0].vanilla_uncertain)
        self.assertEqual(loaded.private_completions, {})

    def test_reservations_include_offline_legacy_and_pending_deduplicated_ids(self):
        communal = self.opening(lane="communal", quest_id="group")
        offline = self.opening(player="Offline", item="minecraft:wheat", quest_id="offline")
        legacy = self.opening(item="minecraft:carrot", quest_id="legacy", legacy=True)
        pending = director.PendingReward(self.opening(item="minecraft:potato", quest_id="pending"), 0,
                                         consumption="uncertain")
        state = director.State(communal_quest=communal, private_quests={"Offline": offline},
                               active_quest=legacy, pending_settlement_rewards=[pending,
                               director.PendingReward(communal, 0, consumption="done")])
        expected = {"minecraft:pumpkin", "minecraft:wheat", "minecraft:carrot", "minecraft:potato"}
        self.assertEqual(director.reserved_items(state), expected)
        director.save_state(state)
        self.assertEqual(director.reserved_items(director.load_state()), expected)
        snapshot = self.local_supply({item: 30 for item in expected})
        self.assertEqual(director.candidate_items("communal", None, snapshot, 100, state=state), [])
        self.assertEqual(director.candidate_items("private", self.profile(), snapshot, 100, state=state), [])

    def test_stale_model_fallback_and_assignment_recheck_both_lane_directions(self):
        for existing_lane, new_lane in (("communal", "private"), ("private", "communal")):
            with self.subTest(existing_lane=existing_lane):
                state = director.State()
                profile = self.profile() if new_lane == "private" else None
                candidates = director.candidate_items(new_lane, profile, self.local_supply({"minecraft:pumpkin": 4}),
                                                      100, state=state)
                quest = director.fallback_quest(["CheekyHambone"], lane=new_lane, candidates=candidates, state=state)
                existing = self.opening(lane=existing_lane, quest_id="existing")
                if existing_lane == "communal":
                    state.communal_quest = existing
                else:
                    state.private_quests[existing.player] = existing
                raw = {"player": "CheekyHambone", "item": quest.item, "quantity": 2, "reward_tier": 1}
                with self.assertRaises(ValueError):
                    director.validate_quest(raw, ["CheekyHambone"], lane=new_lane, candidates=candidates, state=state)
                with self.assertRaises(ValueError):
                    director.fallback_quest(["CheekyHambone"], lane=new_lane, candidates=candidates, state=state)
                self.assertFalse(director.assign_quest(state, quest, candidates))
                self.assertEqual(state.private_issued, {})

    def test_colliding_completion_rejected_before_consumption_on_both_entrypoints(self):
        communal = self.opening(lane="communal", quest_id="group")
        personal = self.opening(quest_id="person")
        state = director.State(communal_quest=communal, private_quests={personal.player: personal})
        self.world.chest_items[:] = [(0, "minecraft:pumpkin", 10)]
        for quest in (communal, personal):
            director.complete_quest(state, quest)
            director.complete_settlement_quest(state, quest, None)
        self.assertEqual(state.pending_settlement_rewards, [])
        self.assertEqual(self.world.chest_items, [(0, "minecraft:pumpkin", 10)])
        self.assertFalse(any(c.startswith(("data remove ", "data modify ", "give ")) for c in self.world.commands))

    def test_personal_reference_ceiling_cadence_and_normal_fallback(self):
        state = director.State(private_completions={"CheekyHambone": 3}, private_issued={"CheekyHambone": 4})
        candidates = director.candidate_items("private", self.profile(score=100), self.local_supply(), 100, state=state)
        self.assertEqual({(c["band"], c["mode"], c["reference_band"]) for c in candidates},
                         {("established", "aspirational", "spawn_local")})
        candidates = director.candidate_items("private", self.profile(score=12), self.local_supply(), 12, state=state)
        self.assertEqual({(c["band"], c["mode"]) for c in candidates}, {("early", "long_term")})
        self.assertEqual(director.candidate_items("private", self.profile(score=0), self.local_supply(), 100,
                                                  state=state, communal_score=200), [])
        self.assertEqual(director.candidate_items("private", self.profile(confidence="limited"),
                                                  self.local_supply(), 100, state=state), [])
        for index, item in enumerate(["minecraft:gold_ingot", "minecraft:redstone", "minecraft:lapis_lazuli",
                                      "minecraft:diamond", "minecraft:emerald"]):
            state.private_quests[f"P{index}"] = self.opening(player=f"P{index}", item=item, quest_id=f"r{index}")
        fallback = director.candidate_items("private", self.profile(), self.local_supply(), 100, state=state)
        self.assertEqual({c["mode"] for c in fallback}, {"long_term"})
        state.communal_quest = self.quest()
        state.communal_quest.lane = "communal"
        state.communal_quest.player = director.COMMUNAL_PLAYER
        state.communal_quest.candidate_band = "endgame"
        self.assertEqual(director.candidate_items("private", self.profile(score=200), self.local_supply(),
                                                  200, state=state), [])
        self.assertEqual(state.private_issued, {"CheekyHambone": 4})

    def test_issued_sequence_and_frozen_metadata_saved_only_on_valid_assignment(self):
        profile = self.profile()
        state = director.State(private_completions={profile.player: 3}, private_issued={profile.player: 4})
        candidates = director.candidate_items("private", profile, self.local_supply(), 100, state=state)
        quest = director.fallback_quest([profile.player], candidates=candidates, state=state)
        with patch.object(director, "DRY_RUN", True):
            self.assertFalse(director.assign_quest(state, quest, candidates))
        self.assertEqual(state.private_issued[profile.player], 4)
        self.assertTrue(director.assign_quest(state, quest, candidates))
        loaded = director.load_state()
        self.assertEqual(loaded.private_issued[profile.player], 5)
        frozen = asdict(loaded.private_quests[profile.player])
        loaded.communal_completions = 3
        director.revalidate_legacy_quests(loaded, profiles={"Novice": self.profile("Novice", 0)},
                                         snapshots={True: self.local_supply({})})
        self.assertEqual(asdict(loaded.private_quests[profile.player]), frozen)
        self.assertIn("Aspirational longer-term", quest.announcement)
        self.assertIn(profile.player, quest.announcement)
        self.assertIn("shared normal temple offering chest", quest.announcement)

    def test_scheduler_communal_first_sorted_personals_and_same_cycle_reservations(self):
        profiles = {name: self.profile(name) for name in ("Zed", "Alex")}
        snapshot = self.local_supply({"minecraft:wheat": 12, "minecraft:pumpkin": 4, "minecraft:carrot": 5})
        state = director.State()
        with patch.object(director, "DEMO_MODE", True), patch.object(director.random, "choice", side_effect=lambda xs: xs[0]):
            assigned = director.schedule_quests(state, ["Zed", "Alex"], [], profiles=profiles, snapshots={True: snapshot})
        self.assertEqual([q.player for q in assigned], [director.COMMUNAL_PLAYER, "Alex", "Zed"])
        self.assertEqual(len({q.item for q in assigned}), 3)
        self.assertNotIn(director.COMMUNAL_PLAYER, assigned[0].announcement)
        self.assertIn("Everyone", assigned[0].announcement)
        self.assertTrue(all(q.quantity == director.QUEST_CATALOG[q.item]["min"] for q in assigned))
        self.assertEqual(state.private_issued, {})

    def test_existing_carrot_quantity_ten_retired_without_consuming_or_counting(self):
        quest = self.opening(lane="communal", item="minecraft:carrot", quantity=10, legacy=True)
        state = director.State(communal_quest=quest)
        self.world.chest_items[:] = [(0, "minecraft:carrot", 10), (1, "minecraft:stick", 2)]
        with patch.object(director, "supply_snapshot", return_value=self.local_supply({"minecraft:carrot": 20})):
            director.complete_quest(state, quest)
        self.assertIsNone(state.communal_quest)
        self.assertEqual(self.world.chest_items, [(0, "minecraft:carrot", 10), (1, "minecraft:stick", 2)])
        self.assertEqual(state.communal_completions, 0)
        self.assertEqual(state.pending_settlement_rewards, [])
        self.assertFalse(any(c.startswith(("give ", "data remove ", "data modify ")) for c in self.world.commands))
        self.assertTrue(any("catalog-minimum" in c for c in self.world.commands))

    def test_legacy_unknown_supply_suspends_and_validated_goal_survives_harvesting(self):
        quest = self.opening(lane="communal", legacy=True)
        state = director.State(communal_quest=quest)
        suspended = director.revalidate_legacy_quests(state, snapshots={True: self.local_supply(complete=False)})
        self.assertIn(quest.quest_id, suspended)
        self.assertIs(state.communal_quest, quest)
        self.assertFalse(director.STATE_PATH.exists())
        director.revalidate_legacy_quests(state, snapshots={True: self.local_supply()})
        self.assertEqual(quest.policy_version, director.QUEST_POLICY_VERSION)
        loaded = director.load_state()
        director.revalidate_legacy_quests(loaded, snapshots={True: self.local_supply({})})
        self.assertIsNotNone(loaded.communal_quest)
        self.assertEqual(loaded.communal_quest.quest_id, quest.quest_id)

    def test_legacy_duplicate_precedence_and_pending_intent_untouched(self):
        communal = self.opening(lane="communal", quest_id="group", legacy=True)
        alex = self.opening(player="Alex", quest_id="alex", legacy=True)
        zed = self.opening(player="Zed", item="minecraft:wheat", quest_id="zed", legacy=True)
        bob = self.opening(player="Bob", item="minecraft:wheat", quest_id="bob", legacy=True)
        state = director.State(communal_quest=communal, private_quests={"Zed": zed, "Bob": bob, "Alex": alex})
        director.revalidate_legacy_quests(state, snapshots={True: self.local_supply()})
        self.assertIs(state.communal_quest, communal)
        self.assertEqual(set(state.private_quests), {"Bob"})
        pending = director.PendingReward(
            communal, 0, consumption="uncertain", consumption_uncertain=True,
            consumption_commands=["data remove block 0 64 0 Items[0]"], recipients=["CheekyHambone"],
            source_snapshot={"slots": [{"slot": 0, "raw": "trusted"}]}, last_error="reconcile")
        competitor = self.opening(player="Other", quest_id="other", legacy=True)
        state.private_quests["Other"] = competitor
        state.pending_settlement_rewards.append(pending)
        preserved = asdict(pending)
        director.revalidate_legacy_quests(state, snapshots={True: self.local_supply(complete=False)})
        self.assertEqual(asdict(pending), preserved)
        self.assertNotIn("Other", state.private_quests)
        self.assertIs(state.communal_quest, communal)

    def test_main_recovers_pending_rewards_with_settlements_disabled(self):
        quest = self.opening()
        state = director.State(pending_settlement_rewards=[
            director.PendingReward(quest, 0, consumption="done", recipients=[quest.player])])
        with patch.object(director, "SETTLEMENT_ENABLED", False), patch.object(director, "RCON_PASSWORD", "test"), \
                patch.object(director, "load_state", return_value=state), \
                patch.object(director.LogTail, "read_new", return_value=[]), \
                patch.object(director, "schedule_quests", return_value=[]), \
                patch.object(director.time, "sleep", side_effect=KeyboardInterrupt):
            self.assertEqual(director.main(), 0)
        self.assertEqual(state.private_completions[quest.player], 1)
        self.assertEqual(state.pending_settlement_rewards, [])

    def test_supply_dry_run_and_legacy_load_do_not_flush_or_write_state(self):
        legacy = asdict(self.opening(legacy=True))
        legacy["submission"] = "ender_chest"
        director.STATE_PATH.write_text(json.dumps({"active_quest": legacy}))
        before = director.STATE_PATH.read_bytes()
        with patch.object(director, "DRY_RUN", True), patch.object(director, "AnvilWorldReader"), \
                patch.object(director, "rcon") as execute:
            director.supply_snapshot(warmup=True)
            director.load_state()
        execute.assert_not_called()
        self.assertEqual(director.STATE_PATH.read_bytes(), before)

    def test_absent_carrots_retire_and_reselect_without_touching_deposit(self):
        quest = self.opening(lane="communal", item="minecraft:carrot", legacy=True)
        state = director.State(communal_quest=quest)
        self.world.chest_items[:] = [(0, "minecraft:carrot", 10), (1, "minecraft:stick", 2)]
        director.revalidate_legacy_quests(state, snapshots={True: self.local_supply()})
        with patch.object(director, "DEMO_MODE", True):
            assigned = director.schedule_quests(
                state, ["CheekyHambone"], [], profiles={"CheekyHambone": self.profile()},
                snapshots={True: self.local_supply()})
        self.assertEqual(len(assigned), 2)
        self.assertEqual({q.item for q in assigned}, {"minecraft:wheat", "minecraft:pumpkin"})
        self.assertEqual(self.world.chest_items, [(0, "minecraft:carrot", 10), (1, "minecraft:stick", 2)])
        self.assertEqual(state.communal_completions, 0)
        self.assertEqual(state.private_completions, {})
        self.assertEqual(state.pending_settlement_rewards, [])

    def test_pending_uncertain_item_blocks_untouched_current_consumption(self):
        quest = self.opening(quest_id="new")
        old = self.opening(player="Offline", quest_id="old", legacy=True)
        pending = director.PendingReward(old, 0, consumption="uncertain",
                                         consumption_uncertain=True, last_error="manual reconciliation")
        state = director.State(private_quests={quest.player: quest}, pending_settlement_rewards=[pending])
        self.world.chest_items[:] = [(0, "minecraft:pumpkin", 10)]
        before = asdict(pending)
        director.complete_quest(state, quest)
        self.assertEqual(asdict(pending), before)
        self.assertEqual(self.world.chest_items, [(0, "minecraft:pumpkin", 10)])
        self.assertEqual(state.private_completions, {})
        self.assertFalse(any(c.startswith(("give ", "data remove ", "data modify ")) for c in self.world.commands))

    def test_communal_third_completion_and_saturation_select_progression_next(self):
        quest = self.opening(lane="communal")
        self.world.players[:] = ["CheekyHambone"]
        self.world.chest_items[:] = [(0, "minecraft:pumpkin", 2)]
        state = director.State(communal_quest=quest, communal_completions=2)
        director.complete_quest(state, quest)
        candidates = director.candidate_items("communal", None, self.local_supply(), 35, state=state)
        self.assertEqual({(c["band"], c["mode"]) for c in candidates}, {("established", "communal")})
        personal = director.candidate_items("private", self.profile(), self.local_supply(), 100, state=state)
        self.assertEqual({c["mode"] for c in personal}, {"warmup"})
        another = self.opening(lane="communal", quest_id="another")
        pending = director.PendingReward(another, 0, consumption="done", recipients=["CheekyHambone"])
        state.pending_settlement_rewards.append(pending)
        director.process_pending_rewards(state, None)
        self.assertEqual(director.load_state().communal_completions, 3)

    def test_scheduler_defer_keeps_postwarmup_sequence_and_announces_after_save(self):
        state = director.State(private_completions={"CheekyHambone": 3},
                               private_issued={"CheekyHambone": 4},
                               last_communal_quest_at=director.time.time())
        assigned = director.schedule_quests(state, ["CheekyHambone"], [],
                                             profiles={"CheekyHambone": self.profile(score=0)},
                                             snapshots={False: self.local_supply()})
        self.assertEqual(assigned, [])
        self.assertEqual(state.private_issued, {"CheekyHambone": 4})
        state.private_quest_at.clear()
        seen = []
        def announce_after_save(text):
            loaded = director.load_state()
            seen.append((text, loaded.private_issued["CheekyHambone"],
                         loaded.private_quests["CheekyHambone"].mode))
        with patch.object(director, "DEMO_MODE", True), \
                patch.object(director, "announce", side_effect=announce_after_save):
            assigned = director.schedule_quests(state, ["CheekyHambone"], [],
                                                 profiles={"CheekyHambone": self.profile()},
                                                 snapshots={False: self.local_supply()})
        self.assertEqual(len(assigned), 1)
        self.assertEqual(seen[0][1:], (5, "aspirational"))
        self.assertIn("CheekyHambone", seen[0][0])

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
