from db.postgis import *
#from db.kafkaProducer import *
from db.sqsProducer import *
from db.meiliSearch import *
import json
import datetime


def setJsonValidate(jsonData):
    # Set the data from the reqyest to our data standrad
    # Connect to the database
    JsonStandrad = {
        "creator_id": jsonData.get('creator_id', '686eaeeb-383b-44d7-9754-4b2e7c0c11c7'),
        "name": jsonData.get('name', 'default'),
        "tags": jsonData.get('tags', []),
        "status": jsonData.get('status', 'unprocessed'),
        "space_id": jsonData.get('space_id', '686eaeeb-383b-44d7-9754-4b2e7c0c11c7'),
        "asset_id": jsonData.get('asset_id', '686eaeeb-383b-44d7-9754-4b2e7c0c11c7'),
        "access": jsonData.get('access', 'private'),
        "originFile": jsonData.get('originFile', ''),
        "mapid": jsonData.get('mapid', ''),
        "accessid": jsonData.get('accessid', ''),
        "action" : jsonData.get('action', ''),
        "location": jsonData.get('location', [-118.4079,33.9434]),
        "recordtime": jsonData.get('recordtime', '2020-01-01 00:00:00.000000')
        
    }
    return JsonStandrad


def mapsSearch(payload):
    #Doing search of maps towards the meilisearch database
    print(payload)
    if payload == None:
        return '{"error":"Missing search"}'
    else:
        print(payload)
        return meiliSearch(payload)



def maps(payload,request):
    print(request.method)

    if request.method   == "POST":
        print("Update database")
        payload["recordtime"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        if payload.get("mapKey"):
            return updateMapDataDb(payload,"maps")
        else:
            return '{"error":"Missing id"}'
    if request.method == "GET":
        print("Search for maps")
        #updateDataDb(id,jsonData)
        lon = 1 #request.args.get('lon', default = 1, type = float)
        lat = 2 #request.args.get('lat', default = 1, type = float)
        returnType = "none"#request.args.get('return', default = "none")
        print(lon)
        print(lat)
        if lon == 1 and lat == 2:
            #We have a no lon ang lat lets dump all data
            return getDataDb("maps")
        else:
            #We have a lon and lat lets find the closest
            if returnType == "points":
                return getDataDbMapsPoints(lon,lat)
            else:
                return getDataDbMaps(lon,lat)
    if request.method == "PUT":
        print("Add to database")
        payload["recordtime"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        clearJson = setJsonValidate(payload)
        #addToSQS(clearJson)
        return addDataDb(clearJson,"maps")
    
