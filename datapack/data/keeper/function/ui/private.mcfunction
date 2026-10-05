data remove storage keeper:work uuid
data modify storage keeper:work uuid set from storage keeper:bridge request.payload.audience
execute store success score #valid keeper run function keeper:validate/uuid
execute unless score #valid keeper matches 1 run return run function keeper:error/invalid_request
function keeper:players/target
tellraw @a[tag=keeper_target] {"nbt":"request.payload.message","storage":"keeper:bridge","interpret":true}
execute if data storage keeper:bridge request.payload{title:1} run title @a[tag=keeper_target] title {"nbt":"request.payload.message","storage":"keeper:bridge","interpret":true}
execute if data storage keeper:bridge request.payload{sound:1} as @a[tag=keeper_target] at @s run playsound minecraft:entity.player.levelup master @s ~ ~ ~ 0.5 1
