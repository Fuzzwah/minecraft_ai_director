execute unless data storage keeper:runtime {enabled:1} run return run tellraw @s {"text":"[The Keeper] Service is paused. No collection or delivery is running.","color":"yellow"}
execute unless data storage keeper:runtime quest.id run return run tellraw @s {"text":"[The Keeper] No active quest. Pending rewards remain claimable."}
tellraw @s {"nbt":"quest.objective_text","storage":"keeper:runtime","interpret":true}
