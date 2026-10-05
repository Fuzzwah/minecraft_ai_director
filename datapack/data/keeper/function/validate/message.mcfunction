execute unless data storage keeper:bridge request.payload.message run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.payload.message
execute store result score #length keeper run data get storage keeper:bridge request.payload.message
execute unless score #length keeper matches 0..4096 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.message run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.message
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
return 1
