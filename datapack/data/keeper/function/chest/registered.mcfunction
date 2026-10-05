scoreboard players set #chest keeper 0
execute unless data storage keeper:config chest.x run return run function keeper:error/not_registered
execute in minecraft:overworld run function keeper:chest/check with storage keeper:config chest
execute unless score #chest keeper matches 1 run return run function keeper:error/chest_invalid
return 1
