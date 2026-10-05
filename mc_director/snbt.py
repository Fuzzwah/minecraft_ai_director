"""Bounded SNBT codec preserving Minecraft numeric and array tag types.

Only data is parsed. No Python evaluation, command execution, or regex inventory
counting is involved. Numeric subclasses remain compatible with JSON consumers;
``dumps`` retains their NBT types for evidence fingerprints and retransmission.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

MAX_BYTES = 1_048_576
MAX_DEPTH = 64


class SnbtError(ValueError):
    pass


class Byte(int):
    suffix = "b"


class Short(int):
    suffix = "s"


class Long(int):
    suffix = "L"


class Float(float):
    suffix = "f"


class Double(float):
    suffix = "d"


class ByteArray(list):
    kind = "B"


class IntArray(list):
    kind = "I"


class LongArray(list):
    kind = "L"


_NUMBER = re.compile(r"[+-]?(?:(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([bBsSlLfFdD]?)\Z")
_INT = re.compile(r"[+-]?\d+\Z")
_BOUNDS = {Byte: (-128, 127), Short: (-32768, 32767), int: (-(2**31), 2**31 - 1), Long: (-(2**63), 2**63 - 1)}


def _integer(value: int, cls: type[int]) -> int:
    low, high = _BOUNDS[cls]
    if not low <= value <= high:
        raise SnbtError("NBT integer outside its tag range")
    return cls(value)


def dumps(value: Any, *, canonical: bool = False, max_bytes: int = MAX_BYTES) -> str:
    """Encode SNBT with quoted keys/strings, exact numeric types, and bounds."""
    def encode(node: Any, depth: int) -> str:
        if depth > MAX_DEPTH:
            raise SnbtError("SNBT nesting limit exceeded")
        if isinstance(node, str):
            return json.dumps(node, ensure_ascii=False)
        if isinstance(node, bool):
            return "1b" if node else "0b"
        if isinstance(node, int):
            cls = type(node) if type(node) in _BOUNDS else int
            _integer(int(node), cls)
            return str(int(node)) + getattr(node, "suffix", "")
        if isinstance(node, float):
            if not math.isfinite(node):
                raise SnbtError("Non-finite NBT number")
            return repr(float(node)) + getattr(node, "suffix", "d")
        if isinstance(node, (ByteArray, IntArray, LongArray)):
            cls = {"B": Byte, "I": int, "L": Long}[node.kind]
            pieces = []
            for item in node:
                if isinstance(item, bool) or not isinstance(item, int):
                    raise SnbtError("Typed NBT array requires integer elements")
                pieces.append(encode(_integer(int(item), cls), depth + 1))
            return "[" + node.kind + ";" + ",".join(pieces) + "]"
        if isinstance(node, (list, tuple)):
            return "[" + ",".join(encode(item, depth + 1) for item in node) + "]"
        if isinstance(node, dict):
            keys = sorted(node) if canonical else node.keys()
            if any(not isinstance(key, str) for key in node):
                raise SnbtError("NBT compound keys must be strings")
            return "{" + ",".join(encode(key, depth + 1) + ":" + encode(node[key], depth + 1) for key in keys) + "}"
        raise SnbtError(f"Unsupported NBT value type: {type(node).__name__}")

    result = encode(value, 0)
    if len(result.encode("utf-8")) > max_bytes:
        raise SnbtError("SNBT size limit exceeded")
    return result


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def whitespace(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def peek(self) -> str:
        self.whitespace()
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def take(self, expected: str) -> None:
        self.whitespace()
        if not self.text.startswith(expected, self.pos):
            raise SnbtError(f"Expected {expected!r} at offset {self.pos}")
        self.pos += len(expected)

    def string(self) -> str:
        quote = self.text[self.pos]
        self.pos += 1
        result = []
        escapes = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "\\": "\\", '"': '"', "'": "'", "/": "/"}
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == quote:
                return "".join(result)
            if char != "\\":
                result.append(char)
                continue
            if self.pos >= len(self.text):
                break
            char = self.text[self.pos]
            self.pos += 1
            if char in escapes:
                result.append(escapes[char])
            elif char in ("u", "U", "x"):
                length = {"u": 4, "U": 8, "x": 2}[char]
                digits = self.text[self.pos:self.pos + length]
                if len(digits) != length or not re.fullmatch(r"[0-9a-fA-F]+", digits):
                    raise SnbtError("Invalid SNBT character escape")
                self.pos += length
                try:
                    result.append(chr(int(digits, 16)))
                except ValueError as exc:
                    raise SnbtError("Invalid Unicode code point") from exc
            else:
                raise SnbtError("Unknown SNBT string escape")
        raise SnbtError("Unterminated SNBT string")

    def token(self, *, key: bool = False) -> str:
        self.whitespace()
        start = self.pos
        delimiters = ",]}{[" + (":" if key else "")
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char.isspace() or char in delimiters:
                break
            self.pos += 1
        if start == self.pos:
            raise SnbtError(f"Missing SNBT token at offset {self.pos}")
        return self.text[start:self.pos]

    def value(self, depth: int = 0) -> Any:
        if depth > MAX_DEPTH:
            raise SnbtError("SNBT nesting limit exceeded")
        char = self.peek()
        if char == "{":
            return self.compound(depth)
        if char == "[":
            return self.array(depth)
        if char in ('"', "'"):
            return self.string()
        if not char:
            raise SnbtError("Unexpected end of SNBT")
        token = self.token()
        if token in ("true", "false"):
            return Byte(int(token == "true"))
        match = _NUMBER.fullmatch(token)
        if not match:
            return token
        suffix = match.group(1).lower()
        number = token[:-1] if suffix else token
        if suffix in ("b", "s", "l") or (not suffix and _INT.fullmatch(number)):
            if not _INT.fullmatch(number):
                raise SnbtError("Integer NBT tag has fractional value")
            return _integer(int(number), {"b": Byte, "s": Short, "l": Long, "": int}[suffix])
        value = float(number)
        if not math.isfinite(value):
            raise SnbtError("Non-finite NBT number")
        return Float(value) if suffix == "f" else Double(value)

    def compound(self, depth: int) -> dict[str, Any]:
        self.take("{")
        result = {}
        if self.peek() == "}":
            self.take("}")
            return result
        while True:
            key = self.string() if self.peek() in ('"', "'") else self.token(key=True)
            self.take(":")
            if key in result:
                raise SnbtError("Duplicate NBT compound key")
            result[key] = self.value(depth + 1)
            if self.peek() == "}":
                self.take("}")
                return result
            self.take(",")
            if self.peek() == "}":
                self.take("}")
                return result

    def array(self, depth: int) -> list:
        self.take("[")
        self.whitespace()
        typed = ""
        if self.pos + 1 < len(self.text) and self.text[self.pos].upper() in "BIL" and self.text[self.pos + 1] == ";":
            typed = self.text[self.pos].upper()
            self.pos += 2
        result = {"B": ByteArray, "I": IntArray, "L": LongArray}.get(typed, list)()
        if self.peek() == "]":
            self.take("]")
            return result
        while True:
            item = self.value(depth + 1)
            if typed:
                cls = {"B": Byte, "I": int, "L": Long}[typed]
                if type(item) is not cls:
                    raise SnbtError("Wrong element type in typed NBT array")
            result.append(item)
            if self.peek() == "]":
                self.take("]")
                return result
            self.take(",")
            if self.peek() == "]":
                self.take("]")
                return result


def loads(text: str, *, max_bytes: int = MAX_BYTES) -> Any:
    if not isinstance(text, str) or len(text.encode("utf-8")) > max_bytes:
        raise SnbtError("SNBT size limit exceeded")
    parser = _Parser(text)
    value = parser.value()
    if parser.peek():
        raise SnbtError("Trailing data after SNBT value")
    return value


def extract(text: str, *, max_bytes: int = MAX_BYTES) -> Any:
    """Decode the root compound/array in a complete vanilla ``data get`` reply."""
    offsets = [offset for char in "{[" if (offset := text.find(char)) >= 0]
    if not offsets:
        raise SnbtError("RCON response has no structured NBT payload")
    return loads(text[min(offsets):].strip(), max_bytes=max_bytes)
