import pymongo
import json
from bson.objectid import ObjectId
from bson.json_util import dumps


myclient = pymongo.MongoClient("mongodb://root:example@mongo:27017/ollebo?authSource=admin")
mydb = myclient["ollebo"]
# Add data to the database
mycol = mydb["maps"]


def eventAddDataDb(json):
    # Add data to the database
    # Connect to the database
    mycol = mydb["event"]

    x = mycol.insert_one(json)
    return {"data":"accepted","id":dumps(x.inserted_id)}



def addDataDb(json):
    # Add data to the database
    # Connect to the database

    x = mycol.insert_one(json)
    return {"data":"accepted","id":dumps(x.inserted_id)}

def updateDataDb(id,json):
    # Add data to the database
    # Connect to the database
    filter = {"_id": ObjectId(id)}
    updateJson = { "$set":  json  }

    x = mycol.update_one(filter,updateJson)
    print(x.modified_count)

def getDataDb():
    # Add data to the database
    # Connect to the database
    x = mycol.find()
    return dumps(x)

#get values based on lon and lat
def getDataDb(lon,lat):
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
            "properties": {
                "title": i['name'],
                "tags": i['tags'],
                "status": i['status'],
                "access": i['access'],
                "url"   : "https://maps.ollebo.com/layers/"+str(i['accessid'])+"/"+str(i['mapid']),

            }
        }

        geoJson["features"].append(GeoFeture)

    return geoJson