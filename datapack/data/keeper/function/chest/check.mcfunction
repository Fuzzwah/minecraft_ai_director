scoreboard players set #chest keeper 0
$execute in minecraft:overworld if loaded $(x) $(y) $(z) if block $(x) $(y) $(z) minecraft:chest[type=single] run scoreboard players set #chest keeper 1
$execute in minecraft:overworld if data block $(x) $(y) $(z) LootTable run scoreboard players set #chest keeper 0
$execute in minecraft:overworld positioned $(x) $(y) $(z) run function keeper:chest/neighbors
