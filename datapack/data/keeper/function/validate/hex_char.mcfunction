data modify storage keeper:work char set value ""
$data modify storage keeper:work char set string storage keeper:work hex $(start) $(end)
scoreboard players set #char keeper 0
execute if data storage keeper:work {char:"0"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"1"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"2"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"3"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"4"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"5"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"6"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"7"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"8"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"9"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"a"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"b"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"c"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"d"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"e"} run scoreboard players set #char keeper 1
execute if data storage keeper:work {char:"f"} run scoreboard players set #char keeper 1
