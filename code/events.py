from db.mongo import *
from db.meiliSearch import *
from bson.json_util import dumps
import datetime
import uuid


def event(payload,request):
    # Make event id 
    payload["id"] = str(uuid.uuid4())
    payload["location"] = {
          "type": "Point",
          "coordinates": [float(payload["_geo"]["lat"]), float(payload["_geo"]["lng"])]
    }
    #Adding to Mongodb
    payload["recordtime"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
    mongoDBReturn= eventAddDataDb(payload)
    #Adding to MeiliSearch
    payload["mongoidb"] = mongoDBReturn
    payload["_id"] = json.loads(dumps(payload["_id"]))
    eventaddDatamMe(payload)


    return {"status": "ok", "data": "Event has bean added"}
                   

