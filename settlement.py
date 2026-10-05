"""Conservative, durable settlement construction using only trusted templates.

World inspection requires English vanilla command responses. Existing buildings
are compared against exact recorded block predicates; inventories, signs and beds
are deliberately unsupported. An interrupted mutation is never retried.
"""
import contextlib
import copy
import json
import logging
import os
import re
import sqlite3
import time
from pathlib import Path


class BuildingError(ValueError):
    pass


_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_RESOURCE = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")
_BLOCK = re.compile(r"^minecraft:[a-z0-9_]+(?:\[[a-z0-9_=,]+\])?$")
_PLAYER = re.compile(r"^[A-Za-z0-9_]{1,16}$")
_LIST = re.compile(r"^There are \d+ of a max of \d+ players online:(?:.*)$", re.S)
_AIR = ("minecraft:air", "minecraft:cave_air", "minecraft:void_air")
_COLORS = ("white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray", "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black")
_SENSITIVE_BLOCKS = tuple("minecraft:" + name for name in (
    "chest", "trapped_chest", "barrel", "shulker_box", "furnace", "blast_furnace", "smoker",
    "beacon", "enchanting_table", "anvil", "chipped_anvil", "damaged_anvil", "hopper",
    "dispenser", "dropper", "brewing_stand", "lectern", "beehive", "bee_nest", "crafter",
)) + tuple("minecraft:" + color + suffix for color in _COLORS for suffix in ("_shulker_box", "_bed")) + tuple(
    "minecraft:" + wood + suffix
    for wood in ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry", "bamboo", "crimson", "warped")
    for suffix in ("_sign", "_wall_sign", "_hanging_sign", "_wall_hanging_sign")
)
_ROTATIONS = {"north": "none", "east": "clockwise_90", "south": "clockwise_180", "west": "counterclockwise_90"}
_LOG = logging.getLogger(__name__)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _require(test, message):
    if not test:
        raise BuildingError(message)


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def _constant(value):
    raise BuildingError("Nonfinite JSON number: " + value)


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _keys(value, required, optional=()):
    _require(isinstance(value, dict), "Expected an object")
    _require(set(required) <= value.keys() and not (value.keys() - set(required) - set(optional)), "Missing or unknown configuration fields")


def _text(value, limit=256):
    return isinstance(value, str) and len(value) <= limit and not any(ord(c) < 32 for c in value)


def _box(plot):
    p, s = plot["position"], plot["size"]
    return (p["x"], p["y"], p["z"], p["x"] + s["width"] - 1, p["y"] + s["height"] - 1, p["z"] + s["depth"] - 1)


def _overlap(a, b):
    return all(a[i] <= b[i + 3] and b[i] <= a[i + 3] for i in range(3))


