data modify storage keeper:work receipt.state set value "APPLIED"
data modify storage keeper:work receipt.result set from storage keeper:bridge response.payload
execute store success score #valid keeper run function keeper:journal/store with storage keeper:work
execute unless score #valid keeper matches 1 run return run function keeper:error/review_required
execute if data storage keeper:bridge request{action:"COMPLETE"} run data remove storage keeper:runtime unresolved_chest
execute if data storage keeper:bridge request{action:"COMPLETE"} if data storage keeper:work previous_unresolved run data modify storage keeper:runtime unresolved_chest set from storage keeper:work previous_unresolved
function keeper:journal/publish_result
data modify storage keeper:bridge response.status set value "APPLIED"
data modify storage keeper:bridge response.revision set from storage keeper:runtime revision
return 1
