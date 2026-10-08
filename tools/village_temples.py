"""Author/inspect mandatory 26.3 village roots from the pinned server archive.

python3 -B tools/village_temples.py --archive /path/to/server-26.3.jar
python3 -B tools/village_temples.py --check

The recipes replace each decorative centerpiece with a sandstone landmark on a
25-block plaza. Road jigsaws move to the corresponding outer edge without
changing their height, orientation, pools, or final states. This is development
tooling, never a running-world mutation mechanism.
"""

import argparse
import copy
import hashlib
import json
import zipfile
from collections import deque
from pathlib import Path

if __package__:
    from . import nbt
else:
    import nbt

BASE = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BASE / "datapack/director_village_temples"
RECIPES = Path(__file__).with_name("village_temple_recipes.json")
ARCHIVE_SHA256 = "a362163eec5d1612d520772bc16e5b39c09e3b234fdc045f56bf544284ee8ae6"
STYLES = ("plains", "desert", "savanna", "snowy", "taiga")
MATERIALS = {style: {"column": "sandstone", "wall": "smooth_sandstone",
                     "roof": "cut_sandstone"} for style in STYLES}
# Desert abandonment replaces smooth/cut sandstone with cobwebs. Use the
# unaffected carved/base sandstone family there, without altering processors.
MATERIALS["desert"] = {"column": "sandstone", "wall": "sandstone", "roof": "sandstone"}
DESERT_STONE = {"smooth_sandstone": "sandstone", "cut_sandstone": "sandstone",
                "smooth_sandstone_stairs": "sandstone_stairs",
                "smooth_sandstone_slab": "sandstone_slab"}
ALTAR_BASE = "minecraft:chiseled_stone_bricks"
ALTAR_TOP = {"id": "minecraft:smooth_stone_slab", "properties": {"type": "top", "waterlogged": "false"}}
CONTAINER_IDS = {"offering_chest": "minecraft:chest"}
CONTAINER_STATES = {
    "offering_chest": {"id": "minecraft:chest",
                       "properties": {"waterlogged": "false", "facing": "north", "type": "single"}},
}
PACK_META = {"pack": {"description": "Keeper temples in every vanilla village — Java 26.3 only",
                       "min_format": [121, 0], "max_format": [121, 0]}}
PASSABLE = {"minecraft:air", "minecraft:cave_air", "minecraft:structure_void"}
SOLID = {"minecraft:smooth_stone", "minecraft:chiseled_stone_bricks", "minecraft:sandstone",
         "minecraft:smooth_sandstone", "minecraft:stripped_oak_log", "minecraft:stripped_oak_wood",
         "minecraft:stripped_acacia_log", "minecraft:stripped_acacia_wood", "minecraft:stripped_spruce_log",
         "minecraft:stripped_spruce_wood", "minecraft:snow_block", "minecraft:dirt_path",
         "minecraft:grass_block", "minecraft:cobblestone", "minecraft:sand", "minecraft:mossy_cobblestone"}
SOLID |= {"minecraft:cut_sandstone", "minecraft:chiseled_sandstone",
          "minecraft:gold_block", "minecraft:glowstone", "minecraft:stone_bricks"}


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def resource_path(resource):
    namespace, name = resource.split(":", 1)
    return Path("data") / namespace / "structure" / (name + ".nbt")


def pool_path(style):
    return Path(f"data/minecraft/worldgen/template_pool/village/{style}/town_centers.json")


def joints(root):
    return [b for b in root["blocks"] if root["palette"][b["state"]]["id"] == "minecraft:jigsaw"]


def is_road(block):
    return block["nbt"]["pool"].endswith("/streets")


def joint_record(root, block):
    return {"pos": list(block["pos"]), "state": copy.deepcopy(root["palette"][block["state"]]),
            "nbt": copy.deepcopy(block["nbt"])}


def block_map(root, *, final=True):
    result = {}
    for block in root["blocks"]:
        position = tuple(block["pos"])
        if position in result:
            raise ValueError(f"Duplicate template position {position}")
        state = root["palette"][block["state"]]
        if final and state["id"] == "minecraft:jigsaw":
            state = {"id": block["nbt"]["final_state"].split("[")[0]}
        result[position] = state
    return result


