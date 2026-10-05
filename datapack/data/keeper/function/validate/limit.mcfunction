execute store result score #limit keeper run data get storage keeper:bridge request.payload.limit 1
execute store result storage keeper:work integer int 1 run scoreboard players get #limit keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.limit
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.limit run return run function keeper:error/invalid_request
execute unless score #limit keeper matches 1..16 run return run function keeper:error/invalid_request
return 1
