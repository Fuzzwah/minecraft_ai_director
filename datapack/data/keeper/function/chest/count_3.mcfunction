scoreboard players set #stack keeper 0
execute unless data storage keeper:work before[{Slot:3b}] run return 0
data modify storage keeper:work stack set from storage keeper:work before[{Slot:3b}]
execute store result score #stack keeper run data get storage keeper:work stack.count
data remove storage keeper:work stack.Slot
data remove storage keeper:work stack.count
execute store success score #different keeper run data modify storage keeper:work stack set from storage keeper:work expected
execute unless score #different keeper matches 0 run return 0
execute unless score #stack keeper matches 1..64 run return 0
scoreboard players operation #found keeper += #stack keeper
