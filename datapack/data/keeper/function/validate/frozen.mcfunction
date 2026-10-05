execute unless data storage keeper:runtime quest.item_code run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.item_code run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:runtime quest.item_code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.item_code
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:runtime quest.quantity run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.quantity run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:runtime quest.quantity
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.quantity
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:runtime quest.reward_code run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.reward_code run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:runtime quest.reward_code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.reward_code
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:runtime quest.reward_count run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quest.reward_count run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:runtime quest.reward_count
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.reward_count
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
return 1
