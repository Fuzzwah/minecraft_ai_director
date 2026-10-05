execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
data remove storage keeper:work shape.reason
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.reason run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.payload.reason
execute store result score #length keeper run data get storage keeper:bridge request.payload.reason
execute unless score #length keeper matches 0..1024 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.reason run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.reason
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
data modify storage keeper:runtime enabled set value 0
bossbar set keeper:quest visible false
return run function keeper:bridge/ok
