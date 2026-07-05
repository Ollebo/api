# API 

Api for ollebo.com

- Add new maps 
- Update maps
- Get maps

# Install

Build in docker and run as lamda function in AWS.
All actions are trigger by api-gateways calls


# Setup Docker Compose

Copy the docker-compose.yaml fil from the cp folder to the *fins folder* (In the fins-manager repo) (ORe what you called it)


# Buld and run
In the fins folder (ORe what you called it)
The default image is baes to run ad a small docker image in lamda. And for lcoal develoment its beste to use the docker compose image.
You also need a postgress database server to store the commands.




Build
```
docker-compose build
```

Run
```
docker compose run api /bin/bash
```

## Deploy

To deploy build the aws image and push to the registry. then update lamda to use th new image.

```
./deploy.sh
```
Will build and push the image


## Test

Use the following endpints 

https://vystletavc.execute-api.eu-north-1.amazonaws.com/v1/map/
https://api.ollebo.com

### Adding maps

This sill trigger the creating of map and the correct path to the file in the s3 bucket need to be correct

--> PUT
```
    {
        "name": "grangesberg",
        "tags": ["Country", "animals", "road"],
        "status": "uploaded",
        "access": "public",
        "originFile": "users/543524134233/geotiff/odm_orthophoto.original.tif",
        "mapid": "12345-12345-12345-12345",
        "accessid": "1234-1234-1234-1234",
        "action" : "makingMap"
        
    }
```

response

```
{
    "data": "accepted",
    "id": "1"
}
```

### Update map

--> POST

```
{
        "id": "3",
        "name": "viksjo",
        "tags": ["Country", "animals", "road"],
        "status": "active",
        "url":"none",
        "location": [17.822057235629273, 59.413808385194216],
        "area": {
          "type": "LineString",
          "coordinates": [
            [17.822057235629273, 59.413808385194216],
            [17.825134236343995, 59.41017389364913]
          ]
    }
    }
```

response

´´´
[
    {
        "name": "viksjo",
        "access": "public",
        "status": "active",
        "action": "makingMap",
        "tags": [
            "Country",
            "animals",
            "road"
        ],
        "location": "Point(17.822057235629273 59.413808385194216)"
    }
]
´´´

### Get Maps


--> GET

```
URL /map/?lon=17.825134&lat=59.410173
```

Response

```
```

---

# Mission events & live traffic

Missions carry a time-series of **events** (drone telemetry, sensor readings,
images…). Producers `PUT` events in; consumers read them back over HTTP —
either a one-shot recent history or a live **Server-Sent Events (SSE)** stream.

The API is the only gateway: producers/consumers talk HTTP, and the API fans
events through **NATS JetStream** internally. Events are also persisted to the
Postgres/TimescaleDB `mission_data` hypertable so history survives restarts.

## How it works

```
PUT /event/<key>            GET /event/<key>/stream (SSE)
      │                              ▲
      ▼                              │  backfill (Postgres) + live (NATS)
  resolve mission ──► Postgres  ─────┘
      │              (mission_data)
      ▼
   NATS JetStream
   public  → events.public.<id>
   private → events.private.<space_id>.<id>
```

- `<key>` in the path may be the mission **key** *or* its **id** — both resolve
  to the same mission (see `GET /mission/validate/<key>`).
- Events are stored and streamed keyed by the mission's canonical **id**.
- The stream subject is split by visibility so private traffic is isolated
  server-side. The `events.>` JetStream stream is (re)bound automatically on
  every deploy by the `nats-init` Job (`chart/templates/nats-init-job.yaml`).

## Public vs private missions

Read visibility is driven by the mission's `is_public` column
(`BOOLEAN NOT NULL DEFAULT FALSE` — a mission is public only when explicitly set).

| Mission | `GET /recent` & `/stream` |
|---|---|
| **public** (`is_public = true`) | open, no auth |
| **private** (`is_public = false`, the default) | requires `Authorization: Bearer <jwt>` whose `groups` claim contains the mission's `space_id`; otherwise `403` (bad/expired token → `401`) |

This is the same JWT-`groups`-vs-`space_id` model used by the maps read
endpoints (`GET /maps/`, `POST /search/`).

