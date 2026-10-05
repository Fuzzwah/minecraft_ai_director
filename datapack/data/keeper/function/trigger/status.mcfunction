scoreboard players set @s keeper_status 0
function keeper:trigger/objective
data modify storage keeper:work player.uuid set from entity @s UUID
data modify storage keeper:work pending set from storage keeper:runtime pending
scoreboard players set #pending keeper 0
execute if data storage keeper:work pending[0] run function keeper:trigger/pending
execute store result storage keeper:work pending_count int 1 run scoreboard players get #pending keeper
tellraw @s [{"text":"[The Keeper] Your pending reward stacks: "},{"nbt":"pending_count","storage":"keeper:work","interpret":false}]
