$execute unless data storage keeper:journal evidence.$(operation_id).$(kind) run return run function keeper:error/not_found
$data modify storage keeper:bridge response.payload.items append from storage keeper:journal evidence.$(operation_id).$(kind)[{Slot:$(offset)b}]
return run function keeper:bridge/ok
