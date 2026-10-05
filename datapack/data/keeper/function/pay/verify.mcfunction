scoreboard players set #verified keeper 0
$execute unless data entity @s EnderItems[{Slot:$(slot)b}] run return 0
$data modify storage keeper:work actual set from entity @s EnderItems[{Slot:$(slot)b}]
execute store success score #different keeper run data modify storage keeper:work actual set from storage keeper:work after[0]
execute if score #different keeper matches 0 run scoreboard players set #verified keeper 1
