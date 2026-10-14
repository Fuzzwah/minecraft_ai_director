"""Exact-state Keeper decoration authoring; never modifies generation assets."""

import copy
import json
from collections import deque
from pathlib import Path

if __package__:
    from . import nbt
    from . import village_temples as temples
else:
    import nbt
    import village_temples as temples

DEFAULT_DEFINITIONS = temples.BASE / "config/keeper_temples.json"
AIR = {"id": "minecraft:air"}
FULL_TARGETS = {
    "minecraft:chiseled_sandstone", "minecraft:gold_block", "minecraft:glowstone",
    "minecraft:waxed_copper_block", "minecraft:waxed_cut_copper",
    "minecraft:waxed_chiseled_copper",
}
COPPER = {name for name in FULL_TARGETS if "copper" in name} | {
    "minecraft:waxed_cut_copper_stairs", "minecraft:waxed_cut_copper_slab",
}
TARGET_IDS = FULL_TARGETS | COPPER | {"minecraft:lantern", "minecraft:iron_chain"}


def _state(name, **properties):
    result = {"id": "minecraft:" + name}
    if properties:
        result["properties"] = properties
    return result


def _cells(positions, blocks):
    return [{"pos": list(p), "state": copy.deepcopy(blocks[p])} for p in sorted(positions)]


def _walk_edges(blocks, p):
    """Same no-jumping, directional-stair convention as temple reachability."""
    directions = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
    x, y, z = p
    for dx, dz in directions.values():
        for dy in (-1, 0, 1):
            target = (x + dx, y + dy, z + dz)
            support = blocks.get((target[0], target[1] - 1, target[2]), {})
            if not (support.get("id") in temples.SOLID or (
                support.get("id", "").endswith("_stairs")
                and support.get("properties", {}).get("half") == "bottom")):
                continue
            if any(blocks.get((target[0], target[1] + h, target[2]), {}).get("id")
                   not in temples.PASSABLE for h in (0, 1)):
                continue
            if dy:
                upper = target if dy > 0 else p
                stair = blocks.get((upper[0], upper[1] - 1, upper[2]), {})
                uphill = (dx, dz) if dy > 0 else (-dx, -dz)
                if not stair.get("id", "").endswith("_stairs") or directions.get(
                        stair.get("properties", {}).get("facing")) != uphill:
                    continue
                lower = p if dy > 0 else target
                if blocks.get((lower[0], lower[1] + 2, lower[2]), {}).get("id") not in temples.PASSABLE:
                    continue
            yield target


def _routes(blocks, start, targets, excluded):
    # Reserve one explicit, supported road-to-source route even at partial ranks.
    guarded = dict(blocks)
    for p in excluded:
        guarded[p] = _state("gold_block")
    start = tuple(start)
    # Reconstruct paths with a predecessor-bearing BFS rather than a set of all
    # reachable floor cells, keeping the runtime probe footprint small.
    parents, queue = {start: None}, deque([start])
    while queue:
        p = queue.popleft()
        for target in _walk_edges(guarded, p):
            if target not in parents:
                parents[target] = p
                queue.append(target)
    positions = set()
    for target in targets:
        target = tuple(target)
        if target not in parents:
            raise ValueError(f"No immutable supported access route to {target}")
        while target is not None:
            x, y, z = target
            positions.update({(x, y - 1, z), (x, y, z), (x, y + 1, z)})
            previous = parents[target]
            if previous is not None and previous[1] != y:
                lower = previous if previous[1] < y else target
                positions.add((lower[0], lower[1] + 2, lower[2]))
            target = previous
    return positions


