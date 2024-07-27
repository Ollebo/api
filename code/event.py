#from db.kafkaProducer import *
from db.natsQue import *
from db.addTimescale import *


def event(payload,request,mission_id):
    # Make event id 
    #addEvent(payload,"events_data")
    return addEvent(payload,"events_data",mission_id)
                   

