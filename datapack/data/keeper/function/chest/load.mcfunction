$execute store success score #loaded keeper run forceload query $(x) $(z)
execute if score #loaded keeper matches 0 run data modify storage keeper:work chest.forceload_owned set value 1
$execute if score #loaded keeper matches 0 store success score #loaded keeper run forceload add $(x) $(z)
