execute store result score #heartbeat keeper run data get storage keeper:runtime heartbeat
execute if score #heartbeat keeper matches ..72000 run scoreboard players add #heartbeat keeper 1
execute store result storage keeper:runtime heartbeat int 1 run scoreboard players get #heartbeat keeper
execute store result score #timeout keeper run data get storage keeper:config heartbeat_ticks
execute if data storage keeper:runtime {enabled:1} if score #heartbeat keeper >= #timeout keeper run function keeper:watchdog
execute as @a[scores={keeper_quest=1..}] run function keeper:trigger/quest
execute as @a[scores={keeper_status=1..}] run function keeper:trigger/status
execute as @a[scores={keeper_claim=1..}] run function keeper:trigger/claim
execute as @a[scores={keeper_help=1..}] run function keeper:trigger/help
scoreboard players set @a[scores={keeper_quest=..-1}] keeper_quest 0
scoreboard players set @a[scores={keeper_status=..-1}] keeper_status 0
scoreboard players set @a[scores={keeper_claim=..-1}] keeper_claim 0
scoreboard players set @a[scores={keeper_help=..-1}] keeper_help 0
scoreboard players enable @a keeper_quest
scoreboard players enable @a keeper_status
scoreboard players enable @a keeper_claim
scoreboard players enable @a keeper_help