def author_definition(root, record):
    """Derive a root's four cumulative, ordered stages from its real NBT."""
    original = temples.block_map(root)
    current = dict(original)
    floor = record["floor_y"]
    stages = {str(rank): [] for rank in range(2, 6)}

    def put(rank, x, y, z, state):
        p = (x, floor + y, z)
        stages[str(rank)].append({"pos": list(p), "expected": copy.deepcopy(current[p]),
                                  "target": copy.deepcopy(state)})
        current[p] = state

    standing = _state("lantern", hanging="false", waterlogged="false")
    # Entrance and altar lights are away from the central supported approach.
    for x, z in ((9, 8), (15, 8), (10, 18), (14, 18)):
        put(2, x, 4, z, _state("chiseled_sandstone"))
        put(2, x, 5, z, standing)

    # Two squat golems, 3 wide x 2 deep x 5 high. Feet and legs precede the
    # torso/shoulders; the chiseled face, projecting nose and antenna follow.
    for x in (8, 16):
        for dx in (-1, 1):
            put(3, x + dx, 4, 16, _state("waxed_cut_copper_stairs", facing="north",
                                        half="bottom", shape="straight", waterlogged="false"))
        for dx in (-1, 1):
            put(3, x + dx, 5, 16, _state("waxed_cut_copper"))
        for y in (5, 6):
            put(3, x, y, 16, _state("waxed_copper_block"))
        for dx in (-1, 1):
            put(3, x + dx, 6, 16, _state("waxed_cut_copper_stairs",
                                        facing="east" if dx == -1 else "west", half="bottom",
                                        shape="straight", waterlogged="false"))
        put(3, x, 7, 16, _state("waxed_chiseled_copper"))
        put(3, x, 7, 15, _state("waxed_cut_copper_slab", type="bottom", waterlogged="false"))
        put(3, x, 8, 16, _state("waxed_cut_copper_slab", type="bottom", waterlogged="false"))

    # The seated idol keeps its central stone trunk and original crown. Carve
    # its lower flanks, add copper shoulders and gold brows beside that trunk.
    for x in (11, 13):
        for y in (5, 6):
            put(4, x, y, 19, _state("chiseled_sandstone"))
        put(4, x, 8, 19, _state("waxed_cut_copper"))
        put(4, x, 9, 19, _state("gold_block"))
    for x in (5, 7, 17, 19):
        state = copy.deepcopy(original[(x, floor + 10, 10)])
        state["id"] = "minecraft:waxed_cut_copper_stairs"
        put(4, x, 10, 10, state)

    # Hanging lamps are authored from the roof down: every partial chain is
    # anchored before its lantern is dispatched. Existing lamps remain intact.
    for x in (9, 15):
        for z in (14, 18):
            for y in (10, 9, 8):
                put(5, x, y, z, _state("iron_chain", axis="y", waterlogged="false"))
            put(5, x, 7, z, _state("lantern", hanging="true", waterlogged="false"))
    for x, y in ((11, 14), (13, 14), (12, 13), (12, 15)):
        put(5, x, y, 7, _state("glowstone"))
    for x, y in ((10, 14), (14, 14), (12, 12), (12, 16)):
        put(5, x, y, 7, _state("gold_block"))

    mutable = {tuple(t["pos"]) for stage in stages.values() for t in stage}
    identity = {tuple(record["containers"]["offering_chest"]), tuple(record["altar"]["base"]),
                tuple(record["altar"]["top"])}
    for feature in ("columns", "column_bases", "lighting", "ridge"):
        identity.update(tuple(cell["pos"]) for cell in record["features"][feature])
    identity.update((12, floor + y, 19) for y in range(4, 11))
    identity.update((x, floor + y, 7) for x in (4, 20) for y in (8, 12, 16))
    identity.update({(12, floor + 18, 8), (6, floor + 11, 8), (18, floor + 11, 8)})
    # Preserve actual structural anchor neighbors, not merely target decoration.
    for p in mutable:
        for q in _neighbors(p):
            if q in original and q not in mutable and _solid(original[q]):
                identity.add(q)
    identity -= mutable
    roads = [j["pos"] for j in record["jigsaws"] if j["nbt"]["pool"].endswith("/streets")]
    # Native street/terrain assembly owns the connector plus its two inward
    # columns, not just the endpoint. Untouched same-seed generation leaves
    # paths, grass and plants there instead of literal template states.
    # Reserve exact supported routes from the first internal plaza column.
    w, _, d = root["size"]
    inward_roads = [(max(1, min(w - 2, x)), y, max(1, min(d - 2, z))) for x, y, z in roads]
    perimeter = {p for p in original if p[0] in (0, w - 1) or p[2] in (0, d - 1)}
    street_fringe = {p for p in original if p[0] < 3 or p[0] >= w - 3 or p[2] < 3 or p[2] >= d - 3}
    access = _routes(original, record["altar"]["approach"],
                     [record["entry"], record["chest_approach"], *inward_roads], mutable | perimeter)
    chest = record["containers"]["offering_chest"]
    access.add((chest[0], chest[1] + 1, chest[2]))
    access -= identity
    access -= street_fringe
    # Ancillary jigsaws can also lie on an internal route. Their final
    # structure_void is skipped during placement, not a literal world block.
    access -= {p for p, state in original.items() if state["id"] == "minecraft:structure_void"}
    if access & mutable:
        raise ValueError("Decoration intersects reserved source access")
    return {"size": list(root["size"]), "floor_y": floor, "chest": list(chest),
            "entry": list(record["entry"]), "mutable_baseline": _cells(mutable, original),
            "invariants": _cells(identity, original), "access": _cells(access, original),
            "milestones": stages}


