"""Author/inspect mandatory 26.3 village roots from the pinned server archive.

python3 -B tools/village_temples.py --archive /path/to/server-26.3.jar
python3 -B tools/village_temples.py --check

The recipes deliberately replace each decorative centerpiece with a 5x5 room
and an open supported plaza, retaining the vanilla root anchor and all jigsaws.
This is development tooling, never a running-world mutation mechanism.
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
MATERIALS = {
    "plains": ("stripped_oak_log", "stripped_oak_wood"),
    "desert": ("sandstone", "sandstone"),
    "savanna": ("stripped_acacia_log", "stripped_acacia_wood"),
    "snowy": ("stripped_spruce_log", "snow_block"),
    "taiga": ("stripped_spruce_log", "stripped_spruce_wood"),
}
ALTAR_BASE = "minecraft:chiseled_stone_bricks"
ALTAR_TOP = {"id": "minecraft:smooth_stone_slab", "properties": {"type": "top", "waterlogged": "false"}}
CONTAINER_IDS = {"offering_chest": "minecraft:chest", "ender_chest": "minecraft:ender_chest"}
CONTAINER_OFFSETS = {"offering_chest": (1, 1, 1), "ender_chest": (3, 1, 1)}
CONTAINER_STATES = {
    "offering_chest": {"id": "minecraft:chest",
                       "properties": {"waterlogged": "false", "facing": "south", "type": "single"}},
    "ender_chest": {"id": "minecraft:ender_chest",
                     "properties": {"waterlogged": "false", "facing": "south"}},
}
PACK_META = {"pack": {"description": "Keeper temples in every vanilla village — Java 26.3 only",
                       "min_format": [121, 0], "max_format": [121, 0]}}
PASSABLE = {"minecraft:air", "minecraft:cave_air", "minecraft:structure_void"}
SOLID = {"minecraft:smooth_stone", "minecraft:chiseled_stone_bricks", "minecraft:sandstone",
         "minecraft:stripped_oak_log", "minecraft:stripped_oak_wood", "minecraft:stripped_acacia_log",
         "minecraft:stripped_acacia_wood", "minecraft:stripped_spruce_log", "minecraft:stripped_spruce_wood",
         "minecraft:snow_block", "minecraft:dirt_path", "minecraft:grass_block", "minecraft:cobblestone",
         "minecraft:smooth_sandstone", "minecraft:sand", "minecraft:mossy_cobblestone"}


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


def reachable(blocks, start, floor):
    def walkable(p):
        x, z = p
        return (blocks.get((x, floor, z), {}).get("id") in SOLID
                and all(blocks.get((x, floor + h, z), {}).get("id") in PASSABLE for h in (1, 2)))
    if not walkable(start):
        return set()
    found = {start}
    queue = deque([start])
    while queue:
        x, z = queue.popleft()
        for point in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)):
            if point not in found and walkable(point):
                found.add(point)
                queue.append(point)
    return found


def validate_root(root, record, *, rotations=range(4)):
    """Consumer-visible geometry/jigsaw checks; raise ValueError on defects."""
    size = root["size"]
    if root.get("DataVersion") != 5023 or root.get("entities"):
        raise ValueError("Wrong DataVersion or embedded entities")
    if list(size)[::2] != record["source_size"][::2] or size[1] < record["source_size"][1]:
        raise ValueError("Changed root footprint or lowered vertical extent")
    original = record["source_jigsaws"]
    current = [joint_record(root, b) for b in joints(root)]
    expected = copy.deepcopy(original)
    for adjustment in record["connector_adjustments"]:
        expected[adjustment["index"]]["pos"] = adjustment["to"]
    if sorted(current, key=lambda b: tuple(b["pos"])) != sorted(expected, key=lambda b: tuple(b["pos"])):
        raise ValueError("Lost/changed trusted jigsaw metadata or road position")
    entries = {tuple(block["pos"]): block for block in root["blocks"]}
    for block in root["blocks"]:
        if any(p < 0 or p >= limit for p, limit in zip(block["pos"], size)):
            raise ValueError("Block outside root bounds")
        block_id = root["palette"][block["state"]]["id"]
        if "nbt" in block and block_id not in {"minecraft:jigsaw", *CONTAINER_IDS.values()}:
            raise ValueError("Unexpected block entity payload")
        if block_id in CONTAINER_IDS.values() and "nbt" not in block:
            raise ValueError("Container is missing block entity payload")
    blocks = block_map(root)
    floor = record["floor_y"]
    containers = {name: tuple(position) for name, position in record["containers"].items()}
    expected_container_positions = set(containers.values())
    seen_container_positions = {position for position, state in blocks.items()
                                if state["id"] in CONTAINER_IDS.values()}
    if seen_container_positions != expected_container_positions:
        raise ValueError("Expected exactly one offering chest and one ender chest")
    for name, position in containers.items():
        block = entries.get(position)
        state = blocks.get(position, {})
        if state.get("id") != CONTAINER_IDS[name] or block is None:
            raise ValueError(f"Invalid {name} position or block")
        payload = block.get("nbt", {})
        if payload.get("id") != CONTAINER_IDS[name]:
            raise ValueError(f"Invalid {name} block entity ID")
        if name == "offering_chest":
            if "Items" not in payload or len(payload["Items"]) != 0 or "LootTable" in payload:
                raise ValueError("Offering chest must start empty without a loot table")
    ax, ay, az = record["altar"]["base"]
    if sum(state["id"] == ALTAR_BASE for state in blocks.values()) != 1:
        raise ValueError("Expected exactly one Keeper altar")
    if blocks.get((ax, ay, az), {}).get("id") != ALTAR_BASE or blocks.get((ax, ay + 1, az)) != ALTAR_TOP:
        raise ValueError("Altar identity/position changed")
    x0, z0 = record["room_min"]
    wall, roof = MATERIALS[record["style"]]
    entry = tuple(record["entry"])
    for x in range(x0, x0 + 5):
        for z in range(z0, z0 + 5):
            if blocks.get((x, floor + 4, z), {}).get("id") != "minecraft:" + roof:
                raise ValueError("Incomplete solid roof or wrong biome material")
            if x in (x0, x0 + 4) or z in (z0, z0 + 4):
                for y in range(floor + 1, floor + 4):
                    if (x, z) == (entry[0], entry[2]) and y in (entry[1], entry[1] + 1):
                        continue
                    if blocks.get((x, y, z), {}).get("id") != "minecraft:" + wall:
                        raise ValueError("Incomplete biome-appropriate temple shell")
            for y in range(floor + 1):
                if blocks.get((x, y, z), {}).get("id") not in SOLID:
                    raise ValueError("Unsupported temple floor")
    for x in range(x0 + 1, x0 + 4):
        for z in range(z0 + 1, z0 + 4):
            for y in range(floor + 1, floor + 4):
                position = (x, y, z)
                if (x, z) == (ax, az) and y in (ay, ay + 1):
                    continue
                if position in expected_container_positions:
                    continue
                if blocks.get(position, {}).get("id") != "minecraft:air":
                    raise ValueError("Interior requires explicit air clearance")
    for h in (0, 1):
        if blocks.get((entry[0], entry[1] + h, entry[2]), {}).get("id") != "minecraft:air":
            raise ValueError("Obstructed entry or missing explicit entry air")
    approach = tuple(record["altar"]["approach"])
    roads = [tuple(item["pos"]) for item in original if item["nbt"]["pool"].endswith("/streets")]
    for turns in rotations:
        rotated = {rotate(p, size, turns): rotated_state(state, turns) for p, state in blocks.items()}
        target = rotate(approach, size, turns)
        seen = reachable(rotated, (target[0], target[2]), floor)
        e = rotate(entry, size, turns)
        if (e[0], e[2]) not in seen:
            raise ValueError(f"Altar unreachable through entrance in rotation {turns}")
        for road in roads:
            p = rotate(road, size, turns)
            if (p[0], p[2]) not in seen:
                raise ValueError(f"Road cannot reach altar in rotation {turns}: {road}")
        for x, z in seen:
            if any(rotated.get((x, y, z), {}).get("id") not in SOLID for y in range(floor + 1)):
                raise ValueError("Unsupported walking route")
    return {"rotations": len(tuple(rotations)), "roads": len(roads), "altar": list((ax, ay, az))}


def validate_processors(root, record, processors, tags):
    """Prove all random rule outcomes preserve authored critical cells.

    This does not substitute for actual terrain/downstream-piece generation.
    """
    floor = record["floor_y"]
    x0, z0 = record["room_min"]
    ax, ay, az = record["altar"]["base"]

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
        if y <= floor or y == floor + 4 and x0 <= x <= x0 + 4 and z0 <= z <= z0 + 4:
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


def author_root(source, recipe):
    root = copy.deepcopy(source)
    w, h, d = root["size"]
    source_joints = joints(source)
    roads = [b for b in source_joints if is_road(b)]
    floors = {b["pos"][1] - 1 for b in roads}
    if len(floors) != 1:
        raise ValueError("Recipe requires a single vanilla road ground anchor")
    floor = floors.pop()
    x0, z0 = recipe["room_min"]
    if not (1 <= x0 <= w - 6 and 1 <= z0 <= d - 6):
        raise ValueError("Room cannot retain a walkable perimeter inside vanilla footprint")
    height = max(h, floor + 5)
    root["size"] = nbt.List([w, height, d], item_tag=3)
    wall, roof = MATERIALS[recipe["style"]]
    palette = []
    placed = {}

    def put(pos, state, metadata=None):
        if isinstance(state, str):
            state = {"id": state if ":" in state else "minecraft:" + state}
            if state["id"].endswith(("_log", "_wood")):
                state["properties"] = {"axis": "y"}
        if state not in palette:
            palette.append(state)
        block = {"pos": list(pos), "state": palette.index(state)}
        if metadata is not None:
            block["nbt"] = copy.deepcopy(metadata)
        placed[tuple(pos)] = block

    for x in range(w):
        for z in range(d):
            for y in range(height):
                put((x, y, z), "smooth_stone" if y <= floor else "air")
    for x in range(x0, x0 + 5):
        for z in range(z0, z0 + 5):
            if x in (x0, x0 + 4) or z in (z0, z0 + 4):
                for y in range(floor + 1, floor + 4):
                    put((x, y, z), wall)
            put((x, floor + 4, z), roof)
    entry = [x0 + 2, floor + 1, z0]
    for y in (floor + 1, floor + 2):
        put((entry[0], y, entry[2]), "air")
    altar = [x0 + 2, floor + 1, z0 + 3]
    put(altar, ALTAR_BASE)
    put((altar[0], altar[1] + 1, altar[2]), ALTAR_TOP)
    containers = {
        name: [x0 + offset[0], floor + offset[1], z0 + offset[2]]
        for name, offset in CONTAINER_OFFSETS.items()
    }
    container_positions = {tuple(position) for position in containers.values()}
    source_joint_positions = {tuple(block["pos"]) for block in source_joints}
    if source_joint_positions & container_positions:
        raise ValueError("Vanilla jigsaw collides with an approved container position")
    for name, position in containers.items():
        metadata = {"id": CONTAINER_IDS[name]}
        if name == "offering_chest":
            metadata["Items"] = nbt.List([], item_tag=10)
        put(position, CONTAINER_STATES[name], metadata)
    occupied = {tuple(b["pos"]) for b in roads} | container_positions
    adjustments = []
    final_joints = []
    for index, block in enumerate(source_joints):
        original = list(block["pos"])
        position = original.copy()
        metadata = block["nbt"]
        state = copy.deepcopy(source["palette"][block["state"]])
        if not is_road(block):
            final = metadata["final_state"].split("[")[0]
            # Preserve spawn height for void markers; solid final states belong
            # in the plaza floor, never at a player's feet/head. Decoration
            # sockets keep an extra lateral buffer outside the solid shell.
            y = floor + 1 if final in PASSABLE else floor
            decor = metadata["pool"].endswith("/decor")

            def safe(x, z):
                margin = 1 if decor else 0
                if x0 - margin <= x <= x0 + 4 + margin and z0 - margin <= z <= z0 + 4 + margin:
                    return False
                if x == entry[0] and z <= z0 + 1:
                    return False
                return (x, y, z) not in occupied

            if position[1] != y or not safe(position[0], position[2]):
                candidates = [(x, y, z) for x in range(w) for z in range(d) if safe(x, z)]
                if not candidates:
                    raise ValueError("No safe ancillary connector location within root")
                position = list(min(candidates, key=lambda p: (abs(p[0] - original[0]) + abs(p[2] - original[2]), p)))
            if position != original:
                adjustments.append({"index": index, "from": original, "to": position,
                                    "reason": "Keep room/entry clear and final state on supported open plaza; decor buffered from roof"})
        occupied.add(tuple(position))
        put(position, state, metadata)
        final_joints.append({"pos": position, "state": state, "nbt": copy.deepcopy(metadata)})
    root["palette"] = nbt.List(palette, item_tag=10)
    root["blocks"] = nbt.List([placed[p] for p in sorted(placed, key=lambda p: (p[1], p[0], p[2]))], item_tag=10)
    root["entities"] = nbt.List([], item_tag=10)
    record = {"style": recipe["style"], "source_size": list(source["size"]), "size": list(root["size"]),
              "floor_y": floor, "room_min": [x0, z0], "room_max": [x0 + 4, z0 + 4],
              "roof_y": floor + 4, "entry": entry,
              "altar": {"base": altar, "top": [altar[0], altar[1] + 1, altar[2]],
                        "approach": [altar[0], floor + 1, altar[2] - 1]},
              "containers": containers,
              "materials": {"wall": "minecraft:" + wall, "roof": "minecraft:" + roof,
                            "floor": "minecraft:smooth_stone"},
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
    emitted = {}
    with zipfile.ZipFile(archive) as source:
        version = json.loads(source.read("version.json"))
        if (version["id"], version["world_version"], version["protocol_version"], version["pack_version"]["data_major"],
                version["pack_version"]["data_minor"]) != ("26.3", 5023, 777, 121, 0):
            raise ValueError("Unexpected source version/format/schema")
        manifest = {"schema": 1, "provenance": {"archive_sha256": checksum, "minecraft": "26.3",
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
    emitted[Path("manifest.json")] = json_bytes(manifest)
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
