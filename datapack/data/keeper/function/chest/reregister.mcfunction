data modify storage keeper:work compare set from storage keeper:config chest
data remove storage keeper:work compare.forceload_owned
data remove storage keeper:work chest.forceload_owned
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work chest
execute if score #different keeper matches 1 run return run function keeper:error/already_registered
execute store success score #valid keeper run function keeper:chest/registered
execute unless score #valid keeper matches 1 run return fail
data modify storage keeper:bridge response.payload.chest set from storage keeper:config chest
return run function keeper:bridge/ok
