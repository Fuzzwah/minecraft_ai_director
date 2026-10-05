execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
data remove storage keeper:work shape.cursor
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute store result score #ack keeper run data get storage keeper:bridge request.payload.cursor 1
execute store result storage keeper:work integer int 1 run scoreboard players get #ack keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.cursor
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.cursor run return run function keeper:error/invalid_request
execute unless score #ack keeper matches 0..2147483646 run return run function keeper:error/invalid_request
execute store result score #cursor keeper run data get storage keeper:runtime claim_cursor
execute if score #ack keeper > #cursor keeper run return run function keeper:error/invalid_request
execute if data storage keeper:runtime claims[0] run function keeper:claims/ack
return run function keeper:bridge/ok
