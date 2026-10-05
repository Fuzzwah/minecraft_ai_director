scoreboard players set #found keeper 0
execute in minecraft:overworld run function keeper:chest/read with storage keeper:config chest
execute store result score #code keeper run data get storage keeper:runtime quest.item_code
execute if data storage keeper:bridge request{action:"COMPLETE"} store result score #code keeper run data get storage keeper:bridge request.payload.item_code
execute if score #code keeper matches 0 run data modify storage keeper:work expected set value {id:"minecraft:iron_ingot"}
execute if score #code keeper matches 1 run data modify storage keeper:work expected set value {id:"minecraft:copper_ingot"}
execute if score #code keeper matches 2 run data modify storage keeper:work expected set value {id:"minecraft:gold_ingot"}
execute if score #code keeper matches 3 run data modify storage keeper:work expected set value {id:"minecraft:coal"}
execute if score #code keeper matches 4 run data modify storage keeper:work expected set value {id:"minecraft:redstone"}
execute if score #code keeper matches 5 run data modify storage keeper:work expected set value {id:"minecraft:lapis_lazuli"}
execute if score #code keeper matches 6 run data modify storage keeper:work expected set value {id:"minecraft:oak_log"}
execute if score #code keeper matches 7 run data modify storage keeper:work expected set value {id:"minecraft:bread"}
execute if score #code keeper matches 8 run data modify storage keeper:work expected set value {id:"minecraft:carrot"}
execute if score #code keeper matches 9 run data modify storage keeper:work expected set value {id:"minecraft:cooked_beef"}
function keeper:chest/count_0
function keeper:chest/count_1
function keeper:chest/count_2
function keeper:chest/count_3
function keeper:chest/count_4
function keeper:chest/count_5
function keeper:chest/count_6
function keeper:chest/count_7
function keeper:chest/count_8
function keeper:chest/count_9
function keeper:chest/count_10
function keeper:chest/count_11
function keeper:chest/count_12
function keeper:chest/count_13
function keeper:chest/count_14
function keeper:chest/count_15
function keeper:chest/count_16
function keeper:chest/count_17
function keeper:chest/count_18
function keeper:chest/count_19
function keeper:chest/count_20
function keeper:chest/count_21
function keeper:chest/count_22
function keeper:chest/count_23
function keeper:chest/count_24
function keeper:chest/count_25
function keeper:chest/count_26
