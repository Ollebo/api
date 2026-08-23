import psycopg2
import json
import os
import queue
import select
import sys
import threading
from functools import wraps
from psycopg2 import extensions
from psycopg2.extras import RealDictCursor


# gunicorn runs one worker with 16 threads (code/start.sh) and this module used
# to hand all of them the same module-level connection. psycopg2 serializes
# concurrent use of a single connection, so every request queued behind every
# other one: one slow mission_data INSERT stalled /maps/ and /readyz for
# seconds at a time, which pulled pods out of the Service and timed out the
# map-maker healthcheck. Threads now borrow a connection from a small pool for
# the length of one call and give it straight back.
#
# Sizing: max_connections on the CNPG cluster is the default 100, shared with dw,
# map-maker and the rest, and the HPA may take this Deployment to 10 replicas.
# The per-pod cost is _POOL_MAX + 1 (the probe connection below), so 10 replicas
# draw 50 of those 100 at full stretch — the previous 8 would have drawn 90 and
# left nothing for anyone else. That ceiling has never actually been reached
# because the cluster has no metrics-server, so the HPA cannot scale past
# minReplicas; sizing for the maximum it is *allowed* to reach is the point.
#
# Four is still well above the concurrency observed in practice (queries are
# single-digit ms now that Redis absorbs the hot path, so one connection serves
# hundreds of calls a second). Exhausting the pool now only makes request threads
# wait — /readyz no longer queues behind them — which is the failure mode to
# prefer: a slow pod rather than one evicted from the Service for being busy.
_POOL_MAX = int(os.environ.get('POSTGRES_POOL_MAX', 4))
# How long a thread waits for a free connection before giving up: longer than any
# healthy query, shorter than the 10s read timeout our callers use.
_POOL_TIMEOUT = float(os.environ.get('POSTGRES_POOL_TIMEOUT', 5))

_CONNECT_ARGS = dict(
    database=os.environ.get('POSTGRES_DB', 'ollebo'),
    user=os.environ.get('POSTGRES_USER', 'ollebo'),
    host=os.environ.get('POSTGRES_HOST', 'postgis'),
    password=os.environ.get('POSTGRES_PASSWORD', 'olleb0'),
    port=int(os.environ.get('POSTGRES_PORT', 5432)),
    sslmode='disable',
    # Never let a wedged network hold a request thread open indefinitely.
    connect_timeout=int(os.environ.get('POSTGRES_CONNECT_TIMEOUT', 5)),
)


def _connect():
    c = psycopg2.connect(**_CONNECT_ARGS)
    # Without autocommit psycopg2 opens a transaction for plain SELECTs too and
    # nothing in this module ever ends it, so read-only sessions sat "idle in
    # transaction" indefinitely and held back vacuum. Nothing here spans
    # statements, so committing each one is the same behaviour without that cost.
    c.autocommit = True
    return c


def _usable(c):
    """Whether the idle connection `c` can still be handed out.

    All three checks are local — no round trip on the hot path. The socket one
    matters: when Postgres goes away (a CNPG restart or failover, an admin
    pg_terminate_backend) psycopg2 does not notice until the next statement, so
    `closed` and the transaction status both still say the connection is fine.
    A connection with nothing in flight should have nothing to read; if its
    socket is readable, what is waiting there is the server hanging up.
    """
    if c is None or c.closed:
        return False
    try:
        if c.get_transaction_status() == extensions.TRANSACTION_STATUS_UNKNOWN:
            return False
        return not select.select([c.fileno()], [], [], 0)[0]
    except Exception:
        return False


def _discard(c):
    try:
        c.close()
    except Exception:
        pass


