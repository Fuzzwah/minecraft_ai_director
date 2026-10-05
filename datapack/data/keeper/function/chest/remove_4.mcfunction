execute if score #remaining keeper matches 0 run return 0
execute unless data storage keeper:work before[{Slot:4b}] run return 0
data modify storage keeper:work stack set from storage keeper:work before[{Slot:4b}]
execute store result score #stack keeper run data get storage keeper:work stack.count
data remove storage keeper:work stack.Slot
data remove storage keeper:work stack.count
execute store success score #different keeper run data modify storage keeper:work stack set from storage keeper:work expected
execute unless score #different keeper matches 0 run return 0
execute unless score #stack keeper matches 1..64 run return 0
scoreboard players operation #take keeper = #stack keeper
execute if score #take keeper > #remaining keeper run scoreboard players operation #take keeper = #remaining keeper
scoreboard players operation #remaining keeper -= #take keeper
scoreboard players operation #stack keeper -= #take keeper
execute if score #stack keeper matches 0 run data remove storage keeper:work after[{Slot:4b}]
execute if score #stack keeper matches 1.. store result storage keeper:work after[{Slot:4b}].count int 1 run scoreboard players get #stack keeper
