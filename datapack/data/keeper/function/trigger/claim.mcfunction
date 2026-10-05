scoreboard players set @s keeper_claim 0
execute unless data storage keeper:runtime {enabled:1} run return run tellraw @s {"text":"[The Keeper] Service paused; your pending rewards are retained."}
data modify storage keeper:work claim set value {}
data modify storage keeper:work claim.uuid set from entity @s UUID
data modify storage keeper:work claims set from storage keeper:runtime claims
scoreboard players set #duplicate keeper 0
execute if data storage keeper:work claims[0] run function keeper:claims/dedup
execute if score #duplicate keeper matches 1 run return run tellraw @s {"text":"[The Keeper] Your claim is already queued."}
execute store result score #length keeper run data get storage keeper:runtime claims
execute if score #length keeper matches 64.. run return run tellraw @s {"text":"[The Keeper] Claim queue is full. Please try again later."}
execute store result score #cursor keeper run data get storage keeper:runtime claim_cursor
execute if score #cursor keeper matches 2147483646.. run return run tellraw @s {"text":"[The Keeper] Claim queue counter requires operator maintenance."}
scoreboard players add #cursor keeper 1
execute store result storage keeper:runtime claim_cursor int 1 run scoreboard players get #cursor keeper
execute store result storage keeper:work claim.cursor int 1 run scoreboard players get #cursor keeper
data modify storage keeper:runtime claims append from storage keeper:work claim
tellraw @s {"text":"[The Keeper] Claim queued. Delivery uses your first empty Ender Chest slot."}
