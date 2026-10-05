execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
data remove storage keeper:work shape.x
data remove storage keeper:work shape.y
data remove storage keeper:work shape.z
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
execute if data storage keeper:runtime quest.id run return run function keeper:error/active_quest
execute if data storage keeper:runtime unresolved_chest run return run function keeper:error/review_required
execute store result score #x keeper run data get storage keeper:bridge request.payload.x 1
execute store result storage keeper:work integer int 1 run scoreboard players get #x keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.x
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.x run return run function keeper:error/invalid_request
execute unless score #x keeper matches -29999984..29999983 run return run function keeper:error/invalid_request
execute store result score #y keeper run data get storage keeper:bridge request.payload.y 1
execute store result storage keeper:work integer int 1 run scoreboard players get #y keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.y
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.y run return run function keeper:error/invalid_request
execute unless score #y keeper matches -64..319 run return run function keeper:error/invalid_request
execute store result score #z keeper run data get storage keeper:bridge request.payload.z 1
execute store result storage keeper:work integer int 1 run scoreboard players get #z keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.z
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.z run return run function keeper:error/invalid_request
execute unless score #z keeper matches -29999984..29999983 run return run function keeper:error/invalid_request
data modify storage keeper:work chest set value {forceload_owned:0}
execute store result storage keeper:work chest.x int 1 run scoreboard players get #x keeper
execute store result storage keeper:work chest.y int 1 run scoreboard players get #y keeper
execute store result storage keeper:work chest.z int 1 run scoreboard players get #z keeper
execute if data storage keeper:config chest.x run return run function keeper:chest/reregister
execute in minecraft:overworld run function keeper:chest/check with storage keeper:work chest
execute unless score #chest keeper matches 1 run return run function keeper:error/chest_invalid
execute in minecraft:overworld run function keeper:chest/read with storage keeper:work chest
execute if data storage keeper:work before[0] run return run function keeper:error/chest_not_empty
execute in minecraft:overworld run function keeper:chest/load with storage keeper:work chest
execute unless score #loaded keeper matches 1 run return run function keeper:error/forceload_failed
data modify storage keeper:config chest set from storage keeper:work chest
execute store result score #revision keeper run data get storage keeper:runtime revision
scoreboard players add #revision keeper 1
execute store result storage keeper:runtime revision int 1 run scoreboard players get #revision keeper
execute in minecraft:overworld run function keeper:chest/name with storage keeper:config chest
data modify storage keeper:bridge response.payload.chest set from storage keeper:config chest
return run function keeper:bridge/ok
