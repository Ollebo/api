from db.kafkaProducer import *


def event(payload,request):
    # Make event id 
    addToKafkaEvent(payload)
    return {"status": "ok", "data": "Event has bean accepted"}
                   

