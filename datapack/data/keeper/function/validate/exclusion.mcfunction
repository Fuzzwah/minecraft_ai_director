execute unless data storage keeper:work exclusions[0] run return run function keeper:error/config_invalid
data modify storage keeper:work shape set from storage keeper:work exclusions[0]
data remove storage keeper:work shape.uuid
data modify storage keeper:work empty set value {}
execute store success score #different keeper run data modify storage keeper:work shape set from storage keeper:work empty
execute if score #different keeper matches 1 run return run function keeper:error/config_invalid
data remove storage keeper:work uuid
data modify storage keeper:work uuid set from storage keeper:work exclusions[0].uuid
return run function keeper:validate/uuid
