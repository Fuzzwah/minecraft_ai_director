execute unless data storage keeper:bridge request.payload.audience run tellraw @a {"nbt":"request.payload.message","storage":"keeper:bridge","interpret":true}
execute unless data storage keeper:bridge request.payload.audience if data storage keeper:bridge request.payload{title:1} run title @a title {"nbt":"request.payload.message","storage":"keeper:bridge","interpret":true}
execute unless data storage keeper:bridge request.payload.audience if data storage keeper:bridge request.payload{sound:1} as @a at @s run playsound minecraft:entity.player.levelup master @s ~ ~ ~ 0.5 1
execute if data storage keeper:bridge request.payload.audience run function keeper:ui/private
