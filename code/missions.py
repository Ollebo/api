from db.postgis import *
from flask import jsonify
import json
import datetime





def missions(payload,request):
    print(request.method)

    if request.method == "GET":
        # get missions
        return getMissions("id", "ready")


def mission(id,request):
    print(request.method)

    if request.method == "GET":
        # get missions
        return getMission(id)


def missionValidate(key, request):
    # Validate a mission key (clients call this on startup); reply confirms validity.
    m = getMissionByKey(key)
    if not m:
        return jsonify({"valid": False}), 404
    return jsonify({"valid": True, "mission_id": str(m["id"]), "name": m["name"]}), 200

    
