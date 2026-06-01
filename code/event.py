from flask import jsonify

from db.postgis import addEvent, getRecentEvents
from db.natsQue import addToNats


def event(payload, request, mission_id):
    result = addEvent(payload, "mission_data", mission_id)
    try:
        addToNats("events", {"mission_id": mission_id, "payload": payload})
    except Exception as e:
        print("NATS publish failed: {}".format(e))
    return result


def recent(mission_id, minutes=15):
    rows = getRecentEvents(mission_id, minutes)
    return jsonify(rows)
