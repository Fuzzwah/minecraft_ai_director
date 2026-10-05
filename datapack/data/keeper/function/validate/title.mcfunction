execute store result score #n keeper run data get storage keeper:bridge request.payload.title 1
execute store result storage keeper:work integer int 1 run scoreboard players get #n keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.title
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.title run return run function keeper:error/invalid_request
execute unless score #n keeper matches 0..1 run return run function keeper:error/invalid_request
return 1
