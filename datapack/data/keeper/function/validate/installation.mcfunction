execute unless data storage keeper:config installation_id run return run function keeper:error/installation_mismatch
execute unless data storage keeper:bridge request.installation_id run return run function keeper:error/installation_mismatch
data modify storage keeper:work compare set from storage keeper:config installation_id
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.installation_id
execute if score #different keeper matches 1 run return run function keeper:error/installation_mismatch
return 1
