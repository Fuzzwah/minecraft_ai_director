"""Standard-library, type-preserving Java NBT for offline asset/world inspection.

loads accepts raw, gzip or zlib NBT. dumps emits deterministic gzip by default.
Containers/scalars behave like ordinary Python values; tag types and empty list
item types survive a decode/encode round trip. Plain dict/list/int/float values
are encoded as compound/list/int/double. No Director runtime dependency.
"""

import gzip
import struct
import zlib


class Byte(int):
    tag = 1


class Short(int):
    tag = 2


class Int(int):
    tag = 3


class Long(int):
    tag = 4


class Float(float):
    tag = 5


class Double(float):
    tag = 6


class ByteArray(bytes):
    tag = 7


class List(list):
    tag = 9

    def __init__(self, values=(), item_tag=None):
        super().__init__(values)
        self.item_tag = item_tag


class Compound(dict):
    tag = 10

    def __init__(self, *args, name="", **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name


class IntArray(list):
    tag = 11


class LongArray(list):
    tag = 12


_FORMATS = {1: "b", 2: "h", 3: "i", 4: "q", 5: "f", 6: "d"}
_TYPES = {1: Byte, 2: Short, 3: Int, 4: Long, 5: Float, 6: Double}


def _string_encode(value):
    # Java's DataOutput uses modified UTF-8 over UTF-16 code units.
    units = value.encode("utf-16-be", "surrogatepass")
    out = bytearray()
    for offset in range(0, len(units), 2):
        unit = int.from_bytes(units[offset:offset + 2], "big")
        if 0 < unit < 128:
            out.append(unit)
        elif unit < 2048:
            out.extend((192 | unit >> 6, 128 | unit & 63))
        else:
            out.extend((224 | unit >> 12, 128 | unit >> 6 & 63, 128 | unit & 63))
    if len(out) > 65535:
        raise ValueError("NBT string exceeds unsigned-short byte length")
    return struct.pack(">H", len(out)) + out


def _string_decode(data):
    units = bytearray()
    cursor = 0
    while cursor < len(data):
        first = data[cursor]
        cursor += 1
        if first < 128:
            unit = first
        elif first & 224 == 192:
            if cursor >= len(data) or data[cursor] & 192 != 128:
                raise ValueError("Invalid modified UTF-8")
            unit = (first & 31) << 6 | data[cursor] & 63
            cursor += 1
        elif first & 240 == 224:
            if cursor + 1 >= len(data) or any(b & 192 != 128 for b in data[cursor:cursor + 2]):
                raise ValueError("Invalid modified UTF-8")
            unit = (first & 15) << 12 | (data[cursor] & 63) << 6 | data[cursor + 1] & 63
            cursor += 2
        else:
            raise ValueError("Invalid modified UTF-8")
        units.extend(struct.pack(">H", unit))
    return units.decode("utf-16-be", "surrogatepass")


def loads(payload):
    """Decode a named compound, rejecting truncated or trailing NBT data."""
    if payload[:2] == b"\x1f\x8b":
        payload = gzip.decompress(payload)
    elif payload[:1] == b"x":
        payload = zlib.decompress(payload)
    cursor = 0

    def take(count):
        nonlocal cursor
        if count < 0 or cursor + count > len(payload):
            raise ValueError("Truncated NBT payload or negative array length")
        value = payload[cursor:cursor + count]
        cursor += count
        return value

    def number(fmt):
        return struct.unpack(">" + fmt, take(struct.calcsize(fmt)))[0]

    def string():
        return _string_decode(take(number("H")))

    def value(tag):
        if tag in _FORMATS:
            return _TYPES[tag](number(_FORMATS[tag]))
        if tag == 7:
            return ByteArray(take(number("i")))
        if tag == 8:
            return string()
        if tag == 9:
            child, count = number("B"), number("i")
            if count < 0 or child not in range(13) or child == 0 and count:
                raise ValueError("Invalid NBT list type/length")
            return List((value(child) for _ in range(count)), item_tag=child)
        if tag == 10:
            result = Compound()
            while True:
                child = number("B")
                if child == 0:
                    return result
                key = string()
                if key in result:
                    raise ValueError("Duplicate NBT compound key")
                result[key] = value(child)
        if tag in (11, 12):
            count = number("i")
            if count < 0:
                raise ValueError("Negative NBT array length")
            fmt = "i" if tag == 11 else "q"
            return (IntArray if tag == 11 else LongArray)(number(fmt) for _ in range(count))
        raise ValueError(f"Unsupported NBT tag {tag}")

    if number("B") != 10:
        raise ValueError("NBT root must be a named compound")
    name = string()
    result = value(10)
    result.name = name
    if cursor != len(payload):
        raise ValueError("Trailing bytes after NBT root")
    return result


def _tag(value):
    if hasattr(value, "tag"):
        return value.tag
    if isinstance(value, str):
        return 8
    if isinstance(value, dict):
        return 10
    if isinstance(value, bytes):
        return 7
    if isinstance(value, list):
        return 9
    if isinstance(value, int):
        return 3
    if isinstance(value, float):
        return 6
    raise TypeError(f"Unsupported NBT value {type(value).__name__}")


def dumps(data, *, compressed=True):
    """Encode a compound, preserving tag types; gzip has mtime=0/no filename."""
    def value(item, tag):
        if tag in _FORMATS:
            return struct.pack(">" + _FORMATS[tag], item)
        if tag == 7:
            return struct.pack(">i", len(item)) + bytes(item)
        if tag == 8:
            return _string_encode(item)
        if tag == 9:
            child = getattr(item, "item_tag", None)
            if child is None:
                child = _tag(item[0]) if item else 0
            if any(_tag(entry) != child for entry in item):
                raise ValueError("NBT lists must have homogeneous tag types")
            return struct.pack(">Bi", child, len(item)) + b"".join(value(entry, child) for entry in item)
        if tag == 10:
            return b"".join(bytes([_tag(entry)]) + _string_encode(key) + value(entry, _tag(entry))
                            for key, entry in item.items()) + b"\0"
        if tag in (11, 12):
            fmt = "i" if tag == 11 else "q"
            return struct.pack(">i", len(item)) + b"".join(struct.pack(">" + fmt, entry) for entry in item)
        raise ValueError(f"Unsupported NBT tag {tag}")

    if not isinstance(data, dict):
        raise TypeError("NBT root must be a compound")
    payload = b"\x0a" + _string_encode(getattr(data, "name", "")) + value(data, 10)
    return gzip.compress(payload, mtime=0) if compressed else payload
