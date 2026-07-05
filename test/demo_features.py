#!/usr/bin/env python3
"""Demo/test tool — exercises every mission event type end-to-end.

Fires one of each event kind into a mission so you can see the features live
(open the SSE stream in another terminal while this runs):

    measurement  a solar-exposure sensor reading
    alert        a "person detected" detection
    picture      a two-phase photo: announce it (status pending), then upload
                 REAL image bytes fetched from the internet — a cat from
                 cataas.com — linking it into the flight, and finally retrieve
                 the bytes back through the API to prove the round-trip.

Pure stdlib (urllib), no deps. Run against the local docker-compose stack:

    python3 test/demo_features.py

Watch it land live in another terminal:

    curl -N http://localhost:8888/event/<MISSION_KEY>/stream

Config (env, all optional):
    API_BASE     default http://localhost:8888
    MISSION_KEY  default dddddddd-dddd-dddd-dddd-dddddddddddd  (local public
                 mission; accepts the mission key or its id)
    CAT_URL      default https://cataas.com/cat
"""
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

API_BASE = os.environ.get("API_BASE", "http://localhost:8888").rstrip("/")
MISSION_KEY = os.environ.get("MISSION_KEY", "dddddddd-dddd-dddd-dddd-dddddddddddd")
CAT_URL = os.environ.get("CAT_URL", "https://cataas.com/cat")

# A point over Stockholm so the events land somewhere sensible on the map.
GEOPOINT = [18.0686, 59.3293]


def _req(method, url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def put_event(payload):
    status, _h, body = _req(
        "PUT", "{}/event/{}".format(API_BASE, MISSION_KEY),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    return status, body.decode("utf-8", "replace")


def fetch_cat():
    """Grab a real cat image off the internet. Returns (bytes, content_type).

    Falls back to a generated PNG if the internet isn't reachable from here, so
    the demo still shows the upload/retrieve feature offline.
    """
    try:
        status, headers, data = _req("GET", CAT_URL, headers={"User-Agent": "ollebo-demo/1.0"})
        if status == 200 and data:
            ctype = headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
            return data, ctype, CAT_URL
        print("  ! cat fetch returned HTTP {} — using a generated fallback image".format(status))
    except Exception as e:
        print("  ! cat fetch failed ({}) — using a generated fallback image".format(e))
    return _fallback_png(), "image/png", "(generated fallback)"


def _fallback_png():
    import struct, zlib
    w = h = 64
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            raw += bytes([(x * 4) & 255, (y * 4) & 255, ((x + y) * 2) & 255])

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def step(n, title):
    print("\n[{}] {}".format(n, title))


def main():
    print("demo -> {}  mission={}".format(API_BASE, MISSION_KEY))

    step(1, "measurement — solar exposure reading")
    status, body = put_event({
        "type": "measurement",
        "data": 842.5,
        "geopoint": GEOPOINT,
        "device": "sensor-demo",
        "jsonData": {"assetType": "sensor", "name": "Demo Sensor", "kind": "solar", "unit": "W/m2"},
    })
    print("  PUT /event -> {} {}".format(status, body))

    step(2, "alert — person detected")
    status, body = put_event({
        "type": "alert",
        "geopoint": GEOPOINT,
        "device": "drone-demo",
        "jsonData": {
            "assetType": "drone", "name": "Demo Drone",
            "kind": "person", "severity": "high",
            "message": "Person detected in the search area",
        },
    })
    print("  PUT /event -> {} {}".format(status, body))

    step(3, "picture (phase 1) — announce the photo")
    picture_id = "demo-cat-{}".format(uuid.uuid4().hex[:8])
    status, body = put_event({
        "type": "picture",
        "geopoint": GEOPOINT,
        "device": "drone-demo",
        "jsonData": {
            "assetType": "drone", "name": "Demo Drone",
            "picture_id": picture_id, "status": "pending", "camera": "RGB",
        },
    })
    print("  picture_id={}".format(picture_id))
    print("  PUT /event -> {} {}".format(status, body))

    step(4, "picture (phase 2) — fetch a cat from the internet and upload it")
    cat_bytes, cat_ctype, source = fetch_cat()
    print("  fetched {} bytes ({}) from {}".format(len(cat_bytes), cat_ctype, source))
    status, _h, body = _req(
        "PUT", "{}/mission/{}/picture/{}".format(API_BASE, MISSION_KEY, picture_id),
        data=cat_bytes, headers={"Content-Type": cat_ctype},
    )
    print("  PUT /mission/.../picture -> {} {}".format(status, body.decode("utf-8", "replace")))
    try:
        stored_url = json.loads(body).get("url")
    except Exception:
        stored_url = None

    step(5, "picture retrieval — fetch it back through the API")
    status, headers, data = _req("GET", "{}/mission/{}/picture/{}".format(API_BASE, MISSION_KEY, picture_id))
    ok = status == 200 and data == cat_bytes
    print("  GET /mission/.../picture -> {} content-type={} bytes={}".format(
        status, headers.get("Content-Type"), len(data)))
    print("  round-trip byte-identical: {}".format("YES" if ok else "NO"))

    print("\nDone. The cat is now linked into the flight as picture '{}'.".format(picture_id))
    if stored_url:
        print("  stored object URL : {}".format(stored_url))
    print("  fetch via the API : {}/mission/{}/picture/{}".format(API_BASE, MISSION_KEY, picture_id))
    print("  recent events     : {}/event/{}/recent".format(API_BASE, MISSION_KEY))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
