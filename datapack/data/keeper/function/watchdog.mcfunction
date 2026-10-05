data modify storage keeper:runtime enabled set value 0
bossbar set keeper:quest visible false
tellraw @a {"text":"[The Keeper] Service paused: director heartbeat expired. Chest contents are untouched.","color":"yellow"}
