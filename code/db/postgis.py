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


def addDataDb(json, db="maps"):
    query = (
        "INSERT INTO maps (creator_id, space_id, asset_id, name, tags, status, "
        "access, originFile, mapid, accessid, action, location) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
    )
    data = (
        json['creator_id'],
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
        "Point({} {})".format(json['location'][0], json['location'][1]),
    )

    cur = conn.cursor()
    try:
        cur.execute(query, data)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("ERROR addDataDb failed: mapid={} err={}".format(json.get('mapid'), e))
        raise
    return {"data": "accepted", "mapid": json.get('mapid')}


def updateMapDataDb(jsonData, db="maps"):
    mapid = jsonData['mapid']
    action = jsonData['action']
    if action == "error":
        query = "UPDATE maps SET action = %s WHERE mapid = %s;"
        data = (action, mapid)
    else:
        mapdata_blob = json.dumps({
            **jsonData['mapData'],
            'inputType': jsonData.get('inputType'),
            'variants': jsonData.get('variants'),
        })
        coords = jsonData['mapData']['location']['coordinates']
        query = (
            "UPDATE maps SET action = %s, mapdata = %s, location = %s, tilesurl = %s "
            "WHERE mapid = %s;"
        )
        data = (
            action,
            mapdata_blob,
            "Point({} {})".format(coords[0], coords[1]),
            jsonData['tilesURL'],
            mapid,
        )

    cur = conn.cursor()
    try:
        cur.execute(query, data)
    except Exception as e:
        conn.rollback()
        print("ERROR updateMapDataDb failed: mapid={} action={} err={}".format(mapid, action, e))
        raise
    rowcount = cur.rowcount
    conn.commit()
    if rowcount == 0:
        print("ERROR updateMapDataDb no row matched: mapid={} action={}".format(mapid, action))
        return {"error": "unknown mapid", "mapid": mapid}
    return {"data": "saved", "mapid": mapid}


    



def getDataDb(db="maps"):
    # Add data to the database
    # Connect to the database
    print("Getting data from db all")
    postgreSQL_select_Query = "select *, ST_AsGeoJSON(location),TO_CHAR(created_at, 'YYYY-MM-DD') AS created_at, TO_CHAR(updated_at, 'YYYY-MM-DD') AS updated_at from maps"
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(postgreSQL_select_Query)
    maps = cur.fetchall()
    print(maps)
    return maps

#get values based on lon and lat
def getDataDbMaps(lon,lat):
    print("Getting close data from db ")
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


def missionExists(mission_id):
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM missions WHERE id = %s LIMIT 1", (str(mission_id),))
        return cur.fetchone() is not None
    except Exception as e:
        print("missionExists failed: {}".format(e))
        try:
            conn.rollback()
        except Exception:
            pass
        return False


####
## Events / mission_data
####
def addEvent(jsonData, db="mission_data", mission_id="none"):
    type = jsonData.get('type', 'none')
    db_insert_time = "now()"

    temp = jsonData.get('temp', 0)
    humidity = jsonData.get('humidity', 0)
    geopoint = jsonData.get('geopoint', [0, 0])
    img = jsonData.get('img', "none")
    x = jsonData.get('x', 0)
    y = jsonData.get('y', 0)
    z = jsonData.get('z', 0)
    data_val = jsonData.get('data', 0)
    try:
        jsonDataSql = json.dumps(jsonData['jsonData'])
    except KeyError:
        jsonDataSql = json.dumps({"value": "none"})
    device = jsonData.get('device', "none")
    try:
        deviceJSON = json.dumps(jsonData['deviceJson'])
    except KeyError:
        deviceJSON = json.dumps({"value": "none"})

    query = (
        "INSERT INTO mission_data "
        "(db_insert_time, mission, type, temperature, humidity, location, "
        "img, x, y, z, data, jsonData, device, deviceJSON) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
    )
    values = (
        db_insert_time,
        mission_id,
        type,
        temp,
        humidity,
        "Point({} {})".format(geopoint[0], geopoint[1]),
        img,
        x,
        y,
        z,
        data_val,
        jsonDataSql,
        device,
        deviceJSON,
    )

    cur = conn.cursor()
    try:
        cur.execute(query, values)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("addEvent failed: {}".format(e))
        return {"error": str(e)}
    return {"data": "stored"}


def getRecentEvents(mission_id, minutes=15):
    minutes = max(1, min(int(minutes), 60))
    query = (
        "SELECT mission, type, temperature, humidity, "
        "ST_AsGeoJSON(location) AS location, "
        "img, x, y, z, data, jsonData, device, deviceJSON, "
        "to_char(db_insert_time AT TIME ZONE 'UTC', "
        "'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"') AS db_insert_time "
        "FROM mission_data "
        "WHERE mission = %s "
        "AND db_insert_time >= NOW() - (%s || ' minutes')::interval "
        "ORDER BY db_insert_time ASC"
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(query, (mission_id, str(minutes)))
        rows = cur.fetchall()
    except Exception as e:
        conn.rollback()
        print("getRecentEvents failed: {}".format(e))
        return []

    for row in rows:
        if row.get("location"):
            try:
                row["location"] = json.loads(row["location"])
            except (TypeError, ValueError):
                pass
    return rows


####
## Search (replaces Meilisearch)
####
def searchMaps(payload):
    print("Searching maps in postgis")
    name = payload.get("name")
    tags = payload.get("tags")
    fromdate = payload.get("fromdate")
    todate = payload.get("todate")

    clauses = []
    params = []

    if name:
        clauses.append("name ILIKE %s")
        params.append("%{}%".format(name))
    if tags:
        clauses.append("tags ILIKE %s")
        params.append("%{}%".format(tags))
    if fromdate:
        clauses.append("created_at >= %s")
        params.append(fromdate)
    if todate:
        clauses.append("created_at <= %s")
        params.append(todate)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    query = (
        "SELECT *, ST_AsGeoJSON(location) AS geometry, "
        "TO_CHAR(created_at, 'YYYY-MM-DD') AS created_at, "
        "TO_CHAR(updated_at, 'YYYY-MM-DD') AS updated_at "
        "FROM maps" + where
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(query, params)
        return cur.fetchall()
    except Exception as e:
        conn.rollback()
        print("searchMaps failed: {}".format(e))
        return {"error": str(e)}