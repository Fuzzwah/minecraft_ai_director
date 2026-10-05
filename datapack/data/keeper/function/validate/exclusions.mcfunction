execute store success score #valid keeper run function keeper:validate/exclusion
execute unless score #valid keeper matches 1 run scoreboard players set #bad keeper 1
data remove storage keeper:work exclusions[0]
execute if data storage keeper:work exclusions[0] run function keeper:validate/exclusions
