import hmac
import os
import uuid

from db.postgis import getSpaceKey, getMapSpaceId
from db.redisCache import getCachedSpaceKey, setCachedSpaceKey


API_KEY = os.environ.get("API_KEY")


def _log_unauthorized(method, space_id, headers_get, reason):
    fwd = headers_get("X-Forwarded-For") or headers_get("X-Real-Ip") or "?"
    print("ERROR /maps/ unauthorized: method={} space_id={} reason={} ip={}".format(
        method, space_id, reason, fwd
    ))


def _unauthorized():
    return ({"error": "unauthorized"}, 401)


def _lookup_space_key(space_id):
    cached = getCachedSpaceKey(space_id)
    if cached is not None:
        return cached or None
    key = getSpaceKey(space_id)
    setCachedSpaceKey(space_id, key)
    return key


def verify_map_request(method, payload, headers_get):
    provided = headers_get("X-Api-Key")
    if not provided:
        _log_unauthorized(method, None, headers_get, "no_header")
        return _unauthorized()

    if API_KEY and hmac.compare_digest(provided, API_KEY):
        return None

    if not isinstance(payload, dict):
        _log_unauthorized(method, None, headers_get, "no_payload")
        return _unauthorized()

    if method == "PUT":
        raw = payload.get("space_id")
        if not raw:
            _log_unauthorized(method, None, headers_get, "missing_space_id")
            return _unauthorized()
        try:
            space_id = str(uuid.UUID(str(raw)))
        except (ValueError, AttributeError, TypeError):
            _log_unauthorized(method, raw, headers_get, "bad_space_id")
            return _unauthorized()
    elif method == "POST":
        mapid = payload.get("mapid")
        if not mapid:
            _log_unauthorized(method, None, headers_get, "missing_mapid")
            return _unauthorized()
        space_id = getMapSpaceId(mapid)
        if not space_id:
            _log_unauthorized(method, None, headers_get, "unknown_mapid")
            return _unauthorized()
    else:
        _log_unauthorized(method, None, headers_get, "bad_method")
        return _unauthorized()

    space_key = _lookup_space_key(space_id)
    if not space_key:
        _log_unauthorized(method, space_id, headers_get, "no_space_key")
        return _unauthorized()

    if not hmac.compare_digest(provided, space_key):
        _log_unauthorized(method, space_id, headers_get, "key_mismatch")
        return _unauthorized()

    return None
