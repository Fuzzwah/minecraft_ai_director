"""Durable authoritative ledger; Minecraft persistence is a separate domain."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

SCHEMA_VERSION = 2
TERMINAL_OPERATIONS = ('COMMITTED', 'ABORTED')
LIVE_QUESTS = ('GENERATING', 'ACTIVE', 'PAUSED', 'COMPLETING', 'REVIEW_REQUIRED')


def dumps(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def loads(value):
    return json.loads(value) if value is not None else None


def fingerprint(value):
    return hashlib.sha256(dumps(value).encode()).hexdigest()


_SCHEMA = """
CREATE TABLE server_state (
 id INTEGER PRIMARY KEY CHECK(id=1), installation_id TEXT NOT NULL UNIQUE,
 version TEXT NOT NULL CHECK(version='26.3'), protocol INTEGER NOT NULL CHECK(protocol=1),
 sequence INTEGER NOT NULL DEFAULT 0 CHECK(sequence>=0), revision INTEGER NOT NULL DEFAULT 0,
 config_revision INTEGER NOT NULL DEFAULT 1, epoch INTEGER, session TEXT,
 active_quest TEXT, cooldown REAL NOT NULL DEFAULT 0 CHECK(cooldown>=0),
 operator_paused INTEGER NOT NULL DEFAULT 0 CHECK(operator_paused IN (0,1)),
 last_checkpoint TEXT, backup_generation TEXT NOT NULL, config TEXT NOT NULL
);
CREATE TABLE chests (
 id INTEGER PRIMARY KEY CHECK(id=1), installation_id TEXT NOT NULL,
 dimension TEXT NOT NULL CHECK(dimension='minecraft:overworld'), x INTEGER NOT NULL,
 y INTEGER NOT NULL, z INTEGER NOT NULL, forceload_owned INTEGER NOT NULL CHECK(forceload_owned IN(0,1))
);
CREATE TABLE daily_caps(day TEXT PRIMARY KEY, activations INTEGER NOT NULL DEFAULT 0 CHECK(activations>=0), calls INTEGER NOT NULL DEFAULT 0 CHECK(calls>=0));
CREATE TABLE generations (
 id TEXT PRIMARY KEY, revision INTEGER NOT NULL, seed TEXT NOT NULL, candidates TEXT NOT NULL,
 config TEXT NOT NULL, elapsed REAL NOT NULL DEFAULT 0 CHECK(elapsed>=0),
 request_started INTEGER NOT NULL DEFAULT 0 CHECK(request_started IN(0,1)),
 request_status TEXT NOT NULL, proposal TEXT, model TEXT, metadata TEXT, created REAL NOT NULL
);
CREATE TABLE quests (
 id TEXT PRIMARY KEY, generation_id TEXT REFERENCES generations(id), revision INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN('GENERATING','ACTIVE','PAUSED','COMPLETING','COMPLETED','EXPIRED','CANCELLED','REVIEW_REQUIRED')),
 objective TEXT NOT NULL, reward TEXT NOT NULL, title TEXT NOT NULL, flavor TEXT NOT NULL,
 source TEXT NOT NULL, model TEXT, config TEXT NOT NULL, remaining REAL NOT NULL CHECK(remaining>=0),
 active_elapsed REAL NOT NULL DEFAULT 0 CHECK(active_elapsed>=0), milestones INTEGER NOT NULL DEFAULT 0,
 warning INTEGER NOT NULL DEFAULT 0, reminders INTEGER NOT NULL DEFAULT 0,
 created REAL NOT NULL, terminal_at REAL, terminal_reason TEXT, recipients_count INTEGER NOT NULL DEFAULT 0,
 total_issued INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX one_live_quest ON quests((1)) WHERE status IN('GENERATING','ACTIVE','PAUSED','COMPLETING','REVIEW_REQUIRED');
