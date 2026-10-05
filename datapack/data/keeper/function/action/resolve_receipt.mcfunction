execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
data remove storage keeper:work shape.operation_id
data remove storage keeper:work shape.decision
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
execute unless data storage keeper:bridge request.payload.operation_id run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.payload.operation_id
execute store result score #length keeper run data get storage keeper:bridge request.payload.operation_id
execute unless score #length keeper matches 32..32 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.operation_id run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.operation_id
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
data modify storage keeper:work hex set value ""
data modify storage keeper:work hex set from storage keeper:bridge request.payload.operation_id
execute store result score #length keeper run data get storage keeper:work hex
execute unless score #length keeper matches 32 run return run function keeper:error/invalid_request
scoreboard players set #index keeper 0
scoreboard players set #bad keeper 0
scoreboard players set #hexlength keeper 32
function keeper:validate/hex
execute if score #bad keeper matches 1.. run return run function keeper:error/invalid_request
data modify storage keeper:work operation_id set from storage keeper:bridge request.payload.operation_id
function keeper:journal/find with storage keeper:work
scoreboard players set #decision keeper 0
execute if data storage keeper:bridge request.payload{decision:"applied"} run scoreboard players set #decision keeper 1
execute if data storage keeper:bridge request.payload{decision:"not_applied"} run scoreboard players set #decision keeper 1
execute if data storage keeper:bridge request.payload{decision:"voided"} run scoreboard players set #decision keeper 1
execute unless score #decision keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work receipt.operation_id run return run function keeper:journal/resolve_missing
data modify storage keeper:work receipt.reviewed set value 1
data modify storage keeper:work receipt.decision set from storage keeper:bridge request.payload.decision
execute store success score #valid keeper run function keeper:journal/store with storage keeper:work
execute unless score #valid keeper matches 1 run return run function keeper:error/review_required
execute if data storage keeper:runtime unresolved_chest run function keeper:journal/clear_review
function keeper:journal/metadata
return run function keeper:bridge/ok
