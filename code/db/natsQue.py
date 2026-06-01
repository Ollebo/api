import asyncio
import nest_asyncio
import datetime
import json
import os
import nats
from nats.errors import TimeoutError

nest_asyncio.apply()

async def addNats(to,text):

    nc = await nats.connect("{}".format(os.getenv('NATS')))
    js = nc.jetstream()

    await js.publish(to, json.dumps(text).encode('utf8'))

    await nc.close()


def addToNats(to,dataJson):
    json_upload = {
        "data": dataJson,
        "timestamp": datetime.datetime.now().isoformat()


    } 



    asyncio.run(addNats(to,json_upload))
    #addNats(to,json_upload)
    return {
           "deliverd:{0}".format(to):"ok" 
    }