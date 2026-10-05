data modify storage keeper:work compare set from storage keeper:work claim.uuid
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work claims[0].uuid
execute if score #different keeper matches 0 run scoreboard players set #duplicate keeper 1
data remove storage keeper:work claims[0]
execute if data storage keeper:work claims[0] run function keeper:claims/dedup