The Bearer token is a **Keycloak** JWT (verified via JWKS). Its `groups` claim
carries the caller's Keycloak **group ids, which equal the `space.id` UUIDs**
(`dw` sets `space.id` = the Keycloak group UUID) — so a caller can read a private
mission/map exactly when that resource's `space_id` is one of their group UUIDs.
Non-UUID `groups` entries are ignored. Verification is enabled by the
`JWT_JWKS_URL` / `JWT_ISSUER` / `JWT_AUDIENCE` env vars (chart `jwt.*` values);
with `JWT_JWKS_URL` unset, auth is disabled and only public data is served.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `PUT`  | `/event/<key>` | Append one event (see `Event` schema). Returns `{"data":"stored"}`. |
| `GET`  | `/event/<key>/recent?minutes=15` | Last N minutes (1–60) from Postgres, ascending. |
| `GET`  | `/event/<key>/stream` | SSE: `backfill` → `ready` → `live` frames, `: ping` keepalive every 15s. |
| `PUT`  | `/mission/<key>/picture/<picture_id>` | Upload the image bytes for a `picture` event (phase 2). Body is the raw image. Returns `{"data":"uploaded","url":…}`. |
| `GET`  | `/mission/<key>/picture/<picture_id>` | Retrieve the stored image bytes back through the API. |
| `GET`  | `/mission/validate/<key>` | Resolve a key → `{valid, mission_id, name}`. |

### Event types

Every event carries a `type`. The endpoint understands four canonical types
(plus two legacy aliases kept working); an unknown `type` is still stored and
logged, never rejected. Mapped columns land in `mission_data`; per-type detail
rides in the `jsonData` JSONB and round-trips verbatim on the live stream.

| `type` | Meaning | Key fields |
|---|---|---|
| `location` (alias `telemetry`) | GPS position of a drone/boat/rover | `geopoint` `[lon,lat]`, `x`/`y`/`z`, `device` |
| `measurement` (alias `temperature`) | A generic sensor reading — temperature, humidity, **solar exposure**, anything | value in `data`; `jsonData.{kind,unit}` (temperature also fills `temp`/`humidity`) |
| `picture` | A photo, in **two phases** (announce → upload bytes later) | `jsonData.{picture_id,status}`; `img` becomes the stored URL once uploaded |
| `alert` | A detection ("person detected", etc.) | `jsonData.{kind,severity,message}` |

Examples (each is a body for `PUT /event/<key>`):

```jsonc
// measurement — a solar-exposure reading
{"type":"measurement","data":842.5,"geopoint":[18.0686,59.3293],
 "device":"sensor-01","jsonData":{"kind":"solar","unit":"W/m2","name":"Weather 01"}}

// alert — person detected
{"type":"alert","geopoint":[18.0686,59.3293],"device":"drone-01",
 "jsonData":{"kind":"person","severity":"high","message":"Person detected in the search area"}}
```

### Producing (mock a drone sending telemetry)

```bash
curl -X PUT https://api.ollebo.com/event/<mission-key> \
  -H "Content-Type: application/json" \
  -d '{
        "type": "telemetry",
        "geopoint": [18.0686, 59.3293],
        "z": 42.0,
        "temp": 21.4,
        "device": "drone-01",
        "jsonData": {"battery": 98, "heading": 90, "speed": 8.0}
      }'
# -> {"data":"stored"}
```

`geopoint` is `[longitude, latitude]` (PostGIS order); `z` is a free numeric
axis, commonly altitude. Any keys you put in `jsonData` (or extra top-level
keys) come back **verbatim** in the `payload` of each live SSE frame, so you can
carry app-specific fields.

### Consuming live traffic (SSE)

`backfill`/`recent` rows are DB shape; `live` frames are
`{"timestamp", "payload": <the exact body you PUT>}`.

```bash
curl -N https://api.ollebo.com/event/<mission-key>/stream
# event: backfill\ndata: {...}\n\n     (replayed history, last 15 min)
# event: ready\ndata: {}\n\n           (caught up; live follows)
# event: live\ndata: {"timestamp":"…","payload":{…}}\n\n
```

Browser / frontend:

```js
const es = new EventSource(`https://api.ollebo.com/event/${key}/stream`);
es.addEventListener("backfill", e => render(JSON.parse(e.data)));   // history
es.addEventListener("ready",    () => console.log("live"));
es.addEventListener("live",     e => render(JSON.parse(e.data).payload));
// NOTE: EventSource cannot set an Authorization header — for PRIVATE missions
// use a fetch()-based SSE reader (or an ?access_token=… scheme) instead.
```

Private mission with a token:

```bash
curl -N https://api.ollebo.com/event/<private-key>/stream \
  -H "Authorization: Bearer $JWT"      # JWT.groups must contain the mission space_id
```

### All public missions in one stream (firehose)

`GET /event/public/stream` is a single SSE feed of **every** public mission (no
auth). It's **live-only** (no backfill); each `live` frame's data includes
`mission_id` so you know which mission each event came from:

```js
new EventSource("https://api.ollebo.com/event/public/stream")
  .addEventListener("live", e => {
    const { mission_id, timestamp, payload } = JSON.parse(e.data);
    // payload.device, payload.geopoint, payload.jsonData.{assetType,altitude,…}
  });
