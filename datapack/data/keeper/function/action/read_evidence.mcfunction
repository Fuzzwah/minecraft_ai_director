execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
data remove storage keeper:work shape.operation_id
data remove storage keeper:work shape.kind
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
execute store result score #offset keeper run data get storage keeper:bridge request.payload.offset 1
execute store result storage keeper:work integer int 1 run scoreboard players get #offset keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.offset
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.offset run return run function keeper:error/invalid_request
execute unless score #offset keeper matches 0..26 run return run function keeper:error/invalid_request
execute store result score #limit keeper run data get storage keeper:bridge request.payload.limit 1
execute store result storage keeper:work integer int 1 run scoreboard players get #limit keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.limit
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.limit run return run function keeper:error/invalid_request
execute unless score #limit keeper matches 1..1 run return run function keeper:error/invalid_request
data modify storage keeper:work operation_id set from storage keeper:bridge request.payload.operation_id
data modify storage keeper:work kind set value ""
execute if data storage keeper:bridge request.payload{kind:"before"} run data modify storage keeper:work kind set value "before"
execute if data storage keeper:bridge request.payload{kind:"after"} run data modify storage keeper:work kind set value "after"
execute if data storage keeper:work {kind:""} run return run function keeper:error/invalid_request
execute store result storage keeper:work offset int 1 run scoreboard players get #offset keeper
data modify storage keeper:bridge response.payload set value {items:[],type:"items",done:0}
data modify storage keeper:bridge response.payload.offset set from storage keeper:work offset
scoreboard players add #offset keeper 1
execute store result storage keeper:bridge response.payload.next_offset int 1 run scoreboard players get #offset keeper
execute if score #offset keeper matches 27 run data modify storage keeper:bridge response.payload.done set value 1
return run function keeper:evidence/page with storage keeper:work
