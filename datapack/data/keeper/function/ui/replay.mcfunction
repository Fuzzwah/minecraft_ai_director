execute unless data storage keeper:runtime quest.id run return run function keeper:error/active_quest
execute unless data storage keeper:bridge request.payload.quest.id run return run function keeper:error/active_quest
data modify storage keeper:work compare set from storage keeper:runtime quest.id
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.id
execute if score #different keeper matches 1 run return run function keeper:error/active_quest
execute store result score #current keeper run data get storage keeper:runtime revision
execute if score #questrevision keeper = #current keeper run return run function keeper:ui/replay_exact
execute store result score #expected keeper run data get storage keeper:bridge request.expected_revision 1
execute store result storage keeper:work integer int 1 run scoreboard players get #expected keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.expected_revision
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.expected_revision run return run function keeper:error/invalid_request
execute unless score #expected keeper matches 0..2147483646 run return run function keeper:error/invalid_request
execute store result score #revision keeper run data get storage keeper:runtime revision
execute unless score #expected keeper = #revision keeper run return run function keeper:error/stale_revision
scoreboard players add #current keeper 1
execute unless score #questrevision keeper = #current keeper run return run function keeper:error/stale_revision
data modify storage keeper:runtime quest set from storage keeper:bridge request.payload.quest
execute store result score #revision keeper run data get storage keeper:runtime revision
scoreboard players add #revision keeper 1
execute store result storage keeper:runtime revision int 1 run scoreboard players get #revision keeper
data modify storage keeper:runtime enabled set value 1
data modify storage keeper:runtime heartbeat set value 0
function keeper:ui/update
return run function keeper:bridge/ok
