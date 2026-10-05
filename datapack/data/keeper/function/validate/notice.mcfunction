execute if data storage keeper:bridge request.payload.message store success score #valid keeper run function keeper:validate/message
execute if data storage keeper:bridge request.payload.message unless score #valid keeper matches 1 run return fail
execute if data storage keeper:bridge request.payload.audience store success score #valid keeper run function keeper:validate/audience
execute if data storage keeper:bridge request.payload.audience unless score #valid keeper matches 1 run return fail
execute if data storage keeper:bridge request.payload.title store success score #valid keeper run function keeper:validate/title
execute if data storage keeper:bridge request.payload.title unless score #valid keeper matches 1 run return fail
execute if data storage keeper:bridge request.payload.sound store success score #valid keeper run function keeper:validate/sound
execute if data storage keeper:bridge request.payload.sound unless score #valid keeper matches 1 run return fail
return 1
