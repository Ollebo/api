from pymongo import MongoClient
import redis
import uuid
from datetime import datetime
# Connect to the MongoDB, change the connection string per your MongoDB environment
uri = "mongodb://root:example@mongo:27017/mantiser?authSource=admin"
client = MongoClient(uri)
r = redis.Redis(host='redis', port=6379, db=0)
# Set the db object to point to the business database
db=client.mantiser
# Showcasing the count() method of find, count the total number of 5 ratings 


def getUserId(api_key):
    redisHasKey = r.exists(api_key)
    if redisHasKey:
        print("return key from redis")
        return r.get(api_key).decode()
    else:
        userData = db.users.find_one({'api_key':api_key})
        print(userData)
        if userData == None:
            print("APIkey dont match")
            return False
        else:
            r.set(api_key, str(userData['keycloakID']))
            return str(userData['keycloakID'])



def getProjectID(userid,projectname):
    requestid=str(userid)+str(projectname)
    redisHasKey = r.exists(requestid)
    if redisHasKey:
        print("return key from redis"+str(r.get(requestid).decode()) )
        return r.get(requestid).decode()
    else:
        print(userid)
        print(projectname)
        projectData = db.project.find_one({'userid':str(userid),'name':projectname})
        print(projectData)
        if projectData == None:
            print("Project dont match create ")
            uuiddata = uuid.uuid4()
            data ={
                "name": projectname,
                "status": 'new',
                "userid": userid,
                "uuid" : str(uuiddata),
                "timestamp": str(datetime.now())

            }
            id = db.project.insert_one(data)
            return id.inserted_id
        else:
            r.set(requestid, str(projectData['uuid']))
            return projectData['uuid'].decode()


def saveEvent(data):
    '''
    Save the icomming event to mongo
    '''
    id = db.event.insert_one(data)
    return id.inserted_id