execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
data remove storage keeper:work shape.quest_id
data remove storage keeper:work shape.item_code
data remove storage keeper:work shape.quantity
data remove storage keeper:work shape.preflight_id
data remove storage keeper:work shape.review_of
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
execute unless data storage keeper:bridge request.payload.quest_id run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.payload.quest_id
execute store result score #length keeper run data get storage keeper:bridge request.payload.quest_id
execute unless score #length keeper matches 32..32 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest_id run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest_id
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
data modify storage keeper:work hex set value ""
data modify storage keeper:work hex set from storage keeper:bridge request.payload.quest_id
execute store result score #length keeper run data get storage keeper:work hex
execute unless score #length keeper matches 32 run return run function keeper:error/invalid_request
scoreboard players set #index keeper 0
scoreboard players set #bad keeper 0
scoreboard players set #hexlength keeper 32
function keeper:validate/hex
execute if score #bad keeper matches 1.. run return run function keeper:error/invalid_request
execute store result score #code keeper run data get storage keeper:bridge request.payload.item_code 1
execute store result storage keeper:work integer int 1 run scoreboard players get #code keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.item_code
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.item_code run return run function keeper:error/invalid_request
execute unless score #code keeper matches 0..9 run return run function keeper:error/invalid_request
execute store result score #quantity keeper run data get storage keeper:bridge request.payload.quantity 1
execute store result storage keeper:work integer int 1 run scoreboard players get #quantity keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quantity
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quantity run return run function keeper:error/invalid_request
execute unless score #quantity keeper matches 1..1728 run return run function keeper:error/invalid_request
execute if data storage keeper:bridge request.payload.review_of store success score #valid keeper run function keeper:complete/review
execute unless data storage keeper:bridge request.payload.review_of store success score #valid keeper run function keeper:complete/active
execute unless score #valid keeper matches 1 run return fail
execute store success score #valid keeper run function keeper:chest/registered
execute unless score #valid keeper matches 1 run return fail
function keeper:chest/count
execute if score #found keeper < #quantity keeper run return run function keeper:error/insufficient_items
execute unless data storage keeper:bridge request.payload.review_of run function keeper:players/snapshot
execute store result score #recipients keeper run data get storage keeper:work recipients
execute if score #recipients keeper matches 0 run return run function keeper:error/no_recipients
execute store result score #max keeper run data get storage keeper:config max_recipients
execute if score #recipients keeper > #max keeper run return run function keeper:error/recipient_limit
data modify storage keeper:work plan set value {}
data modify storage keeper:work plan.quest_id set from storage keeper:bridge request.payload.quest_id
data modify storage keeper:work plan.item_code set from storage keeper:bridge request.payload.item_code
data modify storage keeper:work plan.quantity set from storage keeper:bridge request.payload.quantity
data modify storage keeper:work plan.recipients set from storage keeper:work recipients
data remove storage keeper:work previous_unresolved
data modify storage keeper:work previous_unresolved set from storage keeper:runtime unresolved_chest
data modify storage keeper:work after set from storage keeper:work before
scoreboard players operation #remaining keeper = #quantity keeper
function keeper:chest/remove_0
function keeper:chest/remove_1
function keeper:chest/remove_2
function keeper:chest/remove_3
function keeper:chest/remove_4
function keeper:chest/remove_5
function keeper:chest/remove_6
function keeper:chest/remove_7
function keeper:chest/remove_8
function keeper:chest/remove_9
function keeper:chest/remove_10
function keeper:chest/remove_11
function keeper:chest/remove_12
function keeper:chest/remove_13
function keeper:chest/remove_14
function keeper:chest/remove_15
function keeper:chest/remove_16
function keeper:chest/remove_17
function keeper:chest/remove_18
function keeper:chest/remove_19
function keeper:chest/remove_20
function keeper:chest/remove_21
function keeper:chest/remove_22
function keeper:chest/remove_23
function keeper:chest/remove_24
function keeper:chest/remove_25
function keeper:chest/remove_26
execute unless score #remaining keeper matches 0 run return run function keeper:error/invalid_request
execute store success score #valid keeper run function keeper:evidence/check
execute unless score #valid keeper matches 1 run return fail
data modify storage keeper:runtime unresolved_chest set from storage keeper:bridge request.operation_id
execute store success score #valid keeper run function keeper:journal/running
execute unless score #valid keeper matches 1 run return run function keeper:error/review_required
execute store success score #valid keeper run function keeper:journal/evidence with storage keeper:work
execute unless score #valid keeper matches 1 run return run function keeper:error/review_required
execute in minecraft:overworld run function keeper:chest/write with storage keeper:config chest
execute unless score #written keeper matches 1 run return run function keeper:error/review_required
execute in minecraft:overworld run function keeper:chest/verify with storage keeper:config chest
execute unless score #verified keeper matches 1 run return run function keeper:error/review_required
data modify storage keeper:bridge response.payload set value {}
data modify storage keeper:bridge response.payload.consumed set from storage keeper:bridge request.payload.quantity
data modify storage keeper:bridge response.payload.recipients set from storage keeper:work recipients
data modify storage keeper:bridge response.payload.evidence_id set from storage keeper:bridge request.operation_id
execute unless data storage keeper:bridge request.payload.review_of run data modify storage keeper:runtime quest set value {}
execute store result score #revision keeper run data get storage keeper:runtime revision
scoreboard players add #revision keeper 1
execute store result storage keeper:runtime revision int 1 run scoreboard players get #revision keeper
bossbar set keeper:quest visible false
return run function keeper:journal/applied
