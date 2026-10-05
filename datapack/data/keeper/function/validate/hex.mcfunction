execute store result storage keeper:work start int 1 run scoreboard players get #index keeper
scoreboard players operation #end keeper = #index keeper
scoreboard players add #end keeper 1
execute store result storage keeper:work end int 1 run scoreboard players get #end keeper
function keeper:validate/hex_char with storage keeper:work
execute unless score #char keeper matches 1 run scoreboard players set #bad keeper 1
scoreboard players add #index keeper 1
execute if score #index keeper < #hexlength keeper run function keeper:validate/hex
