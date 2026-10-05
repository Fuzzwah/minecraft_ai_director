data modify storage keeper:work compare set from entity @s UUID
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work uuid
execute if score #different keeper matches 0 run tag @s add keeper_target
