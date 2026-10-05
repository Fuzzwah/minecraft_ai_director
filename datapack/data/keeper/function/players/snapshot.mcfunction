tag @a remove keeper_eligible
data modify storage keeper:work players set value []
data modify storage keeper:work recipients set value []
execute as @a run function keeper:players/one
