execute unless data storage keeper:runtime unresolved_chest run return run function keeper:error/review_required
execute unless data storage keeper:bridge request.payload.review_of run return run function keeper:error/review_required
data modify storage keeper:work compare set from storage keeper:runtime unresolved_chest
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.review_of
execute if score #different keeper matches 1 run return run function keeper:error/review_required
