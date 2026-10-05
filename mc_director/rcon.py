"""Minecraft RCON framing and Java Edition server-list status, stdlib only."""
from __future__ import annotations

import json
import socket
import struct
import time
from typing import Any

MAX_RESPONSE_BYTES = 1_100_000
# Vanilla reads one complete frame into a 1460-byte buffer, without stream assembly.
# Leave headroom and include the 14-byte header/terminators in the 1400-byte bound.
MAX_COMMAND_BYTES = 1386


class RconError(RuntimeError):
    """Transport/protocol failure; a sent mutation may have an unknown outcome."""


class MinecraftRcon:
    def __init__(self, host: str, port: int, password: str, timeout: float = 5.0):
        self.host, self.port, self.password, self.timeout = host, port, password, timeout
        self.sock: socket.socket | None = None
        self.request_id = 0
        self._deadline: float | None = None

    def __enter__(self) -> MinecraftRcon:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def connect(self) -> None:
        self.close()
        self._deadline = time.monotonic() + self.timeout
        if not self.password:
            raise RconError("RCON_PASSWORD is required")
        try:
            self.sock = socket.create_connection((self.host, self.port), self.timeout)
            self.sock.settimeout(self.timeout)
            self.request_id = 1
            self._send(self.request_id, 3, self.password)
            for _ in range(3):
                rid, kind, _ = self._receive()
                if rid == -1:
                    raise RconError("RCON authentication rejected")
                if rid != self.request_id:
                    raise RconError("Unexpected RCON authentication response ID")
                if kind == 2:
                    return
                if kind != 0:
                    raise RconError("Unexpected RCON authentication packet type")
            raise RconError("Missing RCON authentication response")
        except (OSError, RconError) as exc:
            self.close()
            if isinstance(exc, RconError):
                raise
            raise RconError("Cannot connect/authenticate to Minecraft RCON") from exc
        finally:
            self._deadline = None

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None
        self._deadline = None

    def command(self, command: str) -> str:
        """Read every response packet using a subsequent read-only command barrier.

        Minecraft emits one or more response packets per command. Sending a `list`
        command with its own ID provides a deterministic end marker. Vanilla
        rejects coalesced input frames, so wait for the first command response
        before sending that barrier. Its response follows all original packets.
        A failure never retries the original command automatically.
        """
        if self.sock is None:
            raise RconError("RCON is not connected")
        if not command or "\x00" in command or "\n" in command or "\r" in command:
            raise RconError("Invalid RCON command framing")
        if len(command.encode("utf-8")) > MAX_COMMAND_BYTES:
            raise RconError("RCON command exceeds the request bound")
        self.request_id = (self.request_id + 2) % 2_000_000_000 or 2
        rid, barrier = self.request_id, self.request_id + 1
        parts: list[bytes] = []
        size = 0
        self._deadline = time.monotonic() + self.timeout
        try:
            self._send(rid, 2, command)
            for _ in range(1024):
                response_id, kind, payload = self._receive()
                if kind != 0:
                    raise RconError("Unexpected RCON command response type")
                if response_id == barrier:
                    return b"".join(parts).decode("utf-8", errors="strict")
                if response_id != rid:
                    raise RconError("Unexpected RCON command response ID")
                if not parts:
                    self._send(barrier, 2, "list")
                size += len(payload)
                if size > MAX_RESPONSE_BYTES:
                    raise RconError("RCON response exceeds the evidence bound")
                parts.append(payload)
            raise RconError("Too many RCON response packets")
        except (OSError, UnicodeError, RconError) as exc:
            self.close()
            if isinstance(exc, RconError):
                raise
            raise RconError("Incomplete RCON response; command outcome may be unknown") from exc
        finally:
            self._deadline = None

    def _set_timeout(self) -> None:
        if self.sock is None:
            raise RconError("RCON is not connected")
        remaining = self.timeout if self._deadline is None else self._deadline - time.monotonic()
        if remaining <= 0:
            raise RconError("RCON command deadline expired; outcome may be unknown")
        self.sock.settimeout(remaining)

    def _send(self, rid: int, kind: int, text: str) -> None:
        if self.sock is None:
            raise RconError("RCON is not connected")
        body = struct.pack("<ii", rid, kind) + text.encode("utf-8") + b"\0\0"
        self._set_timeout()
        self.sock.sendall(struct.pack("<i", len(body)) + body)

    def _exact(self, length: int) -> bytes:
        if self.sock is None:
            raise RconError("RCON is not connected")
        result = bytearray(length)
        view = memoryview(result)
        received = 0
        while received < length:
            self._set_timeout()
            count = self.sock.recv_into(view[received:])
            if not count:
                raise RconError("RCON connection closed before packet completion")
            received += count
        return bytes(result)

    def _receive(self) -> tuple[int, int, bytes]:
        length = struct.unpack("<i", self._exact(4))[0]
        if not 10 <= length <= MAX_RESPONSE_BYTES + 10:
            raise RconError("Invalid RCON packet length")
        body = self._exact(length)
        if body[-2:] != b"\0\0":
            raise RconError("Invalid RCON packet terminator")
        rid, kind = struct.unpack("<ii", body[:8])
        return rid, kind, body[8:-2]


def _varint(value: int) -> bytes:
    value &= 0xFFFFFFFF
    encoded = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        encoded.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(encoded)


def _read_varint(sock: socket.socket) -> int:
    result = 0
    for shift in range(0, 35, 7):
        byte = sock.recv(1)
        if not byte:
            raise RconError("Incomplete Minecraft status packet")
        result |= (byte[0] & 0x7F) << shift
        if not byte[0] & 0x80:
            return result
    raise RconError("Oversized Minecraft status VarInt")


def server_status(host: str, port: int, timeout: float = 5.0) -> dict:
    """Read the running server's actual reported game version, not pack metadata."""
    encoded_host = host.encode("utf-8")
    if len(encoded_host) > 255:
        raise RconError("Minecraft game host is too long")
    handshake = b"\x00" + _varint(-1) + _varint(len(encoded_host)) + encoded_host + struct.pack(">H", port) + b"\x01"
    try:
        with socket.create_connection((host, port), timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(_varint(len(handshake)) + handshake + b"\x01\x00")
            length = _read_varint(sock)
            if not 2 <= length <= 1_048_576:
                raise RconError("Invalid Minecraft status packet size")
            if _read_varint(sock) != 0:
                raise RconError("Unexpected Minecraft status packet ID")
            json_length = _read_varint(sock)
            if not 2 <= json_length <= length:
                raise RconError("Invalid Minecraft status JSON size")
            parts = bytearray()
            while len(parts) < json_length:
                piece = sock.recv(json_length - len(parts))
                if not piece:
                    raise RconError("Incomplete Minecraft status JSON")
                parts.extend(piece)
            result = json.loads(parts)
            if not isinstance(result, dict) or not isinstance(result.get("version"), dict):
                raise RconError("Malformed Minecraft status result")
            return result
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, RconError):
            raise
        raise RconError("Cannot obtain a complete Minecraft server status") from exc
