execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
data remove storage keeper:work shape.quest
data remove storage keeper:work shape.paused
data remove storage keeper:work shape.pending
data remove storage keeper:work shape.message
data remove storage keeper:work shape.audience
data remove storage keeper:work shape.title
data remove storage keeper:work shape.sound
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute store result score #expected keeper run data get storage keeper:bridge request.expected_revision 1
execute store result storage keeper:work integer int 1 run scoreboard players get #expected keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.expected_revision
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.expected_revision run return run function keeper:error/invalid_request
execute unless score #expected keeper matches 0..2147483646 run return run function keeper:error/invalid_request
execute store result score #revision keeper run data get storage keeper:runtime revision
execute unless score #expected keeper = #revision keeper run return run function keeper:error/stale_revision
execute store result score #paused keeper run data get storage keeper:bridge request.payload.paused 1
execute store result storage keeper:work integer int 1 run scoreboard players get #paused keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.paused
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.paused run return run function keeper:error/invalid_request
execute unless score #paused keeper matches 0..1 run return run function keeper:error/invalid_request
execute if data storage keeper:bridge request.payload.quest.id store success score #valid keeper run function keeper:validate/projection
execute if data storage keeper:bridge request.payload.quest.id unless score #valid keeper matches 1 run return fail
execute if data storage keeper:bridge request.payload.quest.id unless score #questrevision keeper = #expected keeper run return run function keeper:error/stale_revision
execute if data storage keeper:bridge request.payload.quest.id unless score #samequest keeper matches 1 run return run function keeper:error/stale_revision
execute unless data storage keeper:bridge request.payload.quest{} run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.id store success score #valid keeper run function keeper:validate/empty_quest
execute unless data storage keeper:bridge request.payload.quest.id unless score #valid keeper matches 1 run return fail
execute unless data storage keeper:bridge request.payload.pending run return run function keeper:error/invalid_request
data modify storage keeper:work list_probe set from storage keeper:bridge request.payload.pending
execute store success score #list keeper run data modify storage keeper:work list_probe append value {}
execute unless score #list keeper matches 1 run return run function keeper:error/invalid_request
execute store success score #valid keeper run function keeper:validate/notice
execute unless score #valid keeper matches 1 run return fail
execute store result score #length keeper run data get storage keeper:bridge request.payload.pending
execute unless score #length keeper matches 0..128 run return run function keeper:error/invalid_request
data modify storage keeper:work pending set from storage keeper:bridge request.payload.pending
scoreboard players set #bad keeper 0
execute if data storage keeper:work pending[0] run function keeper:validate/pending
execute if score #bad keeper matches 1.. run return run function keeper:error/invalid_request
data modify storage keeper:runtime pending set from storage keeper:bridge request.payload.pending
data modify storage keeper:runtime quest set value {}
data modify storage keeper:runtime quest set from storage keeper:bridge request.payload.quest
data modify storage keeper:runtime enabled set value 0
execute if score #paused keeper matches 0 run data modify storage keeper:runtime enabled set value 1
execute if data storage keeper:bridge request.payload.message run function keeper:ui/notice
function keeper:ui/update
return run function keeper:bridge/ok
