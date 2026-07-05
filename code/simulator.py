#!/usr/bin/env python3
"""Mission-event simulator — pushes dummy drone/boat/rover + sensor traffic.

Feeds a live SSE stream so the ollebo-maps GUI has something to render. Drives
several moving assets (different types, different locations) plus a fixed
weather/measurement sensor, all PUT into one public mission. Pure stdlib
(urllib) so it runs from a laptop or inside the api image with no extra deps.

Run locally:
    API_BASE=https://api.ollebo.com python3 code/simulator.py
In-cluster (chart Deployment) it defaults to API_BASE=http://api:8080.

Emits every event type the endpoint understands:
    location    moving-asset GPS/telemetry (type "telemetry", a location alias)
    measurement generic sensor value (temperature/humidity/solar) in top-level
                `data` + jsonData{kind,unit}
    picture     two-phase photo: a type "picture" event (status pending) now,
                then the actual image bytes PUT to /mission/<key>/picture/<id>
                a few ticks LATER (simulating a drone with bad internet)
    alert       a detection (person/animal/vehicle/...) in jsonData{kind,severity,message}

Payload matches what the GUI reads (liveDrones.ts:eventRowToDroneUpdate):
device, geopoint=[lon,lat], and jsonData.{altitude,heading,speed,name,model,
user,visibility,assetType}. Top-level type/temp/humidity/geopoint/x/y/z/data/
device persist to mission_data columns; custom fields ride in jsonData.

Config (env, all optional):
    API_BASE          default http://api:8080
    MISSION_KEY       default a744e376-b35c-43ce-8c61-b82d8bb9f9d0  (demo public mission; key or id)
    INTERVAL_SECONDS  default 2      seconds between ticks
    DRONES/BOATS/ROVERS/TEMP_SENSORS  default 2/1/1/1
    TEMP_EVERY        default 5      emit a measurement every N ticks
    MEASUREMENT_KINDS default temperature,humidity,solar  (comma-separated)
    PICTURE_EVERY     default 8      each asset emits a picture event every N ticks
    PICTURE_UPLOAD_DELAY_TICKS  default 3   ticks between a picture event and its byte upload
    ALERT_EVERY       default 12     an asset emits an alert every N ticks
    MAX_TICKS         default 0      0 = run forever
"""
import base64
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.request
import uuid

API_BASE = os.environ.get("API_BASE", "http://api:8080").rstrip("/")
MISSION_KEY = os.environ.get("MISSION_KEY", "a744e376-b35c-43ce-8c61-b82d8bb9f9d0")
INTERVAL = float(os.environ.get("INTERVAL_SECONDS", "2"))
DRONES = int(os.environ.get("DRONES", "2"))
BOATS = int(os.environ.get("BOATS", "1"))
ROVERS = int(os.environ.get("ROVERS", "1"))
TEMP_SENSORS = int(os.environ.get("TEMP_SENSORS", "1"))
TEMP_EVERY = max(1, int(os.environ.get("TEMP_EVERY", "5")))
MEASUREMENT_KINDS = [k.strip() for k in os.environ.get(
    "MEASUREMENT_KINDS", "temperature,humidity,solar").split(",") if k.strip()]
PICTURE_EVERY = max(1, int(os.environ.get("PICTURE_EVERY", "8")))
PICTURE_UPLOAD_DELAY_TICKS = max(1, int(os.environ.get("PICTURE_UPLOAD_DELAY_TICKS", "3")))
ALERT_EVERY = max(1, int(os.environ.get("ALERT_EVERY", "12")))
MAX_TICKS = int(os.environ.get("MAX_TICKS", "0"))

# Units advertised for each measurement kind (rides in jsonData.unit).
_MEASUREMENT_UNITS = {"temperature": "C", "humidity": "%", "solar": "W/m2"}
# What a drone/boat might flag. Free-form; consumed by the GUI's alert layer.
_ALERT_KINDS = ["person", "animal", "vehicle", "fire", "boat in distress", "debris"]
# A tiny valid 1x1 JPEG — the actual bytes a "photo upload" carries in the demo.
# The API stores whatever bytes arrive; a real image just makes the URL render.
_PIXEL_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAAAv/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AfwD/2Q=="
)

# Named base locations [lon, lat] reused from ollebo-maps dummy data.
_BASES = [
    ("Stockholm", [18.0686, 59.3293]),
    ("Norrbotten Base camp", [22.146, 67.512]),
    ("Stockholm archipelago", [18.32, 59.30]),
    ("Junosuando Takeoff A", [22.183, 67.529]),
    ("Rane river bend", [21.964, 67.488]),
]
_MODELS = ["DJI Mavic 3", "DJI Air 2S", "Parrot Anafi", "Autel EVO II", "Skydio 2+", "Custom Build"]
_USERS = ["mattias", "anders", "lina", "erik", "fleet-ops"]

