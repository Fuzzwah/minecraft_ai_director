data modify storage keeper:work page_items set value []
scoreboard players operation #skip keeper = #offset keeper
scoreboard players operation #left keeper = #limit keeper
execute if score #skip keeper matches 1.. if data storage keeper:work page_source[0] run function keeper:page/skip
execute if data storage keeper:work page_source[0] run function keeper:page/take
