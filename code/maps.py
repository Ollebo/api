from db.mongo import *
from db.kafka import *
import json
import datetime

def maps(payload,request):

    if request.method   == "POST":
        payload["recordtime"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        return {"status": "ok", "data": "Database had bean updated"}
    if request.method == "GET":
        #updateDataDb(id,jsonData)
        lon = request.args.get('lon', default = 1, type = float)
        lat = request.args.get('lat', default = 1, type = float)
        print(lon)
        print(lat)
        if lon == 1 and lat == 1:
            #We have a no lon ang lat lets dump all data
            return getDataDb()
        else:
            #We have a lon and lat lets find the closest
            return getDataDb(lon,lat)
    if request.method == "PUT":
        payload["recordtime"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        addToKafka(payload)
        return addDataDb(payload)
