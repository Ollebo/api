import psycopg2
import json
import os
from psycopg2.extras import RealDictCursor
import sys


print("Connecting to database")
try:
    conn = psycopg2.connect(database = os.environ.get('POSTGRES_DB', 'ollebo'), 
                        user = os.environ.get('POSTGRES_USER', 'ollebo'), 
                        host= os.environ.get('POSTGRES_HOST', 'postgis'),
                        password = os.environ.get('POSTGRES_PASSWORD', 'olleb0'),
                        port = 5432 ,sslmode='disable')
except:
    print("ERROR: Could not connect to Postgres instance.")
    sys.exit()


def addEvent(jsonData,db="mission_data",mission_id="none"):

    #Setting default values 
    type = jsonData['type']
    db_insert_time = "now()"
    
    try:
        temp = jsonData['temp']
    except:
        temp = 0
    try:
        humidity = jsonData['humidity']
    except:
        humidity = 0
    try:    
        geopoint = jsonData['geopoint']
    except:
        geopoint = [0,0]
    try:
        img = jsonData['img']
    except:
        img = "none"
    try:
        x = jsonData['x']
    except:
        x = 0
    try:
        y = jsonData['y']
    except:
        y = 0
    try:
        z = jsonData['z']
    except:
        z = 0
    try:
        data = jsonData['data']
    except:
        data = 0
    try:
        jsonDataSql = json.dumps(jsonData['jsonData'])
    except:
        jsonDataSql = json.dumps({"value":"none"})
    try:
        device = jsonData['device']
    except:
        device = "none"
    try:
        deviceJSON = json.dumps(jsonData['deviceJson'])
    except:
        deviceJSON = json.dumps({"value":"none"})

    # Add data to the database
    # Connect to the database
    query =  "INSERT INTO mission_data (db_insert_time, mission, type, temperature, humidity, location, img, x, y, z, data, jsonData, device, deviceJSON ) VALUES \
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s );"

    #Values in order of the query
    data = (db_insert_time,
            mission_id,
            type, 
            temp,
            humidity,
            "Point("+str(geopoint[0])+" "+str(geopoint[1])+")",
            img,
            x,
            y,
            z,
            data,
            jsonDataSql,
            device,
            deviceJSON


    )

    cur = conn.cursor()
    print(data)
    print(query)
    cur.execute(query,data)
    conn.commit()
    return {"data":"stored"}