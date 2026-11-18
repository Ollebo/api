"""Map pipeline outcomes as seen by the API.

Several map failures are invisible in the HTTP metrics: a callback for an
unknown map and a failed list both answer 200 with an error body, and a failed
NATS publish is swallowed (the map then sits unprocessed forever). These
counters make them visible.

Labels are bounded: action is a fixed set and result is an enum. A map id is
never a label; a failed callback writes one JSON log line with the mapid.
"""

import json

from prometheus_client import Counter


MAP_CALLBACKS = Counter(
    "api_map_callbacks_total", "map-maker callbacks (POST /maps/, PATCH /maps/<mapid>)",
    ["action", "result"])
# result: saved | unknown_mapid | unknown_action | invalid | db_error
MAP_CREATES = Counter(
    "api_map_creates_total", "Maps registered through PUT /maps/", ["result"])
# result: ok | invalid | db_error
MAP_NATS_PUBLISH = Counter(
    "api_map_nats_publish_total", "Map jobs published to NATS", ["subject", "result"])
MAP_LISTS = Counter(
    "api_map_list_total", "GET /maps/ listings", ["result"])  # ok | error
MAP_SEARCHES = Counter(
    "api_map_search_total", "POST /search/ map searches", ["result"])  # ok | error
CACHE_REQUESTS = Counter(
    "api_cache_requests_total", "Redis cache lookups", ["cache", "result"])
# cache: mission | space_key      result: hit | miss | error


def action_label(action, known):
    return action if action in known else "other"


def callback(action, known, result, mapid=None):
    MAP_CALLBACKS.labels(action_label(action, known), result).inc()
    if result != "saved":
        print(json.dumps({"event": "map_callback_error", "mapid": str(mapid or ""),
                          "action": str(action or ""), "result": result}, sort_keys=True),
              flush=True)


def query_result(result):
    """ok/error for the list and search helpers, which return {"error": ...}
    instead of raising."""
    return "error" if isinstance(result, dict) and "error" in result else "ok"
