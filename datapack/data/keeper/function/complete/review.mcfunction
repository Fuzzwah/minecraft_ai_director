execute unless data storage keeper:bridge request.payload.review_of run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.payload.review_of
execute store result score #length keeper run data get storage keeper:bridge request.payload.review_of
execute unless score #length keeper matches 32..32 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.review_of run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.review_of
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
data modify storage keeper:work hex set value ""
data modify storage keeper:work hex set from storage keeper:bridge request.payload.review_of
execute store result score #length keeper run data get storage keeper:work hex
execute unless score #length keeper matches 32 run return run function keeper:error/invalid_request
scoreboard players set #index keeper 0
scoreboard players set #bad keeper 0
scoreboard players set #hexlength keeper 32
function keeper:validate/hex
execute if score #bad keeper matches 1.. run return run function keeper:error/invalid_request
data modify storage keeper:work review_of set from storage keeper:bridge request.payload.review_of
function keeper:complete/source with storage keeper:work
execute unless data storage keeper:work source.plan.recipients[0] run return run function keeper:error/review_required
execute if data storage keeper:runtime unresolved_chest run function keeper:complete/review_guard
execute if data storage keeper:bridge response{status:"REVIEW_REQUIRED"} run return run function keeper:error/review_required
execute unless data storage keeper:work source.plan.quest_id run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest_id run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work source.plan.quest_id
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest_id
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work source.plan.item_code run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.item_code run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work source.plan.item_code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.item_code
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute store result score #original_quantity keeper run data get storage keeper:work source.plan.quantity
execute if score #quantity keeper > #original_quantity keeper run return run function keeper:error/invalid_request
data modify storage keeper:work recipients set from storage keeper:work source.plan.recipients
return 1
