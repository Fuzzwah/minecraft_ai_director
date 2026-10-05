data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
return 1
