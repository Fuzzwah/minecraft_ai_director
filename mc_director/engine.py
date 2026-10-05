"""Single-owner lifecycle, durable intents and conservative inventory reconciliation."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
import math
import os
import re
import sqlite3
import time
import uuid

from . import llm, rules
from .state import Store, dumps, loads
from .bridge import uuid_to_ints, ints_to_uuid
from .events import ServerLog

SAFE_RESULTS = {'INSUFFICIENT_ITEMS', 'OFFLINE', 'NO_SPACE', 'NO_RECIPIENTS', 'RECIPIENT_LIMIT', 'SESSION_MISMATCH', 'STALE_REVISION', 'STALE_PREFLIGHT', 'INVALID_REQUEST', 'CHEST_INVALID', 'PAUSED', 'EVIDENCE_LIMIT'}
PENDING = ('PENDING', 'WAITING_OFFLINE', 'WAITING_SPACE')


class Engine:
    def __init__(self, config, bridge):
        self.config = config
        self.bridge = bridge
        self.store = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='keeper-ai')
        self.future = None
        self.future_generation = None
        self.connected = False
        self.started = False
        self.healthy = False
        self.pause_reason = 'not_started'
        self.snapshot = {}
        self.online = set()
        self.eligible = set()
        self.last_tick = None
        self.last_poll = None
        self.last_timer_save = None
        self.epoch = 0
        self.revision = 0
        self.session = ''
        self.quest = None
        self.cooldown = 0.0
        self.events = None
        self.deferred_config = None
        self.storage_fault = False
        self.last_fault = None
        self.log_source = ServerLog(config.log_path, allow_chat=config.share_chat)

    @staticmethod
    def _day():
        return datetime.now(timezone.utc).date().isoformat()

    def start(self):
        if self.started:
            raise RuntimeError('Engine already started')
        self.store = Store(self.config.db_path, self.config.public())
        server = self.store.server
        fault = self.store.one("SELECT details FROM audit_events WHERE action='service_fault' ORDER BY sequence DESC LIMIT 1")
        self.last_fault = loads(fault['details']) if fault else None
        self.cooldown = server['cooldown']
        self.events = rules.EventContext(server['installation_id'])
        row = self.store.one("SELECT * FROM quests WHERE status IN('GENERATING','ACTIVE','PAUSED','COMPLETING','REVIEW_REQUIRED')")
        self.quest = self._decode_quest(row)
        if self.quest:
            frozen_fields = ('catalog', 'rewards', 'excluded_uuids', 'max_recipients', 'heartbeat_ticks', 'quest_expiry_seconds', 'cooldown_seconds', 'max_quests_per_day', 'max_ai_calls_per_day', 'generation_deadline_seconds', 'llm_timeout_seconds', 'flavor_enabled', 'poll_seconds', 'reward_retry_seconds', 'max_payout_batch', 'demo_mode', 'share_events', 'share_chat', 'llm_url', 'llm_model')
            snapshot = self.quest['config']
            frozen = {field: snapshot[field] for field in frozen_fields if field in snapshot}
            effective = replace(self.config, **frozen)
            if effective.public() != self.config.public():
                self.deferred_config = self.config
                self.config = effective
                self.bridge.config = effective
        if self.log_source.allow_chat != self.config.share_chat:
            self.log_source = ServerLog(self.config.log_path, allow_chat=self.config.share_chat)
        # Even an unchanged epoch cannot prove persistence across a process restart.
        self._quarantine('director startup requires operator reconciliation')
        if self.quest and self.quest['status'] == 'GENERATING':
            generation = self._generation()
            if generation['request_started'] and not generation['proposal']:
                self._choose_fallback('restart_after_request_started')
        self.started = True
        try:
            self._connect()
        except Exception as error:
            self.connected = False
            self.pause_reason = 'connection_or_handshake_fault'
            self._fault(error, 'start')
        now = time.monotonic()
        self.last_tick = now
        self.last_timer_save = now
        return {'installation_id': server['installation_id'], 'connected': self.connected, 'paused': self.pause_reason, 'last_fault': self.last_fault}

    def _fault(self, error, phase):
        from .bridge import BridgeError
        from .rcon import RconError
        if isinstance(error, llm.ProviderError):
            category, message = 'provider', error.category
        elif isinstance(error, sqlite3.Error):
            category, message = 'storage', 'SQLite ' + type(error).__name__ + '; preserve the database and repair/restore coordinated state'
        elif isinstance(error, OSError):
            category = 'connection'
            message = os.strerror(error.errno) if error.errno else 'Socket/OS connection failure'
        elif isinstance(error, (BridgeError, RconError, RuntimeError, ValueError)):
            category = 'protocol' if isinstance(error, (BridgeError, RuntimeError, ValueError)) else 'connection'
            message = str(error)
        else:
            category, message = 'internal', 'Unexpected ' + type(error).__name__ + '; operator inspection required'
        for config in (self.config, self.deferred_config):
            if config is not None:
                for field in ('rcon_password', 'llm_api_key', 'llm_url'):
                    secret = getattr(config, field, '')
                    if secret:
                        message = message.replace(secret, '[redacted]')
        message = re.sub(r'https?://\S+|(?i:bearer)\s+\S+', '[redacted]', message)
        # Never include provider bodies, exception chains, multiline command
        # responses, or arbitrary structured payloads in operator diagnostics.
        message = message.splitlines()[0] if message else category
        if any(mark in message for mark in ('{', '}', '<', '>')):
            message = 'Structured error details withheld; inspect ' + category + ' configuration and connection'
        message = ''.join(char for char in message if char.isprintable())[:300]
        fault = {'category': category, 'message': message, 'phase': phase, 'time': time.time()}
        previous = self.last_fault
        self.last_fault = fault
        if previous is None or any(previous.get(key) != fault[key] for key in ('category', 'message', 'phase')):
            try:
                self.store.audit('service_fault', reason=category, details=fault)
            except (sqlite3.Error, OSError):
                self.storage_fault = True
                self.pause_reason = 'storage_fault'

    def _decode_quest(self, row):
        if row is None:
            return None
        result = dict(row)
        for key in ('objective', 'reward', 'config'):
            result[key] = loads(result[key])
        return result

    def _generation(self):
        if not self.quest or not self.quest['generation_id']:
            return None
        row = self.store.one('SELECT * FROM generations WHERE id=?', (self.quest['generation_id'],))
        for key in ('candidates', 'config', 'proposal', 'metadata'):
            row[key] = loads(row[key])
        return row

    def _chest(self):
        return self.store.one('SELECT * FROM chests WHERE id=1')

    def _connect(self):
        hello = self.bridge.reconnect(self.store.server['installation_id']) if self.session else self.bridge.connect(self.store.server['installation_id'])
        if hello.get('version') != '26.3' or hello.get('build') != 1 or list(hello.get('pack_format', [])) != [121, 0]:
            raise RuntimeError('Unsupported server/datapack handshake')
        if hello.get('installation_id') != self.store.server['installation_id']:
            raise RuntimeError('Installation identity mismatch')
        expected_checkpoint = loads(self.store.server['last_checkpoint']) or {}
        restore_mismatch = bool(expected_checkpoint.get('token')) and hello.get('checkpoint_token') != expected_checkpoint['token']
        self.epoch = int(hello['epoch'])
        self.revision = int(hello.get('revision', self.bridge.revision))
        self.session = getattr(self.bridge, 'session_id', '') or hello.get('session_id', '')
        if not self.session:
            raise RuntimeError('Bridge did not expose verified session_id')
        with self.store.transaction():
            self.store.execute('UPDATE server_state SET epoch=?,session=?,revision=? WHERE id=1', (self.epoch, self.session, self.revision))
        if restore_mismatch:
            with self.store.transaction():
                self.store.execute('UPDATE server_state SET operator_paused=1 WHERE id=1')
                for operation in self.store.all("SELECT * FROM operations WHERE kind IN('COMPLETE','PAY') AND status='COMMITTED'"):
                    self._review(operation, 'world/database checkpoint nonce mismatch; committed issuance may have rolled back')
                self.store.audit('restore_mismatch', reason='world/database checkpoint nonce mismatch', details={'expected_token': expected_checkpoint.get('token'), 'observed_token': hello.get('checkpoint_token')})
            self.pause_reason = 'restore_mismatch'
            self._fault(RuntimeError('World/database checkpoint nonce mismatch; reconcile restored issuance before resume'), 'restore')
        local = self._chest()
        remote = hello.get('chest') or None
        if bool(local) != bool(hello.get('registered')) or (local and (remote is None or any(local[k] != remote.get(k) for k in ('x', 'y', 'z', 'forceload_owned')))):
            self.connected = True
            self.pause_reason = 'chest_registration_mismatch'
            self.bridge.request('PAUSE', {'reason': self.pause_reason}, revision=self.revision)
            return
        self.connected = True
        self._poll()
        # Reinstall durable active projection before publishing updates to it.
        if self.quest and self.quest['status'] in ('ACTIVE', 'PAUSED') and self._ready():
            self._activate_projection()
        self._publish(paused=not self._service_ready())

    def _request(self, action, payload=None, revision=None, **kwargs):
        response = self.bridge.request(action, payload or {}, revision=self.revision if revision is None else revision, **kwargs)
        self.revision = response['revision']
        self.store.execute('UPDATE server_state SET revision=? WHERE id=1', (self.revision,))
        return response

    def _quarantine(self, reason):
        operations = self.store.all("SELECT * FROM operations WHERE status IN('PREPARED','DISPATCHED','APPLIED')")
        with self.store.transaction():
            for operation in operations:
                self._review(operation, reason)

    def _review(self, operation, reason, actor='service'):
        self.store.operation_update(operation['id'], 'REVIEW_REQUIRED', review_reason=reason, revision=operation['revision'] + 1)
        if operation['kind'] == 'COMPLETE':
            self.store.execute("UPDATE quests SET status='REVIEW_REQUIRED' WHERE id=? AND status IN('GENERATING','ACTIVE','PAUSED','COMPLETING','REVIEW_REQUIRED')", (operation['quest_id'],))
            if self.quest and self.quest['id'] == operation['quest_id']:
                self.quest['status'] = 'REVIEW_REQUIRED'
        elif operation['kind'] == 'PAY':
            self.store.execute("UPDATE entitlements SET status='REVIEW_REQUIRED',wait_reason=?,updated=? WHERE id=?", (reason, time.time(), operation['entitlement_id']))
        self.store.audit('review_required', operation['id'], reason=reason, actor=actor)

    def _blocked_chest(self):
        return self.store.one("SELECT id FROM operations WHERE target='chest' AND status NOT IN('COMMITTED','ABORTED')") is not None

    def _service_ready(self):
        return (self.connected and not self.storage_fault and self.pause_reason not in ('chest_registration_mismatch', 'storage_fault') and not self.store.server['operator_paused'] and bool(self.snapshot.get('registered')) and bool(self.snapshot.get('chest_valid')))

    def _ready(self):
        return self._service_ready() and bool(self.eligible) and not self._blocked_chest()

    def _poll(self):
        heartbeat = self._request('HEARTBEAT')
        if heartbeat['status'] != 'OK':
            raise RuntimeError('Heartbeat rejected: ' + heartbeat['status'])
        response = self._request('SNAPSHOT')
        if response['status'] != 'OK':
            raise RuntimeError('Snapshot rejected: ' + response['status'])
        snapshot = response['payload']
        if int(snapshot['epoch']) != self.epoch:
            self._quarantine('datapack load epoch changed')
            self.connected = False
            raise RuntimeError('Datapack epoch changed; handshake required')
        self.snapshot = snapshot
        new_online = {ints_to_uuid(p['uuid']) for p in snapshot.get('players', [])}
        self.eligible = {ints_to_uuid(p['uuid']) for p in snapshot.get('players', []) if p.get('eligible')}
        for player in new_online - self.online:
            self.events.record('join', player)
            self.store.notify('join:' + self.session + ':' + player + ':' + uuid.uuid4().hex, self._status_text(), player)
            self.store.execute('UPDATE entitlements SET next_attempt=0 WHERE player_uuid=? AND status IN(\'PENDING\',\'WAITING_OFFLINE\',\'WAITING_SPACE\')', (player,))
        for player in self.online - new_online:
            self.events.record('leave', player)
        self.online = new_online
        for event in self.log_source.poll(snapshot.get('players', [])):
            if event['kind'] == 'chat':
                self.events.record_chat(event['uuid'], event['text'], player_names=tuple(player['name'] for player in snapshot.get('players', [])))
            else:
                self.events.record(event['kind'], event['uuid'])
        if self.store.server['operator_paused']:
            self.pause_reason = 'operator_pause'
        elif not snapshot.get('registered'):
            self.pause_reason = 'chest_unregistered'
        elif not snapshot.get('chest_valid'):
            self.pause_reason = 'chest_invalid'
        elif not self.eligible:
            self.pause_reason = 'community_offline'
        elif self._blocked_chest():
            self.pause_reason = 'chest_operation_review'
        elif self.pause_reason != 'chest_registration_mismatch':
            self.pause_reason = ''

    def tick(self, now=None):
        if not self.started:
            raise RuntimeError('Engine not started')
        now = time.monotonic() if now is None else float(now)
        elapsed = max(0.0, now - self.last_tick) if self.last_tick is not None else 0.0
        self.last_tick = now
        previous_healthy = self.healthy and elapsed <= max(self.config.poll_seconds * 2, self.config.heartbeat_ticks / 20)
        try:
            if self.quest and self.quest['status'] == 'GENERATING' and not self.storage_fault:
                generation = self._generation()
                generation['elapsed'] += elapsed
                self.store.execute('UPDATE generations SET elapsed=? WHERE id=?', (generation['elapsed'], generation['id']))
                if not generation['proposal'] and generation['elapsed'] >= self.config.generation_deadline_seconds:
                    self._choose_fallback('generation_deadline')
            if not self.connected and not self.storage_fault:
                self._quarantine('transport reconnect')
                self._connect()
            poll_due = self.last_poll is None or now - self.last_poll >= self.config.poll_seconds
            if poll_due and self.connected:
                self._poll()
                self.last_poll = now
            self.healthy = self._ready()
            # Unknown gaps and readiness transitions do not debit healthy counters.
            if previous_healthy and self.healthy:
                if self.quest and self.quest['status'] in ('ACTIVE', 'PAUSED'):
                    self.quest['remaining'] = max(0.0, self.quest['remaining'] - elapsed)
                    self.quest['active_elapsed'] += elapsed
                elif self.quest is None:
                    self.cooldown = max(0.0, self.cooldown - elapsed)
            if self.quest and self.quest['status'] == 'GENERATING':
                self._finish_generation(self._generation())
            if self.quest and self.quest['status'] in ('ACTIVE', 'PAUSED'):
                status = 'ACTIVE' if self.healthy else 'PAUSED'
                changed = self.quest['status'] != status
                self.quest['status'] = status
                if changed:
                    self._save_timers()
                if self.healthy and self.quest['remaining'] <= 0:
                    self._terminal('EXPIRED', 'healthy active deadline reached')
                elif self.healthy and poll_due:
                    self._progress()
            if self.healthy and self.quest is None and self.cooldown <= 0:
                self._begin_generation()
            if self.connected and poll_due:
                self._publish(paused=not self._service_ready())
                if self._service_ready():
                    self._claims()
                    self._payouts()
                self._notifications()
            if self.last_timer_save is None or now - self.last_timer_save >= 30:
                self._save_timers()
                self.last_timer_save = now
            if self.deferred_config is not None and self.quest is None and not self._blocked_chest():
                self._apply_config(self.deferred_config)
                self.deferred_config = None
        except Exception as error:
            # Store errors are not replaced with fresh state or a retrying empty ledger.
            self.healthy = False
            if isinstance(error, sqlite3.Error):
                self.storage_fault = True
                self.pause_reason = 'storage_fault'
            else:
                self.connected = False
                self.pause_reason = 'transport_or_protocol_fault'
            self._fault(error, 'tick')
            if not self.storage_fault:
                try:
                    if self.quest and self.quest['status'] == 'ACTIVE':
                        self.quest['status'] = 'PAUSED'
                    self._save_timers()
                except Exception as storage_error:
                    self.storage_fault = True
                    self.pause_reason = 'storage_fault'
                    self._fault(storage_error, 'timer_save')
            try:
                self.bridge.request('PAUSE', {'reason': self.pause_reason}, revision=self.revision)
            except Exception:
                pass
        return {'state': self.quest['status'] if self.quest else 'IDLE', 'healthy': self.healthy, 'pause_reason': self.pause_reason, 'last_fault': self.last_fault}

    def _save_timers(self):
        with self.store.transaction():
            self.store.execute('UPDATE server_state SET cooldown=?,active_quest=? WHERE id=1', (self.cooldown, self.quest['id'] if self.quest else None))
            if self.quest:
                self.store.execute('UPDATE quests SET remaining=?,active_elapsed=?,status=?,milestones=?,warning=?,reminders=? WHERE id=?', (self.quest['remaining'], self.quest['active_elapsed'], self.quest['status'], self.quest['milestones'], self.quest['warning'], self.quest['reminders'], self.quest['id']))

    def _begin_generation(self, explicit=None, override=False, actor='service', reason=None):
        if self.quest or self._blocked_chest() or not self._ready():
            raise ValueError('A ready community and idle, resolved chest are required')
        cap = self.store.one('SELECT * FROM daily_caps WHERE day=?', (self._day(),))
        if not override and cap and cap['activations'] >= self.config.max_quests_per_day:
            return False
        seed = uuid.uuid4().hex
        recent = [loads(q['objective'])['item'] for q in self.store.all("SELECT objective FROM quests WHERE status IN('COMPLETED','EXPIRED') ORDER BY terminal_at DESC LIMIT 3")]
        choices = rules.candidates(self.config, len(self.eligible), recent, seed, explicit)
        generation_id = uuid.uuid4().hex
        quest_id = uuid.uuid4().hex
        now = time.time()
        proposal = rules.fallback(choices) if explicit is not None else None
        with self.store.transaction():
            self.store.execute('INSERT INTO generations(id,revision,seed,candidates,config,request_status,proposal,created) VALUES(?,1,?,?,?,\'NOT_STARTED\',?,?)', (generation_id, seed, dumps(choices), dumps(self.config.public()), dumps(proposal) if proposal else None, now))
            self.store.execute('INSERT INTO quests(id,generation_id,revision,status,objective,reward,title,flavor,source,config,remaining,created) VALUES(?,?,?,\'GENERATING\',?,?,?,?,?,?,?,?)', (quest_id, generation_id, self.revision, dumps(choices[0]['objective']), dumps(choices[0]['reward']), '', '', 'local', dumps(self.config.public()), self.config.quest_expiry_seconds, now))
            self.store.execute('UPDATE server_state SET active_quest=? WHERE id=1', (quest_id,))
            self.store.audit('generation_created', quest_id, reason=reason, actor=actor, details={'override': override})
        self.quest = self._decode_quest(self.store.one('SELECT * FROM quests WHERE id=?', (quest_id,)))
        if override:
            self.quest['config']['activation_override'] = True
            self.store.execute('UPDATE quests SET config=? WHERE id=?', (dumps(self.quest['config']), quest_id))
        if proposal is not None:
            self._finish_generation(self._generation())
        elif self.config.demo_mode or not self.config.llm_url or not self.config.llm_model:
            self._choose_fallback('provider_disabled')
        elif self.future is not None and not self.future.done():
            self._choose_fallback('previous_request_still_running')
        else:
            with self.store.transaction():
                reserved = self.store.reserve(self._day(), 'calls', self.config.max_ai_calls_per_day)
                if reserved:
                    self.store.execute("UPDATE generations SET request_started=1,request_status='STARTED',model=? WHERE id=?", (self.config.llm_model, generation_id))
            if not reserved:
                self._choose_fallback('daily_call_cap')
            else:
                self.future_generation = generation_id
                self.future = self.executor.submit(llm.generate, self.config, choices, len(self.eligible), self.events.recent(self.config.share_events))
        return True

    def _choose_fallback(self, error):
        generation = self._generation()
        self.store.execute("UPDATE generations SET proposal=?,request_status='FALLBACK',metadata=? WHERE id=?", (dumps(rules.fallback(generation['candidates'])), dumps({'error_category': error}), generation['id']))

    def _finish_generation(self, generation):
        if not generation['proposal'] and generation['elapsed'] >= self.config.generation_deadline_seconds:
            self._choose_fallback('generation_deadline')
            generation = self._generation()
        if not generation['proposal'] and self.future_generation == generation['id'] and self.future is not None and self.future.done():
            try:
                result = self.future.result()
                self.store.execute("UPDATE generations SET proposal=?,request_status='VALID',metadata=?,model=? WHERE id=?", (dumps(result['proposal']), dumps(result['metadata']), result['model'], generation['id']))
            except sqlite3.Error:
                raise
            except Exception as error:
                self._choose_fallback(getattr(error, 'category', 'provider_failure'))
                self._fault(error, 'generation')
            generation = self._generation()
        if not generation['proposal'] or not self._ready():
            return
        proposal = generation['proposal']
        choice = next(c for c in generation['candidates'] if c['candidate_id'] == proposal['candidate_id'])
        override = self.quest['config'].get('activation_override', False)
        # The cap reservation and active intent must commit together: a crash
        # cannot charge again for the same still-generating quest.
        with self.store.transaction():
            if not self.store.reserve(self._day(), 'activations', self.config.max_quests_per_day, override):
                return
            activated = dict(self.quest, objective=choice['objective'], reward=choice['reward'], title=proposal['title'], flavor=proposal['flavor'] if self.config.flavor_enabled else '', source='ai' if generation['request_status'] == 'VALID' else 'local', model=generation['model'], status='ACTIVE')
            self.store.execute("UPDATE quests SET objective=?,reward=?,title=?,flavor=?,source=?,model=?,status='ACTIVE' WHERE id=?", (dumps(activated['objective']), dumps(activated['reward']), activated['title'], activated['flavor'], activated['source'], activated['model'], activated['id']))
            self.store.audit('quest_activated', activated['id'], details={'source': activated['source'], 'override': override})
        self.quest = activated
        self._activate_projection()
        self._save_timers()

    def _projection(self):
        if not self.quest or self.quest['status'] in ('GENERATING', 'REVIEW_REQUIRED'):
            return {}
        q = self.quest
        return {'id': q['id'], 'revision': q['revision'], 'item_code': q['objective']['code'], 'quantity': q['objective']['quantity'], 'reward_code': q['reward']['code'], 'reward_count': q['reward']['count'], 'title': q['title'], 'flavor': q['flavor'], 'objective_text': rules.factual(q, self._chest(), self.snapshot.get('count', 0)), 'remaining_seconds': math.ceil(q['remaining'])}

    def _activate_projection(self):
        self.quest['revision'] = self.revision + 1
        self.store.execute('UPDATE quests SET revision=? WHERE id=?', (self.quest['revision'], self.quest['id']))
        response = self._request('ACTIVATE', {'quest': self._projection()})
        if response['status'] != 'OK':
            raise RuntimeError('Quest activation rejected: ' + response['status'])
        self.quest['revision'] = self.revision
        self.store.execute('UPDATE quests SET revision=? WHERE id=?', (self.revision, self.quest['id']))

    def _status_text(self):
        if self.quest and self.quest['status'] not in ('GENERATING', 'REVIEW_REQUIRED'):
            text = rules.factual(self.quest, self._chest(), self.snapshot.get('count', 0))
        else:
            text = '[The Keeper] ' + ('Preparing the community objective.' if self.quest and self.quest['status'] == 'GENERATING' else 'No active community objective.')
        if self.pause_reason:
            text += ' Service paused: ' + self.pause_reason.replace('_', ' ') + '.'
        return text

    def _publish(self, paused=None, message=None, audience=None):
        pending = self.store.all("SELECT player_uuid,COUNT(*) AS count FROM entitlements WHERE status NOT IN('DELIVERED','VOIDED') GROUP BY player_uuid")
        payload = {'quest': self._projection(), 'paused': int(not self._service_ready() if paused is None else paused), 'pending': [{'uuid': uuid_to_ints(row['player_uuid']), 'count': row['count']} for row in pending if row['player_uuid'] in self.online]}
        if message is not None:
            payload['message'] = message
        if audience is not None:
            payload['audience'] = uuid_to_ints(audience)
        response = self._request('PUBLISH_STATUS', payload)
        if response['status'] != 'OK':
            raise RuntimeError('Status publication rejected: ' + response['status'])

    def _progress(self):
        q = self.quest
        found = self.snapshot.get('count', 0)
        reached = max((level for level in (25, 50, 75) if found * 100 >= q['objective']['quantity'] * level), default=0)
        if reached > q['milestones']:
            q['milestones'] = reached
            self.store.notify(q['id'] + ':milestone:' + str(reached), f"[The Keeper] Offering progress has reached {reached}%. " + self._status_text())
            self._save_timers()
        reminder = int(q['active_elapsed'] // 600)
        if reminder > q['reminders']:
            q['reminders'] = reminder
            self.store.notify(q['id'] + ':reminder:' + str(reminder), self._status_text())
            self._save_timers()
        if q['remaining'] <= 600 and not q['warning']:
            q['warning'] = 1
            self.store.notify(q['id'] + ':deadline_warning', '[The Keeper] Ten minutes or less remain. ' + self._status_text())
            self._save_timers()
        if found >= q['objective']['quantity']:
            self._complete()

    def _terminal(self, status, reason, actor='service'):
        if self.quest is None:
            raise ValueError('No live quest')
        quest_id = self.quest['id']
        with self.store.transaction():
            self.store.execute('UPDATE quests SET status=?,remaining=?,active_elapsed=?,terminal_at=?,terminal_reason=? WHERE id=?', (status, self.quest['remaining'], self.quest['active_elapsed'], time.time(), reason, quest_id))
            self.store.audit('quest_' + status.lower(), quest_id, reason, actor)
            self.store.notify(quest_id + ':' + status, '[The Keeper] Community objective ' + status.lower() + '. Offering Chest contents are unchanged.')
            self.cooldown = float(self.config.cooldown_seconds)
            self.store.execute('UPDATE server_state SET active_quest=NULL,cooldown=? WHERE id=1', (self.cooldown,))
        self.quest = None
        if self.connected:
            self._publish()

    def _collect_evidence(self, operation_id):
        evidence = self.bridge.evidence(operation_id)
        expected = ('evidence_before_snbt', 'evidence_after_snbt')
        if any(not isinstance(evidence.get(key), str) for key in expected):
            raise RuntimeError('Complete typed operation evidence is unavailable')
        if any(len(evidence[key].encode()) > 1048576 for key in expected):
            raise RuntimeError('Operation evidence exceeds supported bound')
        return evidence

    def _dispatch(self, operation):
        self.store.operation_update(operation['id'], 'DISPATCHED')
        request = loads(operation['request'])
        try:
            response = self._request(operation['kind'], request['payload'], revision=request['expected_revision'], operation_id=operation['id'], request_hash=operation['request_hash'])
        except Exception as dispatch_error:
            # Only read an existing receipt, never resend destructive requests.
            try:
                receipt = self._request('READ_RECEIPT', {'operation_id': operation['id']})
                record = receipt.get('payload', {}).get('receipt', receipt.get('payload', {}))
                if record.get('state', record.get('phase')) != 'APPLIED' or record.get('request_hash') != operation['request_hash'] or record.get('operation_id') != operation['id']:
                    raise RuntimeError('No matching complete receipt')
                payload = record.get('result')
                if not isinstance(payload, dict):
                    raise RuntimeError('Receipt result correlation unavailable')
                response = {'status': 'APPLIED', 'operation_id': operation['id'], 'payload': payload, 'revision': self.revision}
                self.store.operation_update(operation['id'], 'DISPATCHED', receipt=record)
            except Exception:
                with self.store.transaction():
                    self._review(operation, 'destructive response lost; no matching verified receipt')
                self._fault(dispatch_error, 'destructive_response')
                self.connected = False
                self.healthy = False
                self.pause_reason = 'transport_or_protocol_fault'
                return None
        if response['status'] in SAFE_RESULTS:
            with self.store.transaction():
                self.store.operation_update(operation['id'], 'ABORTED', result=response)
                resolution = loads(operation['resolution']) or {}
                if resolution.get('compensation_for'):
                    original = self.store.one('SELECT * FROM operations WHERE id=?', (resolution['compensation_for'],))
                    self._review(original, 'corrective operation rejected without mutation; original remains unresolved')
                elif operation['kind'] == 'PAY':
                    status = 'WAITING_OFFLINE' if response['status'] == 'OFFLINE' else 'WAITING_SPACE' if response['status'] == 'NO_SPACE' else 'PENDING'
                    self.store.execute('UPDATE entitlements SET status=?,wait_reason=?,next_attempt=?,updated=? WHERE id=?', (status, response['status'], time.time() + self.config.reward_retry_seconds, time.time(), operation['entitlement_id']))
                elif operation['kind'] == 'COMPLETE':
                    self.store.execute("UPDATE quests SET status='ACTIVE' WHERE id=? AND status='COMPLETING'", (operation['quest_id'],))
                if operation['kind'] == 'COMPLETE' and response['status'] == 'EVIDENCE_LIMIT':
                    reason = 'Completion evidence exceeds the safe limit; remove oversized chest contents or repair evidence support, then explicitly resume'
                    self.store.execute('UPDATE server_state SET operator_paused=1 WHERE id=1')
                    self.store.execute("UPDATE quests SET status='PAUSED' WHERE id=? AND status='ACTIVE'", (operation['quest_id'],))
                    self.store.audit('completion_evidence_limit', operation['id'], reason=reason)
            if operation['kind'] == 'COMPLETE' and response['status'] == 'EVIDENCE_LIMIT':
                self.healthy = False
                if self.quest and self.quest['id'] == operation['quest_id'] and self.quest['status'] in ('ACTIVE', 'PAUSED', 'COMPLETING'):
                    self.quest['status'] = 'PAUSED'
                self.pause_reason = 'operator_pause'
                self._fault(RuntimeError(reason), 'completion_evidence')
                if self.connected:
                    paused = self._request('PAUSE', {'reason': reason})
                    if paused['status'] != 'OK':
                        raise RuntimeError('Evidence-limit pause rejected: ' + paused['status'])
            return response
        if response['status'] != 'APPLIED':
            with self.store.transaction():
                self._review(operation, 'destructive result is not a known nonmutating or applied status')
            return None
        try:
            self._validate_applied(operation, response)
            payload = response['payload']
            if isinstance(payload.get('evidence_before_snbt'), str) and isinstance(payload.get('evidence_after_snbt'), str):
                evidence = {'before_snbt': payload['evidence_before_snbt'], 'after_snbt': payload['evidence_after_snbt']}
            else:
                evidence = self._collect_evidence(operation['id'])
            self.store.operation_update(operation['id'], 'APPLIED', result=response, evidence=evidence)
            token = self.bridge.checkpoint()
            checkpoint = {'acknowledged': True, 'token': token, 'time': time.time(), 'epoch': self.epoch, 'session': self.session}
            self.store.operation_update(operation['id'], 'APPLIED', checkpoint=checkpoint)
        except Exception as error:
            with self.store.transaction():
                # Save any correlated result even when checkpoint/evidence failed.
                self.store.operation_update(operation['id'], 'APPLIED', result=response)
                self._review(operation, 'applied operation evidence or checkpoint uncertain')
            self._fault(error, 'destructive_checkpoint')
            return None
        return response

    def _validate_applied(self, operation, response):
        result = response['payload']
        request = loads(operation['request'])['payload']
        if response.get('operation_id', operation['id']) != operation['id']:
            raise ValueError('Applied result operation identity mismatch')
        if operation['kind'] == 'COMPLETE':
            recipients = result.get('recipients')
            quest = self._decode_quest(self.store.one('SELECT * FROM quests WHERE id=?', (operation['quest_id'],)))
            bound = quest['config'].get('max_recipients', self.config.max_recipients) if quest else self.config.max_recipients
            if quest is None or request.get('quest_id') != quest['id'] or request.get('item_code') != quest['objective']['code']:
                raise ValueError('Completion intent differs from the immutable objective')
            if type(result.get('consumed')) is not int or result['consumed'] != request['quantity'] or not isinstance(recipients, list) or not 1 <= len(recipients) <= bound:
                raise ValueError('Completion acknowledgement is inconsistent')
            identities = [ints_to_uuid(r['uuid']) for r in recipients]
            if len(set(identities)) != len(identities) or (quest and set(identities) & set(quest['config'].get('excluded_uuids', []))):
                raise ValueError('Completion recipient snapshot has duplicate or excluded UUIDs')
        elif operation['kind'] == 'PAY':
            if type(result.get('inserted')) is not int or result['inserted'] != request['count'] or ints_to_uuid(result['player_uuid']) != ints_to_uuid(request['player_uuid']) or type(result.get('slot')) is not int or not 0 <= result['slot'] < 27:
                raise ValueError('Delivery acknowledgement is inconsistent')
            if operation['entitlement_id']:
                entitlement = self.store.one('SELECT * FROM entitlements WHERE id=?', (operation['entitlement_id'],))
                if entitlement is None or request.get('entitlement_id') != entitlement['id'] or ints_to_uuid(request['player_uuid']) != entitlement['player_uuid'] or request.get('reward_code') != loads(entitlement['reward'])['code']:
                    raise ValueError('Delivery intent differs from the immutable entitlement')

    def _complete(self):
        q = self.quest
        if q['remaining'] <= 0:
            self._terminal('EXPIRED', 'expiry observed before dispatch')
            return
        request = {'action': 'COMPLETE', 'expected_revision': self.revision, 'payload': {'quest_id': q['id'], 'item_code': q['objective']['code'], 'quantity': q['objective']['quantity']}}
        operation = self.store.prepare('COMPLETE', 'chest', self.revision, self.session, self.epoch, request, quest_id=q['id'])
        q['status'] = 'COMPLETING'
        self._save_timers()
        response = self._dispatch(operation)
        if response is None:
            return
        if response['status'] in SAFE_RESULTS:
            q['status'] = 'PAUSED' if response['status'] == 'EVIDENCE_LIMIT' else 'ACTIVE'
            self._save_timers()
            return
        try:
            self._commit_complete(operation, response)
        except Exception as error:
            with self.store.transaction():
                self._review(operation, 'verified mutation could not commit its immutable entitlements')
            self._fault(error, 'completion_commit')

    def _commit_complete(self, operation, response):
        self._validate_applied(operation, response)
        resolution = loads(operation['resolution']) or {}
        original = None
        if resolution.get('compensation_for'):
            original = self.store.one('SELECT * FROM operations WHERE id=?', (resolution['compensation_for'],))
            if original is None:
                raise ValueError('Corrective operation lacks its original audit record')
            plan = self._frozen_plan(original)
            if {ints_to_uuid(r['uuid']) for r in response['payload']['recipients']} != {ints_to_uuid(r['uuid']) for r in plan['recipients']}:
                raise ValueError('Correction substituted the original frozen recipients')
        q = self._decode_quest(self.store.one('SELECT * FROM quests WHERE id=?', (operation['quest_id'],)))
        recipients = response['payload']['recipients']
        now = time.time()
        with self.store.transaction():
            frozen = self.store.all('SELECT player_uuid,snapshot FROM recipients WHERE quest_id=?', (q['id'],))
            identities = {ints_to_uuid(recipient['uuid']) for recipient in recipients}
            if frozen and {row['player_uuid'] for row in frozen} != identities:
                raise ValueError('Cannot replace immutable completion recipients')
            rewards = self.store.all('SELECT player_uuid,reward FROM entitlements WHERE quest_id=?', (q['id'],))
            if rewards and ({row['player_uuid'] for row in rewards} != identities or any(loads(row['reward']) != q['reward'] for row in rewards)):
                raise ValueError('Cannot replace immutable reward entitlements')
            for recipient in recipients:
                player = ints_to_uuid(recipient['uuid'])
                self.store.execute('INSERT OR IGNORE INTO recipients(quest_id,player_uuid,snapshot) VALUES(?,?,?)', (q['id'], player, dumps(recipient)))
                self.store.execute("INSERT OR IGNORE INTO entitlements(id,quest_id,player_uuid,reward,status,created,updated) VALUES(?,?,?,?, 'PENDING',?,?)", (uuid.uuid4().hex, q['id'], player, dumps(q['reward']), now, now))
            self.store.execute("UPDATE quests SET status='COMPLETED',terminal_at=?,terminal_reason='verified completion',recipients_count=?,total_issued=? WHERE id=?", (now, len(recipients), len(recipients) * q['reward']['count'], q['id']))
            self.store.operation_update(operation['id'], 'COMMITTED', result=response)
            if original:
                checkpoint = loads(self.store.one('SELECT checkpoint FROM operations WHERE id=?', (operation['id'],))['checkpoint'])
                self.store.operation_update(original['id'], 'COMMITTED', resolution=loads(original['resolution']) or resolution, checkpoint=checkpoint)
            self._ack_checkpoint(operation['id'])
            self.store.notify(q['id'] + ':completed', f"[The Keeper] Community objective completed! {len(recipients)} eligible players each receive {q['reward']['count']} {rules.item_label(q['reward']['item'])} in their Ender Chest; offline/full deliveries remain pending.", kind='completion')
            if self.quest is None or self.quest['id'] == q['id']:
                self.cooldown = float(self.config.cooldown_seconds)
                self.store.execute('UPDATE server_state SET active_quest=NULL,cooldown=? WHERE id=1', (self.cooldown,))
            self.store.audit('completion_committed', operation['id'], details={'recipients': len(recipients), 'consumed': response['payload']['consumed'], 'compensation_for': resolution.get('compensation_for'), 'total_issued': len(recipients) * q['reward']['count']})
        if self.quest and self.quest['id'] == q['id']:
            self.quest = None

    def _claims(self):
        response = self._request('READ_CLAIMS')
        if response['status'] != 'OK':
            return
        payload = response['payload']
        for claim in payload.get('claims', []):
            player = ints_to_uuid(claim['uuid'])
            oldest = self.store.one("SELECT id,status FROM entitlements WHERE player_uuid=? AND status NOT IN('DELIVERED','VOIDED') ORDER BY created,id LIMIT 1", (player,))
            if oldest and oldest['status'] in PENDING:
                self.store.execute('UPDATE entitlements SET next_attempt=0 WHERE id=?', (oldest['id'],))
        acknowledged = self._request('ACK_CLAIMS', {'cursor': payload.get('cursor', 0)})
        if acknowledged['status'] != 'OK':
            raise RuntimeError('Claim acknowledgement rejected')

    def _payouts(self):
        now = time.time()
        candidates = self.store.all("SELECT e.* FROM entitlements e WHERE e.status IN('PENDING','WAITING_OFFLINE','WAITING_SPACE') AND e.next_attempt<=? AND NOT EXISTS(SELECT 1 FROM entitlements older WHERE older.player_uuid=e.player_uuid AND older.status NOT IN('DELIVERED','VOIDED') AND (older.created<e.created OR (older.created=e.created AND older.id<e.id))) ORDER BY e.created,e.id", (now,))
        attempts = 0
        for entitlement in candidates:
            if not self.connected or attempts >= self.config.max_payout_batch:
                break
            player = entitlement['player_uuid']
            if self.store.one("SELECT id FROM operations WHERE target=? AND status NOT IN('COMMITTED','ABORTED')", ('player:' + player,)):
                continue
            if player not in self.online:
                self.store.execute("UPDATE entitlements SET status='WAITING_OFFLINE',wait_reason='offline',next_attempt=?,updated=? WHERE id=?", (now + self.config.reward_retry_seconds, now, entitlement['id']))
                continue
            attempts += 1
            reward = loads(entitlement['reward'])
            request = {'action': 'PAY', 'expected_revision': self.revision, 'payload': {'player_uuid': uuid_to_ints(player), 'entitlement_id': entitlement['id'], 'reward_code': reward['code'], 'count': reward['count']}}
            operation = self.store.prepare('PAY', 'player:' + player, self.revision, self.session, self.epoch, request, quest_id=entitlement['quest_id'], entitlement_id=entitlement['id'])
            self.store.execute("UPDATE entitlements SET status='DELIVERING',attempts=attempts+1,updated=? WHERE id=?", (now, entitlement['id']))
            response = self._dispatch(operation)
            if response is None:
                continue
            if response['status'] in SAFE_RESULTS:
                status = 'WAITING_OFFLINE' if response['status'] == 'OFFLINE' else 'WAITING_SPACE' if response['status'] == 'NO_SPACE' else 'PENDING'
                self.store.execute('UPDATE entitlements SET status=?,wait_reason=?,next_attempt=?,updated=? WHERE id=?', (status, response['status'], now + self.config.reward_retry_seconds, now, entitlement['id']))
                if status == 'WAITING_SPACE':
                    previous = self.store.one("SELECT created FROM notifications WHERE audience=? AND kind='full' ORDER BY created DESC LIMIT 1", (player,))
                    if not previous or now - previous['created'] >= 600:
                        self.store.notify('full:' + player + ':' + str(int(now // 600)), '[The Keeper] Your reward is pending: free one Ender Chest slot, then use /trigger keeper_claim.', player, 'full')
                continue
            with self.store.transaction():
                self.store.operation_update(operation['id'], 'COMMITTED', result=response)
                self._ack_checkpoint(operation['id'])
                self.store.execute("UPDATE entitlements SET status='DELIVERED',wait_reason=NULL,updated=? WHERE id=?", (time.time(), entitlement['id']))
                self.store.notify(entitlement['id'] + ':delivered', f"[The Keeper] Delivered {reward['count']} {rules.item_label(reward['item'])} to your Ender Chest.", player, 'delivered')
                self.store.audit('delivery_committed', operation['id'])

    def _notifications(self):
        for notification in self.store.all("SELECT * FROM notifications WHERE status='PENDING' AND next_attempt<=? ORDER BY created,id LIMIT 8", (time.time(),)):
            if notification['audience'] and notification['audience'] not in self.online:
                continue
            try:
                self._publish(message=loads(notification['content'])['message'], audience=notification['audience'])
            except Exception:
                self.store.execute('UPDATE notifications SET attempts=attempts+1,next_attempt=? WHERE id=?', (time.time() + 30, notification['id']))
                continue
            self.store.execute("UPDATE notifications SET status='SENT',sent=?,attempts=attempts+1 WHERE id=?", (time.time(), notification['id']))

    @staticmethod
    def _reason(args):
        reason = args.get('reason')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise ValueError('A nonempty audit reason of at most 500 characters is required')
        return reason.strip()

    def _idle_chest(self):
        if self.quest or self.store.one("SELECT id FROM operations WHERE status NOT IN('COMMITTED','ABORTED')"):
            raise ValueError('Chest registration requires idle state with no unresolved operations')
        if not self.connected or self.storage_fault:
            raise ValueError('Verified connection and healthy storage required')

    def admin(self, action, args, actor='local'):
        if not self.started:
            raise RuntimeError('Engine not started')
        if not isinstance(args, dict):
            raise ValueError('Administrative arguments must be an object')
        if action == 'doctor':
            pending = self.store.one("SELECT COUNT(*) AS count,MIN(created) AS oldest FROM entitlements WHERE status NOT IN('DELIVERED','VOIDED')")
            fault = self.store.one("SELECT details FROM audit_events WHERE action='service_fault' ORDER BY sequence DESC LIMIT 1")
            durable_fault = loads(fault['details']) if fault else None
            return {'expected_version': '26.3', 'running_version': getattr(self.bridge, 'server_version', None), 'artifact_verified': getattr(self.bridge, 'artifact_verified', False), 'protocol': 1, 'pack_format': [121, 0], 'installation_id': self.store.server['installation_id'], 'connected': self.connected, 'epoch': self.epoch, 'session': self.session, 'revision': self.revision, 'db_integrity': self.store.integrity(), 'chest': self._chest(), 'chest_valid': bool(self.snapshot.get('chest_valid')), 'eligible_players': len(self.eligible), 'state': self.quest['status'] if self.quest else 'IDLE', 'pause_reason': self.pause_reason, 'last_fault': self.last_fault or durable_fault, 'operator_paused': bool(self.store.server['operator_paused']), 'cooldown_seconds': self.cooldown, 'pending': pending, 'review_count': self.store.one("SELECT COUNT(*) AS count FROM operations WHERE status='REVIEW_REQUIRED'")['count'], 'last_checkpoint': loads(self.store.server['last_checkpoint']), 'deferred_config': self.deferred_config is not None, 'event_source': self.log_source.status}
        if action in ('register_chest', 'unregister_chest'):
            self._idle_chest()
            reason = self._reason(args) if action == 'unregister_chest' else args.get('reason', 'explicit chest registration')
            payload = {}
            if action == 'register_chest':
                for coordinate in ('x', 'y', 'z'):
                    value = args.get(coordinate)
                    if type(value) is not int:
                        raise ValueError('Chest coordinates must be integers')
                    if coordinate == 'y' and not -64 <= value <= 319 or coordinate != 'y' and not -29999984 <= value <= 29999984:
                        raise ValueError('Chest coordinates outside supported Overworld bounds')
                    payload[coordinate] = value
            kind = 'REGISTER_CHEST' if action == 'register_chest' else 'UNREGISTER_CHEST'
            request = {'action': kind, 'expected_revision': self.revision, 'payload': payload}
            operation = self.store.prepare(kind, 'chest', self.revision, self.session, self.epoch, request)
            self.store.operation_update(operation['id'], 'DISPATCHED')
            try:
                response = self._request(kind, payload)
                if response['status'] != 'OK':
                    self.store.operation_update(operation['id'], 'ABORTED', result=response)
                    return response
                self.store.operation_update(operation['id'], 'APPLIED', result=response)
                token = self.bridge.checkpoint()
                checkpoint = {'acknowledged': True, 'token': token, 'time': time.time(), 'epoch': self.epoch, 'session': self.session}
                with self.store.transaction():
                    self.store.execute('DELETE FROM chests')
                    if action == 'register_chest':
                        chest = response['payload'].get('chest', response['payload'])
                        self.store.execute("INSERT INTO chests(id,installation_id,dimension,x,y,z,forceload_owned) VALUES(1,?,'minecraft:overworld',?,?,?,?)", (self.store.server['installation_id'], chest['x'], chest['y'], chest['z'], int(chest['forceload_owned'])))
                    self.store.operation_update(operation['id'], 'COMMITTED', result=response, checkpoint=checkpoint)
                    self.store.execute('UPDATE server_state SET last_checkpoint=? WHERE id=1', (dumps(checkpoint),))
                    self.store.audit(action, operation['id'], reason, actor)
            except Exception:
                with self.store.transaction():
                    self._review(operation, 'registration or checkpoint uncertain; compare server/local registration')
                raise RuntimeError('Chest registration outcome requires review') from None
            # Registration and its checkpoint are committed. A later read-only
            # refresh belongs to the normal poll path, not the mutation outcome.
            self.pause_reason = ''
            return {'status': 'OK', 'chest': self._chest(), 'operation_id': operation['id']}
        if action == 'pause':
            reason = self._reason(args)
            with self.store.transaction():
                self.store.execute('UPDATE server_state SET operator_paused=1 WHERE id=1')
                self.store.audit('pause', reason=reason, actor=actor)
            self.healthy = False
            self.pause_reason = 'operator_pause'
            self._save_timers()
            if self.connected:
                self._request('PAUSE', {'reason': reason})
            return {'status': 'PAUSED', 'reason': reason}
        if action == 'resume':
            if self.storage_fault:
                raise ValueError('Storage fault requires repair and restart')
            self._quarantine('operator resume reconciliation')
            self._connect()
            if self._blocked_chest():
                raise ValueError('Resolve chest review before resume')
            self.store.execute('UPDATE server_state SET operator_paused=0 WHERE id=1')
            self.pause_reason = ''
            self._poll()
            self.healthy = self._ready()
            self.last_tick = time.monotonic()
            if self.quest and self.quest['status'] in ('ACTIVE', 'PAUSED') and self.healthy:
                self._activate_projection()
            self._publish(paused=not self._service_ready())
            self.store.audit('resume', actor=actor)
            return {'status': 'OK', 'healthy': self.healthy, 'pause_reason': self.pause_reason}
        if action in ('start', 'start_override'):
            item = args.get('item', args.get('item_id'))
            quantity = args.get('quantity')
            rules.validate_objective(self.config, item, quantity)
            if action == 'start_override':
                reason = self._reason(args)
                if self.quest or not self._ready():
                    raise ValueError('Override still requires ready idle state')
                revision = self.store.server['revision']
                token = self.store.confirmation('start_override', None, revision, {'item': item, 'quantity': quantity, 'reason': reason}, actor)
                return {'status': 'CONFIRMATION_REQUIRED', 'token': token, 'revision': revision, 'preview': {'item': item, 'quantity': quantity, 'bypass': 'activation_daily_cap_only'}}
            started = self._begin_generation((item, quantity), actor=actor, reason=args.get('reason', 'explicit local start'))
            return {'status': 'OK' if started else 'DAILY_CAP', 'quest_id': self.quest['id'] if self.quest else None}
        if action == 'cancel':
            reason = self._reason(args)
            quest_id = args.get('quest_id', args.get('id'))
            if not self.quest or self.quest['id'] != quest_id:
                raise ValueError('Requested quest is not live')
            unresolved = self.store.one("SELECT id FROM operations WHERE kind='COMPLETE' AND quest_id=? AND status NOT IN('COMMITTED','ABORTED')", (quest_id,))
            if self.quest['status'] not in ('ACTIVE', 'PAUSED', 'GENERATING') or unresolved:
                raise ValueError('Cannot cancel a dispatched or unresolved completion')
            self._terminal('CANCELLED', reason, actor)
            return {'status': 'CANCELLED', 'quest_id': quest_id}
        if action == 'history':
            quest_id = args.get('quest_id')
            rows = self.store.all('SELECT * FROM quests WHERE id=?', (quest_id,)) if quest_id else self.store.all('SELECT * FROM quests ORDER BY created DESC LIMIT 100')
            result = []
            for row in rows:
                row = self._decode_quest(row)
                row['operations'] = self.store.all('SELECT id,kind,status,created,review_reason FROM operations WHERE quest_id=? ORDER BY sequence', (row['id'],))
                row['recipients'] = self.store.all('SELECT player_uuid,snapshot FROM recipients WHERE quest_id=?', (row['id'],))
                for recipient in row['recipients']:
                    recipient['snapshot'] = loads(recipient['snapshot'])
                result.append(row)
            return {'quests': result}
        if action == 'rewards':
            player = str(uuid.UUID(args.get('player_uuid', args.get('uuid', ''))))
            rows = self.store.all('SELECT * FROM entitlements WHERE player_uuid=? ORDER BY created,id', (player,))
            for row in rows:
                row['reward'] = loads(row['reward'])
            return {'player_uuid': player, 'entitlements': rows}
        if action == 'review':
            operation = self._operation(args)
            result = dict(operation)
            for key in ('request', 'result', 'receipt', 'evidence', 'checkpoint', 'resolution'):
                result[key] = loads(result[key])
            if self.connected:
                try:
                    result['current_receipt'] = self._request('READ_RECEIPT', {'operation_id': operation['id']})
                    result['current_snapshot'] = self._request('SNAPSHOT')['payload']
                except Exception:
                    result['observation_status'] = 'unavailable'
            result['risk'] = 'Inventory observations/receipts are evidence, not proof of subsequent player movement or consistent restore. No automatic replay or whole-inventory restoration.'
            return result
        if action == 'quarantine':
            operation = self._operation(args)
            reason = self._reason(args)
            if operation['kind'] not in ('COMPLETE', 'PAY') or operation['status'] != 'COMMITTED':
                raise ValueError('Quarantine requires a committed completion or payout')
            details = {'reason': reason, 'kind': operation['kind'], 'target': operation['target'], 'effect': 'Metadata-only review and operator pause; no inventory writes or automatic replay'}
            token = self.store.confirmation('quarantine', operation['id'], operation['revision'], details, actor)
            self.store.audit('quarantine_preview', operation['id'], reason, actor, details)
            return {'status': 'CONFIRMATION_REQUIRED', 'token': token, 'operation_id': operation['id'], 'revision': operation['revision'], 'preview': details}
        if action == 'resolve':
            operation = self._operation(args)
            resolution = args.get('resolution', args.get('mode'))
            reason = self._reason(args)
            if operation['status'] != 'REVIEW_REQUIRED':
                raise ValueError('Operation is not in review')
            if resolution not in ('commit', 'abort', 'compensate', 'void'):
                raise ValueError('Unknown resolution')
            details = {'resolution': resolution, 'reason': reason}
            if resolution == 'commit':
                self._resolution_result(operation)
            elif resolution == 'compensate':
                if operation['kind'] not in ('COMPLETE', 'PAY'):
                    raise ValueError('Registration compensation is not an inventory delta')
                correction = args.get('correction')
                if not isinstance(correction, dict):
                    raise ValueError('Compensation requires a typed correction object')
                if operation['kind'] == 'PAY':
                    if set(correction) != {'kind', 'count'} or correction['kind'] != 'PAY' or type(correction['count']) is not int or not 1 <= correction['count'] <= 64:
                        raise ValueError('Payout correction must be {kind:PAY,count:1..64}, using immutable recipient/item')
                else:
                    if self.quest and self.quest['id'] != operation['quest_id']:
                        raise ValueError('Cancel the unrelated live quest before completion compensation')
                    plan = self._frozen_plan(operation)
                    if set(correction) != {'kind', 'quantity'} or correction['kind'] != 'COMPLETE' or type(correction['quantity']) is not int or not 1 <= correction['quantity'] <= plan['quantity']:
                        raise ValueError('Chest correction requires a positive consumption delta no greater than the original frozen quantity')
                details['correction'] = correction
                details['risk'] = 'Operator accepts possible duplicate issuance or item loss; new operation never overwrites historical inventory.'
            token = self.store.confirmation('resolve', operation['id'], operation['revision'], details, actor)
            self.store.audit('resolution_preview', operation['id'], reason, actor, details)
            return {'status': 'CONFIRMATION_REQUIRED', 'token': token, 'operation_id': operation['id'], 'revision': operation['revision'], 'preview': details}
        if action == 'confirm':
            return self._confirm(args.get('token'), actor)
        if action == 'reload_config':
            new = self.config.reload()
            # Transport/state changes require an orderly process restart, not a live switch.
            restart_fields = ('db_path', 'socket_path', 'rcon_host', 'rcon_port', 'rcon_password', 'game_host', 'game_port', 'version', 'server_jar')
            if any(getattr(new, field, None) != getattr(self.config, field, None) for field in restart_fields):
                raise ValueError('State/transport/version changes require restart')
            if self.quest or self._blocked_chest():
                self.deferred_config = new
                self.store.audit('config_reload_deferred', actor=actor)
                return {'status': 'DEFERRED', 'deferred': list(new.public()), 'reason': 'live quest retains all configuration snapshots'}
            self._apply_config(new)
            self.store.audit('config_reload_applied', actor=actor)
            return {'status': 'OK', 'config': new.public(), 'deferred': []}
        raise ValueError('Unknown administrative action')

    def _apply_config(self, config):
        self.connected = False
        self.healthy = False
        self.config = config
        if self.log_source.path != config.log_path or self.log_source.allow_chat != config.share_chat:
            self.log_source = ServerLog(config.log_path, allow_chat=config.share_chat)
        self.bridge.config = config
        with self.store.transaction():
            self.store.execute('UPDATE server_state SET config=?,config_revision=config_revision+1 WHERE id=1', (dumps(config.public()),))
        try:
            self._connect()
        except Exception as error:
            self.connected = False
            self.pause_reason = 'config_handshake_fault'
            self._fault(error, 'reload_config')
            raise

    def _operation(self, args):
        operation_id = args.get('operation_id', args.get('id'))
        if not isinstance(operation_id, str) or len(operation_id) != 32 or any(c not in '0123456789abcdef' for c in operation_id):
            raise ValueError('Invalid operation ID')
        operation = self.store.one('SELECT * FROM operations WHERE id=?', (operation_id,))
        if operation is None:
            raise ValueError('Unknown operation')
        return operation

    def _resolution_result(self, operation):
        result = loads(operation['result'])
        if not result and operation['kind'] in ('COMPLETE', 'PAY') and self.connected:
            receipt = self._request('READ_RECEIPT', {'operation_id': operation['id']})
            record = receipt.get('payload', {}).get('receipt', {})
            if record.get('state', record.get('phase')) == 'APPLIED' and record.get('request_hash') == operation['request_hash'] and record.get('operation_id') == operation['id'] and isinstance(record.get('result'), dict):
                result = {'status': 'APPLIED', 'operation_id': operation['id'], 'revision': self.revision, 'payload': record['result']}
                self._validate_applied(operation, result)
                evidence = self._collect_evidence(operation['id'])
                self.store.operation_update(operation['id'], 'REVIEW_REQUIRED', result=result, receipt=record, evidence=evidence)
        accepted = ('APPLIED',) if operation['kind'] in ('COMPLETE', 'PAY') else ('OK',)
        if not result or result.get('status') not in accepted:
            raise ValueError('Commit requires a complete correlated applied result and actual frozen recipients')
        if operation['kind'] in ('COMPLETE', 'PAY'):
            if result.get('operation_id') != operation['id']:
                raise ValueError('Applied result does not correlate with the reviewed intent')
            self._validate_applied(operation, result)
            current = self.store.one('SELECT evidence FROM operations WHERE id=?', (operation['id'],))
            if not current['evidence']:
                evidence = self._collect_evidence(operation['id'])
                self.store.operation_update(operation['id'], 'REVIEW_REQUIRED', evidence=evidence)
        return result

    def _ack_checkpoint(self, operation_id):
        row = self.store.one('SELECT checkpoint FROM operations WHERE id=?', (operation_id,))
        if row and row['checkpoint']:
            self.store.execute('UPDATE server_state SET last_checkpoint=? WHERE id=1', (row['checkpoint'],))

    def _resolve_world(self, operation, decision):
        if not self.connected or self.storage_fault:
            raise ValueError('Resolution requires verified connection and healthy storage')
        if operation['kind'] in ('COMPLETE', 'PAY'):
            response = self._request('RESOLVE_RECEIPT', {'operation_id': operation['id'], 'decision': decision})
            if response['status'] != 'OK':
                raise ValueError('Server receipt resolution rejected: ' + response['status'])
        token = self.bridge.checkpoint()
        current = self.store.one('SELECT status FROM operations WHERE id=?', (operation['id'],))
        self.store.operation_update(operation['id'], current['status'], checkpoint={'acknowledged': True, 'token': token, 'time': time.time(), 'epoch': self.epoch, 'session': self.session, 'operator_decision': decision})

    def _frozen_plan(self, operation):
        receipt = loads(operation['receipt']) or {}
        plan = receipt.get('plan')
        if plan is None and self.connected:
            response = self._request('READ_RECEIPT', {'operation_id': operation['id']})
            receipt = response.get('payload', {}).get('receipt', {})
            if response['status'] != 'OK' or receipt.get('request_hash') != operation['request_hash'] or receipt.get('operation_id') != operation['id']:
                raise ValueError('Original frozen receipt is unavailable or does not match the intent')
            plan = receipt.get('plan')
            self.store.operation_update(operation['id'], operation['status'], receipt=receipt)
        if receipt.get('operation_id') != operation['id'] or receipt.get('request_hash') != operation['request_hash']:
            raise ValueError('Frozen plan does not correlate with the original durable intent')
        request = loads(operation['request'])['payload']
        quest = self._decode_quest(self.store.one('SELECT * FROM quests WHERE id=?', (operation['quest_id'],)))
        bound = quest['config'].get('max_recipients', self.config.max_recipients) if quest else self.config.max_recipients
        if not isinstance(plan, dict) or plan.get('quest_id') != request.get('quest_id') or plan.get('item_code') != request.get('item_code') or plan.get('quantity') != request.get('quantity') or not isinstance(plan.get('recipients'), list) or not plan['recipients']:
            raise ValueError('Compensation requires the exact original frozen objective and recipient plan')
        identities = [ints_to_uuid(r['uuid']) for r in plan['recipients']]
        if len(set(identities)) != len(identities) or len(identities) > bound or (quest and set(identities) & set(quest['config'].get('excluded_uuids', []))):
            raise ValueError('Frozen recipient plan is inconsistent')
        return plan

    def _confirm(self, token, actor):
        if not isinstance(token, str):
            raise ValueError('Confirmation token required')
        with self.store.transaction():
            confirmation = self.store.one('SELECT * FROM confirmations WHERE token=?', (token,))
            if confirmation is None or confirmation['used'] or confirmation['expires'] < time.time():
                raise ValueError('Confirmation token is missing, used or expired')
            if confirmation['actor'] != actor:
                raise ValueError('Confirmation actor differs from preview actor')
            if confirmation['action'] in ('resolve', 'quarantine'):
                operation = self.store.one('SELECT * FROM operations WHERE id=?', (confirmation['target'],))
                current = operation['revision'] if operation else None
                expected = 'COMMITTED' if confirmation['action'] == 'quarantine' else 'REVIEW_REQUIRED'
                if operation is None or operation['status'] != expected:
                    raise ValueError('Operation changed since preview')
                if confirmation['action'] == 'quarantine' and operation['kind'] not in ('COMPLETE', 'PAY'):
                    raise ValueError('Quarantine requires a committed completion or payout')
            else:
                current = self.store.server['revision']
            if current != confirmation['revision']:
                raise ValueError('Confirmation revision is stale; preview again')
            self.store.execute('UPDATE confirmations SET used=1 WHERE token=?', (token,))
            if confirmation['action'] == 'quarantine':
                details = loads(confirmation['args'])
                self._review(operation, details['reason'], actor)
                self.store.execute('UPDATE server_state SET operator_paused=1 WHERE id=1')
                if self.quest and self.quest['status'] == 'ACTIVE':
                    self.store.execute("UPDATE quests SET status='PAUSED' WHERE id=?", (self.quest['id'],))
                self.store.audit('quarantine_confirmed', operation['id'], details['reason'], actor, details)
        details = loads(confirmation['args'])
        if confirmation['action'] == 'quarantine':
            self.healthy = False
            self.pause_reason = 'operator_pause'
            if self.quest:
                self.quest = self._decode_quest(self.store.one('SELECT * FROM quests WHERE id=?', (self.quest['id'],)))
            world_paused = False
            if self.connected:
                try:
                    response = self._request('PAUSE', {'reason': details['reason']})
                    if response['status'] != 'OK':
                        raise RuntimeError('Quarantine pause rejected: ' + response['status'])
                    world_paused = True
                except Exception as error:
                    self.connected = False
                    self._fault(error, 'quarantine_pause')
            return {'status': 'REVIEW_REQUIRED', 'operation_id': operation['id'], 'reason': details['reason'], 'operator_paused': True, 'world_paused': world_paused}
        if confirmation['action'] == 'start_override':
            self._begin_generation((details['item'], details['quantity']), override=True, actor=actor, reason=details['reason'])
            return {'status': 'OK', 'quest_id': self.quest['id']}
        resolution = details['resolution']
        reason = details['reason']
        if resolution == 'compensate':
            return self._compensate(operation, details, actor)
        details = {**(loads(operation['resolution']) or {}), **details}
        result = self._resolution_result(operation) if resolution == 'commit' else None
        decision = {'commit': 'applied', 'abort': 'not_applied', 'void': 'voided'}[resolution]
        self._resolve_world(operation, decision)
        original_id = details.get('compensation_for')
        original = self.store.one('SELECT * FROM operations WHERE id=?', (original_id,)) if original_id else None
        if original_id and original is None:
            raise ValueError('Correction lost its original durable intent')
        live_id = self.quest['id'] if self.quest else None
        try:
            # Receipt decision/checkpoint can precede SQLite, but every local
            # outcome, linked intent, entitlement and audit commits together.
            with self.store.transaction():
                if resolution == 'commit':
                    if operation['kind'] == 'COMPLETE':
                        self._commit_complete(operation, result)
                    elif operation['kind'] == 'PAY':
                        self.store.execute("UPDATE entitlements SET status='DELIVERED',wait_reason=NULL,updated=? WHERE id=?", (time.time(), operation['entitlement_id']))
                    else:
                        chest = result['payload'].get('chest', result['payload'])
                        self.store.execute('DELETE FROM chests')
                        if operation['kind'] == 'REGISTER_CHEST':
                            self.store.execute("INSERT INTO chests(id,installation_id,dimension,x,y,z,forceload_owned) VALUES(1,?,'minecraft:overworld',?,?,?,?)", (self.store.server['installation_id'], chest['x'], chest['y'], chest['z'], int(chest['forceload_owned'])))
                elif operation['kind'] == 'PAY':
                    self.store.execute('UPDATE entitlements SET status=?,wait_reason=NULL,terminal_reason=?,updated=?,next_attempt=0 WHERE id=?', ('VOIDED' if resolution == 'void' else 'PENDING', reason if resolution == 'void' else None, time.time(), operation['entitlement_id']))
                elif operation['kind'] == 'COMPLETE':
                    if resolution == 'void':
                        self.store.execute("UPDATE quests SET status='CANCELLED',terminal_at=?,terminal_reason=? WHERE id=? AND status IN('COMPLETING','REVIEW_REQUIRED')", (time.time(), reason, operation['quest_id']))
                        self.store.execute("UPDATE entitlements SET status='VOIDED',terminal_reason=?,updated=? WHERE quest_id=? AND status IN('PENDING','WAITING_OFFLINE','WAITING_SPACE')", (reason, time.time(), operation['quest_id']))
                        if live_id == operation['quest_id']:
                            self.cooldown = float(self.config.cooldown_seconds)
                            self.store.execute('UPDATE server_state SET active_quest=NULL,cooldown=? WHERE id=1', (self.cooldown,))
                    elif live_id == operation['quest_id']:
                        self.store.execute("UPDATE quests SET status='ACTIVE' WHERE id=?", (operation['quest_id'],))
                self.store.operation_update(operation['id'], 'COMMITTED' if resolution == 'commit' else 'ABORTED', resolution=details, revision=operation['revision'] + 1)
                if original:
                    if resolution == 'abort':
                        # A rejected correction says nothing about its original
                        # uncertain mutation. It must not unlock automatic pay.
                        self._review(original, 'correction aborted; original outcome still requires review')
                    else:
                        checkpoint = loads(self.store.one('SELECT checkpoint FROM operations WHERE id=?', (operation['id'],))['checkpoint'])
                        self.store.operation_update(original['id'], 'COMMITTED' if resolution == 'commit' else 'ABORTED', checkpoint=checkpoint, resolution={**(loads(original['resolution']) or {}), 'corrective_resolution': resolution})
                self._ack_checkpoint(operation['id'])
                self.store.audit('resolution_' + resolution, operation['id'], reason, actor)
        except Exception:
            if live_id:
                self.quest = self._decode_quest(self.store.one('SELECT * FROM quests WHERE id=?', (live_id,)))
            raise
        if live_id:
            row = self.store.one('SELECT * FROM quests WHERE id=?', (live_id,))
            self.quest = self._decode_quest(row) if row['status'] in ('GENERATING', 'ACTIVE', 'PAUSED', 'COMPLETING', 'REVIEW_REQUIRED') else None
        return {'status': 'OK', 'operation_id': operation['id'], 'resolution': resolution}

    def _compensate(self, operation, details, actor):
        if not self.connected or self.storage_fault:
            raise ValueError('Compensation requires verified service and healthy storage')
        if operation['kind'] == 'COMPLETE':
            if self.quest and self.quest['id'] != operation['quest_id']:
                raise ValueError('Cancel the unrelated live quest before completion compensation')
            self._frozen_plan(operation)
        payload = dict(loads(operation['request'])['payload'])
        payload['count' if operation['kind'] == 'PAY' else 'quantity'] = details['correction']['count' if operation['kind'] == 'PAY' else 'quantity']
        if operation['kind'] == 'COMPLETE':
            payload['review_of'] = operation['id']
        try:
            # Keep the original in review until preparatory world decisions
            # finish. Their revision changes must precede the immutable new
            # request/hash. A crash here leaves the original blocking replay.
            self._resolve_world(operation, 'voided')
            self._publish(paused=False)
        except Exception as error:
            with self.store.transaction():
                self._review(operation, 'corrective world preparation interrupted; original remains unresolved')
            self._fault(error, 'compensation_prepare')
            return {'status': 'REVIEW_REQUIRED', 'operation_id': operation['id']}
        request = {'action': operation['kind'], 'expected_revision': self.revision, 'payload': payload}
        with self.store.transaction():
            self.store.operation_update(operation['id'], 'ABORTED', resolution=details, revision=operation['revision'] + 1)
            corrective = self.store.prepare(operation['kind'], operation['target'], self.revision, self.session, self.epoch, request, operation['quest_id'], operation['entitlement_id'])
            self.store.operation_update(corrective['id'], 'PREPARED', resolution={**details, 'compensation_for': operation['id']})
            self.store.operation_update(operation['id'], 'ABORTED', resolution={**details, 'superseded_by': corrective['id']}, revision=operation['revision'] + 1)
            if operation['kind'] == 'PAY':
                self.store.execute("UPDATE entitlements SET status='DELIVERING' WHERE id=?", (operation['entitlement_id'],))
            else:
                self.store.execute("UPDATE quests SET status='COMPLETING' WHERE id=? AND status IN('ACTIVE','PAUSED','COMPLETING','REVIEW_REQUIRED')", (operation['quest_id'],))
            self.store.audit('compensation_dispatch', corrective['id'], details['reason'], actor, {'original_operation': operation['id'], 'correction': details['correction'], 'risk': details['risk']})
        corrective = self.store.one('SELECT * FROM operations WHERE id=?', (corrective['id'],))
        try:
            response = self._dispatch(corrective)
        except Exception as error:
            with self.store.transaction():
                self._review(corrective, 'corrective preparation/dispatch interrupted; never replay')
            self._fault(error, 'compensation')
            return {'status': 'REVIEW_REQUIRED', 'operation_id': corrective['id']}
        if response is None:
            return {'status': 'REVIEW_REQUIRED', 'operation_id': corrective['id']}
        if response['status'] in SAFE_RESULTS:
            if operation['kind'] == 'COMPLETE' and self.quest and self.quest['id'] == operation['quest_id']:
                self.quest = self._decode_quest(self.store.one('SELECT * FROM quests WHERE id=?', (operation['quest_id'],)))
            return {'status': response['status'], 'operation_id': corrective['id']}
        try:
            with self.store.transaction():
                if operation['kind'] == 'COMPLETE':
                    self._commit_complete(corrective, response)
                self.store.operation_update(corrective['id'], 'COMMITTED', resolution={**details, 'compensation_for': operation['id']})
                self._ack_checkpoint(corrective['id'])
                checkpoint = loads(self.store.one('SELECT checkpoint FROM operations WHERE id=?', (corrective['id'],))['checkpoint'])
                self.store.operation_update(operation['id'], 'COMMITTED', resolution={**details, 'superseded_by': corrective['id']}, checkpoint=checkpoint)
                if operation['kind'] == 'PAY':
                    self.store.execute("UPDATE entitlements SET status='DELIVERED',wait_reason=NULL,updated=? WHERE id=?", (time.time(), operation['entitlement_id']))
                self.store.audit('compensation_committed', corrective['id'], details['reason'], actor)
        except Exception as error:
            with self.store.transaction():
                self._review(corrective, 'applied correction could not commit; never replay')
            self._fault(error, 'compensation_commit')
            return {'status': 'REVIEW_REQUIRED', 'operation_id': corrective['id']}
        return {'status': 'OK', 'operation_id': corrective['id'], 'original_operation_id': operation['id']}

    def shutdown(self):
        if not self.started:
            self.executor.shutdown(wait=False, cancel_futures=True)
            return
        self.healthy = False
        try:
            self._save_timers()
            if self.connected:
                self._request('PAUSE', {'reason': 'director orderly shutdown'})
                token = self.bridge.checkpoint()
                self.store.execute('UPDATE server_state SET last_checkpoint=? WHERE id=1', (dumps({'acknowledged': True, 'token': token, 'time': time.time(), 'epoch': self.epoch, 'session': self.session, 'shutdown': True}),))
        finally:
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.bridge.close()
            self.store.close()
            self.started = False
