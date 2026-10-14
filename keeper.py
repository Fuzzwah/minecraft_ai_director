"""Temple-owned progression and bounded, exact-state Keeper decoration.

This module has no Director, settlement, authoring, or third-party dependency.
The owning writer supplies its command and durable state-save callbacks.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path


class KeeperError(ValueError):
    """Invalid configuration, source, or ordinary pre-dispatch obstruction."""


class KeeperUncertain(RuntimeError):
    """A world mutation may have happened: stop the writer; never replay it."""


_DIMENSION = "minecraft:overworld"
_DIRECTIONS = ("north", "east", "south", "west")
_RESOURCE = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_LIST = re.compile(r"^There are \d+ of a max of \d+ players online:.*$", re.S)
_POLICY = (
    ("Dormant", 0, 0, 0, 0),
    ("Awakened", 3, 5, 30, 0),
    ("Warden", 10, 10, 60, 30),
    ("Exalted", 25, 15, 90, 60),
    ("Ascendant", 50, 20, 120, 90),
)
_MAX_MUTATIONS = 16
_MAX_EVIDENCE = 8
_MAX_TEXT = 512
_AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
_STATELESS = set("air cave_air void_air smooth_stone chiseled_stone_bricks stone_bricks "
                 "sandstone smooth_sandstone cut_sandstone chiseled_sandstone gold_block "
                 "glowstone cobblestone mossy_cobblestone dirt dirt_path sand snow_block "
                 "oak_planks spruce_planks acacia_planks waxed_copper_block "
                 "waxed_exposed_copper waxed_weathered_copper waxed_oxidized_copper "
                 "waxed_cut_copper waxed_exposed_cut_copper waxed_weathered_cut_copper "
                 "waxed_oxidized_cut_copper waxed_chiseled_copper".split())
_STAIRS = {"sandstone_stairs", "smooth_sandstone_stairs", "stone_brick_stairs"} | {
    "waxed_" + age + "cut_copper_stairs" for age in ("", "exposed_", "weathered_", "oxidized_")}
_SLABS = {"sandstone_slab", "smooth_sandstone_slab", "cut_sandstone_slab", "smooth_stone_slab", "stone_brick_slab"} | {
    "waxed_" + age + "cut_copper_slab" for age in ("", "exposed_", "weathered_", "oxidized_")}
_LOGS = {"stripped_" + wood + ending for wood in ("oak", "spruce", "acacia") for ending in ("_log", "_wood")}


def _require(condition, message):
    if not condition:
        raise KeeperError(message)


def _keys(value, required, optional=()):
    _require(isinstance(value, dict), "Expected Keeper object")
    _require(set(required) <= value.keys() and not (value.keys() - set(required) - set(optional)),
             "Missing or unknown Keeper fields")


def _integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def _text(value, maximum=_MAX_TEXT):
    return isinstance(value, str) and len(value) <= maximum and not any(ord(c) < 32 for c in value)


def _position(value, *, local_size=None):
    _require(isinstance(value, list) and len(value) == 3 and all(type(n) is int for n in value),
             "Invalid Keeper position")
    if local_size is not None:
        _require(all(0 <= n < size for n, size in zip(value, local_size)), "Keeper position outside definition bounds")
    else:
        _require(all(-30_000_000 <= value[i] <= 30_000_000 for i in (0, 2)) and -64 <= value[1] <= 319,
                 "Keeper position outside overworld bounds")
    return tuple(value)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate Keeper JSON key: " + key)
        result[key] = value
    return result


def _constant(value):
    raise KeeperError("Nonfinite Keeper JSON value: " + value)


def policy(value):
    """Return a fresh, code-owned policy for a rank, never a model-selected power."""
    _require(_integer(value, 1, 5), "Invalid Keeper rank")
    return dict(zip(("name", "minimum", "bonus_points", "haste_seconds", "resistance_seconds"), _POLICY[value - 1]))


def rank(record):
    progression = record.get("progression") if isinstance(record, dict) else None
    ledger = progression.get("credited_quest_ids") if isinstance(progression, dict) else None
    _require(isinstance(ledger, list) and all(_text(q, 256) and q for q in ledger) and len(ledger) == len(set(ledger)),
             "Invalid Keeper credit ledger")
    return max(i for i, entry in enumerate(_POLICY, 1) if len(ledger) >= entry[1])


def keeper_id(binding):
    _require(isinstance(binding, dict), "Invalid Keeper binding")
    world = binding.get("world_id")
    _require(_text(world, 256) and bool(world.strip()), "Invalid Keeper world identity")
    _require(binding.get("dimension") == _DIMENSION, "Keeper source must be the overworld")
    minimum = _position(binding.get("minimum"))
    identity = json.dumps([world, _DIMENSION, *minimum], separators=(",", ":"), ensure_ascii=True)
    return "keeper:" + hashlib.sha256(identity.encode()).hexdigest()


def _binding(binding):
    _keys(binding, ("world_id", "dimension", "resource", "minimum", "facing", "chest", "definition_digest"))
    keeper_id(binding)
    _require(isinstance(binding["resource"], str) and _RESOURCE.fullmatch(binding["resource"]), "Invalid Keeper resource")
    _require(binding["facing"] in _DIRECTIONS, "Invalid Keeper facing")
    _position(binding["chest"])
    _require(isinstance(binding["definition_digest"], str) and _DIGEST.fullmatch(binding["definition_digest"]),
             "Invalid Keeper definition digest")


def _state(state, *, chest=False):
    _keys(state, ("id",), ("properties",))
    block = state["id"]
    _require(isinstance(block, str) and block.startswith("minecraft:"), "Unknown Keeper block state")
    name = block.removeprefix("minecraft:")
    properties = state.get("properties", {})
    _require(isinstance(properties, dict), "Invalid Keeper block properties")
    if name in _STATELESS:
        schema = {}
    elif name in _STAIRS:
        schema = {"facing": set(_DIRECTIONS), "half": {"bottom", "top"},
                  "shape": {"straight", "inner_left", "inner_right", "outer_left", "outer_right"}, "waterlogged": {"false"}}
    elif name in _SLABS:
        schema = {"type": {"bottom", "top", "double"}, "waterlogged": {"false"}}
    elif name in _LOGS:
        schema = {"axis": {"x", "y", "z"}}
    elif name == "lantern":
        schema = {"hanging": {"true", "false"}, "waterlogged": {"false"}}
    elif name == "iron_chain":
        schema = {"axis": {"x", "y", "z"}, "waterlogged": {"false"}}
    elif name == "grass_block":
        schema = {"snowy": {"true", "false"}}
    elif name == "chest" and chest:
        schema = {"facing": set(_DIRECTIONS), "type": {"single"}, "waterlogged": {"false"}}
    else:
        raise KeeperError("Forbidden or unsupported Keeper block: " + block)
    _require(properties.keys() == schema.keys() and all(isinstance(v, str) and v in schema[k] for k, v in properties.items()),
             "Incomplete or unsupported Keeper state properties: " + block)
    return state


def _block(state):
    properties = state.get("properties", {})
    return state["id"] + ("[" + ",".join(f"{key}={value}" for key, value in sorted(properties.items())) + "]" if properties else "")


def _rotate(position, size, turns):
    x, y, z = position
    w, _, d = size
    return ((x, y, z), (d - 1 - z, y, x), (w - 1 - x, y, d - 1 - z), (z, y, w - 1 - x))[turns]


def _rotated_state(state, turns):
    result = copy.deepcopy(state)
    properties = result.get("properties", {})
    for key in ("facing", "orientation"):
        if key in properties:
            properties[key] = "_".join(_DIRECTIONS[(_DIRECTIONS.index(part) + turns) % 4] if part in _DIRECTIONS else part
                                       for part in properties[key].split("_"))
    if turns % 2 and properties.get("axis") in ("x", "z"):
        properties["axis"] = "z" if properties["axis"] == "x" else "x"
    return result


def _world(position, definition, binding):
    local = _rotate(position, definition["size"], _DIRECTIONS.index(binding["facing"]))
    result = [n + offset for n, offset in zip(local, binding["minimum"])]
    _position(result)
    return result


def _definition(definition):
    _keys(definition, ("size", "floor_y", "chest", "entry", "mutable_baseline", "invariants", "access", "milestones"))
    size = definition["size"]
    _require(isinstance(size, list) and len(size) == 3 and all(_integer(n, 1, 128) for n in size), "Invalid Keeper temple size")
    _require(_integer(definition["floor_y"], 0, size[1] - 1), "Invalid Keeper temple floor")
    chest = _position(definition["chest"], local_size=size)
    entry = _position(definition["entry"], local_size=size)
    maps = {}
    for name in ("mutable_baseline", "invariants", "access"):
        cells = definition[name]
        _require(isinstance(cells, list) and 0 < len(cells) <= 100_000, "Invalid Keeper " + name)
        found = {}
        for cell in cells:
            _keys(cell, ("pos", "state"))
            pos = _position(cell["pos"], local_size=size)
            _require(pos not in found, "Duplicate Keeper " + name + " position")
            _state(cell["state"], chest=name == "invariants" and pos == chest)
            found[pos] = cell["state"]
        maps[name] = found
    baseline, invariants, access = (maps[n] for n in ("mutable_baseline", "invariants", "access"))
    _require(not (baseline.keys() & (invariants.keys() | access.keys())), "Keeper mutation overlaps no-touch cells")
    _require(all(invariants[p] == access[p] for p in invariants.keys() & access.keys()), "Conflicting Keeper no-touch probes")
    _require(invariants.get(chest, {}).get("id") == "minecraft:chest", "Keeper invariant chest missing")
    probes = {**invariants, **access}
    lid = (chest[0], chest[1] + 1, chest[2])
    _require(access.get(lid, {}).get("id") == "minecraft:air", "Keeper chest lid clearance missing")
    for pos in (entry, (entry[0], entry[1] + 1, entry[2])):
        _require(probes.get(pos, {}).get("id") == "minecraft:air", "Keeper entrance clearance missing")
    support = probes.get((entry[0], entry[1] - 1, entry[2]), {})
    _require(support.get("id") and support["id"] not in _AIR and support["id"] != "minecraft:lantern",
             "Keeper entrance support missing")
    milestones = definition["milestones"]
    _keys(milestones, ("2", "3", "4", "5"))
    states = dict(baseline)
    touched = set()
    for milestone in range(2, 6):
        transitions = milestones[str(milestone)]
        _require(isinstance(transitions, list) and 0 < len(transitions) <= 1024, "Invalid Keeper milestone transitions")
        positions = set()
        for transition in transitions:
            _keys(transition, ("pos", "expected", "target"))
            pos = _position(transition["pos"], local_size=size)
            _require(pos in baseline and pos not in positions, "Unknown or duplicate Keeper transition position")
            _state(transition["expected"])
            _state(transition["target"])
            _require(transition["expected"] == states[pos], "Keeper transition predecessor mismatch")
            _require(transition["target"] != transition["expected"], "Keeper transition makes no change")
            _require(transition["target"]["id"] not in _AIR, "Keeper patches cannot clear terrain")
            states[pos] = transition["target"]
            positions.add(pos)
            touched.add(pos)
    _require(touched == baseline.keys(), "Keeper baseline must equal the complete mutable footprint")
    return definition


def _definition_digest(resource, definition):
    payload = {"version": 1, "minecraft_version": "26.3", "resource": resource, "definition": definition}
    return hashlib.sha256(_json(payload).encode()).hexdigest()


def _transitions(definition, binding, target_rank):
    turns = _DIRECTIONS.index(binding["facing"])
    return [{"pos": _world(t["pos"], definition, binding), "expected": _rotated_state(t["expected"], turns),
             "target": _rotated_state(t["target"], turns)} for t in definition["milestones"][str(target_rank)]]


def _upgrade(upgrade, key, record):
    _keys(upgrade, ("version", "keeper_id", "binding", "definition", "predecessor", "target_rank", "transitions",
                    "step", "uncertain", "status", "evidence"))
    _require(type(upgrade["version"]) is int and upgrade["version"] == 1, "Unsupported Keeper upgrade version")
    binding = record["binding"]
    _binding(upgrade["binding"])
    _require(upgrade["keeper_id"] == key and upgrade["binding"] == binding, "Keeper upgrade binding conflict")
    definition = _definition(upgrade["definition"])
    _require(_definition_digest(binding["resource"], definition) == binding["definition_digest"], "Keeper upgrade digest conflict")
    _require(_world(definition["chest"], definition, binding) == binding["chest"], "Keeper upgrade chest conflict")
    predecessor = record["evolution"]["installed_rank"]
    _require(type(upgrade["predecessor"]) is int and upgrade["predecessor"] == predecessor,
             "Keeper upgrade predecessor conflict")
    target = upgrade["target_rank"]
    _require(_integer(target, 2, 5) and target == predecessor + 1 and target <= rank(record), "Invalid Keeper upgrade milestone")
    _require(isinstance(upgrade["transitions"], list), "Invalid Keeper transition snapshot")
    for transition in upgrade["transitions"]:
        _keys(transition, ("pos", "expected", "target"))
        _position(transition["pos"])
        _state(transition["expected"])
        _state(transition["target"])
    _require(upgrade["transitions"] == _transitions(definition, binding, target), "Keeper upgrade transition snapshot conflict")
    _require(_integer(upgrade["step"], 0, len(upgrade["transitions"])), "Invalid Keeper upgrade progress")
    _require(type(upgrade["uncertain"]) is bool, "Invalid Keeper upgrade uncertainty")
    _require(upgrade["status"] in ("ready", "blocked", "uncertain", "verifying"), "Invalid Keeper upgrade status")
    _require((upgrade["status"] == "uncertain") == upgrade["uncertain"] and
             (not upgrade["uncertain"] or upgrade["step"] < len(upgrade["transitions"])), "Inconsistent Keeper dispatch uncertainty")
    _require((upgrade["status"] != "verifying" or upgrade["step"] == len(upgrade["transitions"])) and
             (upgrade["status"] != "ready" or upgrade["step"] < len(upgrade["transitions"])),
             "Inconsistent Keeper upgrade completion status")
    _require(isinstance(upgrade["evidence"], list) and len(upgrade["evidence"]) <= _MAX_EVIDENCE and
             all(_text(e) for e in upgrade["evidence"]), "Invalid Keeper upgrade evidence")


def _record(record, key=None):
    _keys(record, ("version", "binding", "progression", "evolution"))
    _require(type(record["version"]) is int and record["version"] == 1, "Unsupported Keeper record version")
    _binding(record["binding"])
    identity = keeper_id(record["binding"])
    _require(key is None or key == identity, "Keeper record ID does not match its binding")
    progression = record["progression"]
    _keys(progression, ("credited_quest_ids", "last_announced_rank"))
    earned = rank(record)
    _require(_integer(progression["last_announced_rank"], 1, earned), "Invalid Keeper announcement watermark")
    evolution = record["evolution"]
    _keys(evolution, ("enabled", "installed_rank", "upgrade", "last_error"))
    _require(type(evolution["enabled"]) is bool, "Invalid Keeper evolution enablement")
    _require(_integer(evolution["installed_rank"], 1, earned), "Invalid Keeper installed rank")
    _require(_text(evolution["last_error"]), "Invalid Keeper evolution error")
    if evolution["upgrade"] is not None:
        _upgrade(evolution["upgrade"], identity, record)
    return record


def validate_records(raw):
    """Validate without discarding future versions, debt, or uncertain intent."""
    _require(isinstance(raw, dict), "Keeper records must be an object")
    identities = set()
    for key, record in raw.items():
        _require(isinstance(key, str), "Invalid Keeper record key")
        _record(record, key)
        identity = keeper_id(record["binding"])
        _require(identity not in identities, "Duplicate Keeper identity")
        identities.add(identity)
    return raw


def credit(record, quest_id):
    """Append exactly one quest identity; persistence belongs to the owner."""
    _record(record)
    _require(_text(quest_id, 256) and bool(quest_id), "Invalid Keeper quest credit ID")
    ledger = record["progression"]["credited_quest_ids"]
    if quest_id in ledger:
        return False
    ledger.append(quest_id)
    return True


def status(keepers, selected_id=None):
    validate_records(keepers)
    _require(selected_id is None or selected_id in keepers, "Selected Keeper is not registered")
    records = {}
    for key, record in keepers.items():
        earned = rank(record)
        evolution = record["evolution"]
        records[key] = {"keeper_id": key, "binding": copy.deepcopy(record["binding"]),
                        "xp": len(record["progression"]["credited_quest_ids"]), "rank": earned,
                        "name": policy(earned)["name"], "next_threshold": policy(earned + 1)["minimum"] if earned < 5 else None,
                        "evolution": evolution["enabled"], "installed_rank": evolution["installed_rank"],
                        "due_rank": evolution["installed_rank"] + 1 if evolution["installed_rank"] < earned else None,
                        "upgrade": copy.deepcopy(evolution["upgrade"]), "last_error": evolution["last_error"]}
    return {"selected_id": selected_id, "selected": records.get(selected_id), "keepers": records}


class KeeperController:
    """One explicitly selected original temple; never discovers or repairs others."""

    def __init__(self, definitions_path, world_id, resource, minimum, facing, offering_chest, command, persist,
                 *, dry_run=False, protected_regions=()):
        _require(type(dry_run) is bool, "Invalid Keeper dry-run setting")
        _require(callable(command) and callable(persist), "Keeper command and persistence callbacks are required")
        try:
            with Path(definitions_path).open() as stream:
                manifest = json.load(stream, object_pairs_hook=_object, parse_constant=_constant)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise KeeperError("Cannot load Keeper definitions: " + str(exc)) from exc
        _keys(manifest, ("version", "minecraft_version", "roots"))
        _require(type(manifest["version"]) is int and manifest["version"] == 1 and manifest["minecraft_version"] == "26.3",
                 "Unsupported Keeper manifest version")
        _require(isinstance(manifest["roots"], dict) and manifest["roots"], "Missing Keeper temple definitions")
        for root, definition in manifest["roots"].items():
            _require(isinstance(root, str) and _RESOURCE.fullmatch(root), "Invalid Keeper root resource")
            _definition(definition)
        _require(isinstance(resource, str) and resource in manifest["roots"], "Keeper root is not approved")
        self.definition = copy.deepcopy(manifest["roots"][resource])
        _require(isinstance(minimum, (list, tuple)) and isinstance(offering_chest, (list, tuple)),
                 "Keeper minimum and offering chest must be coordinates")
        self.binding = {"world_id": world_id, "dimension": _DIMENSION, "resource": resource,
                        "minimum": list(minimum), "facing": facing, "chest": list(offering_chest),
                        "definition_digest": _definition_digest(resource, self.definition)}
        _binding(self.binding)
        _require(_world(self.definition["chest"], self.definition, self.binding) == self.binding["chest"],
                 "Configured offering chest disagrees with the transformed original temple")
        self.keeper_id = keeper_id(self.binding)
        self.command = command
        self.persist = persist
        self.dry_run = dry_run
        turns = _DIRECTIONS.index(facing)
        w, h, d = self.definition["size"]
        if turns % 2:
            w, d = d, w
        x, y, z = self.binding["minimum"]
        self.bounds = (x, y, z, x + w - 1, y + h - 1, z + d - 1)
        _position(list(self.bounds[3:]))
        _require(isinstance(protected_regions, (list, tuple)), "Invalid Keeper protected regions")
        self.protected_regions = []
        for region in protected_regions:
            _keys(region, ("min", "max"), ("dimension",))
            dimension = region.get("dimension", _DIMENSION)
            _require(isinstance(dimension, str) and _RESOURCE.fullmatch(dimension), "Invalid protected region dimension")
            points = []
            for edge in ("min", "max"):
                _keys(region[edge], ("x", "y", "z"))
                points.extend(_position([region[edge][axis] for axis in "xyz"]))
            _require(all(points[i] <= points[i + 3] for i in range(3)), "Invalid protected region bounds")
            if dimension == _DIMENSION:
                self.protected_regions.append(tuple(points))

    def _selected(self, keepers):
        validate_records(keepers)
        _require(self.keeper_id in keepers, "Keeper is not enrolled")
        record = keepers[self.keeper_id]
        _require(record["binding"] == self.binding, "Keeper durable binding or definition digest conflicts with configuration")
        upgrade = record["evolution"]["upgrade"]
        if upgrade is not None:
            _require(upgrade["definition"] == self.definition, "Keeper immutable upgrade definition conflict")
            if upgrade["uncertain"]:
                raise KeeperUncertain("Keeper " + self.keeper_id + " has uncertain dispatched decoration; stop writers and reconcile")
        return record

    def _query(self, condition):
        try:
            reply = self.command(f"execute in {_DIMENSION} {condition} run list")
        except Exception as exc:
            raise KeeperError("Keeper read-only probe failed: " + str(exc)) from exc
        return isinstance(reply, str) and _LIST.fullmatch(reply.strip()) is not None

    def _static(self):
        for name in ("invariants", "access"):
            self._verify_cells(self.definition[name], local=True, label="source " + name)

    def _verify_cells(self, cells, *, local=False, label="decoration"):
        turns = _DIRECTIONS.index(self.binding["facing"])
        for cell in cells:
            pos = _world(cell["pos"], self.definition, self.binding) if local else cell["pos"]
            state = _rotated_state(cell["state"], turns) if local else cell["state"]
            xyz = " ".join(map(str, pos))
            _require(self._query(f"if loaded {xyz} if block {xyz} {_block(state)}"),
                     f"Keeper {label} state is unexpected, unloaded, or unreadable at {xyz}")

    def _appearance(self, installed, upgrade=None):
        states = {tuple(cell["pos"]): cell["state"] for cell in self.definition["mutable_baseline"]}
        for milestone in range(2, installed + 1):
            for transition in self.definition["milestones"][str(milestone)]:
                states[tuple(transition["pos"])] = transition["target"]
        turns = _DIRECTIONS.index(self.binding["facing"])
        world = {tuple(_world(pos, self.definition, self.binding)): _rotated_state(state, turns) for pos, state in states.items()}
        if upgrade is not None:
            for transition in upgrade["transitions"][:upgrade["step"]]:
                world[tuple(transition["pos"])] = transition["target"]
        return [{"pos": list(pos), "state": state} for pos, state in sorted(world.items())]

    def _guards(self):
        x, y, z, xx, yy, zz = self.bounds
        loaded = " ".join(f"if loaded {cx * 16} {y} {cz * 16}" for cx in range(x // 16, xx // 16 + 1)
                          for cz in range(z // 16, zz // 16 + 1))
        players = f"unless entity @a[x={x},y={y},z={z},dx={xx-x},dy={yy-y},dz={zz-z}]"
        return f"{loaded} {players}"

    def _environment(self):
        for region in self.protected_regions:
            _require(not all(self.bounds[i] <= region[i + 3] and region[i] <= self.bounds[i + 3] for i in range(3)),
                     "Keeper temple overlaps a protected region")
        _require(self._query(self._guards()), "Keeper temple chunks or full-temple player exclusion cannot be confirmed")

    def _new_record(self):
        return {"version": 1, "binding": copy.deepcopy(self.binding),
                "progression": {"credited_quest_ids": [], "last_announced_rank": 1},
                "evolution": {"enabled": True, "installed_rank": 1, "upgrade": None, "last_error": ""}}

    def _enroll(self, keepers, *, save):
        validate_records(keepers)
        if self.keeper_id in keepers:
            record = self._selected(keepers)
            self._static()
            return record
        for existing in keepers.values():
            binding = existing["binding"]
            _require(not existing["evolution"]["enabled"] and
                     binding["chest"] != self.binding["chest"] and
                     not (binding["dimension"] == self.binding["dimension"] and binding["minimum"] == self.binding["minimum"]),
                     "Keeper original temple is already registered under a conflicting binding; re-enrollment is prohibited")
        self._static()
        self._verify_cells(self.definition["mutable_baseline"], local=True, label="enrollment baseline")
        record = self._new_record()
        keepers[self.keeper_id] = record
        if save:
            self._save()
        return record

    def enroll(self, keepers):
        """Verify registration; only a new explicit enrollment checks rank-1 decoration."""
        self._enroll(copy.deepcopy(keepers) if self.dry_run else keepers, save=not self.dry_run)
        return self.keeper_id

    def verify_source(self, keepers):
        self._selected(keepers)
        self._static()

    def _save(self):
        try:
            self.persist()
        except Exception as exc:
            raise KeeperUncertain("Keeper durability failed; stop the writer: " + str(exc)) from exc

    @staticmethod
    def _evidence(upgrade, message):
        upgrade["evidence"] = (upgrade["evidence"] + [" ".join(str(message).split())[:_MAX_TEXT]])[-_MAX_EVIDENCE:]

    def _blocked(self, record, error):
        message = " ".join(str(error).split())[:_MAX_TEXT]
        evolution = record["evolution"]
        changed = evolution["last_error"] != message
        evolution["last_error"] = message
        upgrade = evolution["upgrade"]
        if upgrade is not None:
            changed = changed or upgrade["status"] != "blocked"
            upgrade["status"] = "blocked"
            if not upgrade["evidence"] or upgrade["evidence"][-1] != message:
                self._evidence(upgrade, message)
                changed = True
        if changed:
            self._save()
        return {"keeper_id": self.keeper_id, "success": False, "blocked": True, "error": message}

    def _intent(self, record):
        installed = record["evolution"]["installed_rank"]
        return {"version": 1, "keeper_id": self.keeper_id, "binding": copy.deepcopy(self.binding),
                "definition": copy.deepcopy(self.definition), "predecessor": installed, "target_rank": installed + 1,
                "transitions": _transitions(self.definition, self.binding, installed + 1),
                "step": 0, "uncertain": False, "status": "ready", "evidence": []}

    def preview(self, keepers):
        """Probe only; enrollment, errors and intents remain in a private copy."""
        temporary = copy.deepcopy(keepers)
        result = {"keeper_id": self.keeper_id, "binding": copy.deepcopy(self.binding), "dry_run": True,
                  "success": True, "blocked": False, "uncertain": False, "transitions": [],
                  "registered": self.keeper_id in temporary}
        try:
            validate_records(temporary)
            if self.keeper_id in temporary:
                saved = temporary[self.keeper_id]
                result.update(status(temporary, self.keeper_id)["selected"])
                intent = saved["evolution"]["upgrade"]
                if intent is None and saved["binding"] == self.binding and saved["evolution"]["installed_rank"] < rank(saved):
                    intent = self._intent(saved)
                if intent is not None:
                    result["transitions"] = copy.deepcopy(intent["transitions"])
                    result["next_step"] = intent["step"]
            record = self._enroll(temporary, save=False)
            evolution = record["evolution"]
            upgrade = evolution["upgrade"]
            if evolution["installed_rank"] < rank(record):
                intent = upgrade if upgrade is not None else self._intent(record)
                result["transitions"] = copy.deepcopy(intent["transitions"])
                result["next_step"] = intent["step"]
                if evolution["enabled"]:
                    self._environment()
                    self._verify_cells(self._appearance(evolution["installed_rank"], upgrade))
            result.update(status(temporary, self.keeper_id)["selected"])
        except (KeeperError, KeeperUncertain) as exc:
            result.update(success=False, blocked=isinstance(exc, KeeperError), uncertain=isinstance(exc, KeeperUncertain), error=str(exc))
            if self.keeper_id in temporary:
                result.update(status(temporary, self.keeper_id)["selected"])
        return result

    def tick(self, keepers):
        if self.dry_run:
            return [self.preview(keepers)]
        record = self._selected(keepers)
        evolution = record["evolution"]
        if not evolution["enabled"] or evolution["installed_rank"] >= rank(record):
            return []
        # Source failures are deliberately exceptions, not decoration blockers.
        self.verify_source(keepers)
        events = []
        mutations = 0
        while evolution["installed_rank"] < rank(record) and mutations < _MAX_MUTATIONS:
            upgrade = evolution["upgrade"]
            try:
                self._environment()
                self._verify_cells(self._appearance(evolution["installed_rank"], upgrade))
            except KeeperError as exc:
                events.append(self._blocked(record, exc))
                return events
            if upgrade is None:
                upgrade = self._intent(record)
                evolution["upgrade"] = upgrade
                evolution["last_error"] = ""
                self._save()
            while upgrade["step"] < len(upgrade["transitions"]) and mutations < _MAX_MUTATIONS:
                transition = upgrade["transitions"][upgrade["step"]]
                xyz = " ".join(map(str, transition["pos"]))
                try:
                    self._environment()
                    self._verify_cells([{"pos": transition["pos"], "state": transition["expected"]}])
                except KeeperError as exc:
                    events.append(self._blocked(record, exc))
                    return events
                upgrade["uncertain"] = True
                upgrade["status"] = "uncertain"
                self._save()
                command = (f"execute in {_DIMENSION} {self._guards()} if block {xyz} {_block(transition['expected'])} "
                           f"run setblock {xyz} {_block(transition['target'])} replace")
                try:
                    response = self.command(command)
                    expected_reply = f"Changed the block at {transition['pos'][0]}, {transition['pos'][1]}, {transition['pos'][2]}"
                    if not isinstance(response, str) or response.strip() != expected_reply:
                        raise KeeperUncertain("Keeper mutation acknowledgement is not exact: " + repr(response)[:256])
                    self._verify_cells([{"pos": transition["pos"], "state": transition["target"]}], label="mutation post-state")
                except Exception as exc:
                    message = " ".join(str(exc).split())[:_MAX_TEXT]
                    evolution["last_error"] = message
                    self._evidence(upgrade, message)
                    self._save()
                    raise KeeperUncertain("Keeper dispatched step remains uncertain; stop writers and reconcile: " + message) from exc
                upgrade["step"] += 1
                upgrade["uncertain"] = False
                upgrade["status"] = "verifying" if upgrade["step"] == len(upgrade["transitions"]) else "ready"
                evolution["last_error"] = ""
                self._evidence(upgrade, expected_reply)
                self._save()
                mutations += 1
            if upgrade["step"] == len(upgrade["transitions"]):
                try:
                    self._static()
                except KeeperError as exc:
                    self._blocked(record, exc)
                    raise
                try:
                    self._environment()
                    self._verify_cells(self._appearance(evolution["installed_rank"], upgrade), label="cumulative postflight")
                except KeeperError as exc:
                    events.append(self._blocked(record, exc))
                    return events
                evolution["installed_rank"] = upgrade["target_rank"]
                evolution["upgrade"] = None
                evolution["last_error"] = ""
                self._save()
                events.append({"keeper_id": self.keeper_id, "success": True, "installed_rank": evolution["installed_rank"]})
        return events