def rotate(position, size, turns):
    x, y, z = position
    w, _, d = size
    return ((x, y, z), (d - 1 - z, y, x), (w - 1 - x, y, d - 1 - z),
            (z, y, w - 1 - x))[turns]


def rotated_state(state, turns):
    state = copy.deepcopy(state)
    properties = state.get("properties", {})
    directions = ("north", "east", "south", "west")
    for key in ("facing", "orientation"):
        if key in properties:
            properties[key] = "_".join(directions[(directions.index(part) + turns) % 4]
                                       if part in directions else part for part in properties[key].split("_"))
    if turns % 2 and properties.get("axis") in ("x", "z"):
        properties["axis"] = "z" if properties["axis"] == "x" else "x"
    return state


def reachable(blocks, start):
    """Conservative two-block clearance, with directed half-block stair access.

    Nodes are feet positions above full cubes or bottom stairs. Ascending onto
    stairs is allowed only through the low face; full-block jumping is not a
    substitute for a usable staircase.
    """
    directions = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}

    def walkable(p):
        x, y, z = p
        support = blocks.get((x, y - 1, z), {})
        return (support.get("id") in SOLID or (
            support.get("id", "").endswith("_stairs")
            and support.get("properties", {}).get("half") == "bottom")) and all(
                blocks.get((x, y + h, z), {}).get("id") in PASSABLE for h in (0, 1))

    start = tuple(start)
    if not walkable(start):
        return set()
    found, queue = {start}, deque([start])
    while queue:
        x, y, z = queue.popleft()
        for dx, dz in directions.values():
            for dy in (-1, 0, 1):
                point = (x + dx, y + dy, z + dz)
                if point in found or not walkable(point):
                    continue
                if dy:
                    upper = point if dy > 0 else (x, y, z)
                    support = blocks.get((upper[0], upper[1] - 1, upper[2]), {})
                    facing = support.get("properties", {}).get("facing")
                    uphill = (dx, dz) if dy > 0 else (-dx, -dz)
                    if not support.get("id", "").endswith("_stairs") or directions.get(facing) != uphill:
                        continue
                    lower = (x, y, z) if dy > 0 else point
                    if blocks.get((lower[0], lower[1] + 2, lower[2]), {}).get("id") not in PASSABLE:
                        continue
                found.add(point)
                queue.append(point)
    return found