class _Pool:
    """A small blocking connection pool.

    psycopg2.pool.ThreadedConnectionPool raises as soon as every connection is
    checked out, which turns a burst into failed requests; this one makes the
    caller wait instead. Connections open lazily, so an idle pod holds one.
    """

    def __init__(self, maxconn):
        self._idle = queue.LifoQueue()
        self._slots = threading.Semaphore(maxconn)
        self._maxconn = maxconn

    def acquire(self, timeout):
        if not self._slots.acquire(timeout=timeout):
            raise RuntimeError(
                "postgres pool exhausted: {} connections busy for {}s".format(
                    self._maxconn, timeout))
        try:
            while True:
                try:
                    c = self._idle.get_nowait()
                except queue.Empty:
                    return _connect()
                if _usable(c):
                    return c
                # Dropped by the server while it sat idle — open a fresh one.
                _discard(c)
        except Exception:
            self._slots.release()
            raise

    def release(self, c):
        if _usable(c):
            self._idle.put(c)
        else:
            _discard(c)
        self._slots.release()


_pool = _Pool(_POOL_MAX)


class _PooledConnection:
    """The `conn` this module (and start.py's /readyz) already talks to.

    Keeps the psycopg2 connection API — cursor/commit/rollback — but resolves it
    to whichever connection the calling thread currently holds, borrowing one on
    first use. @pooled returns it when the call finishes; start.py releases again
    on request teardown so a handler that touches `conn` directly cannot leak one.
    """

    def __init__(self, pool):
        self._pool = pool
        self._local = threading.local()

    def _current(self):
        c = getattr(self._local, 'conn', None)
        if c is None:
            c = self._pool.acquire(_POOL_TIMEOUT)
            self._local.conn = c
        return c

    def held(self):
        return getattr(self._local, 'conn', None) is not None

    def release(self):
        c = getattr(self._local, 'conn', None)
        if c is None:
            return
        self._local.conn = None
        self._pool.release(c)

    def cursor(self, *args, **kwargs):
        return self._current().cursor(*args, **kwargs)

    def commit(self):
        return self._current().commit()

    def rollback(self):
        return self._current().rollback()

    def __getattr__(self, name):
        return getattr(self._current(), name)


conn = _PooledConnection(_pool)


def releaseConnection():
    """Hand this thread's connection back to the pool; no-op if it holds none."""
    conn.release()


# A connection reserved for /readyz, deliberately outside `_pool`.
#
# The probe used to borrow from the pool like any request, so once all _POOL_MAX
# connections were checked out it blocked for _POOL_TIMEOUT — the same 5s as the
# readinessProbe's timeoutSeconds — and the kubelet pulled a pod that was merely
# busy out of the Service, deepening the pile-up it was already struggling with.
# A readiness probe has to answer "can this pod reach Postgres", never "is this
# pod busy", so it gets a connection request traffic can never hold.
_HEALTH_TIMEOUT = float(os.environ.get('POSTGRES_HEALTH_TIMEOUT', 2))
# Bound the probe server-side as well: a backend wedged on a lock must not hold
# the probe open past the kubelet's own timeout. Both halves of the round trip
# (connect, then execute) stay under _HEALTH_TIMEOUT.
_HEALTH_CONNECT_ARGS = dict(
    _CONNECT_ARGS,
    connect_timeout=max(1, int(_HEALTH_TIMEOUT)),
    options='-c statement_timeout={}'.format(int(_HEALTH_TIMEOUT * 1000)),
)
_health_lock = threading.Lock()
_health_conn = None


def healthcheck():
    """SELECT 1 for /readyz. Returns None if reachable, raises if not."""
    global _health_conn
    if not _health_lock.acquire(timeout=_HEALTH_TIMEOUT):
        # Nothing but another probe can hold this lock, so a probe is still in
        # flight: it is stuck on the server, not queued behind request traffic.
        raise RuntimeError(
            'postgres healthcheck still in flight after {}s'.format(
                _HEALTH_TIMEOUT))
    try:
        # Two attempts: the probe connection sits idle between runs, so a CNPG
        # restart or failover can drop it without psycopg2 noticing until this
        # statement. Reconnecting once turns that into a slower ok rather than a
        # spurious 503 that would evict a pod whose database is in fact fine.
        for attempt in (1, 2):
            c = _health_conn
            if not _usable(c):
                if c is not None:
                    _discard(c)
                _health_conn = c = psycopg2.connect(**_HEALTH_CONNECT_ARGS)
                c.autocommit = True
            try:
                with c.cursor() as cur:
                    cur.execute('SELECT 1')
                    cur.fetchone()
                return
            except Exception:
                _discard(c)
                _health_conn = None
                if attempt == 2:
                    raise
    finally:
        _health_lock.release()


