import json
import os
import redis

_VALID_TTL = 3600
_INVALID_TTL = 600
_KEY_PREFIX = "mission_valid:"

_MISSION_PREFIX = "mission_meta:"
_MISSION_TTL = 3600
_MISSION_MISS_TTL = 600

_SPACE_KEY_PREFIX = "space_key:"
_SPACE_KEY_TTL = 300
_SPACE_KEY_MISS_TTL = 60

try:
    client = redis.Redis(
        host=os.environ.get("REDIS_HOST", "redis"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        password=os.environ.get("REDIS_PASSWORD") or None,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=True,
    )
except Exception as e:
    print("ERROR: Could not init Redis client: {}".format(e))
    client = None


def getMissionValidity(mission_id):
    if client is None:
        return None
    try:
        v = client.get(_KEY_PREFIX + str(mission_id))
    except Exception as e:
        print("Redis GET failed: {}".format(e))
        return None
    if v is None:
        return None
    return v == "1"


def setMissionValidity(mission_id, valid):
    if client is None:
        return
    try:
        ttl = _VALID_TTL if valid else _INVALID_TTL
        client.set(_KEY_PREFIX + str(mission_id), "1" if valid else "0", ex=ttl)
    except Exception as e:
        print("Redis SET failed: {}".format(e))


# Resolved-mission cache. Stores the visibility-relevant fields
# ({id, space_id, is_private}) as JSON so ingest and read-auth don't re-query
# Postgres per event/stream. Empty string is a cached-miss sentinel (mission
# absent) so unknown ids don't hammer the DB.
def getCachedMission(key):
    """Return the cached mission dict, "" for a cached miss, or None if unknown."""
    if client is None:
        return None
    try:
        v = client.get(_MISSION_PREFIX + str(key))
    except Exception as e:
        print("Redis GET failed: {}".format(e))
        return None
    if v is None:
        return None
    if v == "":
        return ""
    try:
        return json.loads(v)
    except ValueError:
        return None


def setCachedMission(key, mission):
    if client is None:
        return
    try:
        ttl = _MISSION_TTL if mission else _MISSION_MISS_TTL
        payload = json.dumps(mission, default=str) if mission else ""
        client.set(_MISSION_PREFIX + str(key), payload, ex=ttl)
    except Exception as e:
        print("Redis SET failed: {}".format(e))


# Per-space API key cache.
# Stored plaintext (internal Redis, short TTL); revisit if Redis ever leaves the
# private network. Empty string is a sentinel for cached miss (space row absent
# or space.key NULL) so we don't re-query Postgres on every unauthorized request.
def getCachedSpaceKey(space_id):
    if client is None:
        return None
    try:
        return client.get(_SPACE_KEY_PREFIX + str(space_id))
    except Exception as e:
        print("Redis GET failed: {}".format(e))
        return None


def setCachedSpaceKey(space_id, key):
    if client is None:
        return
    try:
        ttl = _SPACE_KEY_TTL if key else _SPACE_KEY_MISS_TTL
        client.set(_SPACE_KEY_PREFIX + str(space_id), key or "", ex=ttl)
    except Exception as e:
        print("Redis SET failed: {}".format(e))