def validate_root(root, record, *, rotations=range(4)):
    """Validate landmark geometry, chest usability, and every road-to-altar route."""
    size = root["size"]
    floor = record["floor_y"]
    if root.get("DataVersion") != 5023 or root.get("entities"):
        raise ValueError("Wrong DataVersion or embedded entities")
    if list(size) != [25, floor + 20, 25]:
        raise ValueError("Changed landmark bounds")
    original = record["source_jigsaws"]
    expected = copy.deepcopy(original)
    for adjustment in record["connector_adjustments"]:
        index = adjustment["index"]
        if adjustment["from"] != original[index]["pos"]:
            raise ValueError("Invalid jigsaw relocation provenance")
        expected[index]["pos"] = adjustment["to"]
    for source, joint in zip(original, expected):
        if source["nbt"]["pool"].endswith("/streets"):
            if joint["pos"] != road_position(source, record["source_size"]):
                raise ValueError("Road jigsaw must face outward at the expanded plaza edge")
    current = [joint_record(root, b) for b in joints(root)]
    if sorted(current, key=lambda b: tuple(b["pos"])) != sorted(expected, key=lambda b: tuple(b["pos"])):
        raise ValueError("Lost/changed trusted jigsaw metadata or position")
    entries = {tuple(block["pos"]): block for block in root["blocks"]}
    if len(entries) != size[0] * size[1] * size[2] or len(entries) != len(root["blocks"]):
        raise ValueError("Missing explicit entry/volume clearance or duplicate blocks")
    for block in root["blocks"]:
        if any(p < 0 or p >= limit for p, limit in zip(block["pos"], size)):
            raise ValueError("Block outside root bounds")
        block_id = root["palette"][block["state"]]["id"]
        if "nbt" in block and block_id not in {"minecraft:jigsaw", *CONTAINER_IDS.values()}:
            raise ValueError("Unexpected block entity payload")
    blocks = block_map(root)
    containers = {name: tuple(position) for name, position in record["containers"].items()}
    actual = {p for p, state in blocks.items() if state["id"] in {*CONTAINER_IDS.values(), "minecraft:ender_chest"}}
    if set(containers) != {"offering_chest"} or actual != set(containers.values()):
        raise ValueError("Expected exactly one normal offering chest and no ender chest")
    for name, position in containers.items():
        payload = entries[position].get("nbt", {})
        if blocks[position] != CONTAINER_STATES[name] or payload.get("id") != CONTAINER_IDS[name]:
            raise ValueError("Invalid offering chest state or block entity")
        if "Items" not in payload or payload["Items"] or "LootTable" in payload:
            raise ValueError("Offering chest must start empty without a loot table")
        if blocks.get((position[0], position[1] + 1, position[2]), {}).get("id") != "minecraft:air":
            raise ValueError("Offering chest lid is obstructed")
    ax, ay, az = record["altar"]["base"]
    if sum(state["id"] == ALTAR_BASE for state in blocks.values()) != 1:
        raise ValueError("Expected exactly one Keeper altar")
    if blocks.get((ax, ay, az), {}).get("id") != ALTAR_BASE or blocks.get((ax, ay + 1, az)) != ALTAR_TOP:
        raise ValueError("Altar identity/position changed")
    for feature, cells in record["features"].items():
        for cell in cells:
            if blocks.get(tuple(cell["pos"])) != cell["state"]:
                raise ValueError(f"Incomplete landmark {feature}")
    # Entire terrace and plaza are supported, not only the selected walking path.
    for x in range(25):
        for z in range(25):
            for y in range(floor + 1):
                if blocks.get((x, y, z), {}).get("id") not in SOLID:
                    raise ValueError("Unsupported temple floor")
    entry = tuple(record["entry"])
    for p in (entry, tuple(record["altar"]["approach"]), tuple(record["chest_approach"])):
        if any(blocks.get((p[0], p[1] + h, p[2]), {}).get("id") != "minecraft:air" for h in (0, 1)):
            raise ValueError("Obstructed entry or interior explicit air clearance")
    roads = [tuple(j["pos"]) for j in expected if j["nbt"]["pool"].endswith("/streets")]
    rotations = tuple(rotations)
    for turns in rotations:
        rotated = {rotate(p, size, turns): rotated_state(state, turns) for p, state in blocks.items()}
        seen = reachable(rotated, rotate(record["altar"]["approach"], size, turns))
        for target in (entry, tuple(record["chest_approach"])):
            if rotate(target, size, turns) not in seen:
                raise ValueError(f"Altar/chest unreachable through entrance in rotation {turns}")
        for road in roads:
            if rotate(road, size, turns) not in seen:
                raise ValueError(f"Road cannot reach altar in rotation {turns}: {road}")
    return {"rotations": len(rotations), "roads": len(roads), "altar": [ax, ay, az],
            **{name: len(cells) for name, cells in record["features"].items()}}


def validate_processors(root, record, processors, tags):
    """Prove all random rule outcomes preserve authored critical cells.

    This does not substitute for actual terrain/downstream-piece generation.
    """
    floor = record["floor_y"]
    ax, ay, az = record["altar"]["base"]
    critical_positions = {tuple(cell["pos"]) for cells in record["features"].values() for cell in cells}
    critical_positions |= {(ax, ay, az), (ax, ay + 1, az)}

    def state(value):
        return {"id": value} if isinstance(value, str) else value

    def matches(predicate, original):
        kind = predicate["predicate_type"]
        if kind in ("minecraft:block_match", "minecraft:random_block_match"):
            return predicate["block"] == original["id"]
        if kind == "minecraft:blockstate_match":
            return state(predicate["block_state"]) == original
        if kind == "minecraft:tag_match":
            return original["id"] in tags[predicate["tag"]]
        raise ValueError(f"Unsupported consumed processor predicate {kind}")

    def outcomes(original):
        possible = [original]
        for processor in processors["processors"]:
            if processor["processor_type"] != "minecraft:rule":
                raise ValueError("Unsupported consumed processor type")
            next_states = []
            for old in possible:
                for rule in processor["rules"]:
                    if rule["location_predicate"]["predicate_type"] != "minecraft:always_true":
                        raise ValueError("Unsupported consumed location predicate")
                    predicate = rule["input_predicate"]
                    if matches(predicate, old):
                        next_states.append(state(rule["output_state"]))
                        if predicate["predicate_type"] != "minecraft:random_block_match":
                            break
                else:
                    next_states.append(old)
            possible = next_states
        return possible

    palette_outcomes = [outcomes(state) for state in root["palette"]]
    for block in root["blocks"]:
        x, y, z = block["pos"]
        original = root["palette"][block["state"]]
        if original["id"] == "minecraft:jigsaw":
            continue
        candidates = palette_outcomes[block["state"]]
        if original["id"] in CONTAINER_IDS.values():
            if any(candidate != original for candidate in candidates):
                raise ValueError("Processor can change approved container")
            continue
        if (x, y, z) in critical_positions and any(candidate != original for candidate in candidates):
            if (x, y, z) in {(ax, ay, az), (ax, ay + 1, az)}:
                raise ValueError("Processor can change recognizable altar")
            raise ValueError("Processor can change Greek structural identity")
        if y <= floor:
            if any(candidate["id"] not in SOLID for candidate in candidates):
                raise ValueError("Processor can remove floor support or solid roof")
        elif (x, z) == (ax, az) and y in (ay, ay + 1):
            if any(candidate != original for candidate in candidates):
                raise ValueError("Processor can change recognizable altar")
        elif original["id"] == "minecraft:air":
            if any(candidate != original for candidate in candidates):
                raise ValueError("Processor can obstruct explicit clearance")