def _neighbors(p):
    x, y, z = p
    return ((x - 1, y, z), (x + 1, y, z), (x, y - 1, z),
            (x, y + 1, z), (x, y, z - 1), (x, y, z + 1))


def _solid(state):
    return state.get("id") in temples.SOLID or state.get("id") in FULL_TARGETS


def _target_state(state):
    if not isinstance(state, dict) or set(state) - {"id", "properties"} or state.get("id") not in TARGET_IDS:
        raise ValueError("Forbidden sensitive or unsupported decoration state")
    properties = state.get("properties", {})
    name = state["id"]
    if name in FULL_TARGETS:
        valid = not properties and "properties" not in state
    elif name.endswith("_stairs"):
        valid = (set(properties) == {"facing", "half", "shape", "waterlogged"}
                 and properties["facing"] in ("north", "east", "south", "west")
                 and properties["half"] in ("bottom", "top")
                 and properties["shape"] == "straight" and properties["waterlogged"] == "false")
    elif name.endswith("_slab"):
        valid = properties == {"type": "bottom", "waterlogged": "false"}
    elif name == "minecraft:lantern":
        valid = (set(properties) == {"hanging", "waterlogged"}
                 and properties["hanging"] in ("true", "false") and properties["waterlogged"] == "false")
    else:
        valid = properties == {"axis": "y", "waterlogged": "false"}
    if not valid:
        raise ValueError("Incomplete or unsupported decoration properties")


def rotated_definition(definition, turns):
    """Rotate local cells and complete directional states with existing conventions."""
    size = definition["size"]
    result = copy.deepcopy(definition)
    if turns % 2:
        result["size"] = [size[2], size[1], size[0]]
    for key in ("chest", "entry"):
        result[key] = list(temples.rotate(definition[key], size, turns))
    for key in ("mutable_baseline", "invariants", "access"):
        for cell in result[key]:
            cell["pos"] = list(temples.rotate(cell["pos"], size, turns))
            cell["state"] = temples.rotated_state(cell["state"], turns)
    for stage in result["milestones"].values():
        for cell in stage:
            cell["pos"] = list(temples.rotate(cell["pos"], size, turns))
            for key in ("expected", "target"):
                cell[key] = temples.rotated_state(cell[key], turns)
    return result


