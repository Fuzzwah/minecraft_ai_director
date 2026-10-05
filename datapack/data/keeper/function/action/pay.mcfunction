execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
data remove storage keeper:work shape.player_uuid
data remove storage keeper:work shape.entitlement_id
data remove storage keeper:work shape.reward_code
data remove storage keeper:work shape.count
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute store success score #valid keeper run function keeper:journal/validate
execute unless score #valid keeper matches 1 run return fail
execute store result score #expected keeper run data get storage keeper:bridge request.expected_revision 1
execute store result storage keeper:work integer int 1 run scoreboard players get #expected keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.expected_revision
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.expected_revision run return run function keeper:error/invalid_request
execute unless score #expected keeper matches 0..2147483646 run return run function keeper:error/invalid_request
execute store result score #revision keeper run data get storage keeper:runtime revision
execute unless score #expected keeper = #revision keeper run return run function keeper:error/stale_revision
execute unless data storage keeper:runtime {enabled:1} run return run function keeper:error/paused
execute store result score #heartbeat keeper run data get storage keeper:runtime heartbeat
execute store result score #timeout keeper run data get storage keeper:config heartbeat_ticks
execute if score #heartbeat keeper >= #timeout keeper run return run function keeper:error/paused
execute unless data storage keeper:bridge request.payload.entitlement_id run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.payload.entitlement_id
execute store result score #length keeper run data get storage keeper:bridge request.payload.entitlement_id
execute unless score #length keeper matches 32..32 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.entitlement_id run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.entitlement_id
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
data modify storage keeper:work hex set value ""
data modify storage keeper:work hex set from storage keeper:bridge request.payload.entitlement_id
execute store result score #length keeper run data get storage keeper:work hex
execute unless score #length keeper matches 32 run return run function keeper:error/invalid_request
scoreboard players set #index keeper 0
scoreboard players set #bad keeper 0
scoreboard players set #hexlength keeper 32
function keeper:validate/hex
execute if score #bad keeper matches 1.. run return run function keeper:error/invalid_request
execute store result score #reward keeper run data get storage keeper:bridge request.payload.reward_code 1
execute store result storage keeper:work integer int 1 run scoreboard players get #reward keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.reward_code
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.reward_code run return run function keeper:error/invalid_request
execute unless score #reward keeper matches 0..12 run return run function keeper:error/invalid_request
execute store result score #rewardcount keeper run data get storage keeper:bridge request.payload.count 1
execute store result storage keeper:work integer int 1 run scoreboard players get #rewardcount keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.count
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.count run return run function keeper:error/invalid_request
execute unless score #rewardcount keeper matches 1..64 run return run function keeper:error/invalid_request
data remove storage keeper:work uuid
data modify storage keeper:work uuid set from storage keeper:bridge request.payload.player_uuid
execute store success score #valid keeper run function keeper:validate/uuid
execute unless score #valid keeper matches 1 run return run function keeper:error/invalid_request
function keeper:players/target
execute unless entity @a[tag=keeper_target] run return run function keeper:error/offline
scoreboard players set #slot keeper -1
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:0b}] run scoreboard players set #slot keeper 0
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:1b}] run scoreboard players set #slot keeper 1
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:2b}] run scoreboard players set #slot keeper 2
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:3b}] run scoreboard players set #slot keeper 3
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:4b}] run scoreboard players set #slot keeper 4
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:5b}] run scoreboard players set #slot keeper 5
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:6b}] run scoreboard players set #slot keeper 6
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:7b}] run scoreboard players set #slot keeper 7
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:8b}] run scoreboard players set #slot keeper 8
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:9b}] run scoreboard players set #slot keeper 9
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:10b}] run scoreboard players set #slot keeper 10
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:11b}] run scoreboard players set #slot keeper 11
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:12b}] run scoreboard players set #slot keeper 12
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:13b}] run scoreboard players set #slot keeper 13
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:14b}] run scoreboard players set #slot keeper 14
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:15b}] run scoreboard players set #slot keeper 15
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:16b}] run scoreboard players set #slot keeper 16
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:17b}] run scoreboard players set #slot keeper 17
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:18b}] run scoreboard players set #slot keeper 18
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:19b}] run scoreboard players set #slot keeper 19
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:20b}] run scoreboard players set #slot keeper 20
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:21b}] run scoreboard players set #slot keeper 21
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:22b}] run scoreboard players set #slot keeper 22
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:23b}] run scoreboard players set #slot keeper 23
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:24b}] run scoreboard players set #slot keeper 24
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:25b}] run scoreboard players set #slot keeper 25
execute as @a[tag=keeper_target] if score #slot keeper matches -1 unless data entity @s EnderItems[{Slot:26b}] run scoreboard players set #slot keeper 26
execute if score #slot keeper matches -1 run return run function keeper:error/no_space
execute store result storage keeper:work slot int 1 run scoreboard players get #slot keeper
execute store result storage keeper:work count int 1 run scoreboard players get #rewardcount keeper
execute if score #reward keeper matches 0 run data modify storage keeper:work item set value "minecraft:iron_ingot"
execute if score #reward keeper matches 1 run data modify storage keeper:work item set value "minecraft:copper_ingot"
execute if score #reward keeper matches 2 run data modify storage keeper:work item set value "minecraft:gold_ingot"
execute if score #reward keeper matches 3 run data modify storage keeper:work item set value "minecraft:coal"
execute if score #reward keeper matches 4 run data modify storage keeper:work item set value "minecraft:redstone"
execute if score #reward keeper matches 5 run data modify storage keeper:work item set value "minecraft:lapis_lazuli"
execute if score #reward keeper matches 6 run data modify storage keeper:work item set value "minecraft:oak_log"
execute if score #reward keeper matches 7 run data modify storage keeper:work item set value "minecraft:bread"
execute if score #reward keeper matches 8 run data modify storage keeper:work item set value "minecraft:carrot"
execute if score #reward keeper matches 9 run data modify storage keeper:work item set value "minecraft:cooked_beef"
execute if score #reward keeper matches 10 run data modify storage keeper:work item set value "minecraft:emerald"
execute if score #reward keeper matches 11 run data modify storage keeper:work item set value "minecraft:diamond"
execute if score #reward keeper matches 12 run data modify storage keeper:work item set value "minecraft:ancient_debris"
data modify storage keeper:work before set value []
function keeper:pay/expected with storage keeper:work
execute store success score #valid keeper run function keeper:journal/running
execute unless score #valid keeper matches 1 run return run function keeper:error/review_required
execute store success score #valid keeper run function keeper:journal/evidence with storage keeper:work
execute unless score #valid keeper matches 1 run return run function keeper:error/review_required
execute as @a[tag=keeper_target] run function keeper:pay/insert with storage keeper:work
execute unless score #written keeper matches 1 run return run function keeper:error/review_required
execute as @a[tag=keeper_target] run function keeper:pay/verify with storage keeper:work
execute unless score #verified keeper matches 1 run return run function keeper:error/review_required
data modify storage keeper:bridge response.payload set value {}
data modify storage keeper:bridge response.payload.inserted set from storage keeper:bridge request.payload.count
data modify storage keeper:bridge response.payload.slot set from storage keeper:work slot
data modify storage keeper:bridge response.payload.player_uuid set from storage keeper:bridge request.payload.player_uuid
data modify storage keeper:bridge response.payload.evidence_id set from storage keeper:bridge request.operation_id
return run function keeper:journal/applied
