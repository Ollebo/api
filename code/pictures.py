"""Phase 2 of the two-phase picture flow: deferred image-byte upload.

Phase 1 is a normal `type=picture` event (see event.py) that lands a `pending`
row in mission_data. The drone, once it has connectivity, later PUTs the raw
image bytes here keyed by the same picture_id. We store the bytes in object
storage, flip the row to `uploaded` with the object URL, and re-publish to NATS
so live SSE subscribers see the pending->uploaded transition.
"""
from flask import jsonify, Response

import storage
from event import resolve_mission, subject_for
from db.postgis import setPictureUploaded
from db.natsQue import addToNats


def upload_picture(mission_key, picture_id, request):
    mission = resolve_mission(mission_key)
    if mission is None:
        return jsonify({"error": "mission not found"}), 404

    # Write posture mirrors event() ingest: no JWT on writes today. Tighten
    # later alongside the event endpoint if writes become authenticated.
    data = request.get_data()
    if not data:
        return jsonify({"error": "empty body", "missing": ["<image bytes>"]}), 400
    content_type = request.headers.get("Content-Type", "image/jpeg")

    try:
        url = storage.put_picture(mission["id"], picture_id, content_type, data)
    except Exception as e:
        print("picture upload store failed: {}".format(e))
        return jsonify({"error": "storage error", "detail": str(e)}), 500

    result = setPictureUploaded(mission["id"], picture_id, url)
    if "error" in result:
        return jsonify({"error": "db error", "detail": result["error"]}), 500

    subject = subject_for(mission)
    if subject is not None:
        try:
            addToNats(subject, {"mission_id": mission["id"], "payload": {
                "type": "picture",
                "img": url,
                "jsonData": {"picture_id": picture_id, "status": "uploaded"},
            }})
        except Exception as e:
            print("NATS publish failed: {}".format(e))

    return jsonify({"data": "uploaded", "url": url}), 200


def download_picture(mission_key, picture_id, request):
    """Retrieve previously-stored image bytes back through the API.

    The store/retrieve counterpart to upload_picture — works regardless of
    whether the bucket allows anonymous GET.
    """
    mission = resolve_mission(mission_key)
    if mission is None:
        return jsonify({"error": "mission not found"}), 404

    try:
        result = storage.get_picture(mission["id"], picture_id)
    except Exception as e:
        print("picture fetch failed: {}".format(e))
        return jsonify({"error": "storage error", "detail": str(e)}), 500

    if result is None:
        return jsonify({"error": "picture not found"}), 404

    data, content_type = result
    return Response(data, mimetype=content_type or "application/octet-stream")