def validate_geometry(root, record, definition, blocks, *, turns=0):
    """Validate a real rotated intermediate map, without baseline feature equality."""
    size = root["size"]
    rotated = rotated_definition(definition, turns)
    for group in ("invariants", "access"):
        for cell in rotated[group]:
            if blocks.get(tuple(cell["pos"])) != cell["state"]:
                raise ValueError(f"Changed required {group} cell {cell['pos']}")
    chest = tuple(rotated["chest"])
    if blocks.get((chest[0], chest[1] + 1, chest[2])) != AIR:
        raise ValueError("Offering chest lid is obstructed")
    seen = temples.reachable(blocks, temples.rotate(record["altar"]["approach"], size, turns))
    targets = [record["entry"], record["chest_approach"]] + [
        j["pos"] for j in record["jigsaws"] if j["nbt"]["pool"].endswith("/streets")]
    if any(temples.rotate(p, size, turns) not in seen for p in targets):
        raise ValueError("Unsupported or obstructed road-to-altar/chest access")
    mutable = {tuple(c["pos"]) for c in rotated["mutable_baseline"]}
    building = {p for p in mutable if blocks.get(p, {}).get("id") in FULL_TARGETS | COPPER}
    anchored = {p for p in building if any(q not in building and _solid(blocks.get(q, {}))
                                          for q in _neighbors(p))}
    queue = deque(anchored)
    while queue:
        for q in _neighbors(queue.popleft()):
            if q in building and q not in anchored:
                anchored.add(q)
                queue.append(q)
    if building - anchored:
        raise ValueError("Unsupported sculpture or decorative stone component")
    # Check original as well as new lamps/chains so removing a hidden roof
    # anchor or reversing chain dispatch cannot pass a partial-stage check.
    for p, state in blocks.items():
        if state.get("id") not in {"minecraft:lantern", "minecraft:iron_chain"}:
            continue
        x, y, z = p
        if state["id"] == "minecraft:lantern" and state["properties"]["hanging"] == "false":
            if not _solid(blocks.get((x, y - 1, z), {})):
                raise ValueError("Unsupported standing lantern")
            continue
        above = (x, y + 1, z)
        while blocks.get(above, {}).get("id") == "minecraft:iron_chain":
            if blocks[above].get("properties") != {"axis": "y", "waterlogged": "false"}:
                raise ValueError("Wrong hanging chain orientation")
            above = (x, above[1] + 1, z)
        if not _solid(blocks.get(above, {})):
            raise ValueError("Unsupported hanging lantern or chain")


def _load_pack(output):
    output = Path(output)
    manifest = json.loads((output / "manifest.json").read_bytes())
    return manifest, {resource: nbt.loads((output / temples.resource_path(resource)).read_bytes())
                      for resource in manifest["roots"]}


def author_manifest(output=temples.DEFAULT_OUTPUT):
    manifest, roots = _load_pack(output)
    return {"version": 1, "minecraft_version": "26.3", "roots": {
        resource: author_definition(root, manifest["roots"][resource])
        for resource, root in roots.items()}}


def _positions(cells, state_keys, size):
    positions = set()
    for cell in cells:
        if not isinstance(cell, dict) or set(cell) != {"pos", *state_keys}:
            raise ValueError("Malformed patch cell or forbidden payload")
        p = cell["pos"]
        if (not isinstance(p, list) or len(p) != 3 or any(type(v) is not int for v in p)
                or any(v < 0 or v >= limit for v, limit in zip(p, size))):
            raise ValueError("Patch position outside root bounds")
        p = tuple(p)
        if p in positions:
            raise ValueError("Duplicate patch position")
        positions.add(p)
    return positions


