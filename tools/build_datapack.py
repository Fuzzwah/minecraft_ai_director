#!/usr/bin/env python3
"""Reproduce the vanilla 26.3 Keeper datapack; no runtime dependency."""
from pathlib import Path
import json

ITEMS = ('iron_ingot', 'copper_ingot', 'gold_ingot', 'coal', 'redstone', 'lapis_lazuli', 'oak_log', 'bread', 'carrot', 'cooked_beef', 'emerald', 'diamond', 'ancient_debris')

def files():
    out = {}
    payload_keys = {
        'hello': ('config',), 'heartbeat': (), 'snapshot': ('offset','limit'),
        'register_chest': ('x','y','z'), 'unregister_chest': (),
        'activate': ('quest',),
        'publish_status': ('quest','paused','pending','message','audience','title','sound'),
        'complete': ('quest_id','item_code','quantity','preflight_id','review_of'),
        'pay': ('player_uuid','entitlement_id','reward_code','count'),
        'read_receipt': ('operation_id','offset','limit'),
        'read_evidence': ('operation_id','kind','offset','limit'),
        'read_claims': (), 'ack_claims': ('cursor',), 'pause': ('reason',),
        'resolve_receipt': ('operation_id','decision'),
        'checkpoint': ('token',),
    }
    def fn(name, lines):
        if name.startswith('action/') and name[7:] in payload_keys:
            lines = [
                'execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request',
                'data modify storage keeper:work shape set from storage keeper:bridge request.payload',
                *[f'data remove storage keeper:work shape.{key}' for key in payload_keys[name[7:]]],
                'data modify storage keeper:work empty set value {}',
                'execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty',
                'execute if score #different keeper matches 1 run return run function keeper:error/invalid_request',
            ] + lines
        out[f'data/keeper/function/{name}.mcfunction'] = '\n'.join(lines) + '\n'
    def jsonfile(name, value):
        out[name] = json.dumps(value, indent=2) + '\n'
    def err(status):
        return f'return run function keeper:error/{status.lower()}'
    def guard(condition, status='INVALID_REQUEST'):
        return f'execute {condition} run {err(status)}'
    def stringcheck(path, maximum, storage='keeper:bridge', minimum=0):
        return [guard(f'unless data storage {storage} {path}'),
                'data modify storage keeper:work text set value ""',
                f'data modify storage keeper:work text set string storage {storage} {path}',
                f'execute store result score #length keeper run data get storage {storage} {path}',
                guard(f'unless score #length keeper matches {minimum}..{maximum}'),
                *equal('keeper:work','text',storage,path,'INVALID_REQUEST')]
    def intcheck(path, minimum, maximum, target='#n', storage='keeper:bridge'):
        return [f'execute store result score {target} keeper run data get storage {storage} {path} 1',
                f'execute store result storage keeper:work integer int 1 run scoreboard players get {target} keeper',
                'data modify storage keeper:work compare set from storage keeper:work integer',
                f'execute store success score #different keeper run data modify storage keeper:work compare set from storage {storage} {path}',
                guard('if score #different keeper matches 1'),
                guard(f'unless data storage {storage} {path}'),
                guard(f'unless score {target} keeper matches {minimum}..{maximum}')]
    def hexcheck(path, length=32):
        return [*stringcheck(path,length,minimum=length),
                'data modify storage keeper:work hex set value ""',
                f'data modify storage keeper:work hex set from storage keeper:bridge {path}',
                f'execute store result score #length keeper run data get storage keeper:work hex',
                guard(f'unless score #length keeper matches {length}'),
                'scoreboard players set #index keeper 0', 'scoreboard players set #bad keeper 0',
                f'scoreboard players set #hexlength keeper {length}',
                'function keeper:validate/hex', guard('if score #bad keeper matches 1..')]
    def equal(a_storage, a_path, b_storage, b_path, status):
        return [guard(f'unless data storage {a_storage} {a_path}', status),
                guard(f'unless data storage {b_storage} {b_path}', status),
                f'data modify storage keeper:work compare set from storage {a_storage} {a_path}',
                f'execute store success score #different keeper run data modify storage keeper:work compare set from storage {b_storage} {b_path}',
                guard('if score #different keeper matches 1', status)]
    def literal(path, value, storage='keeper:bridge', status='INVALID_REQUEST'):
        return [f'data modify storage keeper:work literal set value {value}',
                *equal(storage,path,'keeper:work','literal',status)]
    def shape(path, keys, storage='keeper:bridge', status='INVALID_REQUEST'):
        return [guard(f'unless data storage {storage} {path}',status),
                f'data modify storage keeper:work shape set from storage {storage} {path}',
                *[f'data remove storage keeper:work shape.{key}' for key in keys],
                'data modify storage keeper:work empty set value {}',
                'execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty',
                guard('if score #different keeper matches 1',status)]
    def compound_list(path, storage='keeper:bridge', status='INVALID_REQUEST'):
        return [guard(f'unless data storage {storage} {path}',status),
                f'data modify storage keeper:work list_probe set from storage {storage} {path}',
                'execute store success score #list keeper run data modify storage keeper:work list_probe append value {}',
                guard('unless score #list keeper matches 1',status)]
    def paging():
        return ['scoreboard players set #offset keeper 0','scoreboard players set #limit keeper 16',
                'execute if data storage keeper:bridge request.payload.offset store success score #valid keeper run function keeper:validate/offset',
                'execute if data storage keeper:bridge request.payload.offset unless score #valid keeper matches 1 run return fail',
                'execute if data storage keeper:bridge request.payload.limit store success score #valid keeper run function keeper:validate/limit',
                'execute if data storage keeper:bridge request.payload.limit unless score #valid keeper matches 1 run return fail']
    def revision():
        return intcheck('request.expected_revision', 0, 2147483646, '#expected') + [
            'execute store result score #revision keeper run data get storage keeper:runtime revision',
            guard('unless score #expected keeper = #revision keeper', 'STALE_REVISION')]
    def ready():
        return [guard('unless data storage keeper:runtime {enabled:1}', 'PAUSED'),
                'execute store result score #heartbeat keeper run data get storage keeper:runtime heartbeat',
                'execute store result score #timeout keeper run data get storage keeper:config heartbeat_ticks',
                guard('if score #heartbeat keeper >= #timeout keeper','PAUSED')]
    def inc_revision():
        return ['execute store result score #revision keeper run data get storage keeper:runtime revision',
                'scoreboard players add #revision keeper 1',
                'execute store result storage keeper:runtime revision int 1 run scoreboard players get #revision keeper']
    statuses = ('INVALID_REQUEST','UNKNOWN_ACTION','PROTOCOL_MISMATCH','INSTALLATION_MISMATCH','SESSION_MISMATCH','STALE_REVISION','STALE_PREFLIGHT','PAUSED','CHEST_INVALID','ALREADY_REGISTERED','NOT_REGISTERED','CHEST_NOT_EMPTY','FORCELOAD_FAILED','ACTIVE_QUEST','INSUFFICIENT_ITEMS','NO_RECIPIENTS','RECIPIENT_LIMIT','OFFLINE','NO_SPACE','IDEMPOTENCY_CONFLICT','REVIEW_REQUIRED','EVIDENCE_LIMIT','NOT_FOUND','UNSUPPORTED_ITEM','CONFIG_INVALID')
    for status in statuses:
        fn('error/' + status.lower(), [f'data modify storage keeper:bridge response.status set value "{status}"', 'return fail'])
    jsonfile('pack.mcmeta', {'pack':{'description':'The Keeper — vanilla Java 26.3 AI director bridge', 'pack_format':121, 'min_format':[121,0], 'max_format':[121,0]}})
    for tag in ('load','tick'):
        jsonfile(f'data/minecraft/tags/function/{tag}.json', {'values':[f'keeper:{tag}']})
    fn('load', ['scoreboard objectives add keeper dummy',
        *[f'scoreboard objectives add keeper_{t} trigger' for t in ('quest','status','claim','help')],
        'scoreboard players set #loaded keeper 1',
        'execute unless data storage keeper:config configured run data modify storage keeper:config configured set value 0',
        'execute unless data storage keeper:runtime revision run data modify storage keeper:runtime revision set value 0',
        'execute unless data storage keeper:runtime epoch run data modify storage keeper:runtime epoch set value 0',
        'execute store result score #epoch keeper run data get storage keeper:runtime epoch',
        'scoreboard players add #epoch keeper 1',
        'execute store result storage keeper:runtime epoch int 1 run scoreboard players get #epoch keeper',
        'data modify storage keeper:runtime enabled set value 0',
        'data modify storage keeper:runtime verified set value 0',
        'data modify storage keeper:runtime heartbeat set value 0',
        'execute unless data storage keeper:runtime quest run data modify storage keeper:runtime quest set value {}',
        'execute unless data storage keeper:runtime pending run data modify storage keeper:runtime pending set value []',
        'execute unless data storage keeper:runtime claims run data modify storage keeper:runtime claims set value []',
        'execute unless data storage keeper:runtime claim_cursor run data modify storage keeper:runtime claim_cursor set value 0',
        'execute unless data storage keeper:journal receipts run data modify storage keeper:journal receipts set value {}',
        'data modify storage keeper:work hexchars set value ["0","1","2","3","4","5","6","7","8","9","a","b","c","d","e","f"]',
        'bossbar add keeper:quest {"text":"The Keeper: paused"}', 'bossbar set keeper:quest visible false'])
    fn('validate/hex', ['execute store result storage keeper:work start int 1 run scoreboard players get #index keeper',
        'scoreboard players operation #end keeper = #index keeper', 'scoreboard players add #end keeper 1',
        'execute store result storage keeper:work end int 1 run scoreboard players get #end keeper',
        'function keeper:validate/hex_char with storage keeper:work',
        'execute unless score #char keeper matches 1 run scoreboard players set #bad keeper 1',
        'scoreboard players add #index keeper 1',
        'execute if score #index keeper < #hexlength keeper run function keeper:validate/hex'])
    fn('validate/hex_char', ['data modify storage keeper:work char set value ""', '$data modify storage keeper:work char set string storage keeper:work hex $(start) $(end)',
        'scoreboard players set #char keeper 0',
        *[f'execute if data storage keeper:work {{char:"{c}"}} run scoreboard players set #char keeper 1' for c in '0123456789abcdef']])
    fn('validate/uuid', ['execute store result score #length keeper run data get storage keeper:work uuid', guard('unless score #length keeper matches 4'),
        *sum((intcheck(f'uuid[{i}]',-2147483648,2147483647,f'#u{i}','keeper:work') for i in range(4)), []),
        *[f'execute store result storage keeper:work u{i} int 1 run scoreboard players get #u{i} keeper' for i in range(4)],
        'function keeper:validate/uuid_array with storage keeper:work',
        *equal('keeper:work','uuid','keeper:work','uuid_expected','INVALID_REQUEST'),'return 1'])
    fn('validate/uuid_array', ['$data modify storage keeper:work uuid_expected set value [I;$(u0),$(u1),$(u2),$(u3)]'])
    actions = ('HELLO','HEARTBEAT','SNAPSHOT','REGISTER_CHEST','UNREGISTER_CHEST','ACTIVATE','PUBLISH_STATUS','COMPLETE','PAY','READ_RECEIPT','READ_EVIDENCE','READ_CLAIMS','ACK_CLAIMS','PAUSE','RESOLVE_RECEIPT','CHECKPOINT')
    fn('bridge/dispatch', ['data modify storage keeper:work initialized set value 0',
        'execute store success storage keeper:work initialized int 1 run scoreboard players get #loaded keeper',
        'execute unless data storage keeper:work {initialized:1} run function keeper:load',
        'data modify storage keeper:bridge response set value {protocol:1,request_id:"",session_id:"",status:"INVALID_REQUEST",revision:0,payload:{}}',
        'data modify storage keeper:bridge response.request_id set from storage keeper:bridge request.request_id',
        'data modify storage keeper:bridge response.session_id set from storage keeper:bridge request.session_id',
        'data modify storage keeper:bridge response.operation_id set from storage keeper:bridge request.operation_id',
        'data modify storage keeper:bridge response.revision set from storage keeper:runtime revision',
        *literal('request.protocol','1',status='PROTOCOL_MISMATCH'),
        *stringcheck('request.action',32,minimum=1),
        *intcheck('request.expected_revision',0,2147483646,'#expected'),
        *hexcheck('request.installation_id'), *hexcheck('request.session_id'), *hexcheck('request.request_id'),
        'data modify storage keeper:work envelope set from storage keeper:bridge request',
        *[f'data remove storage keeper:work envelope.{key}' for key in ('protocol','installation_id','session_id','request_id','action','expected_revision','payload','operation_id','request_hash')],
        'data modify storage keeper:work empty set value {}',
        'execute store success score #different keeper run data modify storage keeper:work envelope set from storage keeper:work empty',
        guard('if score #different keeper matches 1'),
        'execute if data storage keeper:bridge request{action:"HELLO"} run return run function keeper:action/hello',
        guard('unless data storage keeper:runtime {verified:1}','SESSION_MISMATCH'),
        *equal('keeper:config','installation_id','keeper:bridge','request.installation_id','INSTALLATION_MISMATCH'),
        *equal('keeper:runtime','session_id','keeper:bridge','request.session_id','SESSION_MISMATCH'),
        *[f'execute if data storage keeper:bridge request{{action:"{a}"}} run return run function keeper:action/{a.lower()}' for a in actions if a != 'HELLO'],
        err('UNKNOWN_ACTION')])
    fn('bridge/ok', ['data modify storage keeper:bridge response.status set value "OK"',
        'data modify storage keeper:bridge response.revision set from storage keeper:runtime revision', 'return 1'])
    fn('bridge/join_string', ['$data modify storage keeper:bridge $(path) set value "' + ''.join(f'$(c{i})' for i in range(32)) + '"'])
    # Configuration accepts only the immutable item-code table, bounded numeric knobs and typed exclusions.
    fn('validate/config_hash',hexcheck('request.payload.config.config_hash',64)+['return 1'])
    cfg = [*shape('request.payload.config',('protocol','build','version','max_recipients','heartbeat_ticks','items','catalog','excluded','config_hash'),status='CONFIG_INVALID'),
        'execute if data storage keeper:bridge request.payload.config.config_hash store success score #valid keeper run function keeper:validate/config_hash',
        'execute if data storage keeper:bridge request.payload.config.config_hash unless score #valid keeper matches 1 run return run function keeper:error/config_invalid',
        'data modify storage keeper:work config set from storage keeper:bridge request.payload.config',
        *literal('config.protocol','1','keeper:work','CONFIG_INVALID'),
        *literal('config.build','1','keeper:work','CONFIG_INVALID'),
        *literal('config.version','"26.3"','keeper:work','CONFIG_INVALID'),
        *intcheck('config.max_recipients',1,128,'#max','keeper:work'),
        *intcheck('config.heartbeat_ticks',20,72000,'#timeout','keeper:work'),
        *compound_list('config.items','keeper:work','CONFIG_INVALID'),
        'execute store result score #length keeper run data get storage keeper:work config.items', guard('unless score #length keeper matches 13','CONFIG_INVALID')]
    for code,item in enumerate(ITEMS):
        cfg += literal(f'config.items[{code}]',f'{{code:{code},item:"minecraft:{item}"}}','keeper:work','CONFIG_INVALID')
    cfg += [*compound_list('config.catalog','keeper:work','CONFIG_INVALID'),
        'execute store result score #length keeper run data get storage keeper:work config.catalog', guard('unless score #length keeper matches 10','CONFIG_INVALID')]
    for code,item in enumerate(ITEMS[:10]):
        cfg += [*shape(f'config.catalog[{code}]',('code','item','min','max','enabled'),'keeper:work','CONFIG_INVALID'),
                *literal(f'config.catalog[{code}].code',str(code),'keeper:work','CONFIG_INVALID'),
                *literal(f'config.catalog[{code}].item',f'"minecraft:{item}"','keeper:work','CONFIG_INVALID'),
                *intcheck(f'config.catalog[{code}].min',1,1728,'#minimum','keeper:work'),
                *intcheck(f'config.catalog[{code}].max',1,1728,'#maximum','keeper:work'),
                guard('if score #minimum keeper > #maximum keeper','CONFIG_INVALID'),
                *intcheck(f'config.catalog[{code}].enabled',0,1,'#n','keeper:work')]
    cfg += [*compound_list('config.excluded','keeper:work','CONFIG_INVALID'),
        'execute store result score #length keeper run data get storage keeper:work config.excluded', guard('unless score #length keeper matches 0..128','CONFIG_INVALID'),
        'data modify storage keeper:work exclusions set from storage keeper:work config.excluded',
        'scoreboard players set #bad keeper 0',
        'execute if data storage keeper:work exclusions[0] run function keeper:validate/exclusions',
        guard('if score #bad keeper matches 1..','CONFIG_INVALID'), 'return 1']
    fn('validate/config',cfg)
    fn('validate/exclusion', [*shape('exclusions[0]',('uuid',),'keeper:work','CONFIG_INVALID'),
        'data modify storage keeper:work uuid set from storage keeper:work exclusions[0].uuid',
        'return run function keeper:validate/uuid'])
    fn('validate/exclusions', [
        'execute store success score #valid keeper run function keeper:validate/exclusion',
        'execute unless score #valid keeper matches 1 run scoreboard players set #bad keeper 1',
        'data remove storage keeper:work exclusions[0]',
        'execute if data storage keeper:work exclusions[0] run function keeper:validate/exclusions'])
    fn('action/hello', ['execute store success score #valid keeper run function keeper:validate/config', guard('unless score #valid keeper matches 1','CONFIG_INVALID'),
        'execute if data storage keeper:config {configured:1} store success score #valid keeper run function keeper:validate/installation',
        'execute if data storage keeper:config {configured:1} unless score #valid keeper matches 1 run return fail',
        'data modify storage keeper:work old_chest set value {}',
        'data modify storage keeper:work old_chest set from storage keeper:config chest',
        'data modify storage keeper:config protocol set value 1', 'data modify storage keeper:config build set value 1', 'data modify storage keeper:config version set value "26.3"',
        'data modify storage keeper:config installation_id set from storage keeper:bridge request.installation_id',
        *[f'data modify storage keeper:config {k} set from storage keeper:work config.{k}' for k in ('items','catalog','excluded','max_recipients','heartbeat_ticks')],
        'function keeper:players/build_exclusions',
        'data modify storage keeper:config configured set value 1',
        'data modify storage keeper:runtime session_id set from storage keeper:bridge request.session_id',
        'data modify storage keeper:runtime verified set value 1', 'data modify storage keeper:runtime enabled set value 0', 'data modify storage keeper:runtime heartbeat set value 0',
        'data modify storage keeper:bridge response.payload set value {version:"26.3",pack_format:[121,0],build:1,registered:0,chest:{}}',
        'data modify storage keeper:bridge response.payload.checkpoint_token set value ""',
        'data modify storage keeper:bridge response.payload.checkpoint_token set from storage keeper:config checkpoint_token',
        *[f'data modify storage keeper:bridge response.payload.{k} set from storage keeper:{s} {k}' for k,s in [('epoch','runtime'),('installation_id','config'),('revision','runtime'),('quest','runtime'),('enabled','runtime')]],
        'execute if data storage keeper:config chest.x run data modify storage keeper:bridge response.payload.registered set value 1',
        'data modify storage keeper:bridge response.payload.chest set from storage keeper:config chest', 'return run function keeper:bridge/ok'])
    fn('validate/installation', equal('keeper:config','installation_id','keeper:bridge','request.installation_id','INSTALLATION_MISMATCH') + ['return 1'])
    fn('action/heartbeat', ['data modify storage keeper:runtime heartbeat set value 0', 'data modify storage keeper:bridge response.payload.heartbeat set value 0', 'data modify storage keeper:bridge response.payload.epoch set from storage keeper:runtime epoch','return run function keeper:bridge/ok'])
    fn('players/snapshot', ['tag @a remove keeper_eligible','data modify storage keeper:work players set value []','data modify storage keeper:work recipients set value []','execute as @a run function keeper:players/one'])
    fn('players/one', ['data modify storage keeper:work player set value {eligible:0}', 'data modify storage keeper:work player.uuid set from entity @s UUID',
        'execute if entity @s[gamemode=survival] run data modify storage keeper:work player.eligible set value 1',
        'execute if entity @s[gamemode=adventure] run data modify storage keeper:work player.eligible set value 1',
        *[f'data modify storage keeper:work u{i} set from entity @s UUID[{i}]' for i in range(4)],
        'function keeper:players/excluded with storage keeper:work',
        'execute if data storage keeper:work player{eligible:1} run tag @s add keeper_eligible',
        'execute if data storage keeper:work player{eligible:1} run function keeper:players/recipient',
        'data modify storage keeper:work players append from storage keeper:work player'])
    fn('players/recipient', ['data modify storage keeper:work recipient set value {}','data modify storage keeper:work recipient.uuid set from entity @s UUID','data modify storage keeper:work recipients append from storage keeper:work recipient'])
    # Map keys contain only validated/native signed integers, never user strings.
    fn('players/build_exclusions',['data modify storage keeper:config exclusion_map set value {}',
        'data modify storage keeper:work exclusions set from storage keeper:config excluded',
        'execute if data storage keeper:work exclusions[0] run function keeper:players/map_exclusion'])
    fn('players/map_exclusion',[
        *[f'data modify storage keeper:work u{i} set from storage keeper:work exclusions[0].uuid[{i}]' for i in range(4)],
        'function keeper:players/map_key with storage keeper:work',
        'data remove storage keeper:work exclusions[0]',
        'execute if data storage keeper:work exclusions[0] run function keeper:players/map_exclusion'])
    fn('players/map_key',['$data modify storage keeper:config exclusion_map."$(u0),$(u1),$(u2),$(u3)" set value 1'])
    fn('players/excluded',['$execute if data storage keeper:config exclusion_map."$(u0),$(u1),$(u2),$(u3)" run data modify storage keeper:work player.eligible set value 0'])
    # Chest checks execute in the Overworld at fixed integer coordinates; all six neighboring positions are checked.
    chest = ['scoreboard players set #chest keeper 0', '$execute in minecraft:overworld if loaded $(x) $(y) $(z) if block $(x) $(y) $(z) minecraft:chest[type=single] run scoreboard players set #chest keeper 1',
        '$execute in minecraft:overworld if data block $(x) $(y) $(z) LootTable run scoreboard players set #chest keeper 0',
        '$execute in minecraft:overworld positioned $(x) $(y) $(z) run function keeper:chest/neighbors']
    fn('chest/check',chest)
    fn('chest/neighbors', [f'execute if block {p} {block} run scoreboard players set #chest keeper 0' for p in ('~1 ~ ~','~-1 ~ ~','~ ~1 ~','~ ~-1 ~','~ ~ ~1','~ ~ ~-1') for block in ('minecraft:hopper','minecraft:dropper','minecraft:dispenser','minecraft:chest','minecraft:trapped_chest')] + ['execute if entity @e[type=minecraft:hopper_minecart,distance=..2] run scoreboard players set #chest keeper 0'])
    fn('chest/read',['$data modify storage keeper:work before set from block $(x) $(y) $(z) Items'])
    fn('chest/registered', ['scoreboard players set #chest keeper 0', guard('unless data storage keeper:config chest.x','NOT_REGISTERED'),
        'execute in minecraft:overworld run function keeper:chest/check with storage keeper:config chest', guard('unless score #chest keeper matches 1','CHEST_INVALID'), 'return 1'])
    # Freeze at most 128 actual players, including ineligible players; overflow is explicit.
    fn('snapshot/freeze', ['data remove storage keeper:bridge snapshot',
        'function keeper:players/snapshot',
        'execute store result score #total keeper run data get storage keeper:work players',
        guard('if score #total keeper matches 129..','EVIDENCE_LIMIT'),
        'scoreboard players set #chest keeper 0','scoreboard players set #found keeper 0',
        'execute if data storage keeper:config chest.x in minecraft:overworld run function keeper:chest/check with storage keeper:config chest',
        'execute if score #chest keeper matches 1 if data storage keeper:runtime quest.item_code run function keeper:chest/count',
        'data modify storage keeper:bridge snapshot set value {registered:0,chest_valid:0,count:0}',
        'data modify storage keeper:bridge snapshot.players set from storage keeper:work players',
        *[f'data modify storage keeper:bridge snapshot.{k} set from storage keeper:runtime {k}' for k in ('epoch','revision','quest','enabled','heartbeat')],
        'execute if data storage keeper:config chest.x run data modify storage keeper:bridge snapshot.registered set value 1',
        'execute store result storage keeper:bridge snapshot.chest_valid int 1 run scoreboard players get #chest keeper',
        'execute store result storage keeper:bridge snapshot.count int 1 run scoreboard players get #found keeper',
        'data modify storage keeper:bridge snapshot_session set from storage keeper:bridge request.session_id','return 1'])
    fn('action/snapshot', [*paging(),
        'execute if score #offset keeper matches 0 store success score #valid keeper run function keeper:snapshot/freeze',
        'execute if score #offset keeper matches 0 unless score #valid keeper matches 1 run return fail',
        *equal('keeper:bridge','snapshot_session','keeper:bridge','request.session_id','SESSION_MISMATCH'),
        guard('unless data storage keeper:bridge snapshot.players','INVALID_REQUEST'),
        'execute store result score #total keeper run data get storage keeper:bridge snapshot.players',
        guard('if score #offset keeper > #total keeper'),
        'data modify storage keeper:bridge response.payload set from storage keeper:bridge snapshot',
        'data modify storage keeper:work page_source set from storage keeper:bridge snapshot.players',
        'function keeper:page/copy',
        'data modify storage keeper:bridge response.payload.players set from storage keeper:work page_items',
        'execute store result storage keeper:bridge response.payload.total int 1 run scoreboard players get #total keeper',
        'function keeper:page/cursor','return run function keeper:bridge/ok'])
    fn('validate/offset',intcheck('request.payload.offset',0,127,'#offset')+['return 1'])
    fn('validate/limit',intcheck('request.payload.limit',1,16,'#limit')+['return 1'])
    fn('page/copy',['data modify storage keeper:work page_items set value []',
        'scoreboard players operation #skip keeper = #offset keeper',
        'scoreboard players operation #left keeper = #limit keeper',
        'execute if score #skip keeper matches 1.. if data storage keeper:work page_source[0] run function keeper:page/skip',
        'execute if data storage keeper:work page_source[0] run function keeper:page/take'])
    fn('page/skip',['data remove storage keeper:work page_source[0]',
        'scoreboard players remove #skip keeper 1',
        'execute if score #skip keeper matches 1.. if data storage keeper:work page_source[0] run function keeper:page/skip'])
    fn('page/take',['data modify storage keeper:work page_items append from storage keeper:work page_source[0]',
        'data remove storage keeper:work page_source[0]','scoreboard players remove #left keeper 1',
        'execute if score #left keeper matches 1.. if data storage keeper:work page_source[0] run function keeper:page/take'])
    fn('page/cursor',['execute store result storage keeper:bridge response.payload.offset int 1 run scoreboard players get #offset keeper',
        'scoreboard players operation #next keeper = #offset keeper',
        'scoreboard players operation #next keeper += #limit keeper',
        'execute if score #next keeper > #total keeper run scoreboard players operation #next keeper = #total keeper',
        'execute store result storage keeper:bridge response.payload.next_offset int 1 run scoreboard players get #next keeper',
        'data modify storage keeper:bridge response.payload.done set value 0',
        'execute if score #next keeper >= #total keeper run data modify storage keeper:bridge response.payload.done set value 1'])
    fn('action/register_chest', [*revision(), guard('if data storage keeper:runtime quest.id','ACTIVE_QUEST'),
        guard('if data storage keeper:runtime unresolved_chest','REVIEW_REQUIRED'),
        *intcheck('request.payload.x',-29999984,29999983,'#x'), *intcheck('request.payload.y',-64,319,'#y'), *intcheck('request.payload.z',-29999984,29999983,'#z'),
        'data modify storage keeper:work chest set value {forceload_owned:0}',
        *[f'execute store result storage keeper:work chest.{c} int 1 run scoreboard players get #{c} keeper' for c in ('x','y','z')],
        'execute if data storage keeper:config chest.x run return run function keeper:chest/reregister',
        'execute in minecraft:overworld run function keeper:chest/check with storage keeper:work chest',guard('unless score #chest keeper matches 1','CHEST_INVALID'),
        'execute in minecraft:overworld run function keeper:chest/read with storage keeper:work chest',guard('if data storage keeper:work before[0]','CHEST_NOT_EMPTY'),
        'execute in minecraft:overworld run function keeper:chest/load with storage keeper:work chest', guard('unless score #loaded keeper matches 1','FORCELOAD_FAILED'),
        'data modify storage keeper:config chest set from storage keeper:work chest', *inc_revision(),
        'execute in minecraft:overworld run function keeper:chest/name with storage keeper:config chest',
        'data modify storage keeper:bridge response.payload.chest set from storage keeper:config chest','return run function keeper:bridge/ok'])
    fn('chest/reregister', ['data modify storage keeper:work compare set from storage keeper:config chest',
        'data remove storage keeper:work compare.forceload_owned', 'data remove storage keeper:work chest.forceload_owned',
        'execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work chest',guard('if score #different keeper matches 1','ALREADY_REGISTERED'),
        'execute store success score #valid keeper run function keeper:chest/registered','execute unless score #valid keeper matches 1 run return fail',
        'data modify storage keeper:bridge response.payload.chest set from storage keeper:config chest','return run function keeper:bridge/ok'])
    fn('chest/load', ['$execute store success score #loaded keeper run forceload query $(x) $(z)',
        'execute if score #loaded keeper matches 0 run data modify storage keeper:work chest.forceload_owned set value 1',
        '$execute if score #loaded keeper matches 0 store success score #loaded keeper run forceload add $(x) $(z)'])
    fn('chest/name',['$data modify block $(x) $(y) $(z) CustomName set value {text:"The Keeper\'s Offering Chest"}'])
    fn('chest/unload',['$execute store success score #unloaded keeper run forceload remove $(x) $(z)'])
    fn('action/unregister_chest', [*revision(), guard('if data storage keeper:runtime quest.id','ACTIVE_QUEST'),guard('unless data storage keeper:config chest.x','NOT_REGISTERED'),
        'data modify storage keeper:bridge response.payload.chest set from storage keeper:config chest',
        'scoreboard players set #unloaded keeper 1',
        'execute if data storage keeper:config chest{forceload_owned:1} in minecraft:overworld run function keeper:chest/unload with storage keeper:config chest',
        guard('unless score #unloaded keeper matches 1','FORCELOAD_FAILED'),
        'data remove storage keeper:config chest', *inc_revision(), 'return run function keeper:bridge/ok'])
    # Exact plain comparison: remove only Slot/count, and compare entire remaining compound to the item ID.
    fn('chest/count', ['scoreboard players set #found keeper 0', 'execute in minecraft:overworld run function keeper:chest/read with storage keeper:config chest',
        'execute store result score #code keeper run data get storage keeper:runtime quest.item_code',
        *[f'execute if score #code keeper matches {c} run data modify storage keeper:work expected set value {{id:"minecraft:{i}"}}' for c,i in enumerate(ITEMS[:10])],
        *[f'function keeper:chest/count_{s}' for s in range(27)]])
    for slot in range(27):
        fn(f'chest/count_{slot}', ['scoreboard players set #stack keeper 0', f'execute unless data storage keeper:work before[{{Slot:{slot}b}}] run return 0',
            f'data modify storage keeper:work stack set from storage keeper:work before[{{Slot:{slot}b}}]',
            'execute store result score #stack keeper run data get storage keeper:work stack.count',
            'data remove storage keeper:work stack.Slot','data remove storage keeper:work stack.count',
            'execute store success score #different keeper run data modify storage keeper:work stack set from storage keeper:work expected',
            'execute unless score #different keeper matches 0 run return 0',
            'execute unless score #stack keeper matches 1..64 run return 0',
            'scoreboard players operation #found keeper += #stack keeper'])
    # Projection validation is reused by activation and publish; prose never appears in a macro.
    projection = [*shape('request.payload.quest',('id','revision','item_code','quantity','reward_code','reward_count','remaining_seconds','title','flavor','objective_text')),
        *hexcheck('request.payload.quest.id'), *intcheck('request.payload.quest.revision',1,2147483646,'#questrevision'),
        *intcheck('request.payload.quest.item_code',0,9,'#code'), *intcheck('request.payload.quest.quantity',1,1728,'#quantity'),
        *intcheck('request.payload.quest.reward_code',0,12,'#reward'), *intcheck('request.payload.quest.reward_count',1,64,'#rewardcount'),
        *intcheck('request.payload.quest.remaining_seconds',0,604800,'#remaining')]
    for field,maximum in (('title',160),('flavor',1024),('objective_text',4096)):
        projection += stringcheck(f'request.payload.quest.{field}',maximum)
    projection += ['scoreboard players set #samequest keeper 0',
        'execute if data storage keeper:runtime quest.id run function keeper:validate/same_quest',
        'execute if score #samequest keeper matches 1 run return run function keeper:validate/frozen']
    for code in range(10):
        projection += [f'execute if score #code keeper matches {code} store result score #enabled keeper run data get storage keeper:config catalog[{code}].enabled',
            f'execute if score #code keeper matches {code} unless score #enabled keeper matches 1 run {err("UNSUPPORTED_ITEM")}',
            f'execute if score #code keeper matches {code} store result score #minimum keeper run data get storage keeper:config catalog[{code}].min',
            f'execute if score #code keeper matches {code} store result score #maximum keeper run data get storage keeper:config catalog[{code}].max']
    projection += [guard('if score #quantity keeper < #minimum keeper'),guard('if score #quantity keeper > #maximum keeper'),'return 1']
    fn('validate/projection',projection)
    fn('validate/same_quest',['data modify storage keeper:work compare set from storage keeper:runtime quest.id',
        'execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.id',
        'execute if score #different keeper matches 0 run scoreboard players set #samequest keeper 1'])
    fn('validate/frozen',sum((equal('keeper:runtime','quest.'+key,'keeper:bridge','request.payload.quest.'+key,'INVALID_REQUEST') for key in ('item_code','quantity','reward_code','reward_count')),[]) + ['return 1'])
    fn('action/activate', ['execute store success score #valid keeper run function keeper:validate/projection','execute unless score #valid keeper matches 1 run return fail',
        guard('if data storage keeper:runtime unresolved_chest','REVIEW_REQUIRED'),
        'execute if data storage keeper:runtime quest.id run return run function keeper:ui/replay',
        *revision(),'scoreboard players add #revision keeper 1', guard('unless score #questrevision keeper = #revision keeper','STALE_REVISION'),
        'execute store success score #valid keeper run function keeper:chest/registered','execute unless score #valid keeper matches 1 run return fail',
        'data modify storage keeper:runtime quest set from storage keeper:bridge request.payload.quest',*inc_revision(),
        'data modify storage keeper:runtime enabled set value 1','data modify storage keeper:runtime heartbeat set value 0',
        'tellraw @a {"nbt":"quest.objective_text","storage":"keeper:runtime","interpret":true}',
        'tellraw @a {"nbt":"quest.flavor","storage":"keeper:runtime","interpret":true}',
        'function keeper:ui/update','return run function keeper:bridge/ok'])
    fn('ui/replay', [*equal('keeper:runtime','quest.id','keeper:bridge','request.payload.quest.id','ACTIVE_QUEST'),
        'execute store result score #current keeper run data get storage keeper:runtime revision',
        'execute if score #questrevision keeper = #current keeper run return run function keeper:ui/replay_exact',
        *revision(),'scoreboard players add #current keeper 1',guard('unless score #questrevision keeper = #current keeper','STALE_REVISION'),
        'data modify storage keeper:runtime quest set from storage keeper:bridge request.payload.quest',*inc_revision(),
        'data modify storage keeper:runtime enabled set value 1','data modify storage keeper:runtime heartbeat set value 0',
        'function keeper:ui/update','return run function keeper:bridge/ok'])
    fn('ui/replay_exact', [*equal('keeper:runtime','quest','keeper:bridge','request.payload.quest','ACTIVE_QUEST'),
        'data modify storage keeper:runtime enabled set value 1','return run function keeper:bridge/ok'])
    fn('action/publish_status', [*revision(), *intcheck('request.payload.paused',0,1,'#paused'),
        'execute if data storage keeper:bridge request.payload.quest.id store success score #valid keeper run function keeper:validate/projection',
        'execute if data storage keeper:bridge request.payload.quest.id unless score #valid keeper matches 1 run return fail',
        'execute if data storage keeper:bridge request.payload.quest.id unless score #questrevision keeper = #expected keeper run return run function keeper:error/stale_revision',
        'execute if data storage keeper:bridge request.payload.quest.id unless score #samequest keeper matches 1 run return run function keeper:error/stale_revision',
        guard('unless data storage keeper:bridge request.payload.quest{}'),
        'execute unless data storage keeper:bridge request.payload.quest.id store success score #valid keeper run function keeper:validate/empty_quest',
        'execute unless data storage keeper:bridge request.payload.quest.id unless score #valid keeper matches 1 run return fail',
        *compound_list('request.payload.pending'),
        'execute store success score #valid keeper run function keeper:validate/notice',
        'execute unless score #valid keeper matches 1 run return fail',
        'execute store result score #length keeper run data get storage keeper:bridge request.payload.pending',guard('unless score #length keeper matches 0..128'),
        'data modify storage keeper:work pending set from storage keeper:bridge request.payload.pending',
        'scoreboard players set #bad keeper 0', 'execute if data storage keeper:work pending[0] run function keeper:validate/pending', guard('if score #bad keeper matches 1..'),
        'data modify storage keeper:runtime pending set from storage keeper:bridge request.payload.pending',
        'data modify storage keeper:runtime quest set value {}','data modify storage keeper:runtime quest set from storage keeper:bridge request.payload.quest',
        'data modify storage keeper:runtime enabled set value 0','execute if score #paused keeper matches 0 run data modify storage keeper:runtime enabled set value 1',
        'execute if data storage keeper:bridge request.payload.message run function keeper:ui/notice',
        'function keeper:ui/update','return run function keeper:bridge/ok'])
    fn('validate/pending',['data modify storage keeper:work uuid set from storage keeper:work pending[0].uuid',
        'execute store success score #valid keeper run function keeper:validate/uuid','execute unless score #valid keeper matches 1 run scoreboard players set #bad keeper 1',
        'execute store success score #valid keeper run function keeper:validate/pending_count','execute unless score #valid keeper matches 1 run scoreboard players set #bad keeper 1',
        'data remove storage keeper:work pending[0]','execute if data storage keeper:work pending[0] run function keeper:validate/pending'])
    fn('validate/pending_count',[*shape('pending[0]',('uuid','count'),'keeper:work'),*intcheck('pending[0].count',0,2147483646,'#n','keeper:work'),'return 1'])
    fn('validate/empty_quest',['data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest',
        'data modify storage keeper:work empty set value {}',
        'execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work empty',
        guard('if score #different keeper matches 1'),'return 1'])
    fn('validate/message',stringcheck('request.payload.message',4096)+['return 1'])
    fn('validate/notice', [
        'execute if data storage keeper:bridge request.payload.message store success score #valid keeper run function keeper:validate/message',
        'execute if data storage keeper:bridge request.payload.message unless score #valid keeper matches 1 run return fail',
        'execute if data storage keeper:bridge request.payload.audience store success score #valid keeper run function keeper:validate/audience',
        'execute if data storage keeper:bridge request.payload.audience unless score #valid keeper matches 1 run return fail',
        'execute if data storage keeper:bridge request.payload.title store success score #valid keeper run function keeper:validate/title',
        'execute if data storage keeper:bridge request.payload.title unless score #valid keeper matches 1 run return fail',
        'execute if data storage keeper:bridge request.payload.sound store success score #valid keeper run function keeper:validate/sound',
        'execute if data storage keeper:bridge request.payload.sound unless score #valid keeper matches 1 run return fail','return 1'])
    fn('validate/audience',['data modify storage keeper:work uuid set from storage keeper:bridge request.payload.audience',
        'return run function keeper:validate/uuid'])
    for flag in ('title','sound'):
        fn('validate/'+flag,intcheck('request.payload.'+flag,0,1,'#n')+['return 1'])
    fn('ui/notice',[
        'execute unless data storage keeper:bridge request.payload.audience run tellraw @a {"nbt":"request.payload.message","storage":"keeper:bridge","interpret":true}',
        'execute unless data storage keeper:bridge request.payload.audience if data storage keeper:bridge request.payload{title:1} run title @a title {"nbt":"request.payload.message","storage":"keeper:bridge","interpret":true}',
        'execute unless data storage keeper:bridge request.payload.audience if data storage keeper:bridge request.payload{sound:1} as @a at @s run playsound minecraft:entity.player.levelup master @s ~ ~ ~ 0.5 1',
        'execute if data storage keeper:bridge request.payload.audience run function keeper:ui/private'])
    fn('ui/private',['data modify storage keeper:work uuid set from storage keeper:bridge request.payload.audience',
        'execute store success score #valid keeper run function keeper:validate/uuid',guard('unless score #valid keeper matches 1'),
        'function keeper:players/target','tellraw @a[tag=keeper_target] {"nbt":"request.payload.message","storage":"keeper:bridge","interpret":true}',
        'execute if data storage keeper:bridge request.payload{title:1} run title @a[tag=keeper_target] title {"nbt":"request.payload.message","storage":"keeper:bridge","interpret":true}',
        'execute if data storage keeper:bridge request.payload{sound:1} as @a[tag=keeper_target] at @s run playsound minecraft:entity.player.levelup master @s ~ ~ ~ 0.5 1'])
    fn('players/target',['tag @a remove keeper_target','execute as @a run function keeper:players/match'])
    fn('players/match',['data modify storage keeper:work compare set from entity @s UUID',
        'execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work uuid',
        'execute if score #different keeper matches 0 run tag @s add keeper_target'])
    fn('ui/update',['bossbar set keeper:quest visible false',
        'execute unless data storage keeper:runtime {enabled:1} run return 0',
        'execute unless data storage keeper:runtime quest.id run return 0', 'function keeper:players/snapshot',
        'bossbar set keeper:quest players @a[tag=keeper_eligible]',
        'execute store result bossbar keeper:quest max run data get storage keeper:runtime quest.quantity',
        'function keeper:chest/registered','execute unless score #chest keeper matches 1 run return 0', 'function keeper:chest/count',
        'scoreboard players operation #shown keeper = #found keeper',
        'execute store result score #goal keeper run data get storage keeper:runtime quest.quantity',
        'scoreboard players operation #shown keeper < #goal keeper',
        *[f'execute if data storage keeper:runtime quest{{item_code:{code}}} run bossbar set keeper:quest name ' + json.dumps({'text': 'The Keeper: ' + item.replace('_', ' ') + ' ', 'extra': [{'score': {'name': '#shown', 'objective': 'keeper'}}, {'text': '/'}, {'nbt': 'quest.quantity', 'storage': 'keeper:runtime', 'plain': True}]}, ensure_ascii=False) for code,item in enumerate(ITEMS[:10])],
        'execute store result bossbar keeper:quest value run scoreboard players get #shown keeper','bossbar set keeper:quest visible true'])
    fn('action/pause',[*stringcheck('request.payload.reason',1024),'data modify storage keeper:runtime enabled set value 0','bossbar set keeper:quest visible false','return run function keeper:bridge/ok'])
    # Receipt helpers only interpolate hexadecimal identifiers that the dispatcher has validated.
    fn('journal/validate', [*hexcheck('request.operation_id'),*hexcheck('request.request_hash',64),
        'data modify storage keeper:work operation_id set from storage keeper:bridge request.operation_id',
        'function keeper:journal/find with storage keeper:work',
        'execute if data storage keeper:work receipt.operation_id run return run function keeper:journal/duplicate','return 1'])
    fn('journal/find',['data remove storage keeper:work receipt','$data modify storage keeper:work receipt set from storage keeper:journal receipts.$(operation_id)'])
    fn('journal/duplicate',equal('keeper:work','receipt.request_hash','keeper:bridge','request.request_hash','IDEMPOTENCY_CONFLICT') + [
        'data remove storage keeper:work stored_request',
        'data modify storage keeper:work stored_request set from storage keeper:work receipt.request',
        'data modify storage keeper:work current_request set from storage keeper:bridge request',
        *[f'data remove storage keeper:work {path}.{key}' for path in ('stored_request','current_request') for key in ('request_id','session_id','expected_revision')],
        *equal('keeper:work','stored_request','keeper:work','current_request','IDEMPOTENCY_CONFLICT'),
        guard('unless data storage keeper:work receipt{state:"APPLIED"}','REVIEW_REQUIRED'),
        'data modify storage keeper:bridge response.status set value "APPLIED"',
        'function keeper:journal/publish_result',
        'data modify storage keeper:bridge response.revision set from storage keeper:runtime revision','return fail'])
    fn('journal/running',['data modify storage keeper:bridge response.status set value "REVIEW_REQUIRED"',
        'data modify storage keeper:work receipt set value {state:"RUNNING"}',
        *[f'data modify storage keeper:work receipt.{k} set from storage keeper:bridge request.{k}' for k in ('operation_id','request_hash')],
        'data modify storage keeper:work receipt.request set from storage keeper:bridge request',
        'data modify storage keeper:work receipt.evidence_id set from storage keeper:bridge request.operation_id',
        'execute if data storage keeper:bridge request{action:"COMPLETE"} run data modify storage keeper:work receipt.plan set from storage keeper:work plan',
        'data modify storage keeper:work receipt.epoch set from storage keeper:runtime epoch',
        'return run function keeper:journal/store with storage keeper:work'])
    fn('journal/store',['$data modify storage keeper:journal receipts.$(operation_id) set from storage keeper:work receipt',
        'data remove storage keeper:work stored',
        '$data modify storage keeper:work stored set from storage keeper:journal receipts.$(operation_id)',
        *equal('keeper:work','stored','keeper:work','receipt','REVIEW_REQUIRED'),'return 1'])
    fn('journal/evidence',['$data modify storage keeper:journal evidence.$(operation_id) set value {}',
        '$data modify storage keeper:journal evidence.$(operation_id).before set from storage keeper:work before',
        '$data modify storage keeper:journal evidence.$(operation_id).after set from storage keeper:work after',
        'data remove storage keeper:work saved_before','data remove storage keeper:work saved_after',
        '$data modify storage keeper:work saved_before set from storage keeper:journal evidence.$(operation_id).before',
        '$data modify storage keeper:work saved_after set from storage keeper:journal evidence.$(operation_id).after',
        *equal('keeper:work','saved_before','keeper:work','before','REVIEW_REQUIRED'),
        *equal('keeper:work','saved_after','keeper:work','after','REVIEW_REQUIRED'),'return 1'])
    fn('journal/applied',['data modify storage keeper:work receipt.state set value "APPLIED"',
        'data modify storage keeper:work receipt.result set from storage keeper:bridge response.payload',
        'execute store success score #valid keeper run function keeper:journal/store with storage keeper:work',
        guard('unless score #valid keeper matches 1','REVIEW_REQUIRED'),
        'execute if data storage keeper:bridge request{action:"COMPLETE"} run data remove storage keeper:runtime unresolved_chest',
        'execute if data storage keeper:bridge request{action:"COMPLETE"} if data storage keeper:work previous_unresolved run data modify storage keeper:runtime unresolved_chest set from storage keeper:work previous_unresolved',
        'function keeper:journal/publish_result',
        'data modify storage keeper:bridge response.status set value "APPLIED"','data modify storage keeper:bridge response.revision set from storage keeper:runtime revision','return 1'])
    fn('journal/publish_result',[
        'data modify storage keeper:bridge response.payload set from storage keeper:work receipt.result',
        'scoreboard players set #total keeper 0',
        'execute if data storage keeper:work receipt.result.recipients store result score #total keeper run data get storage keeper:work receipt.result.recipients',
        'execute if score #total keeper matches 17.. run function keeper:journal/publish_recipients'])
    fn('journal/publish_recipients',[
        'scoreboard players set #offset keeper 0','scoreboard players set #limit keeper 16',
        'data modify storage keeper:work page_source set from storage keeper:work receipt.result.recipients',
        'function keeper:page/copy',
        'data modify storage keeper:bridge response.payload.recipients set from storage keeper:work page_items',
        'data modify storage keeper:bridge response.payload.recipients_paged set value 1',
        'execute store result storage keeper:bridge response.payload.recipient_count int 1 run scoreboard players get #total keeper'])
    complete = ['execute store success score #valid keeper run function keeper:journal/validate','execute unless score #valid keeper matches 1 run return fail',
        *revision(),*ready(),*hexcheck('request.payload.quest_id'),
        *intcheck('request.payload.item_code',0,9,'#code'),*intcheck('request.payload.quantity',1,1728,'#quantity'),
        'execute if data storage keeper:bridge request.payload.review_of store success score #valid keeper run function keeper:complete/review',
        'execute unless data storage keeper:bridge request.payload.review_of store success score #valid keeper run function keeper:complete/active',
        'execute unless score #valid keeper matches 1 run return fail',
        'execute store success score #valid keeper run function keeper:chest/registered','execute unless score #valid keeper matches 1 run return fail',
        'function keeper:chest/count',guard('if score #found keeper < #quantity keeper','INSUFFICIENT_ITEMS'),
        'execute unless data storage keeper:bridge request.payload.review_of run function keeper:players/snapshot',
        'execute store result score #recipients keeper run data get storage keeper:work recipients',guard('if score #recipients keeper matches 0','NO_RECIPIENTS'),
        'execute store result score #max keeper run data get storage keeper:config max_recipients',guard('if score #recipients keeper > #max keeper','RECIPIENT_LIMIT'),
        'data modify storage keeper:work plan set value {}',
        *[f'data modify storage keeper:work plan.{key} set from storage keeper:bridge request.payload.{key}' for key in ('quest_id','item_code','quantity')],
        'data modify storage keeper:work plan.recipients set from storage keeper:work recipients',
        'data remove storage keeper:work previous_unresolved',
        'data modify storage keeper:work previous_unresolved set from storage keeper:runtime unresolved_chest',
        'data modify storage keeper:work after set from storage keeper:work before','scoreboard players operation #remaining keeper = #quantity keeper',
        *[f'function keeper:chest/remove_{s}' for s in range(27)],guard('unless score #remaining keeper matches 0','INVALID_REQUEST'),
        'execute store success score #valid keeper run function keeper:evidence/check','execute unless score #valid keeper matches 1 run return fail',
        'data modify storage keeper:runtime unresolved_chest set from storage keeper:bridge request.operation_id',
        'execute store success score #valid keeper run function keeper:journal/running',guard('unless score #valid keeper matches 1','REVIEW_REQUIRED'),
        'execute store success score #valid keeper run function keeper:journal/evidence with storage keeper:work',guard('unless score #valid keeper matches 1','REVIEW_REQUIRED'),
        'execute in minecraft:overworld run function keeper:chest/write with storage keeper:config chest',
        guard('unless score #written keeper matches 1','REVIEW_REQUIRED'),
        'execute in minecraft:overworld run function keeper:chest/verify with storage keeper:config chest',guard('unless score #verified keeper matches 1','REVIEW_REQUIRED'),
        'data modify storage keeper:bridge response.payload set value {}',
        'data modify storage keeper:bridge response.payload.consumed set from storage keeper:bridge request.payload.quantity',
        'data modify storage keeper:bridge response.payload.recipients set from storage keeper:work recipients',
        'data modify storage keeper:bridge response.payload.evidence_id set from storage keeper:bridge request.operation_id',
        'execute unless data storage keeper:bridge request.payload.review_of run data modify storage keeper:runtime quest set value {}',
        *inc_revision(),'bossbar set keeper:quest visible false','return run function keeper:journal/applied']
    fn('action/complete',complete)
    fn('complete/active', [guard('if data storage keeper:runtime unresolved_chest','REVIEW_REQUIRED'),
        *equal('keeper:runtime','quest.id','keeper:bridge','request.payload.quest_id','STALE_REVISION'),
        *equal('keeper:runtime','quest.item_code','keeper:bridge','request.payload.item_code','INVALID_REQUEST'),
        *equal('keeper:runtime','quest.quantity','keeper:bridge','request.payload.quantity','INVALID_REQUEST'),'return 1'])
    fn('complete/review', [*hexcheck('request.payload.review_of'),
        'data modify storage keeper:work review_of set from storage keeper:bridge request.payload.review_of',
        'function keeper:complete/source with storage keeper:work',
        guard('unless data storage keeper:work source.plan.recipients[0]','REVIEW_REQUIRED'),
        'execute if data storage keeper:runtime unresolved_chest run function keeper:complete/review_guard',
        guard('if data storage keeper:bridge response{status:"REVIEW_REQUIRED"}','REVIEW_REQUIRED'),
        *equal('keeper:work','source.plan.quest_id','keeper:bridge','request.payload.quest_id','INVALID_REQUEST'),
        *equal('keeper:work','source.plan.item_code','keeper:bridge','request.payload.item_code','INVALID_REQUEST'),
        'execute store result score #original_quantity keeper run data get storage keeper:work source.plan.quantity',
        guard('if score #quantity keeper > #original_quantity keeper'),
        'data modify storage keeper:work recipients set from storage keeper:work source.plan.recipients','return 1'])
    fn('complete/source',['data remove storage keeper:work source',
        '$data modify storage keeper:work source set from storage keeper:journal receipts.$(review_of)'])
    fn('complete/review_guard',equal('keeper:runtime','unresolved_chest','keeper:bridge','request.payload.review_of','REVIEW_REQUIRED'))
    fn('action/checkpoint',[*hexcheck('request.payload.token'),
        'data modify storage keeper:config checkpoint_token set from storage keeper:bridge request.payload.token',
        'data modify storage keeper:bridge response.payload.token set from storage keeper:config checkpoint_token','return run function keeper:bridge/ok'])
    fn('action/resolve_receipt',[*revision(),*hexcheck('request.payload.operation_id'),
        'data modify storage keeper:work operation_id set from storage keeper:bridge request.payload.operation_id',
        'function keeper:journal/find with storage keeper:work',
        'scoreboard players set #decision keeper 0',
        *[f'execute if data storage keeper:bridge request.payload{{decision:"{d}"}} run scoreboard players set #decision keeper 1' for d in ('applied','not_applied','voided')],
        guard('unless score #decision keeper matches 1'),
        'execute unless data storage keeper:work receipt.operation_id run return run function keeper:journal/resolve_missing',
        'data modify storage keeper:work receipt.reviewed set value 1',
        'data modify storage keeper:work receipt.decision set from storage keeper:bridge request.payload.decision',
        'execute store success score #valid keeper run function keeper:journal/store with storage keeper:work',guard('unless score #valid keeper matches 1','REVIEW_REQUIRED'),
        'execute if data storage keeper:runtime unresolved_chest run function keeper:journal/clear_review',
        'function keeper:journal/metadata','return run function keeper:bridge/ok'])
    fn('journal/metadata',['data modify storage keeper:bridge response.payload.receipt set value {}',
        *[f'data modify storage keeper:bridge response.payload.receipt.{key} set from storage keeper:work receipt.{key}' for key in ('operation_id','request_hash','state','epoch','evidence_id','reviewed','decision')]])
    fn('journal/clear_review',['data modify storage keeper:work compare set from storage keeper:runtime unresolved_chest',
        'execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work operation_id',
        'execute if score #different keeper matches 0 run data remove storage keeper:runtime unresolved_chest'])
    fn('journal/resolve_missing', [guard('if data storage keeper:bridge request.payload{decision:"applied"}','REVIEW_REQUIRED'),
        'execute if data storage keeper:runtime unresolved_chest run function keeper:journal/clear_review',
        'data modify storage keeper:bridge response.payload.receipt_missing set value 1',
        'data modify storage keeper:bridge response.payload.operation_id set from storage keeper:bridge request.payload.operation_id',
        'data modify storage keeper:bridge response.payload.decision set from storage keeper:bridge request.payload.decision',
        'return run function keeper:bridge/ok'])
    for slot in range(27):
        fn(f'chest/remove_{slot}', ['execute if score #remaining keeper matches 0 run return 0',
            f'execute unless data storage keeper:work before[{{Slot:{slot}b}}] run return 0',
            f'data modify storage keeper:work stack set from storage keeper:work before[{{Slot:{slot}b}}]',
            'execute store result score #stack keeper run data get storage keeper:work stack.count',
            'data remove storage keeper:work stack.Slot','data remove storage keeper:work stack.count',
            'execute store success score #different keeper run data modify storage keeper:work stack set from storage keeper:work expected',
            'execute unless score #different keeper matches 0 run return 0', 'execute unless score #stack keeper matches 1..64 run return 0',
            'scoreboard players operation #take keeper = #stack keeper',
            'execute if score #take keeper > #remaining keeper run scoreboard players operation #take keeper = #remaining keeper',
            'scoreboard players operation #remaining keeper -= #take keeper','scoreboard players operation #stack keeper -= #take keeper',
            f'execute if score #stack keeper matches 0 run data remove storage keeper:work after[{{Slot:{slot}b}}]',
            f'execute if score #stack keeper matches 1.. store result storage keeper:work after[{{Slot:{slot}b}}].count int 1 run scoreboard players get #stack keeper'])
    fn('chest/write',['$execute store success score #written keeper run data modify block $(x) $(y) $(z) Items set from storage keeper:work after'])
    fn('chest/verify',['$data modify storage keeper:work actual set from block $(x) $(y) $(z) Items',
        'execute store success score #different keeper run data modify storage keeper:work actual set from storage keeper:work after',
        'scoreboard players set #verified keeper 0','execute if score #different keeper matches 0 run scoreboard players set #verified keeper 1'])
    # Single-slot Ender Chest delivery is the only player inventory write.
    pay = ['execute store success score #valid keeper run function keeper:journal/validate','execute unless score #valid keeper matches 1 run return fail',
        *revision(),*ready(),*hexcheck('request.payload.entitlement_id'),
        *intcheck('request.payload.reward_code',0,12,'#reward'),*intcheck('request.payload.count',1,64,'#rewardcount'),
        'data modify storage keeper:work uuid set from storage keeper:bridge request.payload.player_uuid',
        'execute store success score #valid keeper run function keeper:validate/uuid',guard('unless score #valid keeper matches 1'),
        'function keeper:players/target',guard('unless entity @a[tag=keeper_target]','OFFLINE'),
        'scoreboard players set #slot keeper -1',
        *[f'execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{{Slot:{s}b}}] run scoreboard players set #slot keeper {s}' for s in range(27)],
        guard('if score #slot keeper matches -1','NO_SPACE'),
        'execute store result storage keeper:work slot int 1 run scoreboard players get #slot keeper',
        'execute store result storage keeper:work count int 1 run scoreboard players get #rewardcount keeper',
        *[f'execute if score #reward keeper matches {c} run data modify storage keeper:work item set value "minecraft:{i}"' for c,i in enumerate(ITEMS)],
        'data modify storage keeper:work before set value []','function keeper:pay/expected with storage keeper:work',
        'execute store success score #valid keeper run function keeper:journal/running',guard('unless score #valid keeper matches 1','REVIEW_REQUIRED'),
        'execute store success score #valid keeper run function keeper:journal/evidence with storage keeper:work',guard('unless score #valid keeper matches 1','REVIEW_REQUIRED'),
        'execute as @a[tag=keeper_target] run function keeper:pay/insert with storage keeper:work',guard('unless score #written keeper matches 1','REVIEW_REQUIRED'),
        'execute as @a[tag=keeper_target] run function keeper:pay/verify with storage keeper:work',guard('unless score #verified keeper matches 1','REVIEW_REQUIRED'),
        'data modify storage keeper:bridge response.payload set value {}',
        'data modify storage keeper:bridge response.payload.inserted set from storage keeper:bridge request.payload.count',
        'data modify storage keeper:bridge response.payload.slot set from storage keeper:work slot',
        'data modify storage keeper:bridge response.payload.player_uuid set from storage keeper:bridge request.payload.player_uuid',
        'data modify storage keeper:bridge response.payload.evidence_id set from storage keeper:bridge request.operation_id','return run function keeper:journal/applied']
    fn('action/pay',pay)
    fn('pay/expected',['$data modify storage keeper:work after set value [{Slot:$(slot)b,id:"$(item)",count:$(count)}]'])
    fn('pay/insert',['scoreboard players set #written keeper 0',
        '$execute unless data entity @s EnderItems[{Slot:$(slot)b}] store success score #written keeper run item replace entity @s enderchest.$(slot) with $(item) $(count)'])
    fn('pay/verify',['scoreboard players set #verified keeper 0',
        '$execute unless data entity @s EnderItems[{Slot:$(slot)b}] run return 0',
        '$data modify storage keeper:work actual set from entity @s EnderItems[{Slot:$(slot)b}]',
        'execute store success score #different keeper run data modify storage keeper:work actual set from storage keeper:work after[0]',
        'execute if score #different keeper matches 0 run scoreboard players set #verified keeper 1'])
    fn('action/read_receipt', [*hexcheck('request.payload.operation_id'),*paging(),
        'data modify storage keeper:work operation_id set from storage keeper:bridge request.payload.operation_id',
        'function keeper:journal/find with storage keeper:work',guard('unless data storage keeper:work receipt.operation_id','NOT_FOUND'),
        'data modify storage keeper:bridge response.payload.receipt set from storage keeper:work receipt',
        'scoreboard players set #total keeper 0',
        *[line for kind in ('plan','result') for line in (
            f'execute if data storage keeper:work receipt.{kind}.recipients store result score #length keeper run data get storage keeper:work receipt.{kind}.recipients',
            f'execute if data storage keeper:work receipt.{kind}.recipients if score #length keeper > #total keeper run scoreboard players operation #total keeper = #length keeper')],
        guard('if score #total keeper matches 129..','EVIDENCE_LIMIT'),
        guard('if score #offset keeper > #total keeper'),
        *[f'execute if data storage keeper:work receipt.{kind}.recipients run function keeper:journal/page_{kind}' for kind in ('plan','result')],
        'function keeper:page/cursor','return run function keeper:bridge/ok'])
    for kind in ('plan','result'):
        fn(f'journal/page_{kind}',[
            f'data modify storage keeper:work page_source set from storage keeper:work receipt.{kind}.recipients',
            'function keeper:page/copy',
            f'data modify storage keeper:bridge response.payload.receipt.{kind}.recipients set from storage keeper:work page_items'])
    fn('evidence/check', [*hexcheck('request.payload.preflight_id'),
        *equal('keeper:bridge','request.payload.preflight_id','keeper:bridge','request.operation_id','STALE_PREFLIGHT'),
        *equal('keeper:bridge','preflight.id','keeper:bridge','request.operation_id','STALE_PREFLIGHT'),
        guard('unless data storage keeper:bridge preflight{approved:1}','EVIDENCE_LIMIT'),
        *equal('keeper:work','before','keeper:bridge','preflight.items','STALE_PREFLIGHT'),'return 1'])
    fn('action/read_evidence', [*hexcheck('request.payload.operation_id'),
        *intcheck('request.payload.offset',0,26,'#offset'),*intcheck('request.payload.limit',1,1,'#limit'),
        'data modify storage keeper:work operation_id set from storage keeper:bridge request.payload.operation_id',
        'data modify storage keeper:work kind set value ""',
        'execute if data storage keeper:bridge request.payload{kind:"before"} run data modify storage keeper:work kind set value "before"',
        'execute if data storage keeper:bridge request.payload{kind:"after"} run data modify storage keeper:work kind set value "after"',
        guard('if data storage keeper:work {kind:""}'),
        'execute store result storage keeper:work offset int 1 run scoreboard players get #offset keeper',
        'data modify storage keeper:bridge response.payload set value {items:[],type:"items",done:0}',
        'data modify storage keeper:bridge response.payload.offset set from storage keeper:work offset',
        'scoreboard players add #offset keeper 1',
        'execute store result storage keeper:bridge response.payload.next_offset int 1 run scoreboard players get #offset keeper',
        'execute if score #offset keeper matches 27 run data modify storage keeper:bridge response.payload.done set value 1',
        'return run function keeper:evidence/page with storage keeper:work'])
    fn('evidence/page', [
        '$execute unless data storage keeper:journal evidence.$(operation_id).$(kind) run return run function keeper:error/not_found',
        '$data modify storage keeper:bridge response.payload.items append from storage keeper:journal evidence.$(operation_id).$(kind)[{Slot:$(offset)b}]',
        'return run function keeper:bridge/ok'])
    fn('action/read_claims', ['data modify storage keeper:bridge response.payload.claims set from storage keeper:runtime claims',
        'data modify storage keeper:bridge response.payload.cursor set from storage keeper:runtime claim_cursor','return run function keeper:bridge/ok'])
    fn('action/ack_claims', [*intcheck('request.payload.cursor',0,2147483646,'#ack'),
        'execute store result score #cursor keeper run data get storage keeper:runtime claim_cursor',guard('if score #ack keeper > #cursor keeper'),
        'execute if data storage keeper:runtime claims[0] run function keeper:claims/ack','return run function keeper:bridge/ok'])
    fn('claims/ack',['execute store result score #first keeper run data get storage keeper:runtime claims[0].cursor',
        'execute if score #first keeper > #ack keeper run return 0',
        'data remove storage keeper:runtime claims[0]','execute if data storage keeper:runtime claims[0] run function keeper:claims/ack'])
    fn('tick', ['execute store result score #heartbeat keeper run data get storage keeper:runtime heartbeat',
        'execute if score #heartbeat keeper matches ..72000 run scoreboard players add #heartbeat keeper 1',
        'execute store result storage keeper:runtime heartbeat int 1 run scoreboard players get #heartbeat keeper',
        'execute store result score #timeout keeper run data get storage keeper:config heartbeat_ticks',
        'execute if data storage keeper:runtime {enabled:1} if score #heartbeat keeper >= #timeout keeper run function keeper:watchdog',
        *[f'execute as @a[scores={{keeper_{t}=1..}}] run function keeper:trigger/{t}' for t in ('quest','status','claim','help')],
        *[f'scoreboard players set @a[scores={{keeper_{t}=..-1}}] keeper_{t} 0' for t in ('quest','status','claim','help')],
        *[f'scoreboard players enable @a keeper_{t}' for t in ('quest','status','claim','help')]])
    fn('watchdog',['data modify storage keeper:runtime enabled set value 0','bossbar set keeper:quest visible false',
        'tellraw @a {"text":"[The Keeper] Service paused: director heartbeat expired. Chest contents are untouched.","color":"yellow"}'])
    fn('trigger/quest',['scoreboard players set @s keeper_quest 0','function keeper:trigger/objective'])
    fn('trigger/objective',['execute unless data storage keeper:runtime {enabled:1} run return run tellraw @s {"text":"[The Keeper] Service is paused. No collection or delivery is running.","color":"yellow"}',
        'execute unless data storage keeper:runtime quest.id run return run tellraw @s {"text":"[The Keeper] No active quest. Pending rewards remain claimable."}',
        'tellraw @s {"nbt":"quest.objective_text","storage":"keeper:runtime","interpret":true}'])
    fn('trigger/status',['scoreboard players set @s keeper_status 0','function keeper:trigger/objective',
        'data modify storage keeper:work player.uuid set from entity @s UUID','data modify storage keeper:work pending set from storage keeper:runtime pending',
        'scoreboard players set #pending keeper 0','execute if data storage keeper:work pending[0] run function keeper:trigger/pending',
        'execute store result storage keeper:work pending_count int 1 run scoreboard players get #pending keeper',
        'tellraw @s [{"text":"[The Keeper] Your pending reward stacks: "},{"nbt":"pending_count","storage":"keeper:work","interpret":false}]'])
    fn('trigger/pending',['data modify storage keeper:work compare set from storage keeper:work player.uuid',
        'execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work pending[0].uuid',
        'execute if score #different keeper matches 0 store result score #pending keeper run data get storage keeper:work pending[0].count',
        'data remove storage keeper:work pending[0]','execute if data storage keeper:work pending[0] run function keeper:trigger/pending'])
    fn('trigger/help',['scoreboard players set @s keeper_help 0',
        'tellraw @s {"text":"[The Keeper] Deposit plain requested items in the Offering Chest. Every eligible survival/adventure player online at completion receives the shown reward in their personal Ender Chest. Full/offline rewards wait; custom items do not count. /trigger keeper_quest • /trigger keeper_status • /trigger keeper_claim • /trigger keeper_help"}'])
    fn('trigger/claim',['scoreboard players set @s keeper_claim 0',
        'execute unless data storage keeper:runtime {enabled:1} run return run tellraw @s {"text":"[The Keeper] Service paused; your pending rewards are retained."}',
        'data modify storage keeper:work claim set value {}','data modify storage keeper:work claim.uuid set from entity @s UUID',
        'data modify storage keeper:work claims set from storage keeper:runtime claims','scoreboard players set #duplicate keeper 0',
        'execute if data storage keeper:work claims[0] run function keeper:claims/dedup',
        'execute if score #duplicate keeper matches 1 run return run tellraw @s {"text":"[The Keeper] Your claim is already queued."}',
        'execute store result score #length keeper run data get storage keeper:runtime claims',
        'execute if score #length keeper matches 64.. run return run tellraw @s {"text":"[The Keeper] Claim queue is full. Please try again later."}',
        'execute store result score #cursor keeper run data get storage keeper:runtime claim_cursor',
        'execute if score #cursor keeper matches 2147483646.. run return run tellraw @s {"text":"[The Keeper] Claim queue counter requires operator maintenance."}',
        'scoreboard players add #cursor keeper 1','execute store result storage keeper:runtime claim_cursor int 1 run scoreboard players get #cursor keeper',
        'execute store result storage keeper:work claim.cursor int 1 run scoreboard players get #cursor keeper',
        'data modify storage keeper:runtime claims append from storage keeper:work claim',
        'tellraw @s {"text":"[The Keeper] Claim queued. Delivery uses your first empty Ender Chest slot."}'])
    fn('claims/dedup',['data modify storage keeper:work compare set from storage keeper:work claim.uuid',
        'execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work claims[0].uuid',
        'execute if score #different keeper matches 0 run scoreboard players set #duplicate keeper 1',
        'data remove storage keeper:work claims[0]','execute if data storage keeper:work claims[0] run function keeper:claims/dedup'])
    # The current completion code, including reviewed deltas, selects counting.
    count_path = 'data/keeper/function/chest/count.mcfunction'
    out[count_path] = out[count_path].replace(
        'execute store result score #code keeper run data get storage keeper:runtime quest.item_code\n',
        'execute store result score #code keeper run data get storage keeper:runtime quest.item_code\n'
        'execute if data storage keeper:bridge request{action:"COMPLETE"} store result score #code keeper run data get storage keeper:bridge request.payload.item_code\n')
    unregister_path = 'data/keeper/function/action/unregister_chest.mcfunction'
    out[unregister_path] = guard('if data storage keeper:runtime unresolved_chest','REVIEW_REQUIRED') + '\n' + out[unregister_path]
    # Missing sources must never reuse scratch values from an earlier request.
    for name, content in list(out.items()):
        if not name.endswith('.mcfunction'):
            continue
        lines = []
        for line in content.splitlines():
            if line.startswith('data modify storage keeper:work uuid set from '):
                lines.append('data remove storage keeper:work uuid')
            lines.append(line)
        out[name] = '\n'.join(lines) + '\n'
    return out


def main():
    root = Path(__file__).resolve().parents[1] / 'datapack'
    for relative, content in files().items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

if __name__ == '__main__':
    main()
