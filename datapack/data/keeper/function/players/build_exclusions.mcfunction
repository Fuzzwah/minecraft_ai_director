data modify storage keeper:config exclusion_map set value {}
data modify storage keeper:work exclusions set from storage keeper:config excluded
execute if data storage keeper:work exclusions[0] run function keeper:players/map_exclusion