def choose_weighted(pool, ticket):
    if not 0 <= ticket < sum(e["weight"] for e in pool["elements"]):
        raise ValueError("Weighted selection ticket outside pool")
    for entry in pool["elements"]:
        if ticket < entry["weight"]:
            return entry["element"]["location"]
        ticket -= entry["weight"]
    raise AssertionError("Unreachable weighted selection")


def validate_pack(output=DEFAULT_OUTPUT):
    output = Path(output)
    manifest = json.loads((output / "manifest.json").read_bytes())
    if json.loads((output / "pack.mcmeta").read_bytes()) != PACK_META:
        raise ValueError("Pack must target precisely 121.0")
    selected = set()
    counts = {}
    for style in STYLES:
        pool = json.loads((output / pool_path(style)).read_bytes())
        vanilla = copy.deepcopy(manifest["source_pools"][style])
        for entry in vanilla["elements"]:
            entry["element"]["element_type"] = "minecraft:single_pool_element"
        if pool != vanilla:
            raise ValueError("Changed vanilla pool ordering/weights/processors/projections")
        boundary = 0
        for entry in pool["elements"]:
            for ticket in (boundary, boundary + entry["weight"] - 1):
                resource = choose_weighted(pool, ticket)
                if resource not in manifest["roots"]:
                    raise ValueError(f"Missing authored root {resource}")
                file = output / resource_path(resource)
                if not file.is_file():
                    raise ValueError(f"Missing root asset {resource}")
                if resource not in selected:
                    root = nbt.loads(file.read_bytes())
                    record = manifest["roots"][resource]
                    validate_root(root, record)
                    processor = entry["element"]["processors"]
                    processors = manifest["processor_lists"][processor] if isinstance(processor, str) else processor
                    validate_processors(root, record, processors, manifest["processor_tags"])
                    selected.add(resource)
            boundary += entry["weight"]
        counts[style] = len(pool["elements"])
    if len(selected) != 32 or selected != set(manifest["roots"]):
        raise ValueError("Incomplete 32-way effective root coverage")
    actual = {path.relative_to(output).as_posix() for path in (output / "data").rglob("*") if path.is_file()}
    expected = {resource_path(resource).as_posix() for resource in selected} | {pool_path(s).as_posix() for s in STYLES}
    if actual != expected:
        raise ValueError("Unexpected optional piece or structure/placement override")
    return {"roots": len(selected), "rotations": len(selected) * 4, "styles": counts}


def road_position(joint, source_size):
    """Move the outward connector to its corresponding enlarged plaza edge."""
    x, y, z = joint["pos"]
    facing = joint["state"]["properties"]["orientation"].split("_")[0]
    w, _, d = source_size
    if facing == "west":
        return [0, y, 2 + round(z * 20 / (d - 1))]
    if facing == "east":
        return [24, y, 2 + round(z * 20 / (d - 1))]
    if facing == "north":
        return [2 + round(x * 20 / (w - 1)), y, 0]
    if facing == "south":
        return [2 + round(x * 20 / (w - 1)), y, 24]
    raise ValueError("Road jigsaw lacks a horizontal facing")