def validate_definition(root, record, definition, *, processors=(), tags=None):
    """Validate every mutation prefix in four facings against actual root states."""
    if set(definition) != {"size", "floor_y", "chest", "entry", "mutable_baseline", "invariants", "access", "milestones"}:
        raise ValueError("Malformed Keeper root definition")
    if (definition["size"] != list(root["size"]) or definition["floor_y"] != record["floor_y"]
            or definition["chest"] != record["containers"]["offering_chest"] or definition["entry"] != record["entry"]):
        raise ValueError("Wrong root geometry or source")
    size = definition["size"]
    original = temples.block_map(root)
    baseline = _positions(definition["mutable_baseline"], ("state",), size)
    immutable = set()
    for group in ("invariants", "access"):
        positions = _positions(definition[group], ("state",), size)
        if positions & (baseline | immutable):
            raise ValueError("Decoration intersects forbidden identity/access cells")
        immutable |= positions
    if tuple(definition["chest"]) not in {tuple(c["pos"]) for c in definition["invariants"]}:
        raise ValueError("Offering chest missing from invariant identity")
    for group in ("mutable_baseline", "invariants", "access"):
        for cell in definition[group]:
            if original.get(tuple(cell["pos"])) != cell["state"]:
                raise ValueError(f"Incorrect exact NBT baseline for {group}")
            if cell["state"]["id"] == "minecraft:structure_void":
                raise ValueError("Skipped jigsaw cells cannot be exact world probes")
            for processor in processors:
                if any(outcome != cell["state"] for outcome in temples.processor_outcomes(
                        cell["state"], processor, tags or {})):
                    raise ValueError("Processor-unstable Keeper probe or target baseline")
    payloads = {tuple(b["pos"]) for b in root["blocks"] if "nbt" in b}
    if baseline & payloads:
        raise ValueError("Forbidden sensitive template cell")
    if set(definition["milestones"]) != {"2", "3", "4", "5"}:
        raise ValueError("Incomplete four-stage milestone coverage")
    union = set()
    expected = dict(original)
    for rank in range(2, 6):
        stage = definition["milestones"][str(rank)]
        positions = _positions(stage, ("expected", "target"), size)
        if not stage or positions - baseline or positions & immutable:
            raise ValueError("Unapproved or forbidden milestone footprint")
        union |= positions
        for cell in stage:
            p = tuple(cell["pos"])
            _target_state(cell["target"])
            if cell["expected"] != expected[p] or cell["expected"] == cell["target"]:
                raise ValueError("Wrong exact predecessor state or no-op transition")
            if (cell["expected"].get("id") not in temples.SOLID | temples.PASSABLE | TARGET_IDS
                    and not cell["expected"].get("id", "").endswith("_stairs")) or p[1] <= record["floor_y"]:
                raise ValueError("Forbidden sensitive or foundational replacement")
            expected[p] = cell["target"]
    if union != baseline:
        raise ValueError("Mutable baseline does not exactly cover all transitions")
    prefixes = 0
    for turns in range(4):
        blocks = {temples.rotate(p, size, turns): temples.rotated_state(s, turns) for p, s in original.items()}
        rotated = rotated_definition(definition, turns)
        validate_geometry(root, record, definition, blocks, turns=turns)
        for rank in range(2, 6):
            for cell in rotated["milestones"][str(rank)]:
                blocks[tuple(cell["pos"])] = cell["target"]
                validate_geometry(root, record, definition, blocks, turns=turns)
                prefixes += 1
    # Geometry is necessary but not a license to silently author a different
    # silhouette, rotate an arm incorrectly, or omit one of the intended stages.
    if definition != author_definition(root, record):
        raise ValueError("Patch differs from reviewed authored milestone geometry")
    return {"rotations": 4, "ranks": 5, "prefixes": prefixes}


def validate_manifest(value, output=temples.DEFAULT_OUTPUT):
    manifest, roots = _load_pack(output)
    if (not isinstance(value, dict) or set(value) != {"version", "minecraft_version", "roots"}
            or type(value["version"]) is not int or value["version"] != 1 or value["minecraft_version"] != "26.3"
            or set(value["roots"]) != set(roots)):
        raise ValueError("Unsupported manifest or incomplete normal/abandoned root coverage")
    selected = {resource: [] for resource in roots}
    for pool in manifest["source_pools"].values():
        for entry in pool["elements"]:
            element = entry["element"]
            processors = element["processors"]
            selected[element["location"]].append(manifest["processor_lists"][processors]
                                                  if isinstance(processors, str) else processors)
    prefixes = 0
    for resource, root in roots.items():
        try:
            temples.validate_root(root, manifest["roots"][resource])
            result = validate_definition(root, manifest["roots"][resource], value["roots"][resource],
                                         processors=selected[resource], tags=manifest["processor_tags"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"{resource}: {exc}") from exc
        prefixes += result["prefixes"]
    return {"roots": len(roots), "rotations": 4 * len(roots), "ranks": 5,
            "cumulative_states": 20 * len(roots), "prefixes": prefixes}


def check_patches(path=DEFAULT_DEFINITIONS, output=temples.DEFAULT_OUTPUT):
    return validate_manifest(json.loads(Path(path).read_bytes()), output)


def write_patches(path=DEFAULT_DEFINITIONS, output=temples.DEFAULT_OUTPUT):
    value = author_manifest(output)
    result = validate_manifest(value, output)
    Path(path).write_bytes(temples.json_bytes(value))
    return result
