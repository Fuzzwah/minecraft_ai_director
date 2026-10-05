data remove storage keeper:bridge snapshot
function keeper:players/snapshot
execute store result score #total keeper run data get storage keeper:work players
execute if score #total keeper matches 129.. run return run function keeper:error/evidence_limit
scoreboard players set #chest keeper 0
scoreboard players set #found keeper 0
execute if data storage keeper:config chest.x in minecraft:overworld run function keeper:chest/check with storage keeper:config chest
execute if score #chest keeper matches 1 if data storage keeper:runtime quest.item_code run function keeper:chest/count
data modify storage keeper:bridge snapshot set value {registered:0,chest_valid:0,count:0}
data modify storage keeper:bridge snapshot.players set from storage keeper:work players
data modify storage keeper:bridge snapshot.epoch set from storage keeper:runtime epoch
data modify storage keeper:bridge snapshot.revision set from storage keeper:runtime revision
data modify storage keeper:bridge snapshot.quest set from storage keeper:runtime quest
data modify storage keeper:bridge snapshot.enabled set from storage keeper:runtime enabled
data modify storage keeper:bridge snapshot.heartbeat set from storage keeper:runtime heartbeat
execute if data storage keeper:config chest.x run data modify storage keeper:bridge snapshot.registered set value 1
execute store result storage keeper:bridge snapshot.chest_valid int 1 run scoreboard players get #chest keeper
execute store result storage keeper:bridge snapshot.count int 1 run scoreboard players get #found keeper
data modify storage keeper:bridge snapshot_session set from storage keeper:bridge request.session_id
return 1