def author_root(source, recipe):
    root = copy.deepcopy(source)
    source_joints = joints(source)
    floors = {b["pos"][1] - 1 for b in source_joints if is_road(b)}
    if len(floors) != 1:
        raise ValueError("Recipe requires a single vanilla road ground anchor")
    floor = floors.pop()
    height = floor + 20
    root["size"] = nbt.List([25, height, 25], item_tag=3)
    palette, placed, features = [], {}, {}

    def put(x, y, z, state, feature=None, metadata=None):
        y += floor
        if isinstance(state, str):
            state = {"id": "minecraft:" + state}
        if recipe["style"] == "desert":
            name = state["id"].removeprefix("minecraft:")
            if name in DESERT_STONE:
                state = {**state, "id": "minecraft:" + DESERT_STONE[name]}
        if state not in palette:
            palette.append(state)
        block = {"pos": [x, y, z], "state": palette.index(state)}
        if metadata is not None:
            block["nbt"] = copy.deepcopy(metadata)
        placed[x, y, z] = block
        if feature:
            features.setdefault(feature, {})[x, y, z] = state

    def stair(facing, half="bottom"):
        return {"id": "minecraft:smooth_sandstone_stairs",
                "properties": {"facing": facing, "half": half, "shape": "straight", "waterlogged": "false"}}

    def slab():
        return {"id": "minecraft:smooth_sandstone_slab", "properties": {"type": "bottom", "waterlogged": "false"}}

    for x in range(25):
        for z in range(25):
            for y in range(-floor, height - floor):
                put(x, y, z, "smooth_stone" if y <= 0 else "air")
    # Raised terrace, broad three-step approach, and carved retaining walls.
    for x in range(3, 22):
        for z in range(7, 22):
            for y in range(1, 4):
                edge = x in (3, 21) or z in (7, 21)
                put(x, y, z, "chiseled_sandstone" if edge and y == 2 else "cut_sandstone", "foundation")
    for z in range(4, 7):
        top = z - 3
        for x in range(9, 16):
            for y in range(1, top):
                put(x, y, z, "cut_sandstone", "foundation")
            put(x, top, z, stair("south"), "approach_steps")
    # Sanctuary walls leave a deep, open portico in front.
    for x in range(5, 20):
        for z in range(12, 21):
            if x in (5, 19) or z == 20:
                for y in range(4, 11):
                    put(x, y, z, "chiseled_sandstone" if y in (4, 10) else "smooth_sandstone", "walls")
    for x in (6, 9, 15, 18):
        put(x, 4, 10, "cut_sandstone", "column_bases")
        for y in range(5, 10):
            put(x, y, 10, "sandstone", "columns")
        put(x, 10, 10, "gold_block", "capitals")
        for dx in (-1, 1):
            put(x + dx, 10, 10, stair("east" if dx == -1 else "west", "top"), "capitals")
    # Solid gable with stepped eaves; its front tympanum carries the sun.
    for y in range(11, 19):
        inset = y - 11
        for x in range(4 + inset, 21 - inset):
            for z in range(9, 22):
                put(x, y, z, "cut_sandstone", "roof")
        for z in range(8, 23):
            put(4 + inset, y, z, stair("east"), "pediment")
            put(20 - inset, y, z, stair("west"), "pediment")
        for x in range(5 + inset, 20 - inset):
            put(x, y, 8, "chiseled_sandstone", "pediment")
    for x, y in ((12, 14), (11, 14), (13, 14), (12, 13), (12, 15),
                 (10, 12), (14, 12), (10, 16), (14, 16)):
        put(x, y, 7, "glowstone" if (x, y) == (12, 14) else "gold_block", "sun")
    put(12, 19, 15, slab(), "ridge")
    # Paired carved obelisks, separate from the four-column facade.
    for x in (4, 20):
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                put(x + dx, 4, 7 + dz, "cut_sandstone", "obelisks")
        for y in range(5, 16):
            put(x, y, 7, "chiseled_sandstone" if y % 3 else "smooth_sandstone", "obelisks")
        put(x, 16, 7, slab(), "obelisks")
    # Seated stone idol behind the altar, with gold crown and brow.
    for x in range(11, 14):
        for y in range(4, 7):
            put(x, y, 19, "cut_sandstone", "idol")
    for y in range(7, 10):
        put(12, y, 19, "chiseled_sandstone", "idol")
    for x in (11, 13):
        put(x, 7, 19, "sandstone", "idol")
    put(12, 10, 19, "gold_block", "idol")
    altar = [12, floor + 4, 18]
    put(12, 4, 18, ALTAR_BASE.removeprefix("minecraft:"))
    put(12, 5, 18, ALTAR_TOP)
    chest = [12, floor + 4, 16]
    put(12, 4, 16, CONTAINER_STATES["offering_chest"],
        metadata={"id": "minecraft:chest", "Items": nbt.List([], item_tag=10)})
    for x in (7, 17):
        for y in (8, 9, 10):
            put(x, y, 12, {"id": "minecraft:iron_chain", "properties": {"axis": "y", "waterlogged": "false"}}, "lighting")
        put(x, 7, 12, {"id": "minecraft:lantern", "properties": {"hanging": "true", "waterlogged": "false"}}, "lighting")
    for x in (7, 17):
        for z in (7, 17):
            put(x, 4, z, "chiseled_sandstone", "lighting")
            put(x, 5, z, {"id": "minecraft:lantern", "properties": {"hanging": "false", "waterlogged": "false"}}, "lighting")
    # Road positions are derived, never guessed; ancillary connectors stay on
    # the ground-level outer plaza, away from stairs and the raised terrace.
    occupied = set()
    final_joints, adjustments = [], []
    for index, block in enumerate(source_joints):
        original = list(block["pos"])
        metadata = block["nbt"]
        state = copy.deepcopy(source["palette"][block["state"]])
        if is_road(block):
            position = road_position(joint_record(source, block), source["size"])
        else:
            final = metadata["final_state"].split("[")[0]
            y = floor + 1 if final in PASSABLE else floor
            candidates = [(x, y, z) for x in (1, 23) for z in range(2, 23)
                          if (x, y, z) not in occupied]
            position = list(min(candidates, key=lambda p: (abs(p[0] - original[0]) + abs(p[2] - original[2]), p)))
        if tuple(position) in occupied:
            raise ValueError("Expanded jigsaw positions collide")
        occupied.add(tuple(position))
        if position != original:
            adjustments.append({"index": index, "from": original, "to": position,
                                "reason": "Expand road to matching plaza edge" if is_road(block)
                                else "Keep ancillary connector on supported outer plaza"})
        put(position[0], position[1] - floor, position[2], state, metadata=metadata)
        final_joints.append({"pos": position, "state": state, "nbt": copy.deepcopy(metadata)})
    root["palette"] = nbt.List(palette, item_tag=10)
    root["blocks"] = nbt.List([placed[p] for p in sorted(placed, key=lambda p: (p[1], p[0], p[2]))], item_tag=10)
    root["entities"] = nbt.List([], item_tag=10)
    # Retain only final cells if a later architectural detail overlays a feature.
    features = {name: [{"pos": list(p), "state": state} for p, state in sorted(cells.items())
                       if palette[placed[p]["state"]] == state] for name, cells in features.items()}
    record = {"style": recipe["style"], "source_size": list(source["size"]), "size": list(root["size"]),
              "floor_y": floor, "room_min": [5, 12], "room_max": [19, 20],
              "roof_y": floor + 11, "entry": [12, floor + 4, 10],
              "altar": {"base": altar, "top": [12, floor + 5, 18], "approach": [12, floor + 4, 17]},
              "containers": {"offering_chest": chest}, "chest_approach": [12, floor + 4, 15],
              "features": features,
              "materials": {key: "minecraft:" + value for key, value in MATERIALS[recipe["style"]].items()},
              "source_jigsaws": [joint_record(source, b) for b in source_joints],
              "jigsaws": final_joints, "connector_adjustments": adjustments}
    validate_root(root, record)
    return root, record


