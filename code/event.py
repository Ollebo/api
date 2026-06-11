from flask import jsonify

from db.postgis import addEvent, getRecentEvents, missionExists
from db.natsQue import addToNats
from db.redisCache import getMissionValidity, setMissionValidity


def event(payload, request, mission_id):
    if not _validateMission(mission_id):
        return jsonify({"error": "mission not found"}), 404

    result = addEvent(payload, "mission_data", mission_id)
    try:
        addToNats("events", {"mission_id": mission_id, "payload": payload})
    except Exception as e:
        print("NATS publish failed: {}".format(e))
    return result


def recent(mission_id, minutes=15):
    rows = getRecentEvents(mission_id, minutes)
    return jsonify(rows)


def _validateMission(mission_id):
    cached = getMissionValidity(mission_id)
    if cached is not None:
        return cached
    valid = missionExists(mission_id)
    setMissionValidity(mission_id, valid)
    return valid
