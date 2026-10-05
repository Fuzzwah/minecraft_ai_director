execute store result score #offset keeper run data get storage keeper:bridge request.payload.offset 1
execute store result storage keeper:work integer int 1 run scoreboard players get #offset keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.offset
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.offset run return run function keeper:error/invalid_request
execute unless score #offset keeper matches 0..127 run return run function keeper:error/invalid_request
return 1
