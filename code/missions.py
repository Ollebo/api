from db.postgis import *
from flask import jsonify
import json
import datetime
import os

import requests

# ollebo-video mints a private per-session RTSP endpoint per stream. Unset =>
# the video block is omitted and the handshake behaves exactly as before.
VIDEO_API = os.environ.get("VIDEO_API", "")
VIDEO_TIMEOUT = float(os.environ.get("VIDEO_TIMEOUT", "3"))


def _video_block(mission_key, device_name=None):
    """Register a video stream for this mission and return its URLs.

    Best-effort by design: video is an add-on to the handshake, and a drone must
    still get its event ingest URLs when the video service is down or absent.
    Any failure returns None and the caller omits the block.
    """
    if not VIDEO_API:
        return None
    try:
        r = requests.post(
            "{}/v1/streams".format(VIDEO_API.rstrip("/")),
            json={"mission_key": str(mission_key), "device_name": device_name},
            timeout=VIDEO_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("video stream registration failed for mission {}: {}".format(mission_key, e))
        return None





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


def missionHello(key, request):
    # Boot-time handshake: mission pings once, we return its identity, media URLs,
    # current stats, and where to send live data next.
    m = getMissionHello(key)
    if not m:
        return jsonify({"ok": False, "error": "mission not found"}), 404
    mid = str(m["id"])
    base = request.url_root.rstrip("/")
    updated_at = m["stats_updated_at"]
    # A fresh video stream per handshake, since a handshake is a boot. The old
    # static `camera` URLs below are kept for clients that have not moved over.
    device_name = request.args.get("device") or (request.get_json(silent=True) or {}).get("device")
    video = _video_block(key, device_name)
    return jsonify({
        "ok": True,
        "mission_id": mid,
        "name": m["name"],
        "is_public": m["is_public"],
        "video": video,
        "camera": {
            "low":    m["camera_stream_low_url"],
            "medium": m["camera_stream_medium_url"],
            "high":   m["camera_stream_high_url"],
        },
        "pictures": {
            "low":    m["picture_upload_low_url"],
            "medium": m["picture_upload_medium_url"],
            "high":   m["picture_upload_high_url"],
        },
        "stats": {
            "events":     m["number_of_events"],
            "pictures":   m["number_of_pictures"],
            "updated_at": updated_at.isoformat() if updated_at else None,
        },
        # Where the mission sends live data next.
        "ingest": {
            "event_url":    "{}/event/{}".format(base, mid),
            "event_method": "PUT",
            "stream_url":   "{}/event/{}/stream".format(base, mid),
            "recent_url":   "{}/event/{}/recent".format(base, mid),
        },
    }), 200

    
