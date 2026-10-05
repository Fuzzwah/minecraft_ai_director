$data modify storage keeper:journal receipts.$(operation_id) set from storage keeper:work receipt
data remove storage keeper:work stored
$data modify storage keeper:work stored set from storage keeper:journal receipts.$(operation_id)
execute unless data storage keeper:work stored run return run function keeper:error/review_required
execute unless data storage keeper:work receipt run return run function keeper:error/review_required
data modify storage keeper:work compare set from storage keeper:work stored
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work receipt
execute if score #different keeper matches 1 run return run function keeper:error/review_required
return 1
