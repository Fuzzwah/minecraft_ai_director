execute store result score #length keeper run data get storage keeper:work uuid
execute unless score #length keeper matches 4 run return run function keeper:error/invalid_request
execute store result score #u0 keeper run data get storage keeper:work uuid[0] 1
execute store result storage keeper:work integer int 1 run scoreboard players get #u0 keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work uuid[0]
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work uuid[0] run return run function keeper:error/invalid_request
execute unless score #u0 keeper matches -2147483648..2147483647 run return run function keeper:error/invalid_request
execute store result score #u1 keeper run data get storage keeper:work uuid[1] 1
execute store result storage keeper:work integer int 1 run scoreboard players get #u1 keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work uuid[1]
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work uuid[1] run return run function keeper:error/invalid_request
execute unless score #u1 keeper matches -2147483648..2147483647 run return run function keeper:error/invalid_request
execute store result score #u2 keeper run data get storage keeper:work uuid[2] 1
execute store result storage keeper:work integer int 1 run scoreboard players get #u2 keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work uuid[2]
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work uuid[2] run return run function keeper:error/invalid_request
execute unless score #u2 keeper matches -2147483648..2147483647 run return run function keeper:error/invalid_request
execute store result score #u3 keeper run data get storage keeper:work uuid[3] 1
execute store result storage keeper:work integer int 1 run scoreboard players get #u3 keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work uuid[3]
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work uuid[3] run return run function keeper:error/invalid_request
execute unless score #u3 keeper matches -2147483648..2147483647 run return run function keeper:error/invalid_request
execute store result storage keeper:work u0 int 1 run scoreboard players get #u0 keeper
execute store result storage keeper:work u1 int 1 run scoreboard players get #u1 keeper
execute store result storage keeper:work u2 int 1 run scoreboard players get #u2 keeper
execute store result storage keeper:work u3 int 1 run scoreboard players get #u3 keeper
function keeper:validate/uuid_array with storage keeper:work
execute unless data storage keeper:work uuid run return run function keeper:error/invalid_request
execute unless data storage keeper:work uuid_expected run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work uuid
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work uuid_expected
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
return 1
