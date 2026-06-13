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
                "summary": "List all maps",
                "responses": {
                    "200": {
                        "description": "Array of map rows from PostGIS",
                        "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/Map"}}}},
                    }
                },
            },
            "put": {
                "tags": ["maps"],
                "summary": "Create a map",
                "description": "Inserts a row into the `maps` PostGIS table and publishes the payload to NATS subject `maps`. Requires `X-Api-Key` when the server has `API_KEY` set.",
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
                "description": "Updates an existing map by `mapid` (UUID). If `action=='error'` only the action column is touched; otherwise mapdata/location/tilesURL are written. Requires `X-Api-Key` when the server has `API_KEY` set.",
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
                "description": "Postgres ILIKE search on `name` and `tags`, optionally bounded by `created_at` range.",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/SearchQuery"}}},
                },
                "responses": {
                    "200": {
                        "description": "Matching map rows",
                        "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/Map"}}}},
                    }
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
        "/event/{mission_id}": {
            "parameters": [
                {"name": "mission_id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}
            ],
            "put": {
                "tags": ["events"],
                "summary": "Append a mission event",
                "description": "Persists a row into the `mission_data` hypertable and publishes to NATS subject `events`.",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Event"}}},
                },
                "responses": {
                    "200": {
                        "description": "Insert result",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WriteResult"}}},
                    }
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
                "description": "Shared secret matching the api's `API_KEY` env var. Required on `/maps/` writes (PUT, POST) when the server is configured with `API_KEY`.",
            }
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
                "required": ["type"],
                "properties": {
                    "type": {"type": "string", "example": "telemetry"},
                    "temp": {"type": "number"},
                    "humidity": {"type": "number"},
                    "geopoint": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "maxItems": 2,
                        "example": [18.0686, 59.3293],
                    },
                    "img": {"type": "string"},
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "z": {"type": "number"},
                    "data": {"type": "number"},
                    "jsonData": {"type": "object"},
                    "device": {"type": "string"},
                    "deviceJson": {"type": "object"},
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