def generate(archive, output=DEFAULT_OUTPUT):
    archive, output = Path(archive), Path(output)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    if checksum != ARCHIVE_SHA256:
        raise ValueError("Archive checksum does not match pinned Java 26.3 source")
    recipes = json.loads(RECIPES.read_bytes())
    if recipes.get("composition") != "sandstone_landmark" or recipes.get("plaza_size") != [25, 25]:
        raise ValueError("Recipes must declare the sandstone 25x25 landmark composition")
    emitted = {}
    with zipfile.ZipFile(archive) as source:
        version = json.loads(source.read("version.json"))
        if (version["id"], version["world_version"], version["protocol_version"], version["pack_version"]["data_major"],
                version["pack_version"]["data_minor"]) != ("26.3", 5023, 777, 121, 0):
            raise ValueError("Unexpected source version/format/schema")
        manifest = {"schema": 2, "provenance": {"archive_sha256": checksum, "minecraft": "26.3",
                    "data_version": 5023, "protocol": 777, "data_pack": [121, 0],
                    "recipes_sha256": hashlib.sha256(RECIPES.read_bytes()).hexdigest(),
                    "server_image": "docker.io/itzg/minecraft-server@sha256:783d2712019a3996b4168752517a08d3448ef8995879b200316c3888f98dc394"},
                    "source_pools": {}, "roots": {}, "processor_lists": {}, "processor_tags": {}}
        def resolve_tag(tag):
            if tag in manifest["processor_tags"]:
                return manifest["processor_tags"][tag]
            namespace, name = tag.split(":")
            contents = json.loads(source.read(f"data/{namespace}/tags/block/{name}.json"))
            values = []
            for value in contents["values"]:
                value = value["id"] if isinstance(value, dict) else value
                values.extend(resolve_tag(value[1:]) if value.startswith("#") else [value])
            manifest["processor_tags"][tag] = sorted(set(values))
            return manifest["processor_tags"][tag]

        for style in STYLES:
            pool = json.loads(source.read(pool_path(style).as_posix()))
            manifest["source_pools"][style] = copy.deepcopy(pool)
            for element in pool["elements"]:
                resource = element["element"]["location"]
                path = resource_path(resource)
                payload = source.read(path.as_posix())
                template = nbt.loads(payload)
                # Prove type-preserving codec can consume each real source.
                if nbt.loads(nbt.dumps(template)) != template:
                    raise ValueError("Vanilla NBT round-trip failed")
                root, record = author_root(template, recipes["roots"][resource])
                record["source_sha256"] = hashlib.sha256(payload).hexdigest()
                record["processors"] = element["element"]["processors"]
                record["abandoned"] = "/zombie/" in resource
                processor = element["element"]["processors"]
                if isinstance(processor, str):
                    manifest["processor_lists"][processor] = json.loads(source.read(
                        "data/minecraft/worldgen/processor_list/" + processor.split(":")[1] + ".json"))
                    for item in manifest["processor_lists"][processor]["processors"]:
                        for rule in item.get("rules", []):
                            if rule["input_predicate"]["predicate_type"] == "minecraft:tag_match":
                                resolve_tag(rule["input_predicate"]["tag"])
                manifest["roots"][resource] = record
                emitted[path] = nbt.dumps(root)
                element["element"]["element_type"] = "minecraft:single_pool_element"
            emitted[pool_path(style)] = json_bytes(pool)
    if set(recipes["roots"]) != set(manifest["roots"]):
        raise ValueError("Recipes do not cover exactly the selected roots")
    emitted[Path("pack.mcmeta")] = json_bytes(PACK_META)
    emitted[Path("manifest.json")] = (json.dumps(manifest, separators=(",", ":")) + "\n").encode()
    # Generated outputs only: reject stale/foreign files rather than silently
    # retaining an optional house override or deleting unrelated admin files.
    if output.exists():
        foreign = {p.relative_to(output) for p in output.rglob("*") if p.is_file()} - set(emitted)
        if foreign:
            raise ValueError(f"Output directory contains unexpected files: {sorted(map(str, foreign))}")
    for path, payload in emitted.items():
        destination = output / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    return validate_pack(output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", type=Path, help="Exact pinned vanilla Java 26.3 server archive")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Inspect committed pack without the source archive")
    args = parser.parse_args(argv)
    if args.check == bool(args.archive):
        parser.error("choose exactly one of --archive or --check")
    try:
        result = validate_pack(args.output) if args.check else generate(args.archive, args.output)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Temple assets rejected: {exc}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
