scoreboard players set #offset keeper 0
scoreboard players set #limit keeper 16
data modify storage keeper:work page_source set from storage keeper:work receipt.result.recipients
function keeper:page/copy
data modify storage keeper:bridge response.payload.recipients set from storage keeper:work page_items
data modify storage keeper:bridge response.payload.recipients_paged set value 1
execute store result storage keeper:bridge response.payload.recipient_count int 1 run scoreboard players get #total keeper
