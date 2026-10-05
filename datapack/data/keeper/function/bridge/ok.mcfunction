data modify storage keeper:bridge response.status set value "OK"
data modify storage keeper:bridge response.revision set from storage keeper:runtime revision
return 1