def pooled(fn):
    """Give `fn` a connection for its duration and return it when it exits.

    A nested call reuses the caller's connection: only the frame that actually
    borrowed it releases. Cursors never outlive the call — every function here
    materializes its rows before returning — so the connection is free for
    another thread immediately.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        borrowed = not conn.held()
        try:
            return fn(*args, **kwargs)
        finally:
            if borrowed:
                conn.release()

    return wrapper


# Fail fast at boot the way the old module-level connect() did: a process that
# cannot reach Postgres should not come up and start answering probes.
print("Connecting to database")
try:
    _boot_conn = _pool.acquire(_POOL_TIMEOUT)
    _pool.release(_boot_conn)
except Exception as e:
    print("ERROR: Could not connect to Postgres instance: {}".format(e))
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


@pooled
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


@pooled
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
    # `groups` are the caller's authorized space_ids — validated canonical UUIDs
    # from jwt_auth.get_auth_context, so the `::uuid[]` cast below is safe.
    if not groups:
        return ("access = %s", ['public'])
    return ("(access = %s OR space_id = ANY(%s::uuid[]))", ['public', list(groups)])


@pooled
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
@pooled
def getMissions(spaceID, status):
    print("Getting close data from db")
    postgreSQL_select_Query = "select * from missions "
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(postgreSQL_select_Query)
    maps = json.dumps(cur.fetchall(), indent=4, sort_keys=True, default=str)
    return maps


@pooled
def getMission(id):
    print("Getting close data from db")
    postgreSQL_select_Query = "select * from missions  where id = '"+str(id)+"'"
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(postgreSQL_select_Query)
    mission = json.dumps(cur.fetchall(), indent=4, sort_keys=True, default=str)
    return mission


@pooled
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


@pooled
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


@pooled
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


@pooled
def getMissionHello(key):
    # Full mission profile for the boot-time "hello" handshake (media URLs + stats).
    # Accepts key or id like getMissionByKey. Kept separate from getMissionByKey so
    # the cached auth hot path (event.resolve_mission) keeps its minimal column set.
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT id, name, space_id, is_public, "
            "camera_stream_low_url, camera_stream_medium_url, camera_stream_high_url, "
            "picture_upload_low_url, picture_upload_medium_url, picture_upload_high_url, "
            "number_of_events, number_of_pictures, stats_updated_at "
            "FROM missions WHERE key = %s OR id = %s LIMIT 1",
            (str(key), str(key)))
        return cur.fetchone()
    except Exception as e:
        print("getMissionHello failed: {}".format(e))
        try:
            conn.rollback()
        except Exception:
            pass
        return None


@pooled
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


@pooled
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
## Models (mirror of maps: worker copies the file, then PATCH /models/<id>)
####
_MODEL_ACTION_TO_STATUS = {
    "makingModel": "processing",
    "ready": "ready",
    "error": "failed",
}


@pooled
def getModelSpaceId(modelid):
    try:
        cur = conn.cursor()
        cur.execute("SELECT space_id::text FROM model WHERE modelid = %s LIMIT 1", (str(modelid),))
        row = cur.fetchone()
    except Exception as e:
        print("getModelSpaceId failed: modelid={} err={}".format(modelid, e))
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    if row is None:
        return None
    return row[0]


@pooled
def updateModelDataDb(jsonData, db="model"):
    modelid = jsonData['modelid']
    action = jsonData['action']
    status = _MODEL_ACTION_TO_STATUS.get(action)
    if status is None:
        print("ERROR updateModelDataDb unknown action: modelid={} action={}".format(modelid, action))
        return {"error": "unknown action", "action": action}

    sets = ["status = %s", "updated_at = now()"]
    params = [status]

    # The worker copies the file to the public/private bucket and reports the
    # new object key; store it as the served originfile.
    origin = jsonData.get('originFile') or jsonData.get('originfile')
    if origin:
        sets.append("originfile = %s")
        params.append(origin)

    params.append(modelid)
    query = "UPDATE model SET " + ", ".join(sets) + " WHERE modelid = %s::uuid;"

    cur = conn.cursor()
    try:
        cur.execute(query, params)
    except Exception as e:
        conn.rollback()
        print("ERROR updateModelDataDb failed: modelid={} action={} err={}".format(modelid, action, e))
        raise
    rowcount = cur.rowcount
    conn.commit()
    if rowcount == 0:
        print("ERROR updateModelDataDb no row matched: modelid={} action={}".format(modelid, action))
        return {"error": "unknown modelid", "modelid": modelid}
    return {"data": "saved", "modelid": modelid}


@pooled
def getModelsDb(groups=None):
    vis_sql, vis_params = _visibility_clause(groups)
    query = (
        "SELECT *, "
        "TO_CHAR(created_at, 'YYYY-MM-DD') AS created_at, "
        "TO_CHAR(updated_at, 'YYYY-MM-DD') AS updated_at "
        "FROM model WHERE " + vis_sql
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
        print("getModelsDb failed: {}".format(e))
        return {"error": str(e)}


####
## Events / mission_data
####
@pooled
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


@pooled
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


@pooled
def setPictureUploaded(mission_id, picture_id, url):
    """Phase 2 of the two-phase picture flow: the bytes finally arrived.

    Flip the pending `type=picture` row (matched by its jsonData picture_id) to
    `uploaded`, recording the stored object URL in `img`. If no pending row
    exists yet (bytes can arrive before the event on a flaky link), insert a
    fresh picture row already marked uploaded so nothing is lost.

    Returns {"data": "uploaded"|"created"} or {"error": ...}.
    """
    update = (
        "UPDATE mission_data "
        "SET img = %s, "
        "    jsonData = COALESCE(jsonData, '{}'::jsonb) "
        "        || jsonb_build_object('status', 'uploaded', 'uploaded_at', "
        "           to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"')) "
        "WHERE mission = %s AND type = 'picture' "
        "AND jsonData->>'picture_id' = %s"
    )
    cur = conn.cursor()
    try:
        cur.execute(update, (url, mission_id, picture_id))
        if cur.rowcount == 0:
            insert = (
                "INSERT INTO mission_data "
                "(db_insert_time, mission, type, temperature, humidity, location, "
                "img, x, y, z, data, jsonData, device, deviceJSON) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
            )
            jsonDataSql = json.dumps({"picture_id": picture_id, "status": "uploaded"})
            deviceJSON = json.dumps({"value": "none"})
            cur.execute(insert, (
                "now()", mission_id, "picture", 0, 0,
                "Point(0 0)", url, 0, 0, 0, 0, jsonDataSql, "none", deviceJSON,
            ))
            conn.commit()
            return {"data": "created"}
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("setPictureUploaded failed: {}".format(e))
        return {"error": str(e)}
    return {"data": "uploaded"}


####
## Search (replaces Meilisearch)
####
@pooled
def searchMaps(payload, groups=None):
    print("Searching maps in postgis")
    name = payload.get("name")
    tags = payload.get("tags")
    fromdate = payload.get("fromdate")
    todate = payload.get("todate")

    vis_sql, vis_params = _visibility_clause(groups)
    # Only surface finished maps; visibility still applies (public + entitled private).
    clauses = [vis_sql, "status = %s"]
    params = list(vis_params) + ["ready"]

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