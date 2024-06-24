# -*- coding: utf-8 -*-
import time
import time
import json
from event import event



def handler(lamda_event, context):
    # Your code goes here!
    print(lamda_event)
    payload ={}
    request = {  
          "method": "PUT"
    }
    try:
        payload = json.loads(lamda_event["body"])
    except:
        payload = lamda_event["body"]
    returnFromFunction = event(payload,request)
    reply = {} 
    reply['body'] = returnFromFunction
    reply["statusCode"] = 200 
    reply.update({"headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Credentials": True}})

    return reply