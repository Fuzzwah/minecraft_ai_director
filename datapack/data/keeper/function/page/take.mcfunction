data modify storage keeper:work page_items append from storage keeper:work page_source[0]
data remove storage keeper:work page_source[0]
scoreboard players remove #left keeper 1
execute if score #left keeper matches 1.. if data storage keeper:work page_source[0] run function keeper:page/take
