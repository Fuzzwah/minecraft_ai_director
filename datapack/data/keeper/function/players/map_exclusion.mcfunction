data modify storage keeper:work u0 set from storage keeper:work exclusions[0].uuid[0]
data modify storage keeper:work u1 set from storage keeper:work exclusions[0].uuid[1]
data modify storage keeper:work u2 set from storage keeper:work exclusions[0].uuid[2]
data modify storage keeper:work u3 set from storage keeper:work exclusions[0].uuid[3]
function keeper:players/map_key with storage keeper:work
data remove storage keeper:work exclusions[0]
execute if data storage keeper:work exclusions[0] run function keeper:players/map_exclusion
