scoreboard objectives add keeper dummy
scoreboard objectives add keeper_quest trigger
scoreboard objectives add keeper_status trigger
scoreboard objectives add keeper_claim trigger
scoreboard objectives add keeper_help trigger
scoreboard players set #loaded keeper 1
execute unless data storage keeper:config configured run data modify storage keeper:config configured set value 0
execute unless data storage keeper:runtime revision run data modify storage keeper:runtime revision set value 0
execute unless data storage keeper:runtime epoch run data modify storage keeper:runtime epoch set value 0
execute store result score #epoch keeper run data get storage keeper:runtime epoch
scoreboard players add #epoch keeper 1
execute store result storage keeper:runtime epoch int 1 run scoreboard players get #epoch keeper
data modify storage keeper:runtime enabled set value 0
data modify storage keeper:runtime verified set value 0
data modify storage keeper:runtime heartbeat set value 0
execute unless data storage keeper:runtime quest run data modify storage keeper:runtime quest set value {}
execute unless data storage keeper:runtime pending run data modify storage keeper:runtime pending set value []
execute unless data storage keeper:runtime claims run data modify storage keeper:runtime claims set value []
execute unless data storage keeper:runtime claim_cursor run data modify storage keeper:runtime claim_cursor set value 0
execute unless data storage keeper:journal receipts run data modify storage keeper:journal receipts set value {}
data modify storage keeper:work hexchars set value ["0","1","2","3","4","5","6","7","8","9","a","b","c","d","e","f"]
bossbar add keeper:quest {"text":"The Keeper: paused"}
bossbar set keeper:quest visible false