```

## Pictures (two-phase upload + retrieval)

A drone announces a photo the instant it takes it, but the bytes may arrive much
later (poor connectivity → upload when reconnected). So pictures are **two
phases**:

1. **Announce** — `PUT /event/<key>` with `type:"picture"` and a `picture_id` in
   `jsonData` (status defaults to `pending`). This is a normal event: it lands in
   `mission_data` and streams live like any other.
2. **Upload the bytes** — later, `PUT /mission/<key>/picture/<picture_id>` with
   the raw image as the body. The API stores it in object storage, flips the
   matching row to `status:"uploaded"` and sets `img` to the stored URL, and
   re-publishes a `picture`/`uploaded` frame so live subscribers see the
   transition. (If the bytes arrive before the announce event, a fresh uploaded
   row is created instead.)

Retrieve the image any time with `GET /mission/<key>/picture/<picture_id>` — it
streams the bytes back through the API (works regardless of bucket ACL).

```bash
# 1. announce
curl -X PUT https://api.ollebo.com/event/<key> -H 'Content-Type: application/json' \
  -d '{"type":"picture","geopoint":[18.0686,59.3293],"jsonData":{"picture_id":"p-1","status":"pending"}}'
# 2. upload the bytes (later)
curl -X PUT --data-binary @photo.jpg -H 'Content-Type: image/jpeg' \
  https://api.ollebo.com/mission/<key>/picture/p-1
# -> {"data":"uploaded","url":"https://hel1.your-objectstorage.com/map-storage/<realm>/missions/<id>/pictures/p-1"}
# 3. fetch it back
curl https://api.ollebo.com/mission/<key>/picture/p-1 --output got.jpg
```

**Object storage.** Bytes go to the same S3-compatible backend as the `dw` app
(Hetzner Object Storage in prod), using the shared `AWS_*` conventions and
credentials from the `ollebo` k8s Secret. Objects are keyed
`<realm>/missions/<mission_id>/pictures/<picture_id>` in the `map-storage`
bucket. Config (chart `storage.*` / env): `AWS_ENDPOINT`, `AWS_BUCKET`,
`AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. Locally,
`docker-compose` runs **MinIO** as a stand-in (bucket auto-created) so the whole
flow works offline.

## Dummy traffic simulator

`code/simulator.py` pushes realistic dummy traffic so the GUI has live data to
render. It drives several moving assets of different types (**drone / boat /
rover**) at different locations plus a fixed measurement sensor, and emits **every
event type**: `location` telemetry, `measurement` (temperature/humidity/solar),
`picture` (announced then uploaded a few ticks later, simulating bad internet),
and `alert` detections — all into the public mission. It runs as a pod beside the
API (`chart/templates/simulator.yaml`, gated by `simulator.enabled`, on by
default) and can also be run locally:

```bash
API_BASE=https://api.ollebo.com \
MISSION_KEY=a744e376-b35c-43ce-8c61-b82d8bb9f9d0 \
python3 code/simulator.py
# knobs (env): INTERVAL_SECONDS, DRONES, BOATS, ROVERS, TEMP_SENSORS, TEMP_EVERY,
#              MEASUREMENT_KINDS, PICTURE_EVERY, PICTURE_UPLOAD_DELAY_TICKS,
#              ALERT_EVERY, MAX_TICKS
```

Moving assets emit `jsonData.{assetType,name,model,altitude,heading,speed,
battery,visibility}` so the ollebo-maps consumer renders them directly. **Turn it
off in prod once real data flows:** set `simulator.enabled: false` in
`chart/values.yaml` and redeploy.

## Version / which build is live

```bash
curl -s https://api.ollebo.com/version
# {"name":"ollebo-api","version":"<git-sha>"}   ("dev" for local builds)
```

## Interactive API docs

The full OpenAPI spec (all maps, missions, and event endpoints, with schemas
and auth) is served live: **`https://api.ollebo.com/doc`** (raw JSON at
`/doc/openapi.json`).

## End-to-end test

`test/e2e_mission_stream.py` mocks a drone flight into the public mission and
verifies ingest + backfill + live stream + the private auth gate (stdlib only):

```bash
API_BASE=https://api.ollebo.com python3 test/e2e_mission_stream.py
```

Or via the `/e2e-mission-stream` Claude skill.

## Feature demo tool

`test/demo_features.py` fires one of **each** event type into a mission so you can
see the features live — a `measurement`, a `person detected` `alert`, and a
two-phase `picture` that pulls a **real cat photo off the internet**
(`cataas.com`), uploads it, and retrieves it back byte-for-byte (stdlib only):

```bash
python3 test/demo_features.py
# watch it land, in another terminal:
curl -N http://localhost:8888/event/<MISSION_KEY>/stream
# knobs (env): API_BASE, MISSION_KEY, CAT_URL   (falls back to a generated image offline)
```
