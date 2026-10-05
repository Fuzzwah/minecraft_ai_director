execute unless data storage keeper:bridge request.payload.config.config_hash run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.payload.config.config_hash
execute store result score #length keeper run data get storage keeper:bridge request.payload.config.config_hash
execute unless score #length keeper matches 64..64 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.config.config_hash run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.config.config_hash
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
data modify storage keeper:work hex set value ""
data modify storage keeper:work hex set from storage keeper:bridge request.payload.config.config_hash
execute store result score #length keeper run data get storage keeper:work hex
execute unless score #length keeper matches 64 run return run function keeper:error/invalid_request
scoreboard players set #index keeper 0
scoreboard players set #bad keeper 0
scoreboard players set #hexlength keeper 64
function keeper:validate/hex
execute if score #bad keeper matches 1.. run return run function keeper:error/invalid_request
return 1
