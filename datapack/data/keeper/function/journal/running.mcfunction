data modify storage keeper:bridge response.status set value "REVIEW_REQUIRED"
data modify storage keeper:work receipt set value {state:"RUNNING"}
data modify storage keeper:work receipt.operation_id set from storage keeper:bridge request.operation_id
data modify storage keeper:work receipt.request_hash set from storage keeper:bridge request.request_hash
data modify storage keeper:work receipt.request set from storage keeper:bridge request
data modify storage keeper:work receipt.evidence_id set from storage keeper:bridge request.operation_id
execute if data storage keeper:bridge request{action:"COMPLETE"} run data modify storage keeper:work receipt.plan set from storage keeper:work plan
data modify storage keeper:work receipt.epoch set from storage keeper:runtime epoch
return run function keeper:journal/store with storage keeper:work
