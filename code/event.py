#from db.kafkaProducer import *
from db.sqsProducer import *


def event(payload,request):
    # Make event id 
    addToSQSEvent(payload)
    return {"status": "ok", "data": "Event has bean accepted"}
                   

