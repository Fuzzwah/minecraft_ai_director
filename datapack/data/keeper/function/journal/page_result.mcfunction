data modify storage keeper:work page_source set from storage keeper:work receipt.result.recipients
function keeper:page/copy
data modify storage keeper:bridge response.payload.receipt.result.recipients set from storage keeper:work page_items
