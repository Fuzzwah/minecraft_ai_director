data modify storage keeper:bridge response.payload set from storage keeper:work receipt.result
scoreboard players set #total keeper 0
execute if data storage keeper:work receipt.result.recipients store result score #total keeper run data get storage keeper:work receipt.result.recipients
execute if score #total keeper matches 17.. run function keeper:journal/publish_recipients
