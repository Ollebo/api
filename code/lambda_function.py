# -*- coding: utf-8 -*-
import time
import time
import json
from maps import maps



print("run lamda maps")

def handler(event, context):
    # Your code goes here!
    print(event)
    payload ={}
    request = {  
          "method": "put"
    }
    try:
      request["method"] = event["requestContext"]["http"]["method"] 
    except:
      print("An exception occurred")
    try:
      request["method"] = event["httpMethod"]
    except:
      print("An exception occurred")

    try:
        payload = json.loads(event["body"])
    except:
        payload = event["body"]
    returnFromFunction = maps(payload,request)
    reply = {} 
    reply['body'] = returnFromFunction
    reply["statusCode"] = 200 
    reply.update({"headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Credentials": True}})
    return reply
    