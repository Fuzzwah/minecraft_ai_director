execute if data storage keeper:runtime unresolved_chest run return run function keeper:error/review_required
execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
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
execute unless data storage keeper:config chest.x run return run function keeper:error/not_registered
data modify storage keeper:bridge response.payload.chest set from storage keeper:config chest
scoreboard players set #unloaded keeper 1
execute if data storage keeper:config chest{forceload_owned:1} in minecraft:overworld run function keeper:chest/unload with storage keeper:config chest
execute unless score #unloaded keeper matches 1 run return run function keeper:error/forceload_failed
data remove storage keeper:config chest
execute store result score #revision keeper run data get storage keeper:runtime revision
scoreboard players add #revision keeper 1
execute store result storage keeper:runtime revision int 1 run scoreboard players get #revision keeper
return run function keeper:bridge/ok
