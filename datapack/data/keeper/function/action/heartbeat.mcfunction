execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
data modify storage keeper:runtime heartbeat set value 0
data modify storage keeper:bridge response.payload.heartbeat set value 0
data modify storage keeper:bridge response.payload.epoch set from storage keeper:runtime epoch
return run function keeper:bridge/ok
