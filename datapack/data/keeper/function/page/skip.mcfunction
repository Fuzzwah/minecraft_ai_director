data remove storage keeper:work page_source[0]
scoreboard players remove #skip keeper 1
execute if score #skip keeper matches 1.. if data storage keeper:work page_source[0] run function keeper:page/skip
