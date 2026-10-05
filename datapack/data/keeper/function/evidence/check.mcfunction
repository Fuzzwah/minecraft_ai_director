execute unless data storage keeper:bridge request.payload.preflight_id run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.payload.preflight_id
execute store result score #length keeper run data get storage keeper:bridge request.payload.preflight_id
execute unless score #length keeper matches 32..32 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.preflight_id run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.preflight_id
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
data modify storage keeper:work hex set value ""
data modify storage keeper:work hex set from storage keeper:bridge request.payload.preflight_id
execute store result score #length keeper run data get storage keeper:work hex
execute unless score #length keeper matches 32 run return run function keeper:error/invalid_request
scoreboard players set #index keeper 0
scoreboard players set #bad keeper 0
scoreboard players set #hexlength keeper 32
function keeper:validate/hex
execute if score #bad keeper matches 1.. run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.preflight_id run return run function keeper:error/stale_preflight
execute unless data storage keeper:bridge request.operation_id run return run function keeper:error/stale_preflight
data modify storage keeper:work compare set from storage keeper:bridge request.payload.preflight_id
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.operation_id
execute if score #different keeper matches 1 run return run function keeper:error/stale_preflight
execute unless data storage keeper:bridge preflight.id run return run function keeper:error/stale_preflight
execute unless data storage keeper:bridge request.operation_id run return run function keeper:error/stale_preflight
data modify storage keeper:work compare set from storage keeper:bridge preflight.id
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.operation_id
execute if score #different keeper matches 1 run return run function keeper:error/stale_preflight
execute unless data storage keeper:bridge preflight{approved:1} run return run function keeper:error/evidence_limit
execute unless data storage keeper:work before run return run function keeper:error/stale_preflight
execute unless data storage keeper:bridge preflight.items run return run function keeper:error/stale_preflight
data modify storage keeper:work compare set from storage keeper:work before
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge preflight.items
execute if score #different keeper matches 1 run return run function keeper:error/stale_preflight
return 1
