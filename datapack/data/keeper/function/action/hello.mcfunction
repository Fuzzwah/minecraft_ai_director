execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
data remove storage keeper:work shape.config
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute store success score #valid keeper run function keeper:validate/config
execute unless score #valid keeper matches 1 run return run function keeper:error/config_invalid
execute if data storage keeper:config {configured:1} store success score #valid keeper run function keeper:validate/installation
execute if data storage keeper:config {configured:1} unless score #valid keeper matches 1 run return fail
data modify storage keeper:work old_chest set value {}
data modify storage keeper:work old_chest set from storage keeper:config chest
data modify storage keeper:config protocol set value 1
data modify storage keeper:config build set value 1
data modify storage keeper:config version set value "26.3"
data modify storage keeper:config installation_id set from storage keeper:bridge request.installation_id
data modify storage keeper:config items set from storage keeper:work config.items
data modify storage keeper:config catalog set from storage keeper:work config.catalog
data modify storage keeper:config excluded set from storage keeper:work config.excluded
data modify storage keeper:config max_recipients set from storage keeper:work config.max_recipients
data modify storage keeper:config heartbeat_ticks set from storage keeper:work config.heartbeat_ticks
function keeper:players/build_exclusions
data modify storage keeper:config configured set value 1
data modify storage keeper:runtime session_id set from storage keeper:bridge request.session_id
data modify storage keeper:runtime verified set value 1
data modify storage keeper:runtime enabled set value 0
data modify storage keeper:runtime heartbeat set value 0
data modify storage keeper:bridge response.payload set value {version:"26.3",pack_format:[121,0],build:1,registered:0,chest:{}}
data modify storage keeper:bridge response.payload.checkpoint_token set value ""
data modify storage keeper:bridge response.payload.checkpoint_token set from storage keeper:config checkpoint_token
data modify storage keeper:bridge response.payload.epoch set from storage keeper:runtime epoch
data modify storage keeper:bridge response.payload.installation_id set from storage keeper:config installation_id
data modify storage keeper:bridge response.payload.revision set from storage keeper:runtime revision
data modify storage keeper:bridge response.payload.quest set from storage keeper:runtime quest
data modify storage keeper:bridge response.payload.enabled set from storage keeper:runtime enabled
execute if data storage keeper:config chest.x run data modify storage keeper:bridge response.payload.registered set value 1
data modify storage keeper:bridge response.payload.chest set from storage keeper:config chest
return run function keeper:bridge/ok
