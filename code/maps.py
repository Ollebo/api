from db.postgis import *
from db.natsQue import addToNats
from flask import jsonify
import datetime
import json
import uuid

import map_metrics


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


_KNOWN_ACTIONS = ("makingMap", "ready", "partial", "error",
                  # publish-only callbacks (spridningstillstand.md)
                  "publicReady", "publicRefused", "unpublished", "unpublishFailed",
                  # Lantmäteriet permit material package (map_permit, dw 029)
                  "exportReady", "exportFailed")
_PUBLISH_ONLY = ("publicReady", "publicRefused", "unpublished", "unpublishFailed",
                 "exportReady", "exportFailed")


def _validate_post(payload):
    if not isinstance(payload, dict):
        return ["<body>"]
    missing = [k for k in ("mapid", "action") if not payload.get(k)]
    if missing:
        return missing
    action = payload["action"]
    if action not in _KNOWN_ACTIONS:
        return ["action(unknown:{})".format(action)]
    if action == "makingMap" or action in _PUBLISH_ONLY:
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
    result = searchMaps(payload, groups=groups)
    map_metrics.MAP_SEARCHES.labels(map_metrics.query_result(result)).inc()
    return result



def maps(payload, request, groups=None):
    print(request.method)

    # POST and PATCH both persist worker results by updating the map row in
    # place. The map-maker worker uses PATCH /maps/<mapid>; older callers POST
    # to /maps/ with mapid in the body. Both land here with the same payload.
    if request.method in ("POST", "PATCH"):
        print("Update database")
        if payload is None:
            print("ERROR {} /maps/ bad payload: missing=['<body>']".format(request.method))
            map_metrics.callback(None, _KNOWN_ACTIONS, "invalid")
            return jsonify({"error": "missing body", "missing": ["<body>"]}), 400
        payload["recordtime"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        missing = _validate_post(payload)
        if missing:
            print("ERROR {} /maps/ bad payload: missing={} mapid={} action={} keys={}".format(
                request.method, missing, payload.get("mapid"), payload.get("action"), sorted(payload.keys())
            ))
            map_metrics.callback(payload.get("action"), _KNOWN_ACTIONS, "invalid", payload.get("mapid"))
            return jsonify({"error": "invalid payload", "missing": missing}), 400
        try:
            result = updateMapDataDb(payload, "maps")
        except Exception as e:
            print("ERROR {} /maps/ db error: mapid={} err={}".format(request.method, payload.get("mapid"), e))
            map_metrics.callback(payload["action"], _KNOWN_ACTIONS, "db_error", payload.get("mapid"))
            return jsonify({"error": "db error", "detail": str(e)}), 500
        # updateMapDataDb answers {"error": "unknown mapid" | "unknown action"}
        # with a 200, so the HTTP metrics cannot see these.
        outcome = "saved"
        if isinstance(result, dict) and result.get("error"):
            outcome = str(result["error"]).replace(" ", "_")
            if outcome not in ("unknown_mapid", "unknown_action"):
                outcome = "db_error"
        map_metrics.callback(payload["action"], _KNOWN_ACTIONS, outcome, payload.get("mapid"))
        return result
    if request.method == "GET":
        print("List maps (groups={})".format(groups))
        result = getDataDb("maps", groups=groups)
        map_metrics.MAP_LISTS.labels(map_metrics.query_result(result)).inc()
        return result
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
            map_metrics.MAP_CREATES.labels("invalid").inc()
            return jsonify({"error": "invalid space_id"}), 400
        try:
            result = addDataDb(clearJson, "maps")
        except Exception as e:
            print("ERROR PUT /maps/ db error: mapid={} err={}".format(clearJson.get("mapid"), e))
            map_metrics.MAP_CREATES.labels("db_error").inc()
            return jsonify({"error": "db error", "detail": str(e)}), 500
        map_metrics.MAP_CREATES.labels("ok").inc()
        try:
            addToNats("maps", clearJson)
            map_metrics.MAP_NATS_PUBLISH.labels("maps", "ok").inc()
        except Exception as e:
            # The row exists but no worker will ever pick it up.
            print("NATS publish failed: {}".format(e))
            map_metrics.MAP_NATS_PUBLISH.labels("maps", "error").inc()
            print(json.dumps({"event": "map_publish_error", "mapid": str(clearJson.get("mapid") or ""),
                              "error": str(e)}, sort_keys=True), flush=True)
        return result
