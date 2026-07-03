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

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `PUT`  | `/event/<key>` | Append one event (see `Event` schema). Returns `{"data":"stored"}`. |
| `GET`  | `/event/<key>/recent?minutes=15` | Last N minutes (1–60) from Postgres, ascending. |
| `GET`  | `/event/<key>/stream` | SSE: `backfill` → `ready` → `live` frames, `: ping` keepalive every 15s. |
| `GET`  | `/mission/validate/<key>` | Resolve a key → `{valid, mission_id, name}`. |

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

## Dummy traffic simulator

`code/simulator.py` pushes realistic dummy telemetry so the GUI has live data to
render. It drives several moving assets of different types (**drone / boat /
rover**) at different locations plus a fixed **temperature** sensor, all into the
public mission. It runs as a pod beside the API (`chart/templates/simulator.yaml`,
gated by `simulator.enabled`, on by default) and can also be run locally:

```bash
API_BASE=https://api.ollebo.com \
MISSION_KEY=6f737b8c-f2ff-4e67-b7ee-abf29a2d7373 \
python3 code/simulator.py
# knobs (env): INTERVAL_SECONDS, DRONES, BOATS, ROVERS, TEMP_SENSORS, TEMP_EVERY, MAX_TICKS
```

Each asset emits the `Event` shape above with `jsonData.{assetType,name,model,
altitude,heading,speed,battery,visibility}` so the ollebo-maps consumer renders
it directly. **Turn it off in prod once real data flows:** set
`simulator.enabled: false` in `chart/values.yaml` and redeploy.

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
