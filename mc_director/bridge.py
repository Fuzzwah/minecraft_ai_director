"""Serialized, typed RCON requests to the installed vanilla datapack.

The bridge never retries an inventory dispatch. Large logical requests are staged
as data in small RCON frames; inventory mutation exists only in datapack functions.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path

from . import snbt
from .config import SERVER_SHA1
from .rcon import MinecraftRcon, RconError, server_status


class BridgeError(RuntimeError):
    pass


ACTIONS = frozenset({
    "HELLO", "HEARTBEAT", "SNAPSHOT", "REGISTER_CHEST", "UNREGISTER_CHEST",
    "ACTIVATE", "PUBLISH_STATUS", "COMPLETE", "PAY", "READ_RECEIPT",
    "READ_EVIDENCE", "READ_CLAIMS", "ACK_CLAIMS", "PAUSE", "CHECKPOINT", "RESOLVE_RECEIPT",
})
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_PLAYER = re.compile(r"[A-Za-z0-9_]{1,16}\Z")
_PATH = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])*\Z")


def uuid_to_ints(value: str) -> snbt.IntArray:
    try:
        integer = uuid.UUID(value).int
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("Invalid player UUID") from exc
    result = [(integer >> shift) & 0xFFFFFFFF for shift in (96, 64, 32, 0)]
    return snbt.IntArray([part if part < 2**31 else part - 2**32 for part in result])


def ints_to_uuid(parts: list) -> str:
    if not isinstance(parts, (list, tuple)) or len(parts) != 4 or any(type(part) not in (int, snbt.Byte, snbt.Short, snbt.Long) or not -(2**31) <= part < 2**31 for part in parts):
        raise ValueError("Invalid Minecraft UUID integer array")
    value = 0
    for part in parts:
        value = (value << 32) | (int(part) & 0xFFFFFFFF)
    return str(uuid.UUID(int=value))


def _typed(node):
    if isinstance(node, dict):
        result = {}
        for key, value in node.items():
            if key in ("uuid", "player_uuid", "audience") and isinstance(value, str):
                result[key] = uuid_to_ints(value)
            elif key in ("uuid", "player_uuid", "audience") and isinstance(value, list):
                result[key] = uuid_to_ints(ints_to_uuid(value))
            else:
                result[key] = _typed(value)
        return result
    if isinstance(node, (snbt.ByteArray, snbt.IntArray, snbt.LongArray)):
        return node
    if isinstance(node, (list, tuple)):
        return [_typed(value) for value in node]
    return node


class GameBridge:
    def __init__(self, config):
        self.config = config
        self.client = MinecraftRcon(config.rcon_host, config.rcon_port, config.rcon_password)
        self.installation_id = ""
        self.session_id = ""
        self.epoch = None
        self.revision = 0
        self.chest: dict | None = None
        self.server_version: dict = {}
        self.artifact_verified = False
        self.last_response: dict | None = None
        self._names: dict[str, str] = {}
        self._verified = False
        self._last_heartbeat = 0.0

    def connect(self, installation_id: str) -> dict:
        if not _HEX32.fullmatch(installation_id):
            raise BridgeError("Installation ID must be a UUID hex value")
        self.close()
        status = server_status(self.config.game_host, self.config.game_port)
        if status["version"].get("name") != "26.3" or status["version"].get("protocol") != 777:
            raise BridgeError("Running Minecraft server is not the supported 26.3 release/protocol")
        self.server_version = status["version"]
        self.artifact_verified = False
        if self.config.server_jar is not None:
            path = Path(self.config.server_jar)
            try:
                with path.open("rb") as handle:
                    digest = hashlib.file_digest(handle, "sha1").hexdigest()
            except OSError as exc:
                raise BridgeError("Cannot verify configured official server jar") from exc
            if digest != SERVER_SHA1:
                raise BridgeError("Configured server jar is not Mojang's official 26.3 artifact")
            self.artifact_verified = True
        self.installation_id = installation_id
        self.session_id = uuid.uuid4().hex
        self.client.connect()
        response = self.request("HELLO", {"config": self.config.pack_config()})
        if response["status"] != "OK":
            self.close()
            raise BridgeError("Datapack handshake rejected: " + response["status"])
        payload = response["payload"]
        if payload.get("version") != "26.3" or payload.get("build") != 1 or list(payload.get("pack_format", [])) != [121, 0]:
            self.close()
            raise BridgeError("Installed datapack version/build does not match this director")
        if payload.get("installation_id") != installation_id:
            self.close()
            raise BridgeError("World installation identity does not match local state")
        if type(payload.get("epoch")) is not int or not 0 <= payload["epoch"] <= 2147483646 or type(payload.get("revision")) is not int or payload["revision"] != response["revision"]:
            self.close()
            raise BridgeError("Datapack handshake has no valid epoch/revision")
        self.epoch = payload.get("epoch")
        self.revision = int(response["revision"])
        self.chest = payload.get("chest") or None
        return payload

    def reconnect(self, installation_id: str) -> dict:
        return self.connect(installation_id)

    def close(self) -> None:
        self.client.close()
        self._verified = False

    def request(self, action: str, payload: dict | None = None, revision: int = 0,
                operation_id: str | None = None, request_hash: str | None = None) -> dict:
        if not isinstance(action, str) or action not in ACTIONS or type(revision) is not int or not 0 <= revision <= 2147483646:
            raise BridgeError("Invalid bridge action/revision")
        if not self.installation_id or not self.session_id:
            raise BridgeError("Bridge session has not been initialized")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise BridgeError("Bridge payload must be a compound")
        payload = _typed(payload)
        if action not in ("HELLO", "HEARTBEAT"):
            self._maintain_heartbeat()
        if action in ("ACTIVATE", "PUBLISH_STATUS") and payload.get("quest"):
            if not isinstance(payload["quest"], dict) or len(snbt.dumps(payload["quest"]).encode()) > 6144:
                raise BridgeError("Quest projection exceeds the 6KiB snapshot-page budget")
        request_id = uuid.uuid4().hex
        request = {"protocol": 1, "installation_id": self.installation_id, "session_id": self.session_id,
                   "request_id": request_id, "action": action, "expected_revision": revision, "payload": payload}
        if operation_id is not None:
            if not _HEX32.fullmatch(operation_id):
                raise BridgeError("Invalid operation ID")
            request["operation_id"] = operation_id
            if request_hash is None:
                request_hash = hashlib.sha256(snbt.dumps({"action": action, "revision": revision, "payload": payload}, canonical=True).encode()).hexdigest()
            if not _HEX64.fullmatch(request_hash):
                raise BridgeError("Invalid operation request fingerprint")
            request["request_hash"] = request_hash
        if action in ("COMPLETE", "PAY") and operation_id is None:
            raise BridgeError("Inventory operation requires a journal operation ID")
        if action == "COMPLETE":
            refusal = self._preflight(operation_id)
            payload["preflight_id"] = operation_id
            if refusal:
                response = self._refusal_or_receipt(request, refusal)
                if response["status"] == "APPLIED":
                    self._collect_evidence(operation_id, response["payload"])
                return response
        try:
            encoded = snbt.dumps(request, max_bytes=16_384)
            self._stage(request, encoded)
            self.client.command("function keeper:bridge/dispatch")
            response = self._data("keeper:bridge", "response", max_bytes=8192)
            self._validate(response, request)
            self.last_response = response
            self.revision = int(response["revision"])
            if response["status"] == "OK" and action in ("HELLO", "HEARTBEAT"):
                self._last_heartbeat = time.monotonic()
                if action == "HELLO":
                    self._verified = True
            if response["status"] == "OK" and action in ("REGISTER_CHEST", "HELLO"):
                self.chest = response["payload"].get("chest") or self.chest
            if response["status"] == "OK" and action == "UNREGISTER_CHEST":
                self.chest = None
            if action == "READ_RECEIPT" and response["status"] == "OK" and "offset" not in payload:
                self._assemble_receipt(response["payload"], payload["operation_id"])
            if action == "SNAPSHOT" and response["status"] == "OK" and "offset" not in payload:
                self._assemble_snapshot(response["payload"])
                self._decorate_players(response["payload"])
            if action in ("COMPLETE", "PAY") and response["status"] == "APPLIED":
                if response["payload"].get("recipients_paged"):
                    receipt = self.request("READ_RECEIPT", {"operation_id": operation_id}, revision=self.revision)
                    record = receipt["payload"].get("receipt", {})
                    if receipt["status"] != "OK" or record.get("state") != "APPLIED" or record.get("request_hash") != request["request_hash"] or record.get("operation_id") != operation_id:
                        raise BridgeError("Paged completion receipt is not correlated")
                    result = record.get("result")
                    if not isinstance(result, dict) or len(result.get("recipients", [])) != response["payload"].get("recipient_count"):
                        raise BridgeError("Paged completion recipient count is inconsistent")
                    response["payload"] = result
                slot = response["payload"].get("slot") if action == "PAY" else None
                self._collect_evidence(operation_id, response["payload"], slot=slot)
                for player in response["payload"].get("recipients", []):
                    value = ints_to_uuid(player["uuid"])
                    player.setdefault("name", self._names.get(value, value))
            return response
        except (snbt.SnbtError, ValueError, KeyError, TypeError) as exc:
            raise BridgeError("Invalid or incomplete datapack structured result") from exc

    @staticmethod
    def _validate(response: dict, request: dict) -> None:
        if not isinstance(response, dict) or response.get("protocol") != 1:
            raise BridgeError("Malformed datapack response envelope")
        if response.get("request_id") != request["request_id"] or response.get("session_id") != request["session_id"]:
            raise BridgeError("Datapack response correlation/session mismatch")
        if "operation_id" in request and response.get("operation_id") != request["operation_id"]:
            raise BridgeError("Datapack response operation mismatch")
        if type(response.get("revision")) is not int or response["revision"] < 0 or not isinstance(response.get("status"), str) or not isinstance(response.get("payload"), dict):
            raise BridgeError("Invalid datapack response field types")

    def _maintain_heartbeat(self) -> None:
        interval = min(self.config.poll_seconds, self.config.heartbeat_ticks / 40)
        if self._verified and time.monotonic() - self._last_heartbeat >= interval:
            response = self.request("HEARTBEAT", revision=self.revision)
            if response["status"] != "OK":
                raise BridgeError("Verified heartbeat rejected during bounded transport work")

    def _refusal_or_receipt(self, request: dict, refusal: str) -> dict:
        # Even an invalid/oversized current chest cannot invalidate a prior APPLIED
        # operation. Read its receipt; never dispatch a mutation to discover this.
        observed = self.request("READ_RECEIPT", {"operation_id": request["operation_id"]}, revision=self.revision)
        result = {"protocol": 1, "request_id": request["request_id"], "session_id": self.session_id,
                  "operation_id": request["operation_id"], "status": refusal, "revision": self.revision, "payload": {}}
        if observed["status"] == "NOT_FOUND":
            return result
        if observed["status"] != "OK":
            raise BridgeError("Cannot verify existing receipt for refused chest preflight")
        record = observed["payload"].get("receipt", {})
        ignored = {"request_id", "session_id", "expected_revision"}
        original = record.get("request", {})
        old = {key: value for key, value in original.items() if key not in ignored}
        new = {key: value for key, value in request.items() if key not in ignored}
        if record.get("operation_id") != request["operation_id"] or record.get("request_hash") != request["request_hash"] or snbt.dumps(old, canonical=True) != snbt.dumps(new, canonical=True):
            result["status"] = "IDEMPOTENCY_CONFLICT"
        elif record.get("state") == "APPLIED" and isinstance(record.get("result"), dict):
            result["status"] = "APPLIED"
            result["payload"] = record["result"]
        else:
            result["status"] = "REVIEW_REQUIRED"
        return result

    @staticmethod
    def _cursor(page: dict, offset: int) -> tuple[int, bool]:
        next_offset = page.get("next_offset")
        done = page.get("done")
        if page.get("offset") != offset or type(next_offset) is not int or not offset <= next_offset <= 128 or type(done) is not int or done not in (0, 1) or not done and next_offset == offset:
            raise BridgeError("Invalid bounded metadata cursor")
        return next_offset, bool(done)

    @staticmethod
    def _receipt_metadata(record: dict) -> str:
        metadata = {key: ({name: value for name, value in section.items() if name != "recipients"}
                          if key in ("plan", "result") and isinstance(section, dict) else section)
                    for key, section in record.items()}
        return snbt.dumps(metadata, canonical=True)

    def _assemble_receipt(self, payload: dict, operation_id: str) -> None:
        record = payload.get("receipt")
        if not isinstance(record, dict) or record.get("operation_id") != operation_id:
            raise BridgeError("Malformed receipt identity")
        fields = {key: [] for key in ("plan", "result") if isinstance(record.get(key), dict) and "recipients" in record[key]}
        metadata = self._receipt_metadata(record)
        page, offset = payload, 0
        for _ in range(128):
            current = page.get("receipt")
            if not isinstance(current, dict) or self._receipt_metadata(current) != metadata:
                raise BridgeError("Receipt metadata changed while paging")
            for key in fields:
                values = current.get(key, {}).get("recipients")
                if not isinstance(values, list) or len(values) > 16 or len(fields[key]) + len(values) > 128:
                    raise BridgeError("Malformed bounded receipt recipient page")
                fields[key].extend(values)
            next_offset, done = self._cursor(page, offset)
            if done:
                break
            offset = next_offset
            response = self.request("READ_RECEIPT", {"operation_id": operation_id, "offset": offset, "limit": 16}, revision=self.revision)
            if response["status"] != "OK":
                raise BridgeError("Receipt continuation is unavailable")
            page = response["payload"]
        else:
            raise BridgeError("Receipt page bound exceeded")
        for key, values in fields.items():
            record[key]["recipients"] = values
        payload.update(offset=0, next_offset=next_offset, done=1)

    def _assemble_snapshot(self, payload: dict) -> None:
        total = payload.get("total")
        if type(total) is not int or not 0 <= total <= 128:
            raise BridgeError("Online snapshot exceeds the certified player bound")
        excluded = {"players", "offset", "next_offset", "done"}
        metadata = snbt.dumps({key: value for key, value in payload.items() if key not in excluded}, canonical=True)
        players, page, offset = [], payload, 0
        for _ in range(128):
            if snbt.dumps({key: value for key, value in page.items() if key not in excluded}, canonical=True) != metadata:
                raise BridgeError("Frozen snapshot metadata changed while paging")
            values = page.get("players")
            if not isinstance(values, list) or len(values) > 16 or len(players) + len(values) > total:
                raise BridgeError("Malformed bounded online-player page")
            players.extend(values)
            next_offset, done = self._cursor(page, offset)
            if done:
                break
            offset = next_offset
            response = self.request("SNAPSHOT", {"offset": offset, "limit": 16}, revision=self.revision)
            if response["status"] != "OK":
                raise BridgeError("Snapshot continuation is unavailable")
            page = response["payload"]
        else:
            raise BridgeError("Snapshot page bound exceeded")
        if len(players) != total or len({ints_to_uuid(player["uuid"]) for player in players}) != total:
            raise BridgeError("Frozen online snapshot cardinality/UUID identity mismatch")
        payload.update(players=players, offset=0, next_offset=total, done=1)

    def _data(self, storage: str, path: str, *, max_bytes: int = snbt.MAX_BYTES):
        text = self.client.command(f"data get storage {storage} {path}")
        return snbt.extract(text, max_bytes=max_bytes)

    def _stage(self, request: dict, encoded: str) -> None:
        command = "data modify storage keeper:bridge request set value " + encoded
        if len(command.encode()) <= 1300:
            self.client.command(command)
        else:
            self._assign("request", request)

    def _assign(self, path: str, value) -> None:
        if not _PATH.fullmatch(path):
            raise BridgeError("Unsafe internal staging data path")
        encoded = snbt.dumps(value, max_bytes=16_384)
        command = f"data modify storage keeper:bridge {path} set value {encoded}"
        if len(command.encode()) <= 1300:
            self.client.command(command)
            return
        if isinstance(value, dict):
            self.client.command(f"data modify storage keeper:bridge {path} set value {{}}")
            for key, item in value.items():
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                    raise BridgeError("Unsupported staging compound key")
                self._assign(path + "." + key, item)
        elif isinstance(value, list) and not isinstance(value, (snbt.ByteArray, snbt.IntArray, snbt.LongArray)):
            self.client.command(f"data modify storage keeper:bridge {path} set value []")
            for index, item in enumerate(value):
                self.client.command(f"data modify storage keeper:bridge {path} append value {{}}")
                self._assign(f"{path}[{index}]", item)
        elif isinstance(value, str):
            self._long_string(path, value)
        else:
            raise BridgeError("Scalar staging value exceeds vanilla RCON frame size")

    def _long_string(self, path: str, value: str) -> None:
        # Each macro fragment is JSON-escaped independently before storage. Quotes,
        # backslashes, control escapes, and line breaks cannot escape the final literal.
        chunks = []
        piece = ""
        for char in value:
            proposed = piece + char
            escaped = json.dumps(proposed, ensure_ascii=False)[1:-1]
            if len(snbt.dumps(escaped).encode()) > 900:
                if not piece:
                    raise BridgeError("Cannot stage Unicode string within RCON frame limit")
                chunks.append(json.dumps(piece, ensure_ascii=False)[1:-1])
                piece = char
            else:
                piece = proposed
        if piece:
            chunks.append(json.dumps(piece, ensure_ascii=False)[1:-1])
        if len(chunks) > 32:
            raise BridgeError("String staging exceeds the bounded macro fragment count")
        self._assign("join_args", {"path": path, **{f"c{index}": "" for index in range(32)}})
        for index, chunk in enumerate(chunks):
            self._assign(f"join_args.c{index}", chunk)
        self.client.command("function keeper:bridge/join_string with storage keeper:bridge join_args")

    def _preflight(self, operation_id: str) -> str | None:
        if not self.chest:
            return "CHEST_INVALID"
        try:
            coordinates = [self.chest[key] for key in ("x", "y", "z")]
            if any(type(value) is not int for value in coordinates):
                return "CHEST_INVALID"
            xyz = " ".join(str(value) for value in coordinates)
            initial = {"id": operation_id, "items": [], "approved": 0}
            self.client.command("data modify storage keeper:bridge preflight set value " + snbt.dumps(initial))
            self.client.command(f"execute in minecraft:overworld run data modify storage keeper:bridge preflight.items set from block {xyz} Items")
            items = self._data("keeper:bridge", "preflight.items")
            if not isinstance(items, list):
                return "CHEST_INVALID"
            snbt.dumps(items, max_bytes=snbt.MAX_BYTES)
            if any(len(snbt.dumps(item).encode()) > 4096 for item in items):
                return "EVIDENCE_LIMIT"
            self.client.command("data modify storage keeper:bridge preflight.approved set value 1")
            return None
        except snbt.SnbtError:
            return "EVIDENCE_LIMIT"

    def _collect_evidence(self, operation_id: str, payload: dict, *, slot: int | None = None) -> None:
        for kind in ("before", "after"):
            items = []
            offset = 0 if slot is None else slot
            for _ in range(28):
                response = self.request("READ_EVIDENCE", {"operation_id": operation_id, "kind": kind, "offset": offset, "limit": 1}, revision=self.revision)
                if response["status"] != "OK":
                    raise BridgeError("Applied operation evidence is unavailable")
                page = response["payload"]
                if not isinstance(page.get("items"), list) or len(page["items"]) > 1 or page.get("offset") != offset:
                    raise BridgeError("Malformed inventory evidence page")
                items.extend(page["items"])
                if page.get("done") or slot is not None:
                    break
                next_offset = page.get("next_offset")
                if type(next_offset) is not int or next_offset <= offset or next_offset > 27:
                    raise BridgeError("Invalid evidence cursor")
                offset = next_offset
            else:
                raise BridgeError("Inventory evidence page limit exceeded")
            payload[f"evidence_{kind}_snbt"] = snbt.dumps(items, canonical=True)

    def evidence(self, operation_id: str) -> dict:
        receipt = self.request("READ_RECEIPT", {"operation_id": operation_id}, revision=self.revision)
        record = receipt["payload"].get("receipt", {})
        if receipt["status"] != "OK" or record.get("operation_id") != operation_id:
            raise BridgeError("Operation receipt is unavailable for evidence")
        slot = record.get("result", {}).get("slot") if record.get("request", {}).get("action") == "PAY" else None
        result = {}
        self._collect_evidence(operation_id, result, slot=slot)
        return result

    def checkpoint(self) -> str:
        token = uuid.uuid4().hex
        response = self.request("CHECKPOINT", {"token": token}, revision=self.revision)
        if response["status"] != "OK" or response["payload"].get("token") != token:
            raise BridgeError("World checkpoint marker was not acknowledged")
        result = self.client.command("save-all flush")
        if "Saved the game" not in result:
            raise BridgeError("Minecraft checkpoint failed or was not acknowledged")
        return token

    def _decorate_players(self, payload: dict) -> None:
        players = payload.get("players", [])
        if not isinstance(players, list):
            raise BridgeError("Malformed online-player snapshot")
        observed = {ints_to_uuid(player["uuid"]) for player in players}
        if observed - self._names.keys():
            response = self.client.command("list")
            names = response.split(":", 1)[1].strip().split(",") if ":" in response else []
            for name in (value.strip() for value in names):
                if not _PLAYER.fullmatch(name):
                    continue
                self._maintain_heartbeat()
                try:
                    value = snbt.extract(self.client.command(f"data get entity {name} UUID"))
                    self._names[ints_to_uuid(value)] = name
                except (snbt.SnbtError, ValueError):
                    continue  # A player may disconnect between these read-only queries.
        self._names = {key: value for key, value in self._names.items() if key in observed}
        for player in players:
            value = ints_to_uuid(player["uuid"])
            player.setdefault("name", self._names.get(value, value))
