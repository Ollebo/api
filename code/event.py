from flask import jsonify

from db.postgis import addEvent, getRecentEvents, getMissionByKey
from db.natsQue import addToNats
from db.redisCache import getCachedMission, setCachedMission
from jwt_auth import get_auth_context, JwtError


# Canonical event types a drone/boat/rover can emit. `type` is stored verbatim
# in mission_data (no wire rewrite) so existing consumers keep working, but we
# recognise a small formal set for documentation, per-type handling and demo
# traffic. Legacy aliases map onto a canonical type for reference only.
#   location    -> GPS/telemetry: geopoint/x/y/z/device (+ jsonData)
#   measurement -> generic sensor value: `data` + jsonData{kind,unit} (temp/humidity too)
#   picture     -> two-phase photo: jsonData{picture_id,status}; bytes uploaded later
#   alert       -> detection: jsonData{kind,severity,message}
KNOWN_EVENT_TYPES = {"location", "measurement", "picture", "alert"}
TYPE_ALIASES = {"telemetry": "location", "temperature": "measurement"}


def event(payload, request, mission_id):
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid or missing JSON body"}), 400

    mission = resolve_mission(mission_id)
    if mission is None:
        return jsonify({"error": "mission not found"}), 404

    _normalize_event(payload)

    # Canonicalize on the mission UUID so backfill/read lookups line up
    # regardless of whether the caller posted by key or id.
    result = addEvent(payload, "mission_data", mission["id"])

    subject = subject_for(mission)
    if subject is None:
        print("event: mission {} private without space_id; skipping NATS publish".format(mission["id"]))
        return result
    try:
        addToNats(subject, {"mission_id": mission["id"], "payload": payload})
    except Exception as e:
        print("NATS publish failed: {}".format(e))
    return result


def _normalize_event(payload):
    """Light, non-destructive typing pass run before storing/publishing.

    Does NOT rewrite the payload's `type` on the wire (existing GUI/SSE
    consumers key on the original values). It only warns on unrecognised
    types and, for `picture` events, ensures the two-phase bookkeeping
    (`picture_id` + a default `status`) is present in `jsonData`.
    """
    etype = payload.get("type", "none")
    if etype not in KNOWN_EVENT_TYPES and etype not in TYPE_ALIASES:
        print("event: unknown type {!r}; storing as-is".format(etype))

    if etype == "picture":
        jd = payload.get("jsonData")
        if not isinstance(jd, dict):
            jd = {}
            payload["jsonData"] = jd
        if not jd.get("picture_id"):
            print("event: picture event without picture_id; upload cannot be correlated")
        jd.setdefault("status", "pending")


def recent(mission_id, minutes=15):
    rows = getRecentEvents(mission_id, minutes)
    return jsonify(rows)


def authorize_mission_read(param, headers_get):
    """Gate a read (stream/recent) against mission visibility.

    Returns (mission, subject, None) when allowed, or
    (None, None, (body, status)) with a JSON body + HTTP status when denied.
    Public missions are open; private ones require a JWT whose `groups` claim
    contains the mission's space_id. Takes a `headers_get` callable so it works
    unchanged under both the Flask and Lambda runtimes.
    """
    mission = resolve_mission(param)
    if mission is None:
        return None, None, ({"error": "mission not found"}, 404)

    if _is_public(mission):
        return mission, subject_for(mission), None

    space_id = mission.get("space_id")
    try:
        groups = get_auth_context(headers_get)
    except JwtError as e:
        return None, None, ({"error": "unauthorized", "detail": str(e)}, 401)

    groups_norm = {g.lower() for g in groups} if groups else set()
    if not space_id or space_id.lower() not in groups_norm:
        return None, None, ({"error": "forbidden"}, 403)
    return mission, subject_for(mission), None


def subject_for(mission):
    """NATS subject a mission's events publish to / are consumed from.

    Public -> events.public.<id>; private -> events.private.<space_id>.<id>.
    Returns None for a private mission lacking a space_id (unroutable).
    """
    if _is_public(mission):
        return "events.public.{}".format(mission["id"])
    space_id = mission.get("space_id")
    if not space_id:
        return None
    return "events.private.{}.{}".format(space_id, mission["id"])


def resolve_mission(param):
    """Resolve a key-or-id path param to {id, space_id, is_public}, Redis-cached."""
    cached = getCachedMission(param)
    if cached == "":
        return None
    if cached:
        return cached

    row = getMissionByKey(param)
    if row is None:
        setCachedMission(param, None)
        return None

    space_id = row.get("space_id")
    mission = {
        "id": str(row["id"]),
        "space_id": str(space_id) if space_id is not None else None,
        "is_public": bool(row.get("is_public")),
    }
    setCachedMission(param, mission)
    return mission


def _is_public(mission):
    # is_public is the authoritative flag (NOT NULL DEFAULT FALSE in the schema):
    # a mission is public iff is_public is true; otherwise it's space-private.
    return bool(mission.get("is_public"))
