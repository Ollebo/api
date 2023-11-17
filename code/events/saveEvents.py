import datetime
import uuid
from bson.json_util import dumps
from db.mongo import *
from db.meiliSearch import *
import json



def saveEvent(payload): 
    payload["id"] = str(uuid.uuid4())

    try:
        payload["location"] = {
              "type": "Point",
              "coordinates": [float(payload["_geo"]["lat"]), float(payload["_geo"]["lng"])]
        }
    except:
        payload["location"] = {
              "type": "Point",
              "coordinates": [0,0]
        }
    #Adding to Mongodb
    payload["recordtime"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
    mongoDBReturn= eventAddDataDb(payload)
    #Adding to MeiliSearch
    payload["mongoidb"] = mongoDBReturn
    payload["_id"] = json.loads(dumps(payload["_id"]))
    eventaddDatamMe(payload)
