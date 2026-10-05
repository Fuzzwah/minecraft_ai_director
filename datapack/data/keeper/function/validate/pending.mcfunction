data remove storage keeper:work uuid
data modify storage keeper:work uuid set from storage keeper:work pending[0].uuid
execute store success score #valid keeper run function keeper:validate/uuid
execute unless score #valid keeper matches 1 run scoreboard players set #bad keeper 1
execute store success score #valid keeper run function keeper:validate/pending_count
execute unless score #valid keeper matches 1 run scoreboard players set #bad keeper 1
data remove storage keeper:work pending[0]
execute if data storage keeper:work pending[0] run function keeper:validate/pending
