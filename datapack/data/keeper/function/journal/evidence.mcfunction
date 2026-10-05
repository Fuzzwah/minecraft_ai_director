$data modify storage keeper:journal evidence.$(operation_id) set value {}
$data modify storage keeper:journal evidence.$(operation_id).before set from storage keeper:work before
$data modify storage keeper:journal evidence.$(operation_id).after set from storage keeper:work after
data remove storage keeper:work saved_before
data remove storage keeper:work saved_after
$data modify storage keeper:work saved_before set from storage keeper:journal evidence.$(operation_id).before
$data modify storage keeper:work saved_after set from storage keeper:journal evidence.$(operation_id).after
execute unless data storage keeper:work saved_before run return run function keeper:error/review_required
execute unless data storage keeper:work before run return run function keeper:error/review_required
data modify storage keeper:work compare set from storage keeper:work saved_before
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work before
execute if score #different keeper matches 1 run return run function keeper:error/review_required
execute unless data storage keeper:work saved_after run return run function keeper:error/review_required
execute unless data storage keeper:work after run return run function keeper:error/review_required
data modify storage keeper:work compare set from storage keeper:work saved_after
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work after
execute if score #different keeper matches 1 run return run function keeper:error/review_required
return 1
