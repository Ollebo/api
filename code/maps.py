from db.postgis import *
#from db.kafkaProducer import *
#from db.sqsProducer import *
import json
import datetime


def setJsonValidate(jsonData):
    # Set the data from the reqyest to our data standrad
    # Connect to the database
    JsonStandrad = {
        "name": jsonData.get('name', 'default'),
        "tags": jsonData.get('tags', []),
        "status": jsonData.get('status', 'unprocessed'),
        "access": jsonData.get('access', 'private'),
        "originFile": jsonData.get('originFile', ''),
        "mapid": jsonData.get('mapid', ''),
        "accessid": jsonData.get('accessid', ''),
        "action" : jsonData.get('action', ''),
        "location": jsonData.get('location', [-118.4079,33.9434]),
        "recordtime": jsonData.get('recordtime', '2020-01-01 00:00:00.000000')
        
    }
    return JsonStandrad



def maps(payload,request):
    print(request["method"])

    if request["method"]   == "POST":
        print("Update database")
        payload["recordtime"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        if payload.get("id"):
            return updateMapDataDb(payload["id"],payload,"maps")
        else:
            return '{"error":"Missing id"}'
    if request["method"] == "GET":
        print("Search for maps")
        #updateDataDb(id,jsonData)
        lon = 1 #request.args.get('lon', default = 1, type = float)
        lat = 2 #request.args.get('lat', default = 1, type = float)
        returnType = "none"#request.args.get('return', default = "none")
        print(lon)
        print(lat)
        if lon == 1 and lat == 1:
            #We have a no lon ang lat lets dump all data
            return getDataDb("maps")
        else:
            #We have a lon and lat lets find the closest
            if returnType == "points":
                return getDataDbMapsPoints(lon,lat)
            else:
                return getDataDbMaps(lon,lat)
    if request["method"] == "PUT":
        print("Add to database")
        payload["recordtime"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        clearJson = setJsonValidate(payload)
        #addToSQS(clearJson)
        return addDataDb(clearJson,"maps")
    
