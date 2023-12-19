from db.mongo import *
from db.kafkaProducer import *
import json
import datetime

def project(payload,request):

    if request.method   == "POST":
        payload["recordtime"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        #return {"status": "ok", "data": "Database had bean updated"}
        return updateDataDb(payload['id'],payload,"project")
    if request.method == "GET":
        #updateDataDb(id,jsonData)
        return getDataDb("project")

    if request.method == "PUT":
        payload["recordtime"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        addToKafka(payload)
        return addDataDb(payload,"project")