execute if data storage keeper:runtime unresolved_chest run return run function keeper:error/review_required
execute unless data storage keeper:runtime quest.id run return run function keeper:error/stale_revision
execute unless data storage keeper:bridge request.payload.quest_id run return run function keeper:error/stale_revision
data modify storage keeper:work compare set from storage keeper:runtime quest.id
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest_id
execute if score #different keeper matches 1 run return run function keeper:error/stale_revision
execute unless data storage keeper:runtime quest.item_code run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.item_code run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:runtime quest.item_code
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.item_code
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:runtime quest.quantity run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.payload.quantity run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:runtime quest.quantity
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quantity
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
return 1
