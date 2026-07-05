OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Ollebo API",
        "version": "1.0.0",
        "description": "HTTP API for managing maps (orthophotos/geotiffs), missions and time-series events. Backed by PostGIS + NATS JetStream.",
    },
    "servers": [
        {"url": "/", "description": "Current host"},
    ],
    "tags": [
        {"name": "maps", "description": "Map (orthophoto) records stored in PostGIS"},
        {"name": "search", "description": "Postgres-backed search across maps"},
        {"name": "missions", "description": "Mission records"},
        {"name": "events", "description": "Time-series mission events"},
        {"name": "meta", "description": "Service health / liveness"},
    ],
    "paths": {
        "/version": {
            "get": {
                "tags": ["meta"],
                "summary": "Build version",
                "description": "Returns the running build's version (the commit SHA baked into the image at build time; `dev` for local builds).",
                "responses": {
                    "200": {
                        "description": "Version info",
                        "content": {"application/json": {"schema": {"type": "object", "properties": {"name": {"type": "string"}, "version": {"type": "string"}}}}},
                    }
                },
            },
        },
        "/": {
            "get": {
                "tags": ["meta"],
                "summary": "Liveness probe",
                "responses": {"200": {"description": "Service is up", "content": {"text/plain": {"schema": {"type": "string"}}}}},
            },
            "post": {
                "tags": ["meta"],
                "summary": "Echo / no-op POST",
                "responses": {"200": {"description": "OK"}},
            },
        },
        "/maps/": {
            "get": {
                "tags": ["maps"],
                "summary": "List maps",
                "description": "Visibility-filtered listing. Without a token, returns only rows where `access='public'`. With a valid `Authorization: Bearer <jwt>`, also returns rows whose `space_id` appears in the token's `groups` claim. Invalid or expired tokens return 401; missing tokens are treated as anonymous.",
                "security": [{"BearerAuth": []}, {}],
                "responses": {
                    "200": {
                        "description": "Array of map rows from PostGIS",
                        "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/Map"}}}},
                    },
                    "401": {"description": "Bearer token provided but verification failed."},
                },
            },
            "put": {
                "tags": ["maps"],
                "summary": "Create a map",
                "description": "Inserts a row into the `maps` PostGIS table and publishes the payload to NATS subject `maps`. Requires `X-Api-Key` matching the target space's `key` (from the `space` table). `space_id` is required in the body and must be a valid UUID. The server's `API_KEY` env var, if set, is accepted as an admin override.",
                "security": [{"ApiKeyAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/MapCreate"}}},
                },
                "responses": {
                    "200": {
                        "description": "Insert result.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WriteResult"}}},
                    },
                    "400": {"description": "Bad payload (missing/invalid body)."},
                    "401": {"description": "Missing or wrong `X-Api-Key` header."},
                    "500": {"description": "Database error."},
                },
            },
            "post": {
                "tags": ["maps"],
                "summary": "Update a map",
                "description": "Updates an existing map by `mapid` (UUID). If `action=='error'` only the action column is touched; otherwise mapdata/location/tilesURL are written. Requires `X-Api-Key` matching the `key` of the space that owns the existing map row (client-supplied `space_id` is ignored on this endpoint). The server's `API_KEY` env var, if set, is accepted as an admin override. Unknown or unauthorized mapids return 401 (not 404) to avoid leaking existence.",
                "security": [{"ApiKeyAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/MapUpdate"}}},
                },
                "responses": {
                    "200": {
                        "description": "Update result. `{\"error\":\"unknown mapid\"}` if no row matched.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WriteResult"}}},
                    },
                    "400": {"description": "Bad payload (missing `mapid`/`action`, or missing `mapData`/`tilesURL` on a non-error update)."},
                    "401": {"description": "Missing or wrong `X-Api-Key` header."},
                    "500": {"description": "Database error."},
                },
            },
        },
        "/search/": {
            "post": {
                "tags": ["search"],
                "summary": "Search maps",
                "description": "Postgres ILIKE search on `name` and `tags`, optionally bounded by `created_at` range. Same visibility rules as `GET /maps/`: anonymous callers see only `access='public'` rows; a valid `Authorization: Bearer <jwt>` additionally unlocks rows whose `space_id` is in the token's `groups` claim.",
                "security": [{"BearerAuth": []}, {}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/SearchQuery"}}},
                },
                "responses": {
                    "200": {
                        "description": "Matching map rows",
                        "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/Map"}}}},
                    },
                    "401": {"description": "Bearer token provided but verification failed."},
                },
            }
        },
        "/missions/": {
            "get": {
                "tags": ["missions"],
                "summary": "List missions",
                "responses": {
                    "200": {
                        "description": "JSON-encoded array of mission rows",
                        "content": {"application/json": {"schema": {"type": "string"}}},
                    }
                },
            }
        },
        "/mission/{id}": {
            "parameters": [
                {"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}
            ],
            "get": {
                "tags": ["missions"],
                "summary": "Get a mission by id",
                "responses": {
                    "200": {
                        "description": "JSON-encoded array containing the mission row (or empty)",
                        "content": {"application/json": {"schema": {"type": "string"}}},
                    }
                },
            },
        },
        "/mission/validate/{key}": {
            "parameters": [
                {"name": "key", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}
            ],
            "get": {
                "tags": ["missions"],
                "summary": "Validate a mission key",
                "responses": {
                    "200": {
                        "description": "Key is valid; returns mission_id and name",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                    "404": {
                        "description": "Key is not valid",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                },
            },
        },
        "/mission/{key}/hello": {
            "parameters": [
                {"name": "key", "in": "path", "required": True, "schema": {"type": "string"}, "description": "Mission key or id"}
            ],
            "get": {
                "tags": ["missions"],
                "summary": "Mission boot-time handshake",
                "description": "A mission pings this once on startup and gets back its identity, camera-feed and picture-upload URLs (3 quality tiers each), current stats, and the ingest URLs telling it where to send live data next. Stats are maintained by a background scheduler and default to 0.",
                "responses": {
                    "200": {
                        "description": "Mission profile + ingest instructions",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/MissionHello"}}},
                    },
                    "404": {
                        "description": "Mission not found",
                        "content": {"application/json": {"schema": {"type": "object", "properties": {"ok": {"type": "boolean"}, "error": {"type": "string"}}}}},
                    },
                },
            },
            "post": {
                "tags": ["missions"],
                "summary": "Mission boot-time handshake (POST)",
                "description": "Identical to GET; accepted so missions can ping with either method.",
                "responses": {
                    "200": {
                        "description": "Mission profile + ingest instructions",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/MissionHello"}}},
                    },
                    "404": {"description": "Mission not found"},
                },
            },
        },
        "/event/{mission_id}": {
            "parameters": [
                {"name": "mission_id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}
            ],
            "put": {
                "tags": ["events"],
                "summary": "Append a mission event",
                "description": "Persists a row into the `mission_data` hypertable (keyed by the mission's canonical id) and publishes to NATS. Public missions publish to `events.public.<id>`; private missions to `events.private.<space_id>.<id>`. `mission_id` may be the mission key or its id.",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Event"}}},
                },
                "responses": {
                    "200": {
                        "description": "Insert result",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WriteResult"}}},
                    },
                    "404": {"description": "Mission not found"},
                },
            },
        },
        "/mission/{key}/picture/{picture_id}": {
            "parameters": [
                {"name": "key", "in": "path", "required": True, "schema": {"type": "string"}, "description": "Mission key or id"},
                {"name": "picture_id", "in": "path", "required": True, "schema": {"type": "string"}, "description": "The picture_id announced by the phase-1 `picture` event"},
            ],
            "get": {
                "tags": ["events"],
                "summary": "Retrieve picture bytes",
                "description": "Streams back the stored image bytes for a picture (uploaded via PUT). Served from object storage through the API, so it works regardless of bucket ACL.",
                "responses": {
                    "200": {"description": "The image", "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}},
                    "404": {"description": "Mission or picture not found"},
                    "500": {"description": "Storage error"},
                },
            },
            "put": {
                "tags": ["events"],
                "summary": "Upload picture bytes (phase 2)",
                "description": "Phase 2 of the two-phase picture flow: uploads the raw image bytes for a `picture` event announced earlier (possibly much later — drones with poor connectivity upload when they can). The bytes are stored in object storage; the matching `mission_data` row is flipped to `status: uploaded` with its `img` set to the stored URL, and a `picture`/`uploaded` frame is re-published to live SSE subscribers. If no pending row exists yet, a new uploaded picture row is created. Body is the raw image (e.g. `image/jpeg`), not JSON.",
                "requestBody": {
                    "required": True,
                    "content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}, "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
                },
                "responses": {
                    "200": {"description": "Stored", "content": {"application/json": {"schema": {"type": "object", "properties": {"data": {"type": "string"}, "url": {"type": "string"}}}}}},
                    "400": {"description": "Empty body"},
                    "404": {"description": "Mission not found"},
                    "500": {"description": "Storage or DB error"},
                },
            },
        },
        "/event/{mission_id}/recent": {
            "parameters": [
                {"name": "mission_id", "in": "path", "required": True, "schema": {"type": "string"}, "description": "Mission key or id"},
                {"name": "minutes", "in": "query", "required": False, "schema": {"type": "integer", "default": 15, "minimum": 1, "maximum": 60}},
            ],
            "get": {
                "tags": ["events"],
                "summary": "Recent mission events",
                "description": "Returns recent `mission_data` rows. Public missions are open; a private mission requires a Bearer JWT whose `groups` contains the mission's `space_id`.",
                "security": [{"BearerAuth": []}, {}],
                "responses": {
                    "200": {"description": "Recent events", "content": {"application/json": {"schema": {"type": "array", "items": {"type": "object"}}}}},
                    "401": {"description": "Malformed/invalid token"},
                    "403": {"description": "Token lacks the mission's space_id (or private mission, no token)"},
                    "404": {"description": "Mission not found"},
                },
            },
        },
        "/event/{mission_id}/stream": {
            "parameters": [
                {"name": "mission_id", "in": "path", "required": True, "schema": {"type": "string"}, "description": "Mission key or id"},
            ],
            "get": {
                "tags": ["events"],
                "summary": "Live mission event stream (SSE)",
                "description": "Server-Sent Events stream: `backfill` frames (last 15 min from Postgres), then `ready`, then `live` frames tailed from NATS. Public missions are open; a private mission requires a Bearer JWT whose `groups` contains the mission's `space_id`.",
                "security": [{"BearerAuth": []}, {}],
                "responses": {
                    "200": {"description": "text/event-stream", "content": {"text/event-stream": {"schema": {"type": "string"}}}},
                    "401": {"description": "Malformed/invalid token"},
                    "403": {"description": "Token lacks the mission's space_id (or private mission, no token)"},
                    "404": {"description": "Mission not found"},
                },
            },
        },
        "/event/public/stream": {
            "get": {
                "tags": ["events"],
                "summary": "Live stream of ALL public missions (SSE)",
                "description": "Server-Sent Events firehose of every public mission (NATS `events.public.>`). No auth. Live-only (no backfill): `ready` then `live` frames. Each `live` frame's data is `{\"timestamp\", \"mission_id\", \"payload\"}` so consumers can tell which mission each event belongs to.",
                "responses": {
                    "200": {"description": "text/event-stream", "content": {"text/event-stream": {"schema": {"type": "string"}}}},
                },
            },
        },
    },
    "components": {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Api-Key",
                "description": "Per-space API key from `space.key`. On PUT, must match the key of the space named in the request body. On POST, must match the key of the space that owns the target `mapid`. The server's `API_KEY` env var, when set, is accepted as an admin override.",
            },
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Keycloak JWT verified via JWKS (RS256/ES256). The `groups` claim must contain the caller's Keycloak group ids, which equal `space.id` UUIDs (`groups: [<space-uuid>, ...]`; non-UUID entries are ignored). Used on read endpoints (`GET /maps/`, `POST /search/`, and private-mission event reads `GET /event/{id}/recent` and `/stream`) to unlock rows/streams whose `space_id` is in `groups`. Without a token, only public maps/missions are returned.",
            },
        },
        "schemas": {
            "MapCreate": {
                "type": "object",
                "properties": {
                    "creator_id": {"type": "string", "format": "uuid"},
                    "name": {"type": "string", "example": "sthlm-orthophoto"},
                    "tags": {"type": "array", "items": {"type": "string"}, "example": ["test", "alpha"]},
                    "status": {"type": "string", "example": "unprocessed"},
                    "space_id": {"type": "string", "format": "uuid"},
                    "asset_id": {"type": "string", "format": "uuid"},
                    "access": {"type": "string", "example": "private"},
                    "originFile": {"type": "string"},
                    "mapid": {"type": "string"},
                    "accessid": {"type": "string"},
                    "action": {"type": "string"},
                    "location": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "maxItems": 2,
                        "description": "[lon, lat]",
                        "example": [18.0686, 59.3293],
                    },
                },
            },
            "MapUpdate": {
                "type": "object",
                "required": ["mapid", "action"],
                "properties": {
                    "mapid": {"type": "string", "format": "uuid", "description": "UUID of the map row to update (`maps.mapid`)."},
                    "action": {"type": "string", "example": "ready", "description": "`ready`/`partial` for successful runs; `error` if the worker failed (only the action column is updated in that case)."},
                    "mapData": {
                        "type": "object",
                        "description": "Required when `action != 'error'`.",
                        "properties": {
                            "location": {
                                "type": "object",
                                "properties": {
                                    "coordinates": {"type": "array", "items": {"type": "number"}, "example": [18.0686, 59.3293]}
                                },
                            }
                        },
                    },
                    "tilesURL": {"type": "string", "format": "uri", "description": "Required when `action != 'error'`."},
                },
            },
            "Map": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "creator_id": {"type": "string", "format": "uuid"},
                    "space_id": {"type": "string", "format": "uuid"},
                    "asset_id": {"type": "string", "format": "uuid"},
                    "name": {"type": "string"},
                    "tags": {"type": "string", "description": "Postgres array text, e.g. `{a,b}`"},
                    "status": {"type": "string"},
                    "access": {"type": "string"},
                    "location": {"type": "string", "description": "PostGIS WKB hex"},
                    "geometry": {"type": "string", "description": "GeoJSON Point (only on /search/)"},
                    "created_at": {"type": "string", "format": "date"},
                    "updated_at": {"type": "string", "format": "date"},
                },
            },
            "SearchQuery": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "example": "sthlm"},
                    "tags": {"type": "string", "example": "alpha"},
                    "fromdate": {"type": "string", "format": "date-time"},
                    "todate": {"type": "string", "format": "date-time"},
                },
            },
            "Event": {
                "type": "object",
                "description": (
                    "A single mission event (e.g. one drone reading). Mapped "
                    "columns are stored in the `mission_data` hypertable and replayed in "
                    "`backfill`/`recent`; the FULL body is echoed back verbatim as the "
                    "`payload` of every `live` SSE frame, so custom keys inside `jsonData` "
                    "(and any extra top-level keys) round-trip to live subscribers.\n\n"
                    "The `type` field selects the event kind. Canonical types:\n"
                    "- `location` (alias `telemetry`): GPS position in `geopoint`/`x`/`y`/`z`.\n"
                    "- `measurement` (alias `temperature`): a generic sensor value in `data` "
                    "with `jsonData.{kind,unit}` (e.g. temperature/humidity/solar); the "
                    "temperature kind also fills `temp`/`humidity`.\n"
                    "- `picture`: phase 1 of a two-phase photo — carries `jsonData.picture_id` "
                    "and `jsonData.status` (defaults to `pending`); the image bytes are "
                    "uploaded later to `PUT /mission/{key}/picture/{picture_id}`, which flips "
                    "the row to `uploaded` and sets `img` to the stored URL.\n"
                    "- `alert`: a detection, with `jsonData.{kind,severity,message}`.\n\n"
                    "Unknown types are stored and logged, not rejected."
                ),
                "required": ["type"],
                "properties": {
                    "type": {"type": "string", "enum": ["location", "measurement", "picture", "alert", "telemetry", "temperature"], "example": "measurement", "description": "Event kind (see schema description). Legacy aliases `telemetry`/`temperature` are accepted."},
                    "temp": {"type": "number", "description": "Temperature; stored as `temperature`."},
                    "humidity": {"type": "number"},
                    "geopoint": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "maxItems": 2,
                        "example": [18.0686, 59.3293],
                        "description": "[longitude, latitude] (PostGIS order). Stored as a geography POINT.",
                    },
                    "img": {"type": "string", "description": "Image URL/reference for this sample."},
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "z": {"type": "number", "description": "Free numeric axis; commonly altitude."},
                    "data": {"type": "number", "description": "Generic numeric measurement."},
                    "jsonData": {"type": "object", "description": "Arbitrary structured payload; persisted to the `jsondata` column and returned in backfill/recent/live."},
                    "device": {"type": "string", "example": "drone-01"},
                    "deviceJson": {"type": "object", "description": "Arbitrary device metadata; persisted to `devicejson`."},
                },
            },
            "MissionHello": {
                "type": "object",
                "description": "Boot-time handshake response for a mission. Media URLs and stats come from the `missions` row; `ingest` is derived from the request host and tells the mission where to send live data.",
                "properties": {
                    "ok": {"type": "boolean"},
                    "mission_id": {"type": "string", "format": "uuid", "description": "Canonical mission id (use this for ingest even if you pinged with the key)."},
                    "name": {"type": "string"},
                    "is_public": {"type": "boolean"},
                    "camera": {
                        "type": "object",
                        "description": "Camera feed stream URLs per quality tier (null until set).",
                        "properties": {
                            "low": {"type": "string", "nullable": True},
                            "medium": {"type": "string", "nullable": True},
                            "high": {"type": "string", "nullable": True},
                        },
                    },
                    "pictures": {
                        "type": "object",
                        "description": "Picture upload endpoint URLs per quality tier (null until set).",
                        "properties": {
                            "low": {"type": "string", "nullable": True},
                            "medium": {"type": "string", "nullable": True},
                            "high": {"type": "string", "nullable": True},
                        },
                    },
                    "stats": {
                        "type": "object",
                        "description": "Scheduler-maintained counters.",
                        "properties": {
                            "events": {"type": "integer"},
                            "pictures": {"type": "integer"},
                            "updated_at": {"type": "string", "format": "date-time", "nullable": True},
                        },
                    },
                    "ingest": {
                        "type": "object",
                        "description": "Where the mission sends live data next.",
                        "properties": {
                            "event_url": {"type": "string", "format": "uri", "description": "PUT telemetry events here (Event schema)."},
                            "event_method": {"type": "string", "example": "PUT"},
                            "stream_url": {"type": "string", "format": "uri", "description": "SSE live event stream."},
                            "recent_url": {"type": "string", "format": "uri", "description": "Recent events (last 15 min)."},
                        },
                    },
                },
            },
            "WriteResult": {
                "oneOf": [
                    {"type": "object", "properties": {"data": {"type": "string"}, "id": {"type": "string"}}},
                    {"type": "object", "properties": {"error": {"type": "string"}}},
                ]
            },
        }
    },
}
