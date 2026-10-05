data modify storage keeper:bridge response.payload.receipt set value {}
data modify storage keeper:bridge response.payload.receipt.operation_id set from storage keeper:work receipt.operation_id
data modify storage keeper:bridge response.payload.receipt.request_hash set from storage keeper:work receipt.request_hash
data modify storage keeper:bridge response.payload.receipt.state set from storage keeper:work receipt.state
data modify storage keeper:bridge response.payload.receipt.epoch set from storage keeper:work receipt.epoch
data modify storage keeper:bridge response.payload.receipt.evidence_id set from storage keeper:work receipt.evidence_id
data modify storage keeper:bridge response.payload.receipt.reviewed set from storage keeper:work receipt.reviewed
data modify storage keeper:bridge response.payload.receipt.decision set from storage keeper:work receipt.decision
