data modify storage keeper:work compare set from storage keeper:work player.uuid
execute store success score #different keeper run data modify storage keeper:work compare set from storage keeper:work pending[0].uuid
execute if score #different keeper matches 0 store result score #pending keeper run data get storage keeper:work pending[0].count
data remove storage keeper:work pending[0]
execute if data storage keeper:work pending[0] run function keeper:trigger/pending
