"""Optional, lossy vanilla log observations; never inventory or recipient authority.

Sources start at EOF, including after rotation, truncation or an outage. Only
English vanilla public death/advancement shapes are recognized by default: 26.3
can omit these messages entirely. Opt-in player chat returns bounded text to the
owning caller; rules.EventContext redacts known identifiers before sharing.
Raw log lines, source paths and exception details are not returned.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat

from . import snbt
from .bridge import ints_to_uuid


MAX_READ_BYTES = 64 * 1024
MAX_LINE_BYTES = 4 * 1024
MAX_EVENTS = 20
_ANCHOR_BYTES = 64
_NAME = re.compile(r"[A-Za-z0-9_]{1,16}\Z")
_PREFIX = re.compile(
    r"\[(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\] "
    r"\[Server thread/INFO\]: (.+)\Z"
)
_CHAT = re.compile(r"(?:System chat: )?<(?P<sender>[A-Za-z0-9_]{1,16})> (?P<text>.*)\Z")
_ADVANCEMENT = re.compile(
    r"(?P<victim>[A-Za-z0-9_]{1,16}) has "
    r"(?:made the advancement|completed the challenge|reached the goal) \[[^\[\]]+\]\Z"
)

# Public English vanilla 26.3 translations (death.attack.* and death.fell.*).
# Placeholder contents are discarded; emitted events contain only kind + UUID.
_DEATH_TEMPLATES = (
    "%1$s was squashed by a falling anvil",
    "%1$s was squashed by a falling anvil while fighting %2$s",
    "%1$s was shot by %2$s",
    "%1$s was shot by %2$s using %3$s",
    "%1$s was killed by %2$s",
    "%1$s was pricked to death",
    "%1$s walked into a cactus while trying to escape %2$s",
    "%1$s was squished too much",
    "%1$s was squashed by %2$s",
    "%1$s was roasted in dragon's breath",
    "%1$s was roasted in dragon's breath by %2$s",
    "%1$s drowned",
    "%1$s drowned while trying to escape %2$s",
    "%1$s died from dehydration",
    "%1$s died from dehydration while trying to escape %2$s",
    "%1$s was killed by even more magic",
    "%1$s blew up",
    "%1$s was blown up by %2$s",
    "%1$s was blown up by %2$s using %3$s",
    "%1$s hit the ground too hard",
    "%1$s hit the ground too hard while trying to escape %2$s",
    "%1$s was squashed by a falling block",
    "%1$s was squashed by a falling block while fighting %2$s",
    "%1$s was skewered by a falling stalactite",
    "%1$s was skewered by a falling stalactite while fighting %2$s",
    "%1$s was fireballed by %2$s",
    "%1$s was fireballed by %2$s using %3$s",
    "%1$s went off with a bang",
    "%1$s went off with a bang due to a firework fired from %3$s by %2$s",
    "%1$s went off with a bang while fighting %2$s",
    "%1$s experienced kinetic energy",
    "%1$s experienced kinetic energy while trying to escape %2$s",
    "%1$s froze to death",
    "%1$s was frozen to death by %2$s",
    "%1$s died",
    "%1$s died because of %2$s",
    "%1$s was killed",
    "%1$s was killed while fighting %2$s",
    "%1$s discovered the floor was lava",
    "%1$s walked into the danger zone due to %2$s",
    "%1$s was killed by %2$s using magic",
    "%1$s was killed by %2$s using %3$s",
    "%1$s went up in flames",
    "%1$s walked into fire while fighting %2$s",
    "%1$s suffocated in a wall",
    "%1$s suffocated in a wall while fighting %2$s",
    "%1$s tried to swim in lava",
    "%1$s tried to swim in lava to escape %2$s",
    "%1$s was struck by lightning",
    "%1$s was struck by lightning while fighting %2$s",
    "%1$s was smashed by %2$s",
    "%1$s was smashed by %2$s with %3$s",
    "%1$s was killed by magic",
    "%1$s was killed by magic while trying to escape %2$s",
    "%1$s was slain by %2$s",
    "%1$s was slain by %2$s using %3$s",
    "%1$s burned to death",
    "%1$s was burned to a crisp while fighting %2$s wielding %3$s",
    "%1$s was burned to a crisp while fighting %2$s",
    "%1$s fell out of the world",
    "%1$s didn't want to live in the same world as %2$s",
    "%1$s left the confines of this world",
    "%1$s left the confines of this world while fighting %2$s",
    "%1$s was obliterated by a sonically-charged shriek",
    "%1$s was obliterated by a sonically-charged shriek while trying to escape %2$s wielding %3$s",
    "%1$s was obliterated by a sonically-charged shriek while trying to escape %2$s",
    "%1$s was speared by %2$s",
    "%1$s was speared by %2$s using %3$s",
    "%1$s was impaled on a stalagmite",
    "%1$s was impaled on a stalagmite while fighting %2$s",
    "%1$s starved to death",
    "%1$s starved to death while fighting %2$s",
    "%1$s was stung to death",
    "%1$s was stung to death by %2$s using %3$s",
    "%1$s was stung to death by %2$s",
    "%1$s died because not just the floor is lava",
    "%2$s showed %1$s that not just the floor is lava using %3$s",
    "%2$s showed %1$s that not just the floor is lava",
    "%1$s was poked to death by a sweet berry bush",
    "%1$s was poked to death by a sweet berry bush while trying to escape %2$s",
    "%1$s was killed while trying to hurt %2$s",
    "%1$s was killed by %3$s while trying to hurt %2$s",
    "%1$s was pummeled by %2$s",
    "%1$s was pummeled by %2$s using %3$s",
    "%1$s was impaled by %2$s",
    "%1$s was impaled by %2$s with %3$s",
    "%1$s withered away",
    "%1$s withered away while fighting %2$s",
    "%1$s was shot by a skull from %2$s",
    "%1$s was shot by a skull from %2$s using %3$s",
    "%1$s fell from a high place",
    "%1$s fell off a ladder",
    "%1$s fell while climbing",
    "%1$s fell off scaffolding",
    "%1$s fell off some twisting vines",
    "%1$s fell off some vines",
    "%1$s fell off some weeping vines",
    "%1$s was doomed to fall by %2$s",
    "%1$s was doomed to fall by %2$s using %3$s",
    "%1$s fell too far and was finished by %2$s",
    "%1$s fell too far and was finished by %2$s using %3$s",
    "%1$s was doomed to fall",
)
_DEATHS = tuple(
    re.compile(
        re.escape(template)
        .replace(re.escape("%1$s"), r"(?P<victim>[A-Za-z0-9_]{1,16})")
        .replace(re.escape("%2$s"), r".+?")
        .replace(re.escape("%3$s"), r".+?")
        + r"\Z"
    )
    for template in _DEATH_TEMPLATES
)


def _identities(players: list[dict]) -> dict[str, str]:
    result = {}
    ambiguous = set()
    for player in players:
        if not isinstance(player, dict):
            continue
        name, parts = player.get("name"), player.get("uuid")
        if not isinstance(name, str) or not _NAME.fullmatch(name) or not isinstance(parts, snbt.IntArray):
            continue
        try:
            identity = ints_to_uuid(parts)
        except ValueError:
            continue
        if name in result and result[name] != identity:
            ambiguous.add(name)
        result[name] = identity
    for name in ambiguous:
        result.pop(name, None)
    return result


def _event(line: bytes, identities: dict[str, str], *, allow_chat: bool = False) -> dict | None:
    try:
        text = line.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        return None
    prefix = _PREFIX.fullmatch(text)
    if prefix is None:
        return None
    message = prefix[1]
    chat = _CHAT.fullmatch(message)
    if chat is not None:
        if not allow_chat:
            return None
        identity = identities.get(chat["sender"])
        content = chat["text"]
        if (
            identity is None
            or not content.strip()
            or len(content) > 256
            or not content.isprintable()
            or content.lstrip().startswith("/")
        ):
            return None
        return {"kind": "chat", "uuid": identity, "text": content}
    match = _ADVANCEMENT.fullmatch(message)
    kind = "advancement"
    if match is None:
        kind = "death"
        for pattern in _DEATHS:
            match = pattern.fullmatch(message)
            if match is not None:
                break
    if match is None:
        return None
    identity = identities.get(match["victim"])
    return {"kind": kind, "uuid": identity} if identity is not None else None


class ServerLog:
    """Bounded incremental source with a path-free diagnostic ``status`` dict.

    At most 64 KiB are read per poll (including the overwrite guard), unfinished
    lines retain at most 4 KiB, and at most twenty events are returned. Excess
    complete events are dropped, not queued. Recovery baselines at EOF, discards
    partial lines and requires a later append; optional outages never raise.
    """

    def __init__(self, path: Path | None = None, *, allow_chat: bool = False):
        if not isinstance(allow_chat, bool):
            raise TypeError("allow_chat must be a bool")
        self.allow_chat = allow_chat
        self.path = path
        self._identity = None
        self._offset = 0
        self._anchor = b""
        self._pending = bytearray()
        self._discard = False
        self.status = {"state": "disabled" if path is None else "missing", "last_reset": None, "backlog_bytes": 0, "chat_enabled": allow_chat}
        if path is not None:
            self._read(initial=True)

    def _reset(self, source, metadata, reason):
        self._identity = (metadata.st_dev, metadata.st_ino)
        self._offset = metadata.st_size
        source.seek(max(0, self._offset - _ANCHOR_BYTES))
        self._anchor = source.read(min(self._offset, _ANCHOR_BYTES))
        self._pending.clear()
        self._discard = bool(self._anchor and not self._anchor.endswith(b"\n"))
        self.status.update(state="ready", last_reset=reason, backlog_bytes=0)

    def _unavailable(self, state):
        self._identity = None
        self._anchor = b""
        self._pending.clear()
        self._discard = False
        self.status.update(state=state, backlog_bytes=0)

    def _read(self, *, initial=False) -> bytes:
        if self.path is None:
            return b""
        try:
            # Nonblocking open plus regular-file validation also handles a path
            # replaced with a FIFO/device without hanging the engine thread.
            descriptor = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb", buffering=0) as source:
                metadata = os.fstat(source.fileno())
                if not stat.S_ISREG(metadata.st_mode):
                    self._unavailable("not_regular")
                    return b""
                identity = (metadata.st_dev, metadata.st_ino)
                if self._identity is None or identity != self._identity:
                    reason = "startup" if initial else "recovered" if self._identity is None else "rotated"
                    self._reset(source, metadata, reason)
                    return b""
                if metadata.st_size < self._offset:
                    self._reset(source, metadata, "truncated")
                    return b""
                source.seek(self._offset - len(self._anchor))
                guard = source.read(len(self._anchor))
                if guard != self._anchor:
                    # Detect truncate-and-regrow between polls, even when the
                    # replacement content is already larger than our cursor.
                    self._reset(source, metadata, "truncated")
                    return b""
                source.seek(self._offset)
                chunk = source.read(MAX_READ_BYTES - len(guard))
                self._offset += len(chunk)
                self._anchor = (self._anchor + chunk)[-_ANCHOR_BYTES:]
                self.status.update(state="ready", backlog_bytes=max(0, metadata.st_size - self._offset))
                return chunk
        except FileNotFoundError:
            self._unavailable("missing")
        except OSError:
            self._unavailable("unreadable")
        return b""

    def poll(self, players: list[dict]) -> list[dict]:
        chunk = self._read()
        if not chunk:
            return []
        identities = _identities(players)
        events = []
        start = 0
        while start < len(chunk):
            end = chunk.find(b"\n", start)
            complete = end != -1
            stop = end if complete else len(chunk)
            length = stop - start
            if not self._discard:
                if len(self._pending) + length > MAX_LINE_BYTES:
                    self._pending.clear()
                    self._discard = True
                else:
                    self._pending.extend(chunk[start:stop])
            if not complete:
                break
            if not self._discard and len(events) < MAX_EVENTS:
                line = bytes(self._pending)
                # Vanilla LF and Windows CRLF are both accepted; other control
                # characters, embedded carriage returns and invalid UTF-8 drop.
                if line.endswith(b"\r"):
                    line = line[:-1]
                event = _event(line, identities, allow_chat=self.allow_chat)
                if event is not None:
                    events.append(event)
            self._pending.clear()
            self._discard = False
            start = end + 1
        return events
