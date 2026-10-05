execute store result storage keeper:bridge response.payload.offset int 1 run scoreboard players get #offset keeper
scoreboard players operation #next keeper = #offset keeper
scoreboard players operation #next keeper += #limit keeper
execute if score #next keeper > #total keeper run scoreboard players operation #next keeper = #total keeper
execute store result storage keeper:bridge response.payload.next_offset int 1 run scoreboard players get #next keeper
data modify storage keeper:bridge response.payload.done set value 0
execute if score #next keeper >= #total keeper run data modify storage keeper:bridge response.payload.done set value 1
