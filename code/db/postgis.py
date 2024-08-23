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

# Execute a command: create datacamp_courses table
#cur.execute("""CREATE TABLE datacamp_courses(
#            course_id SERIAL PRIMARY KEY,
#            course_name VARCHAR (50) UNIQUE NOT NULL,
#            course_instructor VARCHAR (100) NOT NULL,
#            topic VARCHAR (20) NOT NULL);
#            """)
## Make the changes to the database persistent
#conn.commit()
# Close cursor and communication with the database


#cur = conn.cursor()
#cur.execute("""CREATE TABLE maps(
#        id SERIAL PRIMARY KEY,
#        name VARCHAR (250),
#        tags VARCHAR (250),
#        status VARCHAR (250),
#        access VARCHAR (250),
#        originFile VARCHAR (250),
#        mapid VARCHAR (250),
#        accessid VARCHAR (250),
#        action VARCHAR (250),
#        location geography(POINT));
#""")
#conn.commit()


def addDataDb(json,db="maps"):

    # Add data to the database
    # Connect to the database
    query =  "INSERT INTO maps (creator_id, space_id, asset_id, name, tags, status, access, originFile, mapid, accessid, action ,location) VALUES \
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s );"
    #Values in order of the query
    data = (json['creator_id'],
            json['space_id'],
            json['asset_id'],
            json['name'],
            json['tags'], 
            json['status'], 
            json['access'], 
            json['originFile'], 
            json['mapid'], 
            json['accessid'], 
            json['action'], 
            "Point("+str(json['location'][0])+" "+str(json['location'][1])+")")


    cur = conn.cursor()
    print(data)
    cur.execute(query,data)
    conn.commit()
    return {"data":"accepted","id":"1"}


def updateMapDataDb(jsonData,db="maps"):
    print(jsonData)
    if jsonData["action"] == "error":
        query =  "UPDATE  maps SET  action = %s  WHERE id = %s;"
        #Values in order of the query
        data = ("Error",
                jsonData['mapKey'])
        cur = conn.cursor()
        cur.execute(query,data)
        conn.commit()
        
    else:
        query =  "UPDATE  maps SET  action = %s, mapdata =%s,  location=%s, tilesurl=%s WHERE id = %s;"
        #Values in order of the query
        data = ("Ready",
                json.dumps(jsonData['mapData']), 
                "Point("+str(jsonData['mapData']['location']['coordinates'][0])+" "+str(jsonData['mapData']['location']['coordinates'][1])+")",
                jsonData['tilesURL'],
                jsonData['mapKey'])
        cur = conn.cursor()
        cur.execute(query,data)
        conn.commit()
        print("Data saved")


    return {"data":"saved"}


    



def getDataDb(db="maps"):
    # Add data to the database
    # Connect to the database
    print("Getting data from db")
    postgreSQL_select_Query = "select * from maps"
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(postgreSQL_select_Query)
    maps = cur.fetchall()
    print(maps)
    return maps

#get values based on lon and lat
def getDataDbMaps(lon,lat):
    print("Getting close data from db")
    print(lon,lat)
    postgreSQL_select_Query = "select * from maps where location <-> ST_MakePoint("+str(lon)+","+str(lat)+") > 1000"
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(postgreSQL_select_Query)
    maps = cur.fetchall()
    #maps = json.dumps(cur.fetchall(), indent=2)


    return maps

#get values based on lon and lat
def getDataDbMapsPoints(lon,lat):
    print("Getting close and make geo pints from db")
    print(lon,lat)

    #Get data from database
    postgreSQL_select_Query = "select name, tags,  mapid, ST_AsGeojson(location) AS geometry  from maps where location <-> ST_MakePoint("+str(lon)+","+str(lat)+") > 1000"
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(postgreSQL_select_Query)
    maps = json.loads(json.dumps(cur.fetchall(), indent=2))
    #print(maps)


    # make geopints
    geoJson = {"type": "FeatureCollection","features": []}
    for i in maps:
        GeoFeture = {
            "type": "Feature",
            "geometry": json.loads(i['geometry']),
            "title": i['name'],
            "tags": i['tags'],
            "mapid" : i['mapid'],

        }

        geoJson["features"].append(GeoFeture)
    return geoJson

####
## Missions
####
def getMissions(spaceID, status):
    print("Getting close data from db")
    postgreSQL_select_Query = "select * from missions "
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(postgreSQL_select_Query)
    maps = json.dumps(cur.fetchall(), indent=4, sort_keys=True, default=str)
    return maps


def getMission(id):
    print("Getting close data from db")
    postgreSQL_select_Query = "select * from missions  where id = '"+str(id)+"'"
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(postgreSQL_select_Query)
    mission = json.dumps(cur.fetchall(), indent=4, sort_keys=True, default=str)
    return mission