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


# Worker reports progress via `action`; the maps_status_check constraint only
# permits these four status values, so map every callback to one of them.
_ACTION_TO_STATUS = {
    "makingMap": "processing",
    "ready": "ready",
    "error": "failed",
}


def updateMapDataDb(jsonData, db="maps"):
    mapid = jsonData['mapid']
    action = jsonData['action']
    status = _ACTION_TO_STATUS.get(action)
    if status is None:
        print("ERROR updateMapDataDb unknown action: mapid={} action={}".format(mapid, action))
        return {"error": "unknown action", "action": action}

    sets = ["status = %s", "action = %s", "updated_at = now()"]
    params = [status, action]

    mapData = jsonData.get('mapData') or {}
    if mapData:
        sets.append("mapdata = %s")
        params.append(json.dumps({
            **mapData,
            'inputType': jsonData.get('inputType'),
            'variants': jsonData.get('variants'),
        }))
        loc = mapData.get('location')
        if loc:
            sets.append("location = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)::geography")
            params.append(json.dumps(loc))
        area = mapData.get('area')
        if area:
            sets.append("area = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)::geography")
            params.append(json.dumps(area))

    tiles_url = jsonData.get('tilesURL')
    if tiles_url:
        sets.append("tilesurl = %s")
        params.append(tiles_url)

    params.append(mapid)
    query = "UPDATE maps SET " + ", ".join(sets) + " WHERE mapid = %s::uuid;"

    cur = conn.cursor()
    try:
        cur.execute(query, params)
    except Exception as e:
        conn.rollback()
        print("ERROR updateMapDataDb failed: mapid={} action={} status={} err={}".format(mapid, action, status, e))
        raise
    rowcount = cur.rowcount
    conn.commit()
    if rowcount == 0:
        print("ERROR updateMapDataDb no row matched: mapid={} action={}".format(mapid, action))
        return {"error": "unknown mapid", "mapid": mapid}
    return {"data": "saved", "mapid": mapid}


    



def _visibility_clause(groups):
    if not groups:
        return ("access = %s", ['public'])
    return ("(access = %s OR space_id = ANY(%s::uuid[]))", ['public', list(groups)])


def getDataDb(db="maps", groups=None):
    print("Getting data from db all")
    vis_sql, vis_params = _visibility_clause(groups)
    query = (
        "SELECT *, ST_AsGeoJSON(location), "
        "TO_CHAR(created_at, 'YYYY-MM-DD') AS created_at, "
        "TO_CHAR(updated_at, 'YYYY-MM-DD') AS updated_at "
        "FROM maps WHERE " + vis_sql
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(query, vis_params)
        return cur.fetchall()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("getDataDb failed: {}".format(e))
        return {"error": str(e)}

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


def missionExistsByKey(key):
    # Mission clients authenticate with the mission key; accept the id too so callers
    # passing an id still validate.
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM missions WHERE key = %s OR id = %s LIMIT 1",
                    (str(key), str(key)))
        return cur.fetchone() is not None
    except Exception as e:
        print("missionExistsByKey failed: {}".format(e))
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def getMissionByKey(key):
    # Resolves a mission from either its key or its id. `is_public` drives read
    # visibility (public missions stream without auth; non-public ones require a
    # JWT whose groups contain space_id). Feeds both ingest and read authorization.
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT id, name, space_id, is_public FROM missions "
            "WHERE key = %s OR id = %s LIMIT 1",
            (str(key), str(key)))
        return cur.fetchone()
    except Exception as e:
        print("getMissionByKey failed: {}".format(e))
        try:
            conn.rollback()
        except Exception:
            pass
        return None


def getSpaceKey(space_id):
    try:
        cur = conn.cursor()
        cur.execute("SELECT key FROM space WHERE id = %s LIMIT 1", (str(space_id),))
        row = cur.fetchone()
    except Exception as e:
        print("getSpaceKey failed: space_id={} err={}".format(space_id, e))
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    if row is None:
        return None
    return row[0]


def getMapSpaceId(mapid):
    try:
        cur = conn.cursor()
        cur.execute("SELECT space_id::text FROM maps WHERE mapid = %s LIMIT 1", (str(mapid),))
        row = cur.fetchone()
    except Exception as e:
        print("getMapSpaceId failed: mapid={} err={}".format(mapid, e))
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    if row is None:
        return None
    return row[0]


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
def searchMaps(payload, groups=None):
    print("Searching maps in postgis")
    name = payload.get("name")
    tags = payload.get("tags")
    fromdate = payload.get("fromdate")
    todate = payload.get("todate")

    vis_sql, vis_params = _visibility_clause(groups)
    clauses = [vis_sql]
    params = list(vis_params)

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

    where = " WHERE " + " AND ".join(clauses)
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