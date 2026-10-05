execute unless data storage keeper:bridge request.payload{} run return run function keeper:error/invalid_request
data modify storage keeper:work shape set from storage keeper:bridge request.payload
data remove storage keeper:work shape.offset
data remove storage keeper:work shape.limit
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
scoreboard players set #offset keeper 0
scoreboard players set #limit keeper 16
execute if data storage keeper:bridge request.payload.offset store success score #valid keeper run function keeper:validate/offset
execute if data storage keeper:bridge request.payload.offset unless score #valid keeper matches 1 run return fail
execute if data storage keeper:bridge request.payload.limit store success score #valid keeper run function keeper:validate/limit
execute if data storage keeper:bridge request.payload.limit unless score #valid keeper matches 1 run return fail
execute if score #offset keeper matches 0 store success score #valid keeper run function keeper:snapshot/freeze
execute if score #offset keeper matches 0 unless score #valid keeper matches 1 run return fail
execute unless data storage keeper:bridge snapshot_session run return run function keeper:error/session_mismatch
execute unless data storage keeper:bridge request.session_id run return run function keeper:error/session_mismatch
data modify storage keeper:work compare set from storage keeper:bridge snapshot_session
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.session_id
execute if score #different keeper matches 1 run return run function keeper:error/session_mismatch
execute unless data storage keeper:bridge snapshot.players run return run function keeper:error/invalid_request
execute store result score #total keeper run data get storage keeper:bridge snapshot.players
execute if score #offset keeper > #total keeper run return run function keeper:error/invalid_request
data modify storage keeper:bridge response.payload set from storage keeper:bridge snapshot
data modify storage keeper:work page_source set from storage keeper:bridge snapshot.players
function keeper:page/copy
data modify storage keeper:bridge response.payload.players set from storage keeper:work page_items
execute store result storage keeper:bridge response.payload.total int 1 run scoreboard players get #total keeper
function keeper:page/cursor
return run function keeper:bridge/ok
