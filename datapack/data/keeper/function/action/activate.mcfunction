execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
data remove storage keeper:work shape.quest
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute store success score #valid keeper run function keeper:validate/projection
execute unless score #valid keeper matches 1 run return fail
execute if data storage keeper:runtime unresolved_chest run return run function keeper:error/review_required
execute if data storage keeper:runtime quest.id run return run function keeper:ui/replay
execute store result score #expected keeper run data get storage keeper:bridge request.expected_revision 1
execute store result storage keeper:work integer int 1 run scoreboard players get #expected keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.expected_revision
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.expected_revision run return run function keeper:error/invalid_request
execute unless score #expected keeper matches 0..2147483646 run return run function keeper:error/invalid_request
execute store result score #revision keeper run data get storage keeper:runtime revision
execute unless score #expected keeper = #revision keeper run return run function keeper:error/stale_revision
scoreboard players add #revision keeper 1
execute unless score #questrevision keeper = #revision keeper run return run function keeper:error/stale_revision
execute store success score #valid keeper run function keeper:chest/registered
execute unless score #valid keeper matches 1 run return fail
data modify storage keeper:runtime quest set from storage keeper:bridge request.payload.quest
execute store result score #revision keeper run data get storage keeper:runtime revision
scoreboard players add #revision keeper 1
execute store result storage keeper:runtime revision int 1 run scoreboard players get #revision keeper
data modify storage keeper:runtime enabled set value 1
data modify storage keeper:runtime heartbeat set value 0
tellraw @a {"nbt":"quest.objective_text","storage":"keeper:runtime","interpret":true}
tellraw @a {"nbt":"quest.flavor","storage":"keeper:runtime","interpret":true}
function keeper:ui/update
return run function keeper:bridge/ok
