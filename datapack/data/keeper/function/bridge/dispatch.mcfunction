data modify storage keeper:work initialized set value 0
execute store success storage keeper:work initialized int 1 run scoreboard players get #loaded keeper
execute unless data storage keeper:work {initialized:1} run function keeper:load
data modify storage keeper:bridge response set value {protocol:1,request_id:"",session_id:"",status:"INVALID_REQUEST",revision:0,payload:{}}
data modify storage keeper:bridge response.request_id set from storage keeper:bridge request.request_id
data modify storage keeper:bridge response.session_id set from storage keeper:bridge request.session_id
data modify storage keeper:bridge response.operation_id set from storage keeper:bridge request.operation_id
data modify storage keeper:bridge response.revision set from storage keeper:runtime revision
data modify storage keeper:work literal set value 1
execute unless data storage keeper:bridge request.protocol run return run function keeper:error/protocol_mismatch
execute unless data storage keeper:work literal run return run function keeper:error/protocol_mismatch
data modify storage keeper:work compare set from storage keeper:bridge request.protocol
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work literal
execute if score #different keeper matches 1 run return run function keeper:error/protocol_mismatch
execute unless data storage keeper:bridge request.action run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.action
execute store result score #length keeper run data get storage keeper:bridge request.action
execute unless score #length keeper matches 1..32 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.action run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.action
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute store result score #expected keeper run data get storage keeper:bridge request.expected_revision 1
execute store result storage keeper:work integer int 1 run scoreboard players get #expected keeper
data modify storage keeper:work compare set from storage keeper:work integer
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.expected_revision
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.expected_revision run return run function keeper:error/invalid_request
execute unless score #expected keeper matches 0..2147483646 run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.installation_id run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.installation_id
execute store result score #length keeper run data get storage keeper:bridge request.installation_id
execute unless score #length keeper matches 32..32 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.installation_id run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.installation_id
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
data modify storage keeper:work hex set value ""
data modify storage keeper:work hex set from storage keeper:bridge request.installation_id
execute store result score #length keeper run data get storage keeper:work hex
execute unless score #length keeper matches 32 run return run function keeper:error/invalid_request
scoreboard players set #index keeper 0
scoreboard players set #bad keeper 0
scoreboard players set #hexlength keeper 32
function keeper:validate/hex
execute if score #bad keeper matches 1.. run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.session_id run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.session_id
execute store result score #length keeper run data get storage keeper:bridge request.session_id
execute unless score #length keeper matches 32..32 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.session_id run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.session_id
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
data modify storage keeper:work hex set value ""
data modify storage keeper:work hex set from storage keeper:bridge request.session_id
execute store result score #length keeper run data get storage keeper:work hex
execute unless score #length keeper matches 32 run return run function keeper:error/invalid_request
scoreboard players set #index keeper 0
scoreboard players set #bad keeper 0
scoreboard players set #hexlength keeper 32
function keeper:validate/hex
execute if score #bad keeper matches 1.. run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.request_id run return run function keeper:error/invalid_request
data modify storage keeper:work text set value ""
data modify storage keeper:work text set string storage keeper:bridge request.request_id
execute store result score #length keeper run data get storage keeper:bridge request.request_id
execute unless score #length keeper matches 32..32 run return run function keeper:error/invalid_request
execute unless data storage keeper:work text run return run function keeper:error/invalid_request
execute unless data storage keeper:bridge request.request_id run return run function keeper:error/invalid_request
data modify storage keeper:work compare set from storage keeper:work text
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.request_id
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
data modify storage keeper:work hex set value ""
data modify storage keeper:work hex set from storage keeper:bridge request.request_id
execute store result score #length keeper run data get storage keeper:work hex
execute unless score #length keeper matches 32 run return run function keeper:error/invalid_request
scoreboard players set #index keeper 0
scoreboard players set #bad keeper 0
scoreboard players set #hexlength keeper 32
function keeper:validate/hex
execute if score #bad keeper matches 1.. run return run function keeper:error/invalid_request
data modify storage keeper:work envelope set from storage keeper:bridge request
data remove storage keeper:work envelope.protocol
data remove storage keeper:work envelope.installation_id
data remove storage keeper:work envelope.session_id
data remove storage keeper:work envelope.request_id
data remove storage keeper:work envelope.action
data remove storage keeper:work envelope.expected_revision
data remove storage keeper:work envelope.payload
data remove storage keeper:work envelope.operation_id
data remove storage keeper:work envelope.request_hash
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work envelope set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/invalid_request
execute if data storage keeper:bridge request{action:"HELLO"} run return run function keeper:action/hello
execute unless data storage keeper:runtime {verified:1} run return run function keeper:error/session_mismatch
execute unless data storage keeper:config installation_id run return run function keeper:error/installation_mismatch
execute unless data storage keeper:bridge request.installation_id run return run function keeper:error/installation_mismatch
data modify storage keeper:work compare set from storage keeper:config installation_id
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.installation_id
execute if score #different keeper matches 1 run return run function keeper:error/installation_mismatch
execute unless data storage keeper:runtime session_id run return run function keeper:error/session_mismatch
execute unless data storage keeper:bridge request.session_id run return run function keeper:error/session_mismatch
data modify storage keeper:work compare set from storage keeper:runtime session_id
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.session_id
execute if score #different keeper matches 1 run return run function keeper:error/session_mismatch
execute if data storage keeper:bridge request{action:"HEARTBEAT"} run return run function keeper:action/heartbeat
execute if data storage keeper:bridge request{action:"SNAPSHOT"} run return run function keeper:action/snapshot
execute if data storage keeper:bridge request{action:"REGISTER_CHEST"} run return run function keeper:action/register_chest
execute if data storage keeper:bridge request{action:"UNREGISTER_CHEST"} run return run function keeper:action/unregister_chest
execute if data storage keeper:bridge request{action:"ACTIVATE"} run return run function keeper:action/activate
execute if data storage keeper:bridge request{action:"PUBLISH_STATUS"} run return run function keeper:action/publish_status
execute if data storage keeper:bridge request{action:"COMPLETE"} run return run function keeper:action/complete
execute if data storage keeper:bridge request{action:"PAY"} run return run function keeper:action/pay
execute if data storage keeper:bridge request{action:"READ_RECEIPT"} run return run function keeper:action/read_receipt
execute if data storage keeper:bridge request{action:"READ_EVIDENCE"} run return run function keeper:action/read_evidence
execute if data storage keeper:bridge request{action:"READ_CLAIMS"} run return run function keeper:action/read_claims
execute if data storage keeper:bridge request{action:"ACK_CLAIMS"} run return run function keeper:action/ack_claims
execute if data storage keeper:bridge request{action:"PAUSE"} run return run function keeper:action/pause
execute if data storage keeper:bridge request{action:"RESOLVE_RECEIPT"} run return run function keeper:action/resolve_receipt
execute if data storage keeper:bridge request{action:"CHECKPOINT"} run return run function keeper:action/checkpoint
return run function keeper:error/unknown_action
