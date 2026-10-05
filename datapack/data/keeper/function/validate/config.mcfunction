execute unless data storage keeper:bridge request.payload.config run return run function keeper:error/config_invalid
data modify storage keeper:work shape set from storage keeper:bridge request.payload.config
data remove storage keeper:work shape.protocol
data remove storage keeper:work shape.build
data remove storage keeper:work shape.version
data remove storage keeper:work shape.max_recipients
data remove storage keeper:work shape.heartbeat_ticks
data remove storage keeper:work shape.items
data remove storage keeper:work shape.catalog
data remove storage keeper:work shape.excluded
data remove storage keeper:work shape.config_hash
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
execute if data storage keeper:bridge request.payload.config.config_hash store success score #valid keeper run function keeper:validate/config_hash
execute if data storage keeper:bridge request.payload.config.config_hash unless score #valid keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work config set from storage keeper:bridge request.payload.config
data modify storage keeper:work literal set value 1
execute unless data storage keeper:work config.protocol run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.protocol
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value 1
execute unless data storage keeper:work config.build run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.build
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value "26.3"
execute unless data storage keeper:work config.version run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.version
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #max keeper run data get storage keeper:work config.max_recipients 1
execute store result storage keeper:work integer int 1 run scoreboard players get #max keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.max_recipients
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.max_recipients run return run function keeper:error/invalid_request
execute unless score #max keeper matches 1..128 run return run function keeper:error/invalid_request
execute store result score #timeout keeper run data get storage keeper:work config.heartbeat_ticks 1
execute store result storage keeper:work integer int 1 run scoreboard players get #timeout keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.heartbeat_ticks
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.heartbeat_ticks run return run function keeper:error/invalid_request
execute unless score #timeout keeper matches 20..72000 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.items run return run function keeper:error/config_invalid
data modify storage keeper:work list_probe set from storage keeper:work config.items
execute store success score #list keeper run data modify storage keeper:work list_probe append value {}
execute unless score #list keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #length keeper run data get storage keeper:work config.items
execute unless score #length keeper matches 13 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value {code:0,item:"minecraft:iron_ingot"}
execute unless data storage keeper:work config.items[0] run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.items[0]
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value {code:1,item:"minecraft:copper_ingot"}
execute unless data storage keeper:work config.items[1] run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.items[1]
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value {code:2,item:"minecraft:gold_ingot"}
execute unless data storage keeper:work config.items[2] run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.items[2]
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value {code:3,item:"minecraft:coal"}
execute unless data storage keeper:work config.items[3] run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.items[3]
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value {code:4,item:"minecraft:redstone"}
execute unless data storage keeper:work config.items[4] run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.items[4]
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value {code:5,item:"minecraft:lapis_lazuli"}
execute unless data storage keeper:work config.items[5] run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.items[5]
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value {code:6,item:"minecraft:oak_log"}
execute unless data storage keeper:work config.items[6] run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.items[6]
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value {code:7,item:"minecraft:bread"}
execute unless data storage keeper:work config.items[7] run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.items[7]
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value {code:8,item:"minecraft:carrot"}
execute unless data storage keeper:work config.items[8] run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.items[8]
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value {code:9,item:"minecraft:cooked_beef"}
execute unless data storage keeper:work config.items[9] run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.items[9]
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value {code:10,item:"minecraft:emerald"}
execute unless data storage keeper:work config.items[10] run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.items[10]
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value {code:11,item:"minecraft:diamond"}
execute unless data storage keeper:work config.items[11] run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.items[11]
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value {code:12,item:"minecraft:ancient_debris"}
execute unless data storage keeper:work config.items[12] run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.items[12]
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
execute unless data storage keeper:work config.catalog run return run function keeper:error/config_invalid
data modify storage keeper:work list_probe set from storage keeper:work config.catalog
execute store success score #list keeper run data modify storage keeper:work list_probe append value {}
execute unless score #list keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #length keeper run data get storage keeper:work config.catalog
execute unless score #length keeper matches 10 run return run function keeper:error/config_invalid
execute unless data storage keeper:work config.catalog[0] run return run function keeper:error/config_invalid
data modify storage keeper:work shape set from storage keeper:work config.catalog[0]
data remove storage keeper:work shape.code
data remove storage keeper:work shape.item
data remove storage keeper:work shape.min
data remove storage keeper:work shape.max
data remove storage keeper:work shape.enabled
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value 0
execute unless data storage keeper:work config.catalog[0].code run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[0].code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value "minecraft:iron_ingot"
execute unless data storage keeper:work config.catalog[0].item run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[0].item
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #minimum keeper run data get storage keeper:work config.catalog[0].min 1
execute store result storage keeper:work integer int 1 run scoreboard players get #minimum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[0].min
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[0].min run return run function keeper:error/invalid_request
execute unless score #minimum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute store result score #maximum keeper run data get storage keeper:work config.catalog[0].max 1
execute store result storage keeper:work integer int 1 run scoreboard players get #maximum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[0].max
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[0].max run return run function keeper:error/invalid_request
execute unless score #maximum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute if score #minimum keeper > #maximum keeper run return run function keeper:error/config_invalid
execute store result score #n keeper run data get storage keeper:work config.catalog[0].enabled 1
execute store result storage keeper:work integer int 1 run scoreboard players get #n keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[0].enabled
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[0].enabled run return run function keeper:error/invalid_request
execute unless score #n keeper matches 0..1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[1] run return run function keeper:error/config_invalid
data modify storage keeper:work shape set from storage keeper:work config.catalog[1]
data remove storage keeper:work shape.code
data remove storage keeper:work shape.item
data remove storage keeper:work shape.min
data remove storage keeper:work shape.max
data remove storage keeper:work shape.enabled
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value 1
execute unless data storage keeper:work config.catalog[1].code run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[1].code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value "minecraft:copper_ingot"
execute unless data storage keeper:work config.catalog[1].item run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[1].item
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #minimum keeper run data get storage keeper:work config.catalog[1].min 1
execute store result storage keeper:work integer int 1 run scoreboard players get #minimum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[1].min
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[1].min run return run function keeper:error/invalid_request
execute unless score #minimum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute store result score #maximum keeper run data get storage keeper:work config.catalog[1].max 1
execute store result storage keeper:work integer int 1 run scoreboard players get #maximum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[1].max
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[1].max run return run function keeper:error/invalid_request
execute unless score #maximum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute if score #minimum keeper > #maximum keeper run return run function keeper:error/config_invalid
execute store result score #n keeper run data get storage keeper:work config.catalog[1].enabled 1
execute store result storage keeper:work integer int 1 run scoreboard players get #n keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[1].enabled
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[1].enabled run return run function keeper:error/invalid_request
execute unless score #n keeper matches 0..1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[2] run return run function keeper:error/config_invalid
data modify storage keeper:work shape set from storage keeper:work config.catalog[2]
data remove storage keeper:work shape.code
data remove storage keeper:work shape.item
data remove storage keeper:work shape.min
data remove storage keeper:work shape.max
data remove storage keeper:work shape.enabled
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value 2
execute unless data storage keeper:work config.catalog[2].code run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[2].code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value "minecraft:gold_ingot"
execute unless data storage keeper:work config.catalog[2].item run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[2].item
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #minimum keeper run data get storage keeper:work config.catalog[2].min 1
execute store result storage keeper:work integer int 1 run scoreboard players get #minimum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[2].min
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[2].min run return run function keeper:error/invalid_request
execute unless score #minimum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute store result score #maximum keeper run data get storage keeper:work config.catalog[2].max 1
execute store result storage keeper:work integer int 1 run scoreboard players get #maximum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[2].max
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[2].max run return run function keeper:error/invalid_request
execute unless score #maximum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute if score #minimum keeper > #maximum keeper run return run function keeper:error/config_invalid
execute store result score #n keeper run data get storage keeper:work config.catalog[2].enabled 1
execute store result storage keeper:work integer int 1 run scoreboard players get #n keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[2].enabled
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[2].enabled run return run function keeper:error/invalid_request
execute unless score #n keeper matches 0..1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[3] run return run function keeper:error/config_invalid
data modify storage keeper:work shape set from storage keeper:work config.catalog[3]
data remove storage keeper:work shape.code
data remove storage keeper:work shape.item
data remove storage keeper:work shape.min
data remove storage keeper:work shape.max
data remove storage keeper:work shape.enabled
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value 3
execute unless data storage keeper:work config.catalog[3].code run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[3].code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value "minecraft:coal"
execute unless data storage keeper:work config.catalog[3].item run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[3].item
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #minimum keeper run data get storage keeper:work config.catalog[3].min 1
execute store result storage keeper:work integer int 1 run scoreboard players get #minimum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[3].min
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[3].min run return run function keeper:error/invalid_request
execute unless score #minimum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute store result score #maximum keeper run data get storage keeper:work config.catalog[3].max 1
execute store result storage keeper:work integer int 1 run scoreboard players get #maximum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[3].max
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[3].max run return run function keeper:error/invalid_request
execute unless score #maximum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute if score #minimum keeper > #maximum keeper run return run function keeper:error/config_invalid
execute store result score #n keeper run data get storage keeper:work config.catalog[3].enabled 1
execute store result storage keeper:work integer int 1 run scoreboard players get #n keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[3].enabled
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[3].enabled run return run function keeper:error/invalid_request
execute unless score #n keeper matches 0..1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[4] run return run function keeper:error/config_invalid
data modify storage keeper:work shape set from storage keeper:work config.catalog[4]
data remove storage keeper:work shape.code
data remove storage keeper:work shape.item
data remove storage keeper:work shape.min
data remove storage keeper:work shape.max
data remove storage keeper:work shape.enabled
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value 4
execute unless data storage keeper:work config.catalog[4].code run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[4].code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value "minecraft:redstone"
execute unless data storage keeper:work config.catalog[4].item run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[4].item
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #minimum keeper run data get storage keeper:work config.catalog[4].min 1
execute store result storage keeper:work integer int 1 run scoreboard players get #minimum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[4].min
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[4].min run return run function keeper:error/invalid_request
execute unless score #minimum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute store result score #maximum keeper run data get storage keeper:work config.catalog[4].max 1
execute store result storage keeper:work integer int 1 run scoreboard players get #maximum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[4].max
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[4].max run return run function keeper:error/invalid_request
execute unless score #maximum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute if score #minimum keeper > #maximum keeper run return run function keeper:error/config_invalid
execute store result score #n keeper run data get storage keeper:work config.catalog[4].enabled 1
execute store result storage keeper:work integer int 1 run scoreboard players get #n keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[4].enabled
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[4].enabled run return run function keeper:error/invalid_request
execute unless score #n keeper matches 0..1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[5] run return run function keeper:error/config_invalid
data modify storage keeper:work shape set from storage keeper:work config.catalog[5]
data remove storage keeper:work shape.code
data remove storage keeper:work shape.item
data remove storage keeper:work shape.min
data remove storage keeper:work shape.max
data remove storage keeper:work shape.enabled
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value 5
execute unless data storage keeper:work config.catalog[5].code run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[5].code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value "minecraft:lapis_lazuli"
execute unless data storage keeper:work config.catalog[5].item run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[5].item
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #minimum keeper run data get storage keeper:work config.catalog[5].min 1
execute store result storage keeper:work integer int 1 run scoreboard players get #minimum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[5].min
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[5].min run return run function keeper:error/invalid_request
execute unless score #minimum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute store result score #maximum keeper run data get storage keeper:work config.catalog[5].max 1
execute store result storage keeper:work integer int 1 run scoreboard players get #maximum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[5].max
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[5].max run return run function keeper:error/invalid_request
execute unless score #maximum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute if score #minimum keeper > #maximum keeper run return run function keeper:error/config_invalid
execute store result score #n keeper run data get storage keeper:work config.catalog[5].enabled 1
execute store result storage keeper:work integer int 1 run scoreboard players get #n keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[5].enabled
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[5].enabled run return run function keeper:error/invalid_request
execute unless score #n keeper matches 0..1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[6] run return run function keeper:error/config_invalid
data modify storage keeper:work shape set from storage keeper:work config.catalog[6]
data remove storage keeper:work shape.code
data remove storage keeper:work shape.item
data remove storage keeper:work shape.min
data remove storage keeper:work shape.max
data remove storage keeper:work shape.enabled
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value 6
execute unless data storage keeper:work config.catalog[6].code run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[6].code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value "minecraft:oak_log"
execute unless data storage keeper:work config.catalog[6].item run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[6].item
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #minimum keeper run data get storage keeper:work config.catalog[6].min 1
execute store result storage keeper:work integer int 1 run scoreboard players get #minimum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[6].min
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[6].min run return run function keeper:error/invalid_request
execute unless score #minimum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute store result score #maximum keeper run data get storage keeper:work config.catalog[6].max 1
execute store result storage keeper:work integer int 1 run scoreboard players get #maximum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[6].max
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[6].max run return run function keeper:error/invalid_request
execute unless score #maximum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute if score #minimum keeper > #maximum keeper run return run function keeper:error/config_invalid
execute store result score #n keeper run data get storage keeper:work config.catalog[6].enabled 1
execute store result storage keeper:work integer int 1 run scoreboard players get #n keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[6].enabled
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[6].enabled run return run function keeper:error/invalid_request
execute unless score #n keeper matches 0..1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[7] run return run function keeper:error/config_invalid
data modify storage keeper:work shape set from storage keeper:work config.catalog[7]
data remove storage keeper:work shape.code
data remove storage keeper:work shape.item
data remove storage keeper:work shape.min
data remove storage keeper:work shape.max
data remove storage keeper:work shape.enabled
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value 7
execute unless data storage keeper:work config.catalog[7].code run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[7].code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value "minecraft:bread"
execute unless data storage keeper:work config.catalog[7].item run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[7].item
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #minimum keeper run data get storage keeper:work config.catalog[7].min 1
execute store result storage keeper:work integer int 1 run scoreboard players get #minimum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[7].min
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[7].min run return run function keeper:error/invalid_request
execute unless score #minimum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute store result score #maximum keeper run data get storage keeper:work config.catalog[7].max 1
execute store result storage keeper:work integer int 1 run scoreboard players get #maximum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[7].max
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[7].max run return run function keeper:error/invalid_request
execute unless score #maximum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute if score #minimum keeper > #maximum keeper run return run function keeper:error/config_invalid
execute store result score #n keeper run data get storage keeper:work config.catalog[7].enabled 1
execute store result storage keeper:work integer int 1 run scoreboard players get #n keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[7].enabled
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[7].enabled run return run function keeper:error/invalid_request
execute unless score #n keeper matches 0..1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[8] run return run function keeper:error/config_invalid
data modify storage keeper:work shape set from storage keeper:work config.catalog[8]
data remove storage keeper:work shape.code
data remove storage keeper:work shape.item
data remove storage keeper:work shape.min
data remove storage keeper:work shape.max
data remove storage keeper:work shape.enabled
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value 8
execute unless data storage keeper:work config.catalog[8].code run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[8].code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value "minecraft:carrot"
execute unless data storage keeper:work config.catalog[8].item run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[8].item
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #minimum keeper run data get storage keeper:work config.catalog[8].min 1
execute store result storage keeper:work integer int 1 run scoreboard players get #minimum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[8].min
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[8].min run return run function keeper:error/invalid_request
execute unless score #minimum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute store result score #maximum keeper run data get storage keeper:work config.catalog[8].max 1
execute store result storage keeper:work integer int 1 run scoreboard players get #maximum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[8].max
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[8].max run return run function keeper:error/invalid_request
execute unless score #maximum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute if score #minimum keeper > #maximum keeper run return run function keeper:error/config_invalid
execute store result score #n keeper run data get storage keeper:work config.catalog[8].enabled 1
execute store result storage keeper:work integer int 1 run scoreboard players get #n keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[8].enabled
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[8].enabled run return run function keeper:error/invalid_request
execute unless score #n keeper matches 0..1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[9] run return run function keeper:error/config_invalid
data modify storage keeper:work shape set from storage keeper:work config.catalog[9]
data remove storage keeper:work shape.code
data remove storage keeper:work shape.item
data remove storage keeper:work shape.min
data remove storage keeper:work shape.max
data remove storage keeper:work shape.enabled
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value 9
execute unless data storage keeper:work config.catalog[9].code run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[9].code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data modify storage keeper:work literal set value "minecraft:cooked_beef"
execute unless data storage keeper:work config.catalog[9].item run return run function keeper:error/config_invalid
execute unless data storage keeper:work literal run return run function keeper:error/config_invalid
data modify storage keeper:work compare set from storage keeper:work config.catalog[9].item
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #minimum keeper run data get storage keeper:work config.catalog[9].min 1
execute store result storage keeper:work integer int 1 run scoreboard players get #minimum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[9].min
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[9].min run return run function keeper:error/invalid_request
execute unless score #minimum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute store result score #maximum keeper run data get storage keeper:work config.catalog[9].max 1
execute store result storage keeper:work integer int 1 run scoreboard players get #maximum keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[9].max
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[9].max run return run function keeper:error/invalid_request
execute unless score #maximum keeper matches 1..1728 run return run function keeper:error/invalid_request
execute if score #minimum keeper > #maximum keeper run return run function keeper:error/config_invalid
execute store result score #n keeper run data get storage keeper:work config.catalog[9].enabled 1
execute store result storage keeper:work integer int 1 run scoreboard players get #n keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work config.catalog[9].enabled
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.catalog[9].enabled run return run function keeper:error/invalid_request
execute unless score #n keeper matches 0..1 run return run function keeper:error/invalid_request
execute unless data storage keeper:work config.excluded run return run function keeper:error/config_invalid
data modify storage keeper:work list_probe set from storage keeper:work config.excluded
execute store success score #list keeper run data modify storage keeper:work list_probe append value {}
execute unless score #list keeper matches 1 run return run function keeper:error/config_invalid
execute store result score #length keeper run data get storage keeper:work config.excluded
execute unless score #length keeper matches 0..128 run return run function keeper:error/config_invalid
data modify storage keeper:work exclusions set from storage keeper:work config.excluded
scoreboard players set #bad keeper 0
execute if data storage keeper:work exclusions[0] run function keeper:validate/exclusions
execute if score #bad keeper matches 1.. run return run function keeper:error/config_invalid
return 1
