# -*- coding: utf-8 -*-
import time
import time
import json
from events import event



def handler(event, context):
    # Your code goes here!
    print(event)
    payload ={}
    request = {  
          "method": "GET"
    }

    try:
        payload = json.loads(event["body"])
    except:
        payload = event["body"]
    returnFromFunction = event(payload,request)
    reply = {} 
    reply['body'] = returnFromFunction
    reply["statusCode"] = 200 
    reply.update({"headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Credentials": True}})

    return reply