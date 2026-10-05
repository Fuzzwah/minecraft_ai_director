data modify storage keeper:work compare set from storage keeper:runtime quest.id
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:bridge request.payload.quest.id
execute if score #different keeper matches 0 run scoreboard players set #samequest keeper 1
