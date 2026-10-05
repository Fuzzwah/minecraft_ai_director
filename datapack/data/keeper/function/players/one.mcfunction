data modify storage keeper:work player set value {eligible:0}
data modify storage keeper:work player.uuid set from entity @s UUID
execute if entity @s[gamemode=survival] run data modify storage keeper:work player.eligible set value 1
execute if entity @s[gamemode=adventure] run data modify storage keeper:work player.eligible set value 1
data modify storage keeper:work u0 set from entity @s UUID[0]
data modify storage keeper:work u1 set from entity @s UUID[1]
data modify storage keeper:work u2 set from entity @s UUID[2]
data modify storage keeper:work u3 set from entity @s UUID[3]
function keeper:players/excluded with storage keeper:work
execute if data storage keeper:work player{eligible:1} run tag @s add keeper_eligible
execute if data storage keeper:work player{eligible:1} run function keeper:players/recipient
data modify storage keeper:work players append from storage keeper:work player
