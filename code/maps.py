from db.postgis import *
from db.natsQue import addToNats
from flask import jsonify
import datetime
import uuid


def setJsonValidate(jsonData):
    JsonStandrad = {
        "creator_id": jsonData.get('creator_id', '686eaeeb-383b-44d7-9754-4b2e7c0c11c7'),
        "name": jsonData.get('name', 'default'),
        "tags": jsonData.get('tags', []),
        "status": jsonData.get('status', 'unprocessed'),
        "space_id": jsonData.get('space_id'),
        "asset_id": jsonData.get('asset_id', '686eaeeb-383b-44d7-9754-4b2e7c0c11c7'),
        "access": jsonData.get('access', 'private'),
        "originFile": jsonData.get('originFile', ''),
        "mapid": jsonData.get('mapid', ''),
        "accessid": jsonData.get('accessid', ''),
        "action" : jsonData.get('action', ''),
        "location": jsonData.get('location', [-118.4079,33.9434]),
        "recordtime": jsonData.get('recordtime', '2020-01-01 00:00:00.000000')

    }
    return JsonStandrad


_KNOWN_ACTIONS = ("makingMap", "ready", "error")


def _validate_post(payload):
    if not isinstance(payload, dict):
        return ["<body>"]
    missing = [k for k in ("mapid", "action") if not payload.get(k)]
    if missing:
        return missing
    action = payload["action"]
    if action not in _KNOWN_ACTIONS:
        return ["action(unknown:{})".format(action)]
    if action == "makingMap":
        return []
    further = []
    if action == "ready" and not payload.get("tilesURL"):
        further.append("tilesURL")
    mapData = payload.get("mapData")
    if not mapData:
        further.append("mapData")
        return further
    coords = (mapData.get("location") or {}).get("coordinates")
    if not (isinstance(coords, (list, tuple)) and len(coords) >= 2):
        further.append("mapData.location.coordinates")
    return further


def mapsSearch(payload, groups=None):
    print(payload)
    if payload is None:
        return '{"error":"Missing search"}'
    return searchMaps(payload, groups=groups)



def maps(payload, request, groups=None):
    print(request.method)

    if request.method   == "POST":
        print("Update database")
        if payload is None:
            print("ERROR POST /maps/ bad payload: missing=['<body>']")
            return jsonify({"error": "missing body", "missing": ["<body>"]}), 400
        payload["recordtime"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        missing = _validate_post(payload)
        if missing:
            print("ERROR POST /maps/ bad payload: missing={} mapid={} action={} keys={}".format(
                missing, payload.get("mapid"), payload.get("action"), sorted(payload.keys())
            ))
            return jsonify({"error": "invalid payload", "missing": missing}), 400
        try:
            return updateMapDataDb(payload, "maps")
        except Exception as e:
            print("ERROR POST /maps/ db error: mapid={} err={}".format(payload.get("mapid"), e))
            return jsonify({"error": "db error", "detail": str(e)}), 500
    if request.method == "GET":
        print("List maps (groups={})".format(groups))
        return getDataDb("maps", groups=groups)
    if request.method == "PUT":
        print("Add to database")
        if payload is None:
            print("ERROR PUT /maps/ bad payload: missing=['<body>']")
            return jsonify({"error": "missing body"}), 400
        payload["recordtime"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        clearJson = setJsonValidate(payload)
        try:
            uuid.UUID(str(clearJson["space_id"]))
        except (ValueError, AttributeError, TypeError):
            print("ERROR PUT /maps/ bad space_id: value={!r}".format(clearJson.get("space_id")))
            return jsonify({"error": "invalid space_id"}), 400
        try:
            result = addDataDb(clearJson, "maps")
        except Exception as e:
            print("ERROR PUT /maps/ db error: mapid={} err={}".format(clearJson.get("mapid"), e))
            return jsonify({"error": "db error", "detail": str(e)}), 500
        try:
            addToNats("maps", clearJson)
        except Exception as e:
            print("NATS publish failed: {}".format(e))
        return result
