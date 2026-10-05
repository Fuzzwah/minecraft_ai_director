execute unless data storage keeper:work receipt.request_hash run return run function keeper:error/idempotency_conflict
execute unless data storage keeper:bridge request.request_hash run return run function keeper:error/idempotency_conflict
data modify storage keeper:work compare set from storage keeper:work receipt.request_hash
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.request_hash
execute if score #different keeper matches 1 run return run function keeper:error/idempotency_conflict
data remove storage keeper:work stored_request
data modify storage keeper:work stored_request set from storage keeper:work receipt.request
data modify storage keeper:work current_request set from storage keeper:bridge request
data remove storage keeper:work stored_request.request_id
data remove storage keeper:work stored_request.session_id
data remove storage keeper:work stored_request.expected_revision
data remove storage keeper:work current_request.request_id
data remove storage keeper:work current_request.session_id
data remove storage keeper:work current_request.expected_revision
execute unless data storage keeper:work stored_request run return run function keeper:error/idempotency_conflict
execute unless data storage keeper:work current_request run return run function keeper:error/idempotency_conflict
data modify storage keeper:work compare set from storage keeper:work stored_request
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work current_request
execute if score #different keeper matches 1 run return run function keeper:error/idempotency_conflict
execute unless data storage keeper:work receipt{state:"APPLIED"} run return run function keeper:error/review_required
data modify storage keeper:bridge response.status set value "APPLIED"
function keeper:journal/publish_result
data modify storage keeper:bridge response.revision set from storage keeper:runtime revision
return fail