# Per-type motion profile: cruise speed (m/s), altitude range (m), heading jitter (deg).
_PROFILE = {
    "drone": {"speed": (6.0, 18.0), "alt": (40.0, 400.0), "jitter": 25.0, "radius_m": 1500.0},
    "boat":  {"speed": (2.0, 7.0),  "alt": (0.0, 2.0),    "jitter": 12.0, "radius_m": 2500.0},
    "rover": {"speed": (1.0, 4.0),  "alt": (0.0, 3.0),    "jitter": 30.0, "radius_m": 800.0},
}

_METERS_PER_DEG_LAT = 111320.0


class Asset:
    def __init__(self, device, asset_type, name, base):
        self.device = device
        self.asset_type = asset_type
        self.name = name
        self.model = random.choice(_MODELS)
        self.user = random.choice(_USERS)
        self.base_lon, self.base_lat = base
        self.lon, self.lat = base
        prof = _PROFILE[asset_type]
        self.speed = random.uniform(*prof["speed"])
        self.heading = random.uniform(0, 360)
        lo, hi = prof["alt"]
        self.alt = random.uniform(lo, hi)
        self._alt_lo, self._alt_hi = lo, hi
        self._alt_dir = 1.0
        self.battery = random.uniform(60, 100)
        self.jitter = prof["jitter"]
        self.radius_m = prof["radius_m"]

    def step(self, dt):
        # Advance along current heading, converting metres travelled to degrees.
        dist = self.speed * dt
        rad = math.radians(self.heading)
        dlat = (dist * math.cos(rad)) / _METERS_PER_DEG_LAT
        cos_lat = max(0.05, math.cos(math.radians(self.lat)))
        dlon = (dist * math.sin(rad)) / (_METERS_PER_DEG_LAT * cos_lat)
        self.lat += dlat
        self.lon += dlon

        # Steer back toward base once beyond the radius, else wander a little.
        if self._dist_to_base_m() > self.radius_m:
            self.heading = self._bearing_to_base()
        else:
            self.heading = (self.heading + random.uniform(-self.jitter, self.jitter)) % 360

        # Altitude oscillation (drones move a lot; boats/rovers barely).
        span = self._alt_hi - self._alt_lo
        if span > 0:
            self.alt += self._alt_dir * span * 0.05
            if self.alt >= self._alt_hi:
                self.alt, self._alt_dir = self._alt_hi, -1.0
            elif self.alt <= self._alt_lo:
                self.alt, self._alt_dir = self._alt_lo, 1.0

        self.battery -= random.uniform(0.1, 0.6)
        if self.battery <= 10:
            self.battery = 100.0

    def _dist_to_base_m(self):
        dlat = (self.lat - self.base_lat) * _METERS_PER_DEG_LAT
        dlon = (self.lon - self.base_lon) * _METERS_PER_DEG_LAT * math.cos(math.radians(self.lat))
        return math.hypot(dlat, dlon)

    def _bearing_to_base(self):
        dlat = self.base_lat - self.lat
        dlon = self.base_lon - self.lon
        return math.degrees(math.atan2(dlon, dlat)) % 360

    def telemetry(self):
        return {
            "type": "telemetry",
            "geopoint": [round(self.lon, 6), round(self.lat, 6)],
            "x": round(self.lon, 6),
            "y": round(self.lat, 6),
            "z": round(self.alt, 1),
            "device": self.device,
            "jsonData": {
                "assetType": self.asset_type,
                "name": self.name,
                "model": self.model,
                "user": self.user,
                "altitude": round(self.alt, 1),
                "heading": round(self.heading, 1),
                "speed": round(self.speed, 1),
                "battery": round(self.battery, 1),
                "visibility": "public",
            },
        }

    def picture(self):
        # Phase 1 of the two-phase picture flow: announce the photo now; the
        # bytes get uploaded a few ticks later (see put_picture_bytes). Returns
        # (picture_id, payload) so the caller can schedule the deferred upload.
        picture_id = uuid.uuid4().hex
        return picture_id, {
            "type": "picture",
            "geopoint": [round(self.lon, 6), round(self.lat, 6)],
            "device": self.device,
            "img": "none",
            "jsonData": {
                "assetType": self.asset_type,
                "name": self.name,
                "picture_id": picture_id,
                "status": "pending",
                "camera": "RGB",
            },
        }

    def alert(self):
        kind = random.choice(_ALERT_KINDS)
        severity = random.choice(["low", "medium", "high"])
        return {
            "type": "alert",
            "geopoint": [round(self.lon, 6), round(self.lat, 6)],
            "device": self.device,
            "jsonData": {
                "assetType": self.asset_type,
                "name": self.name,
                "kind": kind,
                "severity": severity,
                "message": "{} detected {}".format(self.name, kind),
            },
        }