class StructureManager:
    def __init__(self, registry_path, settlement_path, database_path, command, *, dry_run=False, clock=time.time):
        self.command, self.dry_run, self.clock = command, bool(dry_run), clock
        try:
            with open(registry_path, encoding="utf-8") as stream:
                registry = json.load(stream, object_pairs_hook=_object, parse_constant=_constant)
            with open(settlement_path, encoding="utf-8") as stream:
                config = json.load(stream, object_pairs_hook=_object, parse_constant=_constant)
        except (OSError, ValueError) as exc:
            raise BuildingError("Cannot read settlement configuration: " + str(exc)) from exc
        _keys(registry, ("structures",))
        self.registry = registry["structures"]
        self.config = config
        try:
            self._validate_config()
        except (TypeError, KeyError, OverflowError) as exc:
            raise BuildingError("Malformed settlement configuration: " + str(exc)) from exc
        self.settings = config["settlement"]
        self.sid = self.settings["world_id"] + ":" + self.settings["id"]
        self.db = sqlite3.connect(":memory:" if self.dry_run else database_path, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        if self.dry_run and os.path.isfile(database_path):
            source = sqlite3.connect(Path(database_path).resolve().as_uri() + "?mode=ro", uri=True)
            try:
                source.backup(self.db)
            finally:
                source.close()
        try:
            self._schema()
            self._reconcile()
        except Exception:
            self.db.close()
            raise

    def _validate_config(self):
        c = self.config
        _keys(c, ("settlement", "plots", "levels", "protected_regions", "quest_rewards"))
        s = c["settlement"]
        _keys(s, ("id", "display_name", "world_id", "dimension", "origin", "enabled", "initialize_on_first_run", "starter_structures"))
        _require(isinstance(s["id"], str) and _ID.fullmatch(s["id"]), "Invalid settlement ID")
        _require(_text(s["world_id"], 128) and bool(s["world_id"]), "Invalid world identity")
        _require(_text(s["display_name"]) and bool(s["display_name"]), "Invalid display name")
        _require(isinstance(s["dimension"], str) and _RESOURCE.fullmatch(s["dimension"]), "Invalid dimension")
        self._position(s["origin"])
        _require(type(s["enabled"]) is bool and type(s["initialize_on_first_run"]) is bool, "Flags must be booleans")
        _require(isinstance(self.registry, dict) and bool(self.registry), "Structures must be a nonempty mapping")
        for sid, d in self.registry.items():
            _require(isinstance(sid, str) and _ID.fullmatch(sid), "Invalid structure ID")
            _keys(d, ("display_name", "category", "template", "footprint", "allowed_plots", "progression", "unlocks"), ("stages", "template_blocks", "repeatable"))
            _require(type(d.get("repeatable", False)) is bool, "Invalid repeatable flag")
            _require(_text(d["display_name"]) and _text(d["category"]) and bool(d["category"]), "Invalid structure text")
            self._template(d["template"])
            self._size(d["footprint"])
            self._strings(d["allowed_plots"])
            self._strings(d["unlocks"])
            _require(isinstance(d["progression"], dict), "Invalid structure progression")
            d["progression"].setdefault("upgrades_from", [])
            _keys(d["progression"], ("tier", "upgrades_from"))
            _require(_integer(d["progression"]["tier"], 1), "Invalid structure tier")
            self._strings(d["progression"]["upgrades_from"])
            stages = d.get("stages", [])
            _require(isinstance(stages, list), "Stages must be a list")
            for stage in stages:
                _keys(stage, ("template", "delay_seconds"))
                self._template(stage["template"])
                _require(type(stage["delay_seconds"]) in (int, float) and 0 <= stage["delay_seconds"] <= 31536000, "Invalid stage delay")
            _require(not stages or stages[-1]["template"] == d["template"], "Final stage must use final template")
            palette = d.get("template_blocks", [])
            _require(isinstance(palette, list), "Invalid template palette")
            for block in palette:
                _require(isinstance(block, str) and _BLOCK.fullmatch(block), "Invalid block predicate")
                _require(not self._sensitive(block), "Sensitive blocks cannot be safely managed")
                base = block.split("[")[0]
                # The supported stateless palette plus complete oak-log predicates.
                _require(base in _AIR + ("minecraft:oak_planks", "minecraft:cobblestone", "minecraft:glass", "minecraft:torch", "minecraft:oak_log"), "Unsupported exact-state palette")
                if base == "minecraft:oak_log" and "[" in block:
                    _require(block in tuple("minecraft:oak_log[axis=" + a + "]" for a in "xyz"), "Incomplete log state")
                elif base != "minecraft:oak_log":
                    _require("[" not in block, "Unexpected block states")
        for d in self.registry.values():
            _require(all(x in self.registry for x in d["progression"]["upgrades_from"]), "Unknown upgrade predecessor")
        _require(isinstance(c["plots"], dict), "Plots must be a mapping")
        for pid, p in c["plots"].items():
            _require(isinstance(pid, str) and _ID.fullmatch(pid), "Invalid plot ID")
            _keys(p, ("position", "size", "facing", "categories"), ("protected",))
            self._position(p["position"])
            self._size(p["size"])
            _require(isinstance(p["facing"], str) and p["facing"] in _ROTATIONS, "Invalid plot facing")
            self._strings(p["categories"])
            _require(type(p.get("protected", False)) is bool, "Invalid plot protection")
        plots = list(c["plots"].values())
        for i, p in enumerate(plots):
            _require(not any(_overlap(_box(p), _box(q)) for q in plots[i + 1:]), "Overlapping plots")
        _require(isinstance(c["protected_regions"], list), "Invalid protected regions")
        for region in c["protected_regions"]:
            _keys(region, ("min", "max"))
            self._position(region["min"])
            self._position(region["max"])
            bounds = tuple(region[edge][axis] for edge in ("min", "max") for axis in "xyz")
            _require(all(bounds[i] <= bounds[i + 3] for i in range(3)), "Invalid protected region bounds")
            _require(not any(_overlap(bounds, _box(p)) for p in plots), "Plot overlaps protected region")
        _require(isinstance(c["levels"], dict) and bool(c["levels"]), "Missing levels")
        previous = -1
        _require(all(isinstance(k, str) and re.fullmatch(r"[1-9][0-9]{0,3}", k) for k in c["levels"]), "Invalid level key")
        numbers = sorted(int(k) for k in c["levels"])
        _require(numbers == list(range(1, len(numbers) + 1)), "Levels must be consecutive from 1")
        for n in numbers:
            level = c["levels"][str(n)]
            _keys(level, ("name", "xp_required", "unlocks"))
            _require(_text(level["name"]) and _integer(level["xp_required"]) and level["xp_required"] > previous, "Invalid level")
            previous = level["xp_required"]
            self._strings(level["unlocks"])
            _require(all(x in self.registry for x in level["unlocks"]), "Unknown level unlock")
        _require(c["levels"]["1"]["xp_required"] == 0, "First level must require zero XP")
        _require(isinstance(c["quest_rewards"], dict), "Invalid quest rewards")
        for tier, rewards in c["quest_rewards"].items():
            _require(isinstance(tier, str) and tier.isdigit() and int(tier) > 0 and isinstance(rewards, list), "Invalid reward tier")
            for reward in rewards:
                _require(isinstance(reward, dict), "Invalid reward")
                if reward.get("type") == "settlement_xp":
                    _keys(reward, ("type", "amount"))
                    _require(_integer(reward["amount"], 1), "Invalid XP reward")
                else:
                    _keys(reward, ("type", "structure_id"))
                    _require(reward["type"] == "structure" and reward["structure_id"] in self.registry, "Invalid structure reward")
        _require(isinstance(s["starter_structures"], list), "Invalid starters")
        for starter in s["starter_structures"]:
            if isinstance(starter, str):
                _require(starter in self.registry, "Unknown starter")
            else:
                _keys(starter, ("structure_id",), ("plot_id", "owner"))
                _require(starter["structure_id"] in self.registry and (starter.get("plot_id") is None or starter["plot_id"] in c["plots"]), "Unknown starter target")
                self._owner(starter.get("owner"))

    @staticmethod
    def _position(p):
        _keys(p, ("x", "y", "z"))
        _require(all(type(p[k]) is int and abs(p[k]) <= 30000000 for k in "xyz") and -64 <= p["y"] <= 319, "Invalid coordinates")

    @staticmethod
    def _size(s):
        _keys(s, ("width", "depth", "height"))
        _require(all(_integer(v, 1) and v <= 128 for v in s.values()) and s["width"] * s["depth"] * s["height"] <= 32768, "Invalid or excessive volume")

    @staticmethod
    def _strings(values):
        _require(isinstance(values, list) and all(_text(x, 128) and x for x in values) and len(values) == len(set(values)), "Invalid string list")

    @staticmethod
    def _template(value):
        _require(isinstance(value, str) and _RESOURCE.fullmatch(value) and ".." not in value, "Invalid template resource")

    @staticmethod
    def _owner(owner):
        _require(owner is None or isinstance(owner, str) and _PLAYER.fullmatch(owner), "Invalid owner")

    @staticmethod
    def _sensitive(block):
        return block.split("[", 1)[0] in _SENSITIVE_BLOCKS

    def _history(self, action, structure_id, plot_id, owner, reason, quest_id, success, error=None):
        self.db.execute("INSERT INTO construction_history(settlement,action,plot_id,structure_id,owner,reason,quest_id,timestamp,success,error) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (self.sid, action, plot_id, structure_id, owner, reason, quest_id, self.clock(), int(success), error))

    @contextlib.contextmanager
    def _transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _schema(self):
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS settlements (id TEXT PRIMARY KEY, config TEXT NOT NULL, xp INTEGER NOT NULL DEFAULT 0, initialized INTEGER NOT NULL DEFAULT 0, initialization_started INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS plots (settlement TEXT NOT NULL, id TEXT NOT NULL, config TEXT NOT NULL, status TEXT NOT NULL, structure_id TEXT, owner TEXT, snapshot TEXT, definition TEXT, PRIMARY KEY(settlement,id));
        CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, settlement TEXT NOT NULL, plot_id TEXT NOT NULL, structure_id TEXT NOT NULL, definition TEXT NOT NULL, geometry TEXT NOT NULL, owner TEXT, reason TEXT NOT NULL, quest_id TEXT, action TEXT NOT NULL, stage INTEGER NOT NULL DEFAULT 0, due REAL NOT NULL, status TEXT NOT NULL, error TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS job_quest ON jobs(settlement,quest_id) WHERE quest_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS structures (instance_id INTEGER PRIMARY KEY, settlement_id TEXT NOT NULL, structure_id TEXT NOT NULL, plot_id TEXT NOT NULL, owner_player TEXT, tier INTEGER NOT NULL, created_at REAL NOT NULL, reason TEXT NOT NULL, quest_id TEXT, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS construction_history (id INTEGER PRIMARY KEY, settlement TEXT NOT NULL, action TEXT NOT NULL, plot_id TEXT NOT NULL, structure_id TEXT NOT NULL, owner TEXT, reason TEXT NOT NULL, quest_id TEXT, timestamp REAL NOT NULL, success INTEGER NOT NULL, error TEXT);
        CREATE TABLE IF NOT EXISTS quests (settlement TEXT NOT NULL, id TEXT NOT NULL, player TEXT NOT NULL, title TEXT NOT NULL, timestamp REAL NOT NULL, PRIMARY KEY(settlement,id));
        CREATE TABLE IF NOT EXISTS xp_ledger (settlement TEXT NOT NULL, quest_id TEXT NOT NULL, amount INTEGER NOT NULL, PRIMARY KEY(settlement,quest_id));
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, settlement TEXT NOT NULL, payload TEXT NOT NULL, timestamp REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS removal_history (id INTEGER PRIMARY KEY, settlement TEXT NOT NULL, plot_id TEXT NOT NULL, geometry TEXT NOT NULL, snapshot TEXT NOT NULL, status TEXT NOT NULL, error TEXT, timestamp REAL NOT NULL);
        PRAGMA user_version=1;
        """)

    def _reconcile(self):
        with self._transaction():
            row = self.db.execute("SELECT * FROM settlements WHERE id=?", (self.sid,)).fetchone()
            oldplots = self.db.execute("SELECT * FROM plots WHERE settlement=?", (self.sid,)).fetchall()
            if row:
                old = json.loads(row["config"])
                active = any(p["status"] != "available" for p in oldplots)
                _require(not active or old["settlement"]["dimension"] == self.settings["dimension"], "Cannot change active settlement dimension")
                _require(old["levels"] == self.config["levels"] or not active and row["xp"] == 0, "Cannot change progression of an active settlement")
                _require(not row["initialization_started"] or old["settlement"]["starter_structures"] == self.settings["starter_structures"], "Cannot change initialized starters")
                self.db.execute("UPDATE settlements SET config=? WHERE id=?", (_json(self.config), self.sid))
            else:
                self.db.execute("INSERT INTO settlements(id,config,created_at) VALUES (?,?,?)", (self.sid, _json(self.config), self.clock()))
            for old in oldplots:
                new = self.config["plots"].get(old["id"])
                if old["status"] != "available":
                    _require(new is not None and _json(new) == old["config"], "Cannot change occupied, reserved or protected plot")
                    if old["definition"]:
                        _require(self.registry.get(old["structure_id"]) == json.loads(old["definition"]), "Cannot change active structure definition")
                if new is None:
                    self.db.execute("DELETE FROM plots WHERE settlement=? AND id=?", (self.sid, old["id"]))
            for pid, p in self.config["plots"].items():
                old = next((r for r in oldplots if r["id"] == pid), None)
                if old is None:
                    self.db.execute("INSERT INTO plots(settlement,id,config,status) VALUES (?,?,?,?)", (self.sid, pid, _json(p), "protected" if p.get("protected") else "available"))
                elif old["status"] == "available":
                    self.db.execute("UPDATE plots SET config=?,status=? WHERE settlement=? AND id=?", (_json(p), "protected" if p.get("protected") else "available", self.sid, pid))
            for job in self.db.execute("SELECT * FROM jobs WHERE settlement=? AND status IN ('queued','executing')", (self.sid,)):
                _require(self.registry.get(job["structure_id"]) == json.loads(job["definition"]) and self.config["plots"].get(job["plot_id"]) == json.loads(job["geometry"]), "Cannot change durable job definitions")

    def _enabled(self):
        _require(self.settings["enabled"], "Settlement is disabled")
        _require(not self.settings["world_id"].startswith("CHANGE_ME"), "Configure a unique world identity before enabling settlement")
        _require(json.loads(self._settlement_row()["config"]) == self.config, "Settlement configuration changed; reopen manager")

    def _settlement_row(self):
        return self.db.execute("SELECT * FROM settlements WHERE id=?", (self.sid,)).fetchone()

    def _level(self, xp):
        return max(int(k) for k, v in self.config["levels"].items() if xp >= v["xp_required"])

    def _unlocked(self):
        level = self._level(self._settlement_row()["xp"])
        return sorted({sid for key, d in self.config["levels"].items() if int(key) <= level for sid in d["unlocks"]})

    def _plot(self, pid):
        _require(isinstance(pid, str) and _ID.fullmatch(pid), "Invalid plot ID")
        row = self.db.execute("SELECT * FROM plots WHERE settlement=? AND id=?", (self.sid, pid)).fetchone()
        _require(row is not None, "Unknown plot")
        return row

    def _definition(self, sid):
        _require(isinstance(sid, str) and sid in self.registry, "Unknown structure")
        _require(sid in self._unlocked(), "Structure is locked")
        return self.registry[sid]

    def _fit(self, d, p):
        w, z, h = (d["footprint"][k] for k in ("width", "depth", "height"))
        if p["facing"] in ("east", "west"):
            w, z = z, w
        _require(w <= p["size"]["width"] and z <= p["size"]["depth"] and h <= p["size"]["height"], "Structure does not fit plot")
        _require(p["position"]["y"] + p["size"]["height"] <= 320, "Plot exceeds world height")
        _require(bool(set(p["categories"]) & set(d["allowed_plots"])), "Structure not allowed on plot")
        _require(not p.get("protected"), "Plot is protected")

    def _placement_command(self, definition, plot, template):
        x, y, z = (plot["position"][k] for k in "xyz")
        w, depth = definition["footprint"]["width"], definition["footprint"]["depth"]
        facing = plot["facing"]
        if facing == "east":
            x += depth - 1
        elif facing == "south":
            x += w - 1
            z += depth - 1
        elif facing == "west":
            z += w - 1
        return self._mutation_prefix(plot) + f" run place template {template} {x} {y} {z} {_ROTATIONS[facing]} none 1.0 0"

    def _mutation_prefix(self, plot):
        bx, by, bz, xx, yy, zz = _box(plot)
        guard = f"unless entity @a[x={bx},y={by},z={bz},dx={xx-bx},dy={yy-by},dz={zz-bz}]"
        loaded = " ".join(f"if loaded {cx * 16} {by} {cz * 16}" for cx in range(bx // 16, xx // 16 + 1) for cz in range(bz // 16, zz // 16 + 1))
        return f"execute in {self.settings['dimension']} {loaded} {guard}"

    def _query(self, condition):
        response = self.command(f"execute in {self.settings['dimension']} {condition} run list")
        return isinstance(response, str) and _LIST.fullmatch(response.strip()) is not None

    def _environment(self, plot):
        x, y, z, xx, yy, zz = _box(plot)
        for cx in range(x // 16, xx // 16 + 1):
            for cz in range(z // 16, zz // 16 + 1):
                _require(self._query(f"if loaded {cx * 16} {y} {cz * 16}"), "Plot chunk is not affirmatively loaded")
        selector = f"@a[x={x},y={y},z={z},dx={xx-x},dy={yy-y},dz={zz-z}]"
        _require(self._query("unless entity " + selector), "Player safety exclusion could not be confirmed")

    @staticmethod
    def _coordinates(plot):
        x, y, z, xx, yy, zz = _box(plot)
        for by in range(y, yy + 1):
            for bz in range(z, zz + 1):
                for bx in range(x, xx + 1):
                    yield bx, by, bz

    def _scan(self, plot, definition=None, expected=None):
        self._environment(plot)
        palette = list(_AIR)
        if definition:
            for block in definition.get("template_blocks", []):
                if block == "minecraft:oak_log":
                    block = "minecraft:oak_log[axis=y]"
                if block not in palette:
                    palette.append(block)
        coordinates = list(self._coordinates(plot))
        _require(expected is None or len(expected) == len(coordinates), "Invalid durable block snapshot")
        states = []
        for i, (x, y, z) in enumerate(coordinates):
            candidates = [expected[i]] if expected is not None else palette
            found = next((block for block in candidates if not self._sensitive(block) and self._query(f"if block {x} {y} {z} {block}")), None)
            if found is None:
                sensitive = next((block for block in _SENSITIVE_BLOCKS if self._query(f"if block {x} {y} {z} {block}")), None)
                reason = "sensitive_block_detected" if sensitive else "unexpected_or_unreadable_block"
                self._log("placement_rejected", reason=reason, block=sensitive, position={"x": x, "y": y, "z": z})
                raise BuildingError(f"{reason}: {sensitive or 'unknown'} at {x} {y} {z}")
            states.append(found)
        return states

    def _log(self, event, **fields):
        _LOG.info(_json({"event": event, "settlement": self.sid, **fields}))

    def _event(self, event):
        self.db.execute("INSERT INTO events(settlement,payload,timestamp) VALUES (?,?,?)", (self.sid, _json(event), self.clock()))
        return event

    @staticmethod
    def _completion_commands(definition, owner):
        return [
            "tellraw @a " + _json({"text": "[The Keeper] " + definition["display_name"] + " completed" + (" for " + owner if owner else "") + ".", "color": "gold"}),
            "title @a title " + _json({"text": "THE " + definition["display_name"].upper() + " IS COMPLETE", "color": "gold", "bold": True}),
        ]

    def _prepare(self, sid, pid, owner, reason, quest_id, upgrading):
        self._enabled()
        self._owner(owner)
        _require(_text(reason, 256), "Invalid reason")
        _require(quest_id is None or _text(quest_id, 256) and bool(quest_id), "Invalid quest ID")
        d = self._definition(sid)
        if quest_id is not None:
            old = self.db.execute("SELECT * FROM jobs WHERE settlement=? AND quest_id=?", (self.sid, quest_id)).fetchone()
            if old:
                effective_owner = self._plot(pid)["owner"] if upgrading and owner is None else owner
                _require(old["structure_id"] == sid and (pid is None or old["plot_id"] == pid) and old["owner"] == effective_owner and old["action"] == ("upgrade" if upgrading else "construct"), "Quest reward conflicts with existing job")
                if old["status"] != "rejected":
                    return old, True
                # Rejected before dispatch: safe to retry, unlike uncertain mutation.
                self.db.execute("DELETE FROM jobs WHERE id=?", (old["id"],))
        if pid is None:
            _require(not upgrading, "Upgrade needs plot")
            for candidate in self.db.execute("SELECT * FROM plots WHERE settlement=? AND status='available' ORDER BY id", (self.sid,)):
                try:
                    self._fit(d, json.loads(candidate["config"]))
                except BuildingError:
                    continue
                pid = candidate["id"]
                break
            _require(pid is not None, "No compatible available plot")
        row = self._plot(pid)
        p = json.loads(row["config"])
        self._fit(d, p)
        self._log("plot_selected", structure_id=sid, plot_id=pid, rotation=_ROTATIONS[p["facing"]])
        if upgrading:
            _require(row["status"] == "occupied", "Plot is not occupied")
            _require(row["snapshot"] is not None and row["definition"] is not None, "Missing original block snapshot")
            _require(row["structure_id"] in d["progression"]["upgrades_from"], "Invalid upgrade path")
            _require(d["progression"]["tier"] > self.registry[row["structure_id"]]["progression"]["tier"], "Upgrade must increase tier")
            _require(owner is None or owner == row["owner"], "Owner does not own this building")
            owner = row["owner"]
        else:
            _require(row["status"] == "available", "Plot is unavailable")
        existing = self.db.execute("""
            SELECT id,owner FROM plots WHERE settlement=? AND structure_id=? AND status!='available' AND id!=?
            UNION
            SELECT p.id,j.owner FROM jobs j JOIN plots p ON p.settlement=j.settlement AND p.id=j.plot_id
            WHERE j.settlement=? AND j.structure_id=? AND j.status IN ('queued','executing','failed')
              AND p.status!='available' AND p.id!=?
        """, (self.sid, sid, pid, self.sid, sid, pid)).fetchall()
        _require(not existing or d.get("repeatable", False) and all(r["owner"] != owner for r in existing), "Structure already built or reserved for this owner")
        stages = d.get("stages") or [{"template": d["template"], "delay_seconds": 0}]
        commands = [self._placement_command(d, p, stage["template"]) for stage in stages] + self._completion_commands(d, owner)
        self._scan(p, json.loads(row["definition"]) if upgrading else None, json.loads(row["snapshot"]) if upgrading and row["snapshot"] else None)
        self._log("plot_clear", structure_id=sid, plot_id=pid)
        if self.dry_run:
            self._log("construction_preview", commands=commands, mutation=False)
            return {"success": True, "dry_run": True, "commands": commands, "plot_id": pid, "structure_id": sid, "pending": len(stages) > 1}, True
        self.db.execute("UPDATE plots SET status=? WHERE settlement=? AND id=?", ("upgrading" if upgrading else "reserved", self.sid, pid))
        cursor = self.db.execute("INSERT INTO jobs(settlement,plot_id,structure_id,definition,geometry,owner,reason,quest_id,action,due,status) VALUES (?,?,?,?,?,?,?,?,?,?,'queued')", (self.sid, pid, sid, _json(d), _json(p), owner, reason, quest_id, "upgrade" if upgrading else "construct", self.clock()))
        return self.db.execute("SELECT * FROM jobs WHERE id=?", (cursor.lastrowid,)).fetchone(), False

    def _result(self, job):
        d, p = json.loads(job["definition"]), json.loads(job["geometry"])
        stages = d.get("stages") or [{"template": d["template"], "delay_seconds": 0}]
        return {"success": job["status"] in ("queued", "complete"), "dry_run": self.dry_run, "commands": [self._placement_command(d, p, s["template"]) for s in stages] + self._completion_commands(d, job["owner"]), "plot_id": job["plot_id"], "structure_id": job["structure_id"], "pending": job["status"] == "queued", "error": job["error"]}

    def _submit(self, sid, pid, owner, reason, quest_id, upgrading):
        self._log("construction_requested", structure_id=sid, plot_id=pid, owner=owner, reason=reason)
        try:
            with self._transaction():
                job, existing = self._prepare(sid, pid, owner, reason, quest_id, upgrading)
        except (BuildingError, OSError, RuntimeError) as exc:
            self._log("placement_rejected", structure_id=sid, plot_id=pid, error=str(exc))
            if not self.dry_run:
                with self._transaction():
                    self._history("upgrade" if upgrading else "construct", str(sid), str(pid or ""),
                                  owner if isinstance(owner, str) else None, str(reason)[:256],
                                  quest_id if isinstance(quest_id, str) else None, False, str(exc))
            if isinstance(exc, BuildingError):
                raise
            raise BuildingError(str(exc)) from exc
        if isinstance(job, dict):
            return job
        if not existing and job["due"] <= self.clock():
            self._run_job(job["id"])
        job = self.db.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
        if job["status"] in ("failed", "rejected", "executing"):
            raise BuildingError(job["error"] or "Interrupted placement requires offline reconciliation")
        return self._result(job)

    def place(self, structure_id, plot_id=None, owner=None, reason='', quest_id=None):
        return self._submit(structure_id, plot_id, owner, reason, quest_id, False)

    def upgrade(self, plot_id, target_structure, owner=None, reason='', quest_id=None):
        return self._submit(target_structure, plot_id, owner, reason, quest_id, True)

    def _run_job(self, job_id):
        event = None
        with self._transaction():
            job = self.db.execute("SELECT * FROM jobs WHERE id=? AND settlement=?", (job_id, self.sid)).fetchone()
            if not job or job["status"] != "queued" or job["due"] > self.clock():
                return None
            self._enabled()
            d, p = json.loads(job["definition"]), json.loads(job["geometry"])
            row = self._plot(job["plot_id"])
            try:
                _require(not row["structure_id"] or row["snapshot"] is not None and row["definition"] is not None, "Missing original block snapshot")
                old_d = json.loads(row["definition"]) if row["definition"] else None
                expected = json.loads(row["snapshot"]) if row["snapshot"] else None
                self._scan(p, old_d, expected)
                # Repeat exclusion immediately before the mutation, after the long scan.
                self._environment(p)
            except Exception as exc:
                status = "protected" if job["stage"] > 0 else ("occupied" if row["structure_id"] else "available")
                self.db.execute("UPDATE plots SET status=? WHERE settlement=? AND id=?", (status, self.sid, job["plot_id"]))
                self.db.execute("UPDATE jobs SET status=?,error=? WHERE id=?", ("failed" if job["stage"] else "rejected", str(exc), job_id))
                self._history(job["action"], job["structure_id"], job["plot_id"], job["owner"], job["reason"], job["quest_id"], False, str(exc))
                event = self._event({"type": "construction_failed", "settlement": self.settings["id"], "plot_id": job["plot_id"], "structure_id": job["structure_id"], "error": str(exc)})
            else:
                # Durable uncertainty barrier precedes sending any mutating command.
                self.db.execute("UPDATE jobs SET status='executing' WHERE id=?", (job_id,))
                self.db.execute("UPDATE plots SET status='protected' WHERE settlement=? AND id=?", (self.sid, job["plot_id"]))
        if event:
            self._log("construction_failed", job_id=job_id, error=event["error"])
            return event
        stages = d.get("stages") or [{"template": d["template"], "delay_seconds": 0}]
        command = self._placement_command(d, p, stages[job["stage"]]["template"])
        self._log("placing_template", job_id=job_id, template=stages[job["stage"]]["template"], command=command)
        try:
            response = self.command(command)
            placed = command.rsplit(" run place template ", 1)[1].split()
            expected_response = f'Loaded template "{placed[0]}" at {placed[1]}, {placed[2]}, {placed[3]}'
            _require(isinstance(response, str) and response.strip() == expected_response, "Template placement was not affirmatively acknowledged")
            snapshot = self._scan(p, d)
        except Exception as exc:
            with self._transaction():
                self.db.execute("UPDATE jobs SET status='failed',error=? WHERE id=?", (str(exc), job_id))
                self._history(job["action"], job["structure_id"], job["plot_id"], job["owner"], job["reason"], job["quest_id"], False, str(exc))
                event = self._event({"type": "construction_failed", "settlement": self.settings["id"], "plot_id": job["plot_id"], "structure_id": job["structure_id"], "error": str(exc), "protected": True})
            self._log("construction_failed", job_id=job_id, error=str(exc), protected=True)
            return event
        complete = job["stage"] + 1 == len(stages)
        with self._transaction():
            self.db.execute("UPDATE plots SET status=?,structure_id=?,owner=?,snapshot=?,definition=? WHERE settlement=? AND id=?", ("occupied" if complete else ("upgrading" if job["action"] == "upgrade" else "reserved"), job["structure_id"], job["owner"], _json(snapshot), job["definition"], self.sid, job["plot_id"]))
            if complete:
                self.db.execute("UPDATE jobs SET status='complete' WHERE id=?", (job_id,))
                self._history(job["action"], job["structure_id"], job["plot_id"], job["owner"], job["reason"], job["quest_id"], True)
                self.db.execute("UPDATE structures SET active=0 WHERE settlement_id=? AND plot_id=?", (self.sid, job["plot_id"]))
                self.db.execute("INSERT INTO structures(settlement_id,structure_id,plot_id,owner_player,tier,created_at,reason,quest_id) VALUES (?,?,?,?,?,?,?,?)",
                                (self.sid, job["structure_id"], job["plot_id"], job["owner"], d["progression"]["tier"], self.clock(), job["reason"], job["quest_id"]))
                event = self._event({"type": "construction_complete", "settlement": self.settings["id"], "plot_id": job["plot_id"], "structure_id": job["structure_id"], "owner": job["owner"]})
                self._finish_initialization()
            else:
                stage = job["stage"] + 1
                self.db.execute("UPDATE jobs SET status='queued',stage=?,due=? WHERE id=?", (stage, self.clock() + stages[job["stage"]]["delay_seconds"], job_id))
                event = self._event({"type": "construction_stage", "settlement": self.settings["id"], "plot_id": job["plot_id"], "structure_id": job["structure_id"], "stage": job["stage"], "template": stages[job["stage"]]["template"]})
        self._log("construction_complete" if complete else "construction_stage", job_id=job_id, stage=job["stage"])
        if complete:
            for announcement in self._completion_commands(d, job["owner"]):
                try:
                    self.command(announcement)
                except Exception as exc:
                    self._log("announcement_failed", job_id=job_id, error=str(exc))
        return event

    def tick(self):
        if not self.settings["enabled"]:
            return []
        jobs = self.db.execute("SELECT * FROM jobs WHERE settlement=? AND status='queued' AND due<=? ORDER BY id", (self.sid, self.clock())).fetchall()
        if self.dry_run:
            self._enabled()
            events = []
            for job in jobs:
                row = self._plot(job["plot_id"])
                _require(not row["structure_id"] or row["snapshot"] is not None and row["definition"] is not None, "Missing original block snapshot")
                self._scan(json.loads(job["geometry"]), json.loads(row["definition"]) if row["definition"] else None, json.loads(row["snapshot"]) if row["snapshot"] else None)
                events.append({"type": "construction_preview", **self._result(job)})
            return events
        return [event for job in jobs if (event := self._run_job(job["id"])) is not None]

    def remove(self, plot_id):
        self._enabled()
        with self._transaction():
            row = self._plot(plot_id)
            p = json.loads(row["config"])
            _require(not p.get("protected"), "Configured protected plot cannot be removed")
            _require(not self.db.execute("SELECT 1 FROM jobs WHERE settlement=? AND plot_id=? AND status IN ('queued','executing')", (self.sid, plot_id)).fetchone(), "Plot has an unresolved construction job")
            _require(not self.db.execute("SELECT 1 FROM removal_history WHERE settlement=? AND plot_id=? AND status='executing'", (self.sid, plot_id)).fetchone(), "Plot has an uncertain removal requiring offline reconciliation")
            failed_removal = self.db.execute("SELECT 1 FROM removal_history WHERE settlement=? AND plot_id=? AND status='failed'", (self.sid, plot_id)).fetchone()
            definition = json.loads(row["definition"]) if row["definition"] else None
            states = self._scan(p, definition)
            commands = []
            if not all(block in _AIR for block in states):
                _require(not failed_removal, "Partial failed removal cannot be replayed; manually prepare an empty plot")
                _require(row["status"] == "occupied" and row["snapshot"] is not None, "Only recorded occupied buildings may be removed")
                _require(states == json.loads(row["snapshot"]), "Building was edited; removal rejected")
                prefix = self._mutation_prefix(p)
                # Remove support-dependent blocks before their supporting blocks.
                for (x, y, z), block in sorted(zip(self._coordinates(p), states), key=lambda item: item[0][1], reverse=True):
                    if block not in _AIR:
                        commands.append(f"{prefix} if block {x} {y} {z} {block} run setblock {x} {y} {z} minecraft:air")
            if self.dry_run:
                return {"success": True, "dry_run": True, "commands": commands, "plot_id": plot_id}
            if not commands:
                self.db.execute("UPDATE plots SET status='available',structure_id=NULL,owner=NULL,snapshot=NULL,definition=NULL WHERE settlement=? AND id=?", (self.sid, plot_id))
                self.db.execute("UPDATE structures SET active=0 WHERE settlement_id=? AND plot_id=?", (self.sid, plot_id))
                self._history("remove", row["structure_id"] or "", plot_id, row["owner"], "Admin removal", None, True)
                self.db.execute("UPDATE removal_history SET status='complete' WHERE settlement=? AND plot_id=? AND status='failed'", (self.sid, plot_id))
                self._log("plot_released", plot_id=plot_id)
                return {"success": True, "dry_run": False, "commands": [], "plot_id": plot_id}
            cursor = self.db.execute("INSERT INTO removal_history(settlement,plot_id,geometry,snapshot,status,timestamp) VALUES (?,?,?,?,'executing',?)", (self.sid, plot_id, _json(p), _json(states), self.clock()))
            removal_id = cursor.lastrowid
            self.db.execute("UPDATE plots SET status='protected' WHERE settlement=? AND id=?", (self.sid, plot_id))
        try:
            for command in commands:
                response = self.command(command)
                _require(isinstance(response, str) and re.fullmatch(r"Changed the block at -?\d+, -?\d+, -?\d+", response.strip()), "Block removal was not affirmatively acknowledged")
            self._scan(p)
        except Exception as exc:
            with self._transaction():
                self.db.execute("UPDATE removal_history SET status='failed',error=? WHERE id=?", (str(exc), removal_id))
                self._history("remove", row["structure_id"] or "", plot_id, row["owner"], "Admin removal", None, False, str(exc))
                self._event({"type": "removal_failed", "settlement": self.settings["id"], "plot_id": plot_id, "protected": True, "error": str(exc)})
            self._log("removal_failed", plot_id=plot_id, protected=True, error=str(exc))
            raise BuildingError("Removal failed; plot remains protected: " + str(exc)) from exc
        with self._transaction():
            self.db.execute("UPDATE plots SET status='available',structure_id=NULL,owner=NULL,snapshot=NULL,definition=NULL WHERE settlement=? AND id=?", (self.sid, plot_id))
            self.db.execute("UPDATE structures SET active=0 WHERE settlement_id=? AND plot_id=?", (self.sid, plot_id))
            self._history("remove", row["structure_id"] or "", plot_id, row["owner"], "Admin removal", None, True)
            self.db.execute("UPDATE removal_history SET status='complete' WHERE id=?", (removal_id,))
            self._event({"type": "removal_complete", "settlement": self.settings["id"], "plot_id": plot_id})
        self._log("removal_complete", plot_id=plot_id)
        return {"success": True, "dry_run": False, "commands": commands, "plot_id": plot_id}

    def grant_xp(self, amount, quest_id=None):
        self._enabled()
        _require(_integer(amount, 1), "XP must be a positive integer")
        _require(quest_id is None or _text(quest_id, 256) and bool(quest_id), "Invalid quest ID")
        with self._transaction():
            old = self.db.execute("SELECT amount FROM xp_ledger WHERE settlement=? AND quest_id=?", (self.sid, quest_id)).fetchone() if quest_id is not None else None
            if old:
                _require(old["amount"] == amount, "Conflicting idempotent XP reward")
                return []
            xp = self._settlement_row()["xp"]
            _require(xp + amount <= 9223372036854775807, "XP exceeds storage range")
            events = [{"type": "settlement_level_up", "settlement": self.settings["id"], "new_level": n} for n in range(self._level(xp) + 1, self._level(xp + amount) + 1)]
            if not self.dry_run:
                self.db.execute("UPDATE settlements SET xp=xp+? WHERE id=?", (amount, self.sid))
                if quest_id is not None:
                    self.db.execute("INSERT INTO xp_ledger VALUES (?,?,?)", (self.sid, quest_id, amount))
                for event in events:
                    self._event(event)
        self._log("xp_preview" if self.dry_run else "xp_granted", amount=amount, quest_id=quest_id)
        return events

    def _finish_initialization(self):
        if self._settlement_row()["initialization_started"]:
            statuses = [r["status"] for r in self.db.execute("SELECT status FROM jobs WHERE settlement=? AND quest_id GLOB '__starter__:*'", (self.sid,))]
            if all(status == "complete" for status in statuses):
                self.db.execute("UPDATE settlements SET initialized=1 WHERE id=?", (self.sid,))

    def initialize(self, *, force=False):
        if not force and not self.settings["initialize_on_first_run"]:
            return []
        self._enabled()
        if self._settlement_row()["initialization_started"]:
            return []
        starters = self.settings["starter_structures"]
        if self.dry_run:
            # Preview independent candidates while avoiding choosing one plot twice.
            results, used = [], set()
            for item in starters:
                item = {"structure_id": item} if isinstance(item, str) else item
                pid = item.get("plot_id")
                if pid is None:
                    for p in self.list_plots():
                        if p["status"] == "available" and p["id"] not in used:
                            try:
                                self._fit(self._definition(item["structure_id"]), self.config["plots"][p["id"]])
                            except BuildingError:
                                continue
                            pid = p["id"]
                            break
                _require(pid is not None and pid not in used, "No distinct starter plot")
                results.append(self.place(item["structure_id"], pid, item.get("owner"), "Settlement initialization"))
                used.add(pid)
            return results
        # Reserve every starter and claim initialization in one atomic transaction.
        # A restart can finish queued work through tick(), but never recreate it.
        jobs = []
        with self._transaction():
            if self._settlement_row()["initialization_started"]:
                return []
            for i, item in enumerate(starters):
                item = {"structure_id": item} if isinstance(item, str) else item
                job, _ = self._prepare(item["structure_id"], item.get("plot_id"), item.get("owner"), "Settlement initialization", "__starter__:" + str(i), False)
                jobs.append(job)
            self.db.execute("UPDATE settlements SET initialization_started=1 WHERE id=?", (self.sid,))
            self._finish_initialization()
        results = []
        for job in jobs:
            if job["due"] <= self.clock():
                self._run_job(job["id"])
            current = self.db.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
            result = self._result(current)
            if current["error"]:
                result["error"] = current["error"]
            results.append(result)
        return results

    def record_quest(self, quest_id, player, title):
        _require(_text(quest_id, 256) and bool(quest_id), "Invalid quest ID")
        self._owner(player)
        _require(player is not None and _text(title, 256), "Invalid quest metadata")
        with self._transaction():
            old = self.db.execute("SELECT * FROM quests WHERE settlement=? AND id=?", (self.sid, quest_id)).fetchone()
            if old:
                _require(old["player"] == player and old["title"] == title, "Conflicting quest metadata")
            elif not self.dry_run:
                self.db.execute("INSERT INTO quests VALUES (?,?,?,?,?)", (self.sid, quest_id, player, title, self.clock()))
        return {"quest_id": quest_id, "player": player, "title": title, "dry_run": self.dry_run}

    def list_plots(self):
        return [{"id": row["id"], "settlement_id": self.settings["id"], **json.loads(row["config"]), "status": row["status"], "current_structure": row["structure_id"], "owner_player": row["owner"]} for row in self.db.execute("SELECT * FROM plots WHERE settlement=? ORDER BY id", (self.sid,))]

    def list_structures(self):
        unlocked = set(self._unlocked())
        return [{"id": sid, **copy.deepcopy(d), "unlocked": sid in unlocked} for sid, d in sorted(self.registry.items())]

    def show_settlement(self):
        row = self._settlement_row()
        level = self._level(row["xp"])
        next_level = self.config["levels"].get(str(level + 1))
        return {"id": self.settings["id"], "display_name": self.settings["display_name"], "world_id": self.settings["world_id"], "dimension": self.settings["dimension"], "enabled": self.settings["enabled"], "level": level, "level_name": self.config["levels"][str(level)]["name"], "xp": row["xp"], "next_level_xp": next_level["xp_required"] if next_level else None, "initialized": bool(row["initialized"]), "initialization_started": bool(row["initialization_started"]), "created_at": row["created_at"]}

    def context(self):
        plots = self.list_plots()
        buildings = [dict(r) for r in self.db.execute("SELECT s.instance_id,s.plot_id,s.structure_id,s.owner_player,s.tier,s.reason,s.quest_id FROM structures s JOIN plots p ON p.settlement=s.settlement_id AND p.id=s.plot_id WHERE s.settlement_id=? AND s.active=1 AND p.status='occupied' ORDER BY s.instance_id", (self.sid,))]
        quests = [{"quest_id": r["id"], "player": r["player"], "title": r["title"]} for r in self.db.execute("SELECT * FROM quests WHERE settlement=? ORDER BY timestamp DESC,id DESC LIMIT 10", (self.sid,))]
        events = [json.loads(r["payload"]) for r in self.db.execute("SELECT payload FROM events WHERE settlement=? ORDER BY id DESC LIMIT 10", (self.sid,))]
        return {"settlement": self.show_settlement(), "buildings": buildings, "available_plots": [p["id"] for p in plots if p["status"] == "available"], "categories": sorted({d["category"] for d in self.registry.values()}), "unlocked_structures": self._unlocked(), "capabilities": sorted({c for b in buildings for c in self.registry[b["structure_id"]]["unlocks"]}), "recent_quests": quests, "events": events}

    def validate_action(self, raw, players):
        self._enabled()
        _require(isinstance(raw, dict), "Action must be an object")
        action = raw.get("action")
        if action == "construct_building":
            _keys(raw, ("action", "structure_id", "owner", "reason"))
            self._definition(raw["structure_id"])
        elif action == "upgrade_building":
            _keys(raw, ("action", "plot_id", "target_structure", "owner", "reason"))
            d = self._definition(raw["target_structure"])
            _require(isinstance(raw["plot_id"], str), "Invalid plot ID")
            row = self._plot(raw["plot_id"])
            _require(row["status"] == "occupied" and row["owner"] == raw["owner"] and row["structure_id"] in d["progression"]["upgrades_from"], "Invalid owned upgrade")
        else:
            raise BuildingError("Unsupported settlement action")
        self._owner(raw["owner"])
        _require(raw["owner"] is not None and raw["owner"] in players, "Owner must be a live player")
        _require(_text(raw["reason"], 256), "Invalid reason")
        return copy.deepcopy(raw)

    def execute_action(self, raw, players):
        action = self.validate_action(raw, players)
        if action["action"] == "construct_building":
            return self.place(action["structure_id"], owner=action["owner"], reason=action["reason"])
        return self.upgrade(action["plot_id"], action["target_structure"], owner=action["owner"], reason=action["reason"])

    def close(self):
        self.db.close()
