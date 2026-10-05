execute if data storage keeper:bridge request.payload{decision:"applied"} run return run function keeper:error/review_required
execute if data storage keeper:runtime unresolved_chest run function keeper:journal/clear_review
data modify storage keeper:bridge response.payload.receipt_missing set value 1
data modify storage keeper:bridge response.payload.operation_id set from storage keeper:bridge request.payload.operation_id
data modify storage keeper:bridge response.payload.decision set from storage keeper:bridge request.payload.decision
return run function keeper:bridge/ok
