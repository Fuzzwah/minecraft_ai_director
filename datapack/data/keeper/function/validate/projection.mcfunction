execute unless data storage keeper:bridge request.payload.quest run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload.quest
data remove storage keeper:work shape.id
data remove storage keeper:work shape.revision
data remove storage keeper:work shape.item_code
data remove storage keeper:work shape.quantity
data remove storage keeper:work shape.reward_code
data remove storage keeper:work shape.reward_count
data remove storage keeper:work shape.remaining_seconds
data remove storage keeper:work shape.title
data remove storage keeper:work shape.flavor
data remove storage keeper:work shape.objective_text
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.id run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.payload.quest.id
execute store result score #length keeper run data get storage keeper:bridge request.payload.quest.id
execute unless score #length keeper matches 32..32 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.id run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.id
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
data modify storage keeper:work hex set value ""
data modify storage keeper:work hex set from storage keeper:bridge request.payload.quest.id
execute store result score #length keeper run data get storage keeper:work hex
execute unless score #length keeper matches 32 run return run function keeper:error/invalid_request
scoreboard players set #index keeper 0
scoreboard players set #bad keeper 0
scoreboard players set #hexlength keeper 32
function keeper:validate/hex
execute if score #bad keeper matches 1.. run return run function keeper:error/invalid_request
execute store result score #questrevision keeper run data get storage keeper:bridge request.payload.quest.revision 1
execute store result storage keeper:work integer int 1 run scoreboard players get #questrevision keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.revision
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.revision run return run function keeper:error/invalid_request
execute unless score #questrevision keeper matches 1..2147483646 run return run function keeper:error/invalid_request
execute store result score #code keeper run data get storage keeper:bridge request.payload.quest.item_code 1
execute store result storage keeper:work integer int 1 run scoreboard players get #code keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.item_code
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.item_code run return run function keeper:error/invalid_request
execute unless score #code keeper matches 0..9 run return run function keeper:error/invalid_request
execute store result score #quantity keeper run data get storage keeper:bridge request.payload.quest.quantity 1
execute store result storage keeper:work integer int 1 run scoreboard players get #quantity keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.quantity
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.quantity run return run function keeper:error/invalid_request
execute unless score #quantity keeper matches 1..1728 run return run function keeper:error/invalid_request
execute store result score #reward keeper run data get storage keeper:bridge request.payload.quest.reward_code 1
execute store result storage keeper:work integer int 1 run scoreboard players get #reward keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.reward_code
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.reward_code run return run function keeper:error/invalid_request
execute unless score #reward keeper matches 0..12 run return run function keeper:error/invalid_request
execute store result score #rewardcount keeper run data get storage keeper:bridge request.payload.quest.reward_count 1
execute store result storage keeper:work integer int 1 run scoreboard players get #rewardcount keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.reward_count
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.reward_count run return run function keeper:error/invalid_request
execute unless score #rewardcount keeper matches 1..64 run return run function keeper:error/invalid_request
execute store result score #remaining keeper run data get storage keeper:bridge request.payload.quest.remaining_seconds 1
execute store result storage keeper:work integer int 1 run scoreboard players get #remaining keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.remaining_seconds
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.remaining_seconds run return run function keeper:error/invalid_request
execute unless score #remaining keeper matches 0..604800 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.title run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.payload.quest.title
execute store result score #length keeper run data get storage keeper:bridge request.payload.quest.title
execute unless score #length keeper matches 0..160 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.title run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.title
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.flavor run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.payload.quest.flavor
execute store result score #length keeper run data get storage keeper:bridge request.payload.quest.flavor
execute unless score #length keeper matches 0..1024 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.flavor run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.flavor
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.objective_text run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.payload.quest.objective_text
execute store result score #length keeper run data get storage keeper:bridge request.payload.quest.objective_text
execute unless score #length keeper matches 0..4096 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.objective_text run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.objective_text
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
scoreboard players set #samequest keeper 0
execute if data storage keeper:runtime quest.id run function keeper:validate/same_quest
execute if score #samequest keeper matches 1 run return run function keeper:validate/frozen
execute if score #code keeper matches 0 store result score #enabled keeper run data get storage keeper:config catalog[0].enabled
execute if score #code keeper matches 0 unless score #enabled keeper matches 1 run return run function keeper:error/unsupported_item
execute if score #code keeper matches 0 store result score #minimum keeper run data get storage keeper:config catalog[0].min
execute if score #code keeper matches 0 store result score #maximum keeper run data get storage keeper:config catalog[0].max
execute if score #code keeper matches 1 store result score #enabled keeper run data get storage keeper:config catalog[1].enabled
execute if score #code keeper matches 1 unless score #enabled keeper matches 1 run return run function keeper:error/unsupported_item
execute if score #code keeper matches 1 store result score #minimum keeper run data get storage keeper:config catalog[1].min
execute if score #code keeper matches 1 store result score #maximum keeper run data get storage keeper:config catalog[1].max
execute if score #code keeper matches 2 store result score #enabled keeper run data get storage keeper:config catalog[2].enabled
execute if score #code keeper matches 2 unless score #enabled keeper matches 1 run return run function keeper:error/unsupported_item
execute if score #code keeper matches 2 store result score #minimum keeper run data get storage keeper:config catalog[2].min
execute if score #code keeper matches 2 store result score #maximum keeper run data get storage keeper:config catalog[2].max
execute if score #code keeper matches 3 store result score #enabled keeper run data get storage keeper:config catalog[3].enabled
execute if score #code keeper matches 3 unless score #enabled keeper matches 1 run return run function keeper:error/unsupported_item
execute if score #code keeper matches 3 store result score #minimum keeper run data get storage keeper:config catalog[3].min
execute if score #code keeper matches 3 store result score #maximum keeper run data get storage keeper:config catalog[3].max
execute if score #code keeper matches 4 store result score #enabled keeper run data get storage keeper:config catalog[4].enabled
execute if score #code keeper matches 4 unless score #enabled keeper matches 1 run return run function keeper:error/unsupported_item
execute if score #code keeper matches 4 store result score #minimum keeper run data get storage keeper:config catalog[4].min
execute if score #code keeper matches 4 store result score #maximum keeper run data get storage keeper:config catalog[4].max
execute if score #code keeper matches 5 store result score #enabled keeper run data get storage keeper:config catalog[5].enabled
execute if score #code keeper matches 5 unless score #enabled keeper matches 1 run return run function keeper:error/unsupported_item
execute if score #code keeper matches 5 store result score #minimum keeper run data get storage keeper:config catalog[5].min
execute if score #code keeper matches 5 store result score #maximum keeper run data get storage keeper:config catalog[5].max
execute if score #code keeper matches 6 store result score #enabled keeper run data get storage keeper:config catalog[6].enabled
execute if score #code keeper matches 6 unless score #enabled keeper matches 1 run return run function keeper:error/unsupported_item
execute if score #code keeper matches 6 store result score #minimum keeper run data get storage keeper:config catalog[6].min
execute if score #code keeper matches 6 store result score #maximum keeper run data get storage keeper:config catalog[6].max
execute if score #code keeper matches 7 store result score #enabled keeper run data get storage keeper:config catalog[7].enabled
execute if score #code keeper matches 7 unless score #enabled keeper matches 1 run return run function keeper:error/unsupported_item
execute if score #code keeper matches 7 store result score #minimum keeper run data get storage keeper:config catalog[7].min
execute if score #code keeper matches 7 store result score #maximum keeper run data get storage keeper:config catalog[7].max
execute if score #code keeper matches 8 store result score #enabled keeper run data get storage keeper:config catalog[8].enabled
execute if score #code keeper matches 8 unless score #enabled keeper matches 1 run return run function keeper:error/unsupported_item
execute if score #code keeper matches 8 store result score #minimum keeper run data get storage keeper:config catalog[8].min
execute if score #code keeper matches 8 store result score #maximum keeper run data get storage keeper:config catalog[8].max
execute if score #code keeper matches 9 store result score #enabled keeper run data get storage keeper:config catalog[9].enabled
execute if score #code keeper matches 9 unless score #enabled keeper matches 1 run return run function keeper:error/unsupported_item
execute if score #code keeper matches 9 store result score #minimum keeper run data get storage keeper:config catalog[9].min
execute if score #code keeper matches 9 store result score #maximum keeper run data get storage keeper:config catalog[9].max
execute if score #quantity keeper < #minimum keeper run return run function keeper:error/invalid_request
execute if score #quantity keeper > #maximum keeper run return run function keeper:error/invalid_request
return 1