CREATE TABLE recipients (
 quest_id TEXT NOT NULL REFERENCES quests(id), player_uuid TEXT NOT NULL,
 snapshot TEXT NOT NULL, PRIMARY KEY(quest_id,player_uuid)
);
CREATE TABLE entitlements (
 id TEXT PRIMARY KEY, quest_id TEXT NOT NULL REFERENCES quests(id), player_uuid TEXT NOT NULL,
 reward TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN('PENDING','WAITING_OFFLINE','WAITING_SPACE','DELIVERING','DELIVERED','REVIEW_REQUIRED','VOIDED')),
 created REAL NOT NULL, updated REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
 next_attempt REAL NOT NULL DEFAULT 0, wait_reason TEXT, terminal_reason TEXT,
 UNIQUE(quest_id,player_uuid)
);
CREATE INDEX oldest_rewards ON entitlements(player_uuid,created,id);
CREATE TABLE operations (
 id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE, kind TEXT NOT NULL CHECK(kind IN('COMPLETE','PAY','REGISTER_CHEST','UNREGISTER_CHEST')),
 target TEXT NOT NULL, quest_id TEXT REFERENCES quests(id), entitlement_id TEXT REFERENCES entitlements(id),
 revision INTEGER NOT NULL, session TEXT NOT NULL, epoch INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN('PREPARED','DISPATCHED','APPLIED','COMMITTED','ABORTED','REVIEW_REQUIRED')),
 request TEXT NOT NULL, request_hash TEXT NOT NULL, result TEXT, result_hash TEXT,
 receipt TEXT, evidence TEXT, checkpoint TEXT, review_reason TEXT, resolution TEXT,
 created REAL NOT NULL, updated REAL NOT NULL
);
CREATE UNIQUE INDEX one_unresolved_target ON operations(target) WHERE status IN('PREPARED','DISPATCHED','APPLIED');
CREATE TABLE notifications (
 id TEXT PRIMARY KEY, audience TEXT, kind TEXT NOT NULL, content TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN('PENDING','SENT')), created REAL NOT NULL, sent REAL,
 attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0
);
CREATE TABLE audit_events (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, time REAL NOT NULL, actor TEXT NOT NULL,
 action TEXT NOT NULL, target TEXT, reason TEXT, details TEXT NOT NULL
);
CREATE TABLE confirmations (
 token TEXT PRIMARY KEY, action TEXT NOT NULL, target TEXT, revision INTEGER NOT NULL,
 args TEXT NOT NULL, actor TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL,
 used INTEGER NOT NULL DEFAULT 0 CHECK(used IN(0,1))
);
"""


class Store:
    def __init__(self, path, config=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        existed = self.path.exists()
        if existed and self.path.stat().st_size == 0:
            raise RuntimeError('Existing database is empty; preserve it and restore a coordinated backup')
        try:
            self.db = sqlite3.connect(self.path, isolation_level=None)
            os.chmod(self.path, 0o600)
            self.db.row_factory = sqlite3.Row
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('PRAGMA busy_timeout=5000')
            self.integrity()
            version = self.db.execute('PRAGMA user_version').fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError('Database schema is newer than this director')
            if version not in (0, 1, SCHEMA_VERSION):
                raise RuntimeError('Unsupported database schema version; preserve database')
            if version == 0:
                if existed:
                    raise RuntimeError('Unversioned existing database cannot be initialized as fresh state')
                self.db.executescript('BEGIN IMMEDIATE;\n' + _SCHEMA + '\nPRAGMA user_version=2;\nCOMMIT;')
                with self.transaction():
                    self.db.execute('INSERT INTO server_state(id,installation_id,version,protocol,backup_generation,config) VALUES(1,?,\'26.3\',1,?,?)', (uuid.uuid4().hex, uuid.uuid4().hex, dumps(config or {})))
            elif version == 1:
                self._validate_schema(legacy=True)
                self.backup(str(self.path) + '.pre-v2-' + uuid.uuid4().hex)
                with self.transaction():
                    self.db.execute('DROP INDEX one_unresolved_target')
                    self.db.execute("CREATE UNIQUE INDEX one_unresolved_target ON operations(target) WHERE status IN('PREPARED','DISPATCHED','APPLIED')")
                    self.db.execute('PRAGMA user_version=2')
            self._validate_schema()
        except Exception:
            if hasattr(self, 'db'):
                self.db.close()
            raise

    def _validate_schema(self, legacy=False):
        expected = {'server_state', 'chests', 'daily_caps', 'generations', 'quests', 'recipients', 'entitlements', 'operations', 'notifications', 'audit_events', 'confirmations'}
        actual = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not expected <= actual or self.one('SELECT * FROM server_state WHERE id=1') is None:
            raise RuntimeError('Database schema/state is incomplete; refusing initialization')
        reference = sqlite3.connect(':memory:')
        try:
            reference.executescript(_SCHEMA)
            if legacy:
                reference.execute('DROP INDEX one_unresolved_target')
                reference.execute("CREATE UNIQUE INDEX one_unresolved_target ON operations(target) WHERE status NOT IN('COMMITTED','ABORTED')")
            # table_info omits CHECK/UNIQUE constraints and can miss schema
            # tampering with otherwise identical columns. Validate all SQL and
            # implicit constraint indexes, and reject extra executable schema.
            def definitions(connection):
                return {(row[0], row[1], row[2]): ' '.join(row[3].split()) if row[3] is not None else None
                        for row in connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' OR type='index'")}
            if definitions(self.db) != definitions(reference):
                raise RuntimeError('Database schema constraints/definitions mismatch; preserve database')
            for table in expected:
                wanted = reference.execute('PRAGMA table_info(' + table + ')').fetchall()
                observed = [tuple(row) for row in self.db.execute('PRAGMA table_info(' + table + ')')]
                if observed != wanted:
                    raise RuntimeError('Database table definition mismatch: ' + table)
                wanted_keys = reference.execute('PRAGMA foreign_key_list(' + table + ')').fetchall()
                observed_keys = [tuple(row) for row in self.db.execute('PRAGMA foreign_key_list(' + table + ')')]
                if observed_keys != wanted_keys:
                    raise RuntimeError('Database foreign-key definition mismatch: ' + table)
            for name in ('one_live_quest', 'one_unresolved_target', 'oldest_rewards'):
                wanted = reference.execute('SELECT sql FROM sqlite_master WHERE name=?', (name,)).fetchone()[0]
                observed = self.db.execute('SELECT sql FROM sqlite_master WHERE name=?', (name,)).fetchone()
                if observed is None or ' '.join(observed[0].split()) != ' '.join(wanted.split()):
                    raise RuntimeError('Database index definition mismatch: ' + name)
        finally:
            reference.close()
        self.integrity()

    def integrity(self):
        result = self.db.execute('PRAGMA integrity_check').fetchall()
        if len(result) != 1 or result[0][0] != 'ok':
            raise RuntimeError('SQLite integrity check failed; preserve database and restore coordinated backup')
        if self.db.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise RuntimeError('SQLite foreign-key check failed')
        return 'ok'

    @contextmanager
    def transaction(self):
        nested = self.db.in_transaction
        savepoint = 'nested_' + uuid.uuid4().hex
        self.db.execute('SAVEPOINT ' + savepoint if nested else 'BEGIN IMMEDIATE')
        try:
            yield self
            self.db.execute('RELEASE ' + savepoint if nested else 'COMMIT')
        except BaseException:
            if nested:
                self.db.execute('ROLLBACK TO ' + savepoint)
                self.db.execute('RELEASE ' + savepoint)
            else:
                self.db.execute('ROLLBACK')
            raise

    def one(self, sql, args=()):
        row = self.db.execute(sql, args).fetchone()
        return dict(row) if row is not None else None

    def all(self, sql, args=()):
        return [dict(row) for row in self.db.execute(sql, args)]

    def execute(self, sql, args=()):
        return self.db.execute(sql, args)

    @property
    def server(self):
        return self.one('SELECT * FROM server_state WHERE id=1')

    def audit(self, action, target=None, reason=None, actor='service', details=None):
        self.execute('INSERT INTO audit_events(time,actor,action,target,reason,details) VALUES(?,?,?,?,?,?)', (time.time(), actor, action, target, reason, dumps(details or {})))

    def reserve(self, day, kind, limit, override=False):
        if kind not in ('activations', 'calls'):
            raise ValueError('Unknown reservation kind')
        with self.transaction():
            self.execute('INSERT OR IGNORE INTO daily_caps(day) VALUES(?)', (day,))
            count = self.one('SELECT * FROM daily_caps WHERE day=?', (day,))[kind]
            if count >= limit and not override:
                return False
            self.execute('UPDATE daily_caps SET ' + kind + '=' + kind + '+1 WHERE day=?', (day,))
        return True

    def prepare(self, kind, target, revision, session, epoch, request, quest_id=None, entitlement_id=None):
        with self.transaction():
            if self.one("SELECT id FROM operations WHERE target=? AND status NOT IN('COMMITTED','ABORTED')", (target,)):
                raise sqlite3.IntegrityError('Inventory target has an unresolved operation')
            self.execute('UPDATE server_state SET sequence=sequence+1 WHERE id=1')
            server = self.server
            sequence = server['sequence']
            # The random nonce also prevents ID reuse when an old DB backup is restored.
            operation_id = hashlib.sha256((server['installation_id'] + ':' + str(sequence) + ':' + uuid.uuid4().hex).encode()).hexdigest()[:32]
            now = time.time()
            self.execute('INSERT INTO operations(id,sequence,kind,target,quest_id,entitlement_id,revision,session,epoch,status,request,request_hash,created,updated) VALUES(?,?,?,?,?,?,?,?,?,\'PREPARED\',?,?,?,?)', (operation_id, sequence, kind, target, quest_id, entitlement_id, revision, session, epoch, dumps(request), fingerprint(request), now, now))
            self.audit('operation_prepared', operation_id, details={'kind': kind, 'target': target})
        return self.one('SELECT * FROM operations WHERE id=?', (operation_id,))

    def operation_update(self, operation_id, status, **fields):
        allowed = {'result', 'receipt', 'evidence', 'checkpoint', 'review_reason', 'resolution', 'revision'}
        if not fields.keys() <= allowed:
            raise ValueError('Unknown operation field')
        if status == 'COMMITTED':
            row = self.one('SELECT checkpoint FROM operations WHERE id=?', (operation_id,))
            checkpoint = fields.get('checkpoint', loads(row['checkpoint']) if row else None)
            token = checkpoint.get('token') if isinstance(checkpoint, dict) else None
            if not isinstance(checkpoint, dict) or checkpoint.get('acknowledged') is not True or not isinstance(token, str) or len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
                raise RuntimeError('Operation cannot commit before an acknowledged world checkpoint')
        params = [status, time.time()]
        clauses = ['status=?', 'updated=?']
        for key, value in fields.items():
            clauses.append(key + '=?')
            params.append(dumps(value) if key in {'result', 'receipt', 'evidence', 'checkpoint', 'resolution'} else value)
        if 'result' in fields:
            clauses.append('result_hash=?')
            params.append(fingerprint(fields['result']))
        params.append(operation_id)
        self.execute('UPDATE operations SET ' + ','.join(clauses) + ' WHERE id=?', params)

    def notify(self, event_id, message, audience=None, kind='status'):
        self.execute('INSERT OR IGNORE INTO notifications(id,audience,kind,content,status,created) VALUES(?,?,?,?,\'PENDING\',?)', (event_id, audience, kind, dumps({'message': message}), time.time()))

    def confirmation(self, action, target, revision, args, actor):
        token = uuid.uuid4().hex
        now = time.time()
        self.execute('INSERT INTO confirmations(token,action,target,revision,args,actor,created,expires) VALUES(?,?,?,?,?,?,?,?)', (token, action, target, revision, dumps(args), actor, now, now + 600))
        return token

    def backup(self, path):
        destination = sqlite3.connect(path)
        try:
            self.db.backup(destination)
        finally:
            destination.close()
        os.chmod(path, 0o600)

    def close(self):
        self.db.close()
