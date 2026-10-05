"""Zero-delay completion succession with durable entitlements and economy caps."""
from pathlib import Path
import tempfile
import unittest

from mc_director.bridge import uuid_to_ints
from mc_director.config import Config
from mc_director.engine import Engine
from mc_director.rules import EventContext, candidates
from mc_director.state import Store, dumps, loads


PLAYER = "01234567-89ab-cdef-0123-456789abcdef"


class CommunityBridge:
    """Ready community whose full Ender Chest cannot accept its old reward."""
    def __init__(self):
        self.revision = 1

    def request(self, action, payload, **kwargs):
        if action == "ACTIVATE":
            self.revision += 1
        result = {}
        status = "OK"
        if action == "SNAPSHOT":
            result = {"epoch": 1, "registered": 1, "chest_valid": 1, "count": 0,
                      "players": [{"name": "Player", "uuid": uuid_to_ints(PLAYER), "eligible": 1}]}
        elif action == "PAY":
            status = "NO_SPACE"
        return {"status": status, "revision": self.revision, "payload": result}


class SuccessionTests(unittest.TestCase):
    def test_zero_cooldown_is_valid_but_other_timer_and_type_bounds_remain(self):
        self.assertEqual(Config(cooldown_seconds=0).cooldown_seconds, 0)
        for value in (-1, True, False, float("nan"), float("inf"), 604801, "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Config(cooldown_seconds=value)
        for field in ("quest_expiry_seconds", "poll_seconds", "reward_retry_seconds"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                Config(**{field: 0})

    def completed_community(self, directory, cap=12):
        config = Config(db_path=Path(directory) / "director.sqlite3", cooldown_seconds=0,
                        demo_mode=True, max_quests_per_day=cap)
        store = Store(config.db_path, config.public())
        engine = Engine(config, CommunityBridge())
        engine.store = store
        engine.events = EventContext(store.server["installation_id"])
        engine.started = engine.connected = engine.healthy = True
        engine.epoch, engine.session, engine.revision = 1, "a" * 32, 1
        engine.eligible = engine.online = {PLAYER}
        engine.snapshot = {"registered": 1, "chest_valid": 1, "count": 6}
        store.execute("INSERT INTO chests VALUES(1,?,'minecraft:overworld',2,64,2,0)",
                      (store.server["installation_id"],))
        old_id = "b" * 32
        choice = candidates(config, 1, seed="succession", explicit=("minecraft:iron_ingot", 6))[0]
        store.execute("INSERT INTO quests(id,revision,status,objective,reward,title,flavor,source,config,remaining,created) VALUES(?,1,'ACTIVE',?,?,'Offering','Local','local',?,7200,1)",
                      (old_id, dumps(choice["objective"]), dumps(choice["reward"]), dumps(config.public())))
        store.execute("UPDATE server_state SET active_quest=? WHERE id=1", (old_id,))
        store.reserve(engine._day(), "activations", cap)
        engine.quest = engine._decode_quest(store.one("SELECT * FROM quests WHERE id=?", (old_id,)))
        request = {"action": "COMPLETE", "payload": {"quest_id": old_id, "item_code": choice["objective"]["code"], "quantity": 6}}
        operation = store.prepare("COMPLETE", "chest", 1, engine.session, 1, request, quest_id=old_id)
        store.operation_update(operation["id"], "APPLIED", checkpoint={"acknowledged": True, "token": "c" * 32})
        engine._commit_complete(operation, {"status": "APPLIED", "payload": {"consumed": 6, "recipients": [{"uuid": uuid_to_ints(PLAYER)}]}})
        return engine, store, old_id, choice

    def test_completion_immediately_schedules_one_next_quest_without_waiting_for_full_reward(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, store, old_id, choice = self.completed_community(directory)
            try:
                self.assertEqual(store.one("SELECT status FROM quests WHERE id=?", (old_id,))["status"], "COMPLETED")
                self.assertEqual(engine.cooldown, 0)
                engine.tick(now=100)
                next_id = engine.quest["id"]
                self.assertNotEqual(next_id, old_id)
                engine.tick(now=100.1)
                engine.tick(now=100.2)
                self.assertEqual(engine.quest["id"], next_id)
                self.assertEqual(engine.quest["status"], "ACTIVE")
                self.assertEqual(store.one("SELECT COUNT(*) AS n FROM quests")["n"], 2)
                reward = store.one("SELECT * FROM entitlements WHERE quest_id=?", (old_id,))
                self.assertEqual(reward["status"], "WAITING_SPACE")
                self.assertEqual(loads(reward["reward"]), choice["reward"])
                self.assertEqual(store.one("SELECT activations FROM daily_caps")["activations"], 2)
            finally:
                engine.executor.shutdown(wait=False, cancel_futures=True)
                store.close()

    def test_daily_activation_limit_still_blocks_immediate_successor(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, store, old_id, _ = self.completed_community(directory, cap=1)
            try:
                engine.tick(now=100)
                engine.tick(now=100.1)
                self.assertIsNone(engine.quest)
                self.assertEqual(store.one("SELECT COUNT(*) AS n FROM quests")["n"], 1)
                self.assertEqual(store.one("SELECT status FROM quests WHERE id=?", (old_id,))["status"], "COMPLETED")
                self.assertEqual(store.one("SELECT activations FROM daily_caps")["activations"], 1)
            finally:
                engine.executor.shutdown(wait=False, cancel_futures=True)
                store.close()


if __name__ == "__main__":
    unittest.main()