class Sensor:
    """Fixed measurement sensor — emits generic `measurement` events.

    Cycles through the configured MEASUREMENT_KINDS (temperature/humidity/solar
    by default). The numeric value rides in the top-level `data` column; `kind`
    and `unit` ride in jsonData. For the temperature kind we also populate the
    dedicated temp/humidity columns for backward compatibility with older
    consumers.
    """
    def __init__(self, device, name, base):
        self.device = device
        self.name = name
        self.lon, self.lat = base
        self.temp = random.uniform(8, 18)
        self._kind_idx = 0

    def _value(self, kind):
        if kind == "temperature":
            # Small random walk so the value drifts realistically.
            self.temp = max(-20.0, min(40.0, self.temp + random.uniform(-0.4, 0.4)))
            return round(self.temp, 1)
        if kind == "humidity":
            return round(random.uniform(40, 85), 1)
        if kind == "solar":
            return round(random.uniform(0, 1000), 1)
        return round(random.uniform(0, 100), 1)

    def reading(self):
        kind = MEASUREMENT_KINDS[self._kind_idx % len(MEASUREMENT_KINDS)]
        self._kind_idx += 1
        value = self._value(kind)
        payload = {
            "type": "measurement",
            "data": value,
            "geopoint": [round(self.lon, 6), round(self.lat, 6)],
            "device": self.device,
            "jsonData": {
                "assetType": "sensor",
                "name": self.name,
                "kind": kind,
                "unit": _MEASUREMENT_UNITS.get(kind, ""),
            },
        }
        # Back-compat: keep the dedicated columns populated for temp/humidity.
        if kind == "temperature":
            payload["temp"] = value
            payload["humidity"] = round(random.uniform(40, 85), 1)
        elif kind == "humidity":
            payload["humidity"] = value
        return payload


def put_event(payload):
    req = urllib.request.Request(
        "{}/event/{}".format(API_BASE, MISSION_KEY),
        data=json.dumps(payload).encode("utf-8"),
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # transport error — log and keep going
        print("send failed for {}: {}".format(payload.get("device"), e), flush=True)
        return -1


def put_picture_bytes(picture_id, data):
    # Phase 2: upload the raw image bytes for a previously-announced picture.
    req = urllib.request.Request(
        "{}/mission/{}/picture/{}".format(API_BASE, MISSION_KEY, picture_id),
        data=data,
        method="PUT",
        headers={"Content-Type": "image/jpeg"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # transport error — log and keep going
        print("upload failed for {}: {}".format(picture_id, e), flush=True)
        return -1


def build_roster():
    assets, sensors = [], []
    plan = [("drone", DRONES), ("boat", BOATS), ("rover", ROVERS)]
    for asset_type, count in plan:
        for i in range(count):
            n = i + 1
            base = _BASES[(len(assets) + i) % len(_BASES)][1]
            device = "{}-{:02d}".format(asset_type, n)
            name = "{} {:02d}".format(asset_type.capitalize(), n)
            assets.append(Asset(device, asset_type, name, base))
    for i in range(TEMP_SENSORS):
        base = _BASES[i % len(_BASES)][1]
        sensors.append(Sensor("sensor-{:02d}".format(i + 1), "Weather {:02d}".format(i + 1), base))
    return assets, sensors


def main():
    assets, sensors = build_roster()
    print("simulator -> {}  mission={}  interval={}s".format(API_BASE, MISSION_KEY, INTERVAL), flush=True)
    print("assets: {}  sensors: {}".format(
        ", ".join(a.device for a in assets), ", ".join(s.device for s in sensors)), flush=True)

    tick = 0
    sent = 0
    last_status = None
    pending_uploads = []  # (due_tick, picture_id) — deferred phase-2 byte uploads
    while MAX_TICKS == 0 or tick < MAX_TICKS:
        tick += 1
        for a in assets:
            a.step(INTERVAL)
            last_status = put_event(a.telemetry())
            sent += 1
            # Occasionally take a photo (announce now, upload the bytes later).
            if tick % PICTURE_EVERY == 0:
                picture_id, payload = a.picture()
                last_status = put_event(payload)
                sent += 1
                pending_uploads.append((tick + PICTURE_UPLOAD_DELAY_TICKS, picture_id))
            # Occasionally raise an alert.
            if tick % ALERT_EVERY == 0:
                last_status = put_event(a.alert())
                sent += 1
        if tick % TEMP_EVERY == 0:
            for s in sensors:
                last_status = put_event(s.reading())
                sent += 1
        # Fire any deferred picture uploads that have now "reconnected".
        due = [pid for due_tick, pid in pending_uploads if due_tick <= tick]
        for picture_id in due:
            last_status = put_picture_bytes(picture_id, _PIXEL_JPEG)
            sent += 1
        if due:
            pending_uploads = [pu for pu in pending_uploads if pu[0] > tick]
        if tick % 15 == 0:
            print("tick {} — {} events sent (last status {})".format(tick, sent, last_status), flush=True)
        time.sleep(INTERVAL)

    print("done: {} ticks, {} events sent".format(tick, sent), flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
        sys.exit(130)
