"""Deterministic read-only probes and real bundled template placement for tests."""
import gzip
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_template(name):
    payload = gzip.decompress((ROOT / "datapack/director_buildings/data/director/structure" / (name + ".nbt")).read_bytes())
    offset = 0

    def take(count):
        nonlocal offset
        value = payload[offset:offset + count]
        offset += count
        return value

    def number(fmt):
        return struct.unpack(fmt, take(struct.calcsize(fmt)))[0]

    def string():
        return take(number(">H")).decode()

    def value(kind):
        if kind == 3:
            return number(">i")
        if kind == 8:
            return string()
        if kind == 9:
            inner = number(">B")
            return [value(inner) for _ in range(number(">i"))]
        if kind == 10:
            result = {}
            while True:
                inner = number(">B")
                if inner == 0:
                    return result
                name = string()
                result[name] = value(inner)
        raise AssertionError(f"Unsupported bundled NBT tag {kind}")

    assert number(">B") == 10
    string()
    return value(10)


class FakeMinecraft:
    def __init__(self):
        self.blocks = {}
        self.players = []
        self.commands = []
        self.placements = []
        self.fail_place = False
        self.loaded = True
        self.respond = True
        self.inventory = 20
        self.fail_announce = False

    def command(self, command):
        self.commands.append(command)
        if not self.respond:
            return ""
        if command.startswith("execute "):
            if "if loaded " in command and not self.loaded:
                return "Test failed"
            volume = re.search(r"(?:unless|if) entity @a\[([^]]+)\]", command)
            if volume:
                fields = dict(piece.split("=", 1) for piece in volume[1].split(","))
                if all(axis in fields for axis in ("x", "y", "z", "dx", "dy", "dz")):
                    inside = any(all(float(fields[a]) <= p[i] < float(fields[a]) + float(fields["d" + a]) + 1 for i, a in enumerate(("x", "y", "z"))) for p in self.players)
                    unless = "unless entity" in command
                    if inside == unless:
                        return "Test failed"
            for x, y, z, block in re.findall(r"if block (-?\d+) (-?\d+) (-?\d+) ([^ ]+)", command):
                actual = self.blocks.get((int(x), int(y), int(z)), "minecraft:air")
                if "[" in block:
                    match = actual == block
                else:
                    match = actual.split("[", 1)[0] == block
                if not match:
                    return "Test failed"
        if command == "list" or command.endswith(" run list"):
            return "There are 0 of a max of 20 players online: "
        placement = re.search(r"(?:^| run )place template ([\w:]+) (-?\d+) (-?\d+) (-?\d+) (\w+) none", command)
        if placement:
            if self.fail_place:
                return "Failed to place template"
            template, x, y, z, rotation = placement.groups()
            x, y, z = int(x), int(y), int(z)
            data = read_template(template.split(":")[1])
            for entry in data["blocks"]:
                bx, by, bz = entry["pos"]
                if rotation == "clockwise_90":
                    bx, bz = -bz, bx
                elif rotation == "clockwise_180":
                    bx, bz = -bx, -bz
                elif rotation == "counterclockwise_90":
                    bx, bz = bz, -bx
                state = data["palette"][entry["state"]]
                block = state["Name"]
                if state.get("Properties"):
                    block += "[" + ",".join(f"{k}={v}" for k, v in sorted(state["Properties"].items())) + "]"
                self.blocks[(x + bx, y + by, z + bz)] = block
            self.placements.append(command)
            return f'Loaded template "{template}" at {x}, {y}, {z}'
        removal = re.search(r" run setblock (-?\d+) (-?\d+) (-?\d+) minecraft:air(?: replace)?$", command)
        if removal:
            pos = tuple(int(v) for v in removal.groups())
            self.blocks[pos] = "minecraft:air"
            return f"Changed the block at {pos[0]}, {pos[1]}, {pos[2]}"
        if "data get block" in command:
            match = re.search(r"data get block (-?\d+) (-?\d+) (-?\d+)", command)
            pos = tuple(int(v) for v in match.groups())
            return f"{pos[0]}, {pos[1]}, {pos[2]} has the following block data: {{id: \"{self.blocks.get(pos, 'minecraft:air')}\"}}"
        if " clear " in command or command.startswith("clear "):
            return f"Found {self.inventory} matching items" if command.endswith(" 0") else "Removed 3 items"
        if "tellraw " in command or command.startswith("title "):
            if self.fail_announce:
                raise OSError("Announcement unavailable")
            return ""
        if command.startswith(("give ", "experience ", "playsound ")):
            return "Success"
        raise AssertionError(f"Unexpected RCON command: {command}")


def config_files(directory, *, stages=False):
    registry = json.loads((ROOT / "config/structures.json").read_text())
    if not stages:
        registry["structures"]["workshop_tier_1"].pop("stages", None)
    config = json.loads((ROOT / "config/settlement.json").read_text())
    config["settlement"]["enabled"] = True
    config["settlement"]["world_id"] = "test-world"
    registry_path = Path(directory) / "structures.json"
    config_path = Path(directory) / "settlement.json"
    registry_path.write_text(json.dumps(registry))
    config_path.write_text(json.dumps(config))
    return registry_path, config_path, Path(directory) / "state.sqlite3"
