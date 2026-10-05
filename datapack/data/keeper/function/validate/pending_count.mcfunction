execute unless data storage keeper:work pending[0] run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:work pending[0]
data remove storage keeper:work shape.uuid
data remove storage keeper:work shape.count
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute store result score #n keeper run data get storage keeper:work pending[0].count 1
execute store result storage keeper:work integer int 1 run scoreboard players get #n keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work pending[0].count
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work pending[0].count run return run function keeper:error/invalid_request
execute unless score #n keeper matches 0..2147483646 run return run function keeper:error/invalid_request
return 1
