execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
data remove storage keeper:work shape.operation_id
data remove storage keeper:work shape.offset
data remove storage keeper:work shape.limit
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
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
scoreboard players set #offset keeper 0
scoreboard players set #limit keeper 16
execute if data storage keeper:bridge request.payload.offset store success score #valid keeper run function keeper:validate/offset
execute if data storage keeper:bridge request.payload.offset unless score #valid keeper matches 1 run return fail
execute if data storage keeper:bridge request.payload.limit store success score #valid keeper run function keeper:validate/limit
execute if data storage keeper:bridge request.payload.limit unless score #valid keeper matches 1 run return fail
data modify storage keeper:work operation_id set from storage keeper:bridge request.payload.operation_id
function keeper:journal/find with storage keeper:work
execute unless data storage keeper:work receipt.operation_id run return run function keeper:error/not_found
data modify storage keeper:bridge response.payload.receipt set from storage keeper:work receipt
scoreboard players set #total keeper 0
execute if data storage keeper:work receipt.plan.recipients store result score #length keeper run data get storage keeper:work receipt.plan.recipients
execute if data storage keeper:work receipt.plan.recipients if score #length keeper > #total keeper run scoreboard players operation #total keeper = #length keeper
execute if data storage keeper:work receipt.result.recipients store result score #length keeper run data get storage keeper:work receipt.result.recipients
execute if data storage keeper:work receipt.result.recipients if score #length keeper > #total keeper run scoreboard players operation #total keeper = #length keeper
execute if score #total keeper matches 129.. run return run function keeper:error/evidence_limit
execute if score #offset keeper > #total keeper run return run function keeper:error/invalid_request
execute if data storage keeper:work receipt.plan.recipients run function keeper:journal/page_plan
execute if data storage keeper:work receipt.result.recipients run function keeper:journal/page_result
function keeper:page/cursor
return run function keeper:bridge/ok
