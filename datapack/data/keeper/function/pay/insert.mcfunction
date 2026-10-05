scoreboard players set #written keeper 0
$execute unless data entity @s EnderItems[{Slot:$(slot)b}] store success score #written keeper run item replace entity @s enderchest.$(slot) with $(item) $(count)
