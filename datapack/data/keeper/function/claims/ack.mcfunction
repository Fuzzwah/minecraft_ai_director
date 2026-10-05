execute store result score #first keeper run data get storage keeper:runtime claims[0].cursor
execute if score #first keeper > #ack keeper run return 0
data remove storage keeper:runtime claims[0]
execute if data storage keeper:runtime claims[0] run function keeper:claims/ack
