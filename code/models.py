from db.postgis import updateModelDataDb, getModelsDb
from flask import jsonify
import datetime


_KNOWN_ACTIONS = ("makingModel", "ready", "error")


def _validate_post(payload):
    if not isinstance(payload, dict):
        return ["<body>"]
    missing = [k for k in ("modelid", "action") if not payload.get(k)]
    if missing:
        return missing
    action = payload["action"]
    if action not in _KNOWN_ACTIONS:
        return ["action(unknown:{})".format(action)]
    # A finished model must carry the copied file's path.
    if action == "ready" and not (payload.get("originFile") or payload.get("originfile")):
        return ["originFile"]
    return []


def models(payload, request, groups=None):
    print(request.method)

    # The map-maker worker copies the model file into the public/private bucket
    # and reports the result via PATCH /models/<modelid>. POST is the same path.
    if request.method in ("POST", "PATCH"):
        if payload is None:
            print("ERROR {} /models/ bad payload: missing=['<body>']".format(request.method))
            return jsonify({"error": "missing body", "missing": ["<body>"]}), 400
        payload["recordtime"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        missing = _validate_post(payload)
        if missing:
            print("ERROR {} /models/ bad payload: missing={} modelid={} action={} keys={}".format(
                request.method, missing, payload.get("modelid"), payload.get("action"), sorted(payload.keys())
            ))
            return jsonify({"error": "invalid payload", "missing": missing}), 400
        try:
            return updateModelDataDb(payload, "model")
        except Exception as e:
            print("ERROR {} /models/ db error: modelid={} err={}".format(request.method, payload.get("modelid"), e))
            return jsonify({"error": "db error", "detail": str(e)}), 500

    if request.method == "GET":
        print("List models (groups={})".format(groups))
        return getModelsDb(groups=groups)

    return jsonify({"error": "unsupported method"}), 405
