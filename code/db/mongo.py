import pymongo
import json
import os
from bson.objectid import ObjectId
from bson.json_util import dumps

#uri = os.getenv('MONGOURL', 'mongodb://admin:PpcfCj0Yyrh5S7GkFToaR0OGRGEasAucfxuTh4Tl8L4flVBBvyFvpLYKicijXSaMmqIX@dw-db:27017/ollebo?authSource=admin')
#myclient = pymongo.MongoClient(uri)
#mydb = myclient["ollebo"]
## Add data to the database
#mycol = mydb["maps"]


def addingIndexes():
    print("Adding indexes")
    mycol.create_index([ ("location", "2dsphere") ])





def eventAddDataDb(json):
    # Add data to the database
    # Connect to the database
    mycol = mydb["event"]

    x = mycol.insert_one(json)
    return {"data":"accepted","id":dumps(x.inserted_id)}



def addDataDb(json,db="maps"):
    # Add data to the database
    # Connect to the database
    mycol = mydb[db]
    x = mycol.insert_one(json)
    return {"data":"accepted","id":dumps(x.inserted_id)}

def updateDataDb(id,json,db="maps"):
    # Add data to the database
    # Connect to the database
    filter = {"_id": ObjectId(id)}

    updateJson = { "$set":  json  }
    print(updateJson)
    mycol = mydb[db]
    x = mycol.update_one(filter,updateJson)
    returnData= {"update":x.modified_count}
    
    return returnData

def updateMapDataDb(json,db="maps"):
    # Add data to the database
    # Connect to the database
    filter = {"mapid": json["mapid"]}
    print(filter)
    updateJson = { "$set":  json  }
    print(updateJson)
    mycol = mydb[db]
    x = mycol.update_one(filter,updateJson)
    returnData= {"update":x.modified_count}
    
    return returnData




def getDataDb(db="maps"):
    # Add data to the database
    # Connect to the database
    mycol = mydb[db]
    x = mycol.find()
    return dumps(x)

#get values based on lon and lat
def getDataDbMaps(lon,lat):
    query = { "location": { "$nearSphere": { "$geometry": { "type": "Point",  "coordinates": [ lon, lat ] } } } } 
    x = mycol.find(query)
    #Convert to GEOJson format for the map
    geoJson = {"type": "FeatureCollection","features": []}
    for i in x:
        GeoFeture = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(i['location']['coordinates'][0]), float(i['location']['coordinates'][1])]
            },
            "title": i['name'],
            "tags": i['tags'],
            "status": i['status'],
            "access": i['access'],
            "url"   : i['url'],
            "added" : i['recordtime'],
            "mapid" : i['mapid'],

        }

        geoJson["features"].append(GeoFeture)

    return geoJson


#get values based on lon and lat
def getDataDbMapsPoints(lon,lat):
    query = { "location": { "$nearSphere": { "$geometry": { "type": "Point",  "coordinates": [ lon, lat ] } } } } 
    x = mycol.find(query)
    #Convert to GEOJson format for the map
    geoJson = {"type": "FeatureCollection","features": []}
    for i in x:
        GeoFeture = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(i['location']['coordinates'][0]), float(i['location']['coordinates'][1])]
            },
            "title": i['name'],
            "tags": i['tags'],

        }

        geoJson["features"].append(GeoFeture)

    return geoJson


#addingIndexes()