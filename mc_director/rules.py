"""Pure economy, model-boundary and privacy rules."""
from __future__ import annotations

from collections import deque
import hashlib
import ipaddress
import json
import math
import random
import re
import unicodedata
import uuid


_UUID_LITERAL = re.compile(r'(?<!\w)[0-9a-f]{8}(?:-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{24})(?!\w)', re.IGNORECASE)
_IP_LITERAL = re.compile(
    r'(?<![\w:])(?:[0-9a-f]{0,4}:){2,}(?:(?:[0-9]{1,3}\.){3}[0-9]{1,3}|[0-9a-f]{0,4})(?:%[a-z0-9_.~-]+)?(?![\w:])'
    r'|(?<!\w)(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?!\w)', re.IGNORECASE)


def tier(points):
    return 1 if points <= 24 else 2 if points <= 80 else 3


def quantity_for(entry, participants):
    if type(participants) is not int or participants < 1:
        raise ValueError('Generation requires at least one eligible participant')
    return max(entry['min'], min(entry['max'], math.ceil(entry['base'] * math.sqrt(participants))))


def validate_objective(config, item, quantity):
    entry = config.catalog.get(item)
    if entry is None or not entry.get('enabled', True):
        raise ValueError('Objective item is not in the enabled catalog')
    if type(quantity) is not int or not entry['min'] <= quantity <= entry['max']:
        raise ValueError('Objective quantity is outside configured bounds')
    return {'item': item, 'code': entry['code'], 'quantity': quantity, 'points': quantity * entry['weight'], 'tier': tier(quantity * entry['weight'])}


def candidates(config, participants, recent=(), seed=None, explicit=None):
    rng = random.Random(seed)
    enabled = [item for item, entry in config.catalog.items() if entry.get('enabled', True)]
    if not enabled:
        raise ValueError('No enabled objectives')
    if explicit is not None:
        objectives = [validate_objective(config, explicit[0], explicit[1])]
    else:
        alternatives = [item for item in enabled if item not in recent]
        choices = alternatives or enabled
        rng.shuffle(choices)
        objectives = [validate_objective(config, item, quantity_for(config.catalog[item], participants)) for item in choices[:5]]
    result = []
    for index, objective in enumerate(objectives, 1):
        reward = dict(rng.choice(config.rewards[objective['tier']]))
        result.append({'candidate_id': 'candidate-' + str(index), 'objective': objective, 'reward': reward})
    return result


def parse_proposal(text, choices):
    if not isinstance(text, str):
        raise ValueError('Provider content is not text')
    text = text.strip()
    if text.startswith('```'):
        match = re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```', text, flags=re.DOTALL)
        if match is None:
            raise ValueError('Invalid fenced JSON')
        text = match.group(1).strip()
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate model key')
            result[key] = value
        return result
    value = json.loads(text, object_pairs_hook=unique_pairs)
    if type(value) is not dict or set(value) != {'candidate_id', 'title', 'flavor'}:
        raise ValueError('Model schema requires exactly candidate_id, title and flavor')
    if not all(type(value[key]) is str for key in value):
        raise ValueError('Model fields must be strings')
    if value['candidate_id'] not in {candidate['candidate_id'] for candidate in choices}:
        raise ValueError('Model selected an unknown candidate')
    for key, maximum in (('title', 60), ('flavor', 220)):
        raw = value[key]
        if any(unicodedata.category(char).startswith('C') for char in raw):
            raise ValueError('Model prose contains control characters')
        value[key] = raw.strip()
        if not value[key] or len(value[key]) > maximum:
            raise ValueError('Model prose is empty or exceeds its limit')
    return value


def fallback(choices):
    return {'candidate_id': choices[0]['candidate_id'], 'title': 'The community offering', 'flavor': 'The Keeper invites the community to lend a hand.'}


def item_label(item):
    return item.removeprefix('minecraft:').replace('_', ' ')


def factual(quest, chest, found=0):
    objective = quest['objective']
    reward = quest['reward']
    remaining = max(0, math.ceil(quest['remaining']))
    minutes = math.ceil(remaining / 60)
    coordinates = 'unregistered' if chest is None else f"Overworld ({chest['x']}, {chest['y']}, {chest['z']})"
    return (f"[The Keeper] {quest['title']}. Bring {objective['quantity']} {item_label(objective['item'])} "
            f"to the Offering Chest at {coordinates}. Progress: {found}/{objective['quantity']}. "
            f"Each eligible survival/adventure player online at completion receives {reward['count']} "
            f"{item_label(reward['item'])} in their Ender Chest. Time remaining: {minutes} minutes.")


class EventContext:
    """Bounded, ephemeral summaries redact known identities, not arbitrary secrets."""
    def __init__(self, installation_id):
        self.salt = installation_id
        self.events = deque(maxlen=40)

    def pseudonym(self, identity):
        return 'Player-' + hashlib.sha256((self.salt + ':' + identity).encode()).hexdigest()[:8]

    def record(self, kind, identity=None):
        if kind not in ('join', 'leave', 'death', 'advancement'):
            raise ValueError('Event kind is not allowlisted')
        label = self.pseudonym(identity) if identity is not None else 'A player'
        suffix = {'join': 'joined the community', 'leave': 'left the community', 'death': 'died', 'advancement': 'earned an advancement'}[kind]
        self.events.append(label + ' ' + suffix)

    def record_chat(self, identity, text, *, player_names=()):
        if not isinstance(text, str) or not text.strip() or len(text) > 256 or not text.isprintable():
            raise ValueError('Chat must be nonblank printable text of at most 256 characters')
        if not isinstance(identity, str) or not identity:
            raise ValueError('Chat requires a known sender UUID')
        try:
            identity = str(uuid.UUID(identity))
        except ValueError:
            raise ValueError('Chat requires a known sender UUID') from None

        # A single printable replacement keeps redaction within the input bound.
        text = _UUID_LITERAL.sub('…', text)
        def redact_ip(match):
            try:
                ipaddress.ip_address(match.group())
            except ValueError:
                return match.group()
            return '…'
        text = _IP_LITERAL.sub(redact_ip, text)
        names = sorted({name for name in player_names if isinstance(name, str) and name}, key=len, reverse=True)
        if names:
            text = re.sub(r'(?<!\w)(?:' + '|'.join(re.escape(name) for name in names) + r')(?!\w)', '…', text, flags=re.IGNORECASE)
        self.events.append(self.pseudonym(identity) + ' untrusted chat: ' + json.dumps(text, ensure_ascii=False))

    def recent(self, share=False):
        return list(self.events)[-20:] if share else []
