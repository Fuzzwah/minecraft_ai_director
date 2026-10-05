bossbar set keeper:quest visible false
execute unless data storage keeper:runtime {enabled:1} run return 0
execute unless data storage keeper:runtime quest.id run return 0
function keeper:players/snapshot
bossbar set keeper:quest players @a[tag=keeper_eligible]
execute store result bossbar keeper:quest max run data get storage keeper:runtime quest.quantity
function keeper:chest/registered
execute unless score #chest keeper matches 1 run return 0
function keeper:chest/count
scoreboard players operation #shown keeper = #found keeper
execute store result score #goal keeper run data get storage keeper:runtime quest.quantity
scoreboard players operation #shown keeper < #goal keeper
execute if data storage keeper:runtime quest{item_code:0} run bossbar set keeper:quest name {"text": "The Keeper: iron ingot ", "extra": [{"score": {"name": "#shown", "objective": "keeper"}}, {"text": "/"}, {"nbt": "quest.quantity", "storage": "keeper:runtime", "plain": true}]}
execute if data storage keeper:runtime quest{item_code:1} run bossbar set keeper:quest name {"text": "The Keeper: copper ingot ", "extra": [{"score": {"name": "#shown", "objective": "keeper"}}, {"text": "/"}, {"nbt": "quest.quantity", "storage": "keeper:runtime", "plain": true}]}
execute if data storage keeper:runtime quest{item_code:2} run bossbar set keeper:quest name {"text": "The Keeper: gold ingot ", "extra": [{"score": {"name": "#shown", "objective": "keeper"}}, {"text": "/"}, {"nbt": "quest.quantity", "storage": "keeper:runtime", "plain": true}]}
execute if data storage keeper:runtime quest{item_code:3} run bossbar set keeper:quest name {"text": "The Keeper: coal ", "extra": [{"score": {"name": "#shown", "objective": "keeper"}}, {"text": "/"}, {"nbt": "quest.quantity", "storage": "keeper:runtime", "plain": true}]}
execute if data storage keeper:runtime quest{item_code:4} run bossbar set keeper:quest name {"text": "The Keeper: redstone ", "extra": [{"score": {"name": "#shown", "objective": "keeper"}}, {"text": "/"}, {"nbt": "quest.quantity", "storage": "keeper:runtime", "plain": true}]}
execute if data storage keeper:runtime quest{item_code:5} run bossbar set keeper:quest name {"text": "The Keeper: lapis lazuli ", "extra": [{"score": {"name": "#shown", "objective": "keeper"}}, {"text": "/"}, {"nbt": "quest.quantity", "storage": "keeper:runtime", "plain": true}]}
execute if data storage keeper:runtime quest{item_code:6} run bossbar set keeper:quest name {"text": "The Keeper: oak log ", "extra": [{"score": {"name": "#shown", "objective": "keeper"}}, {"text": "/"}, {"nbt": "quest.quantity", "storage": "keeper:runtime", "plain": true}]}
execute if data storage keeper:runtime quest{item_code:7} run bossbar set keeper:quest name {"text": "The Keeper: bread ", "extra": [{"score": {"name": "#shown", "objective": "keeper"}}, {"text": "/"}, {"nbt": "quest.quantity", "storage": "keeper:runtime", "plain": true}]}
execute if data storage keeper:runtime quest{item_code:8} run bossbar set keeper:quest name {"text": "The Keeper: carrot ", "extra": [{"score": {"name": "#shown", "objective": "keeper"}}, {"text": "/"}, {"nbt": "quest.quantity", "storage": "keeper:runtime", "plain": true}]}
execute if data storage keeper:runtime quest{item_code:9} run bossbar set keeper:quest name {"text": "The Keeper: cooked beef ", "extra": [{"score": {"name": "#shown", "objective": "keeper"}}, {"text": "/"}, {"nbt": "quest.quantity", "storage": "keeper:runtime", "plain": true}]}
execute store result bossbar keeper:quest value run scoreboard players get #shown keeper
bossbar set keeper:quest visible true
