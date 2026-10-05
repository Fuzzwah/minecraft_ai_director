data modify storage keeper:work compare set from storage keeper:runtime unresolved_chest
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work operation_id
execute if score #different keeper matches 0 run data remove storage keeper:runtime unresolved_chest
