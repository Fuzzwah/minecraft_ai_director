execute unless data storage keeper:runtime quest run return run function keeper:error/active_quest
execute unless data storage keeper:bridge request.payload.quest run return run function keeper:error/active_quest
data modify storage keeper:work compare set from storage keeper:runtime quest
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest
execute if score #different keeper matches 1 run return run function keeper:error/active_quest
data modify storage keeper:runtime enabled set value 1
return run function keeper:bridge/ok
