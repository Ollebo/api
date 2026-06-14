# -*- coding: utf-8 -*-
import json
from maps import maps
from auth import verify_map_request
from jwt_auth import get_auth_context, JwtError


print("run lamda maps")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Credentials": True,
}


def _headers_get(event):
    raw = event.get("headers") or {}
    lowered = {k.lower(): v for k, v in raw.items()}
    def get(name, default=None):
        return lowered.get(name.lower(), default)
    return get


def handler(event, context):
    print(event)
    payload = {}
    request = {"method": "put"}
    try:
        request["method"] = event["requestContext"]["http"]["method"]
    except Exception:
        print("An exception occurred")
    try:
        request["method"] = event["httpMethod"]
    except Exception:
        print("An exception occurred")

    try:
        payload = json.loads(event["body"])
    except Exception:
        payload = event["body"]

    method = (request["method"] or "").upper()
    if method in ("PUT", "POST"):
        unauthorized = verify_map_request(method, payload, _headers_get(event))
        if unauthorized is not None:
            body, status = unauthorized
            return {
                "statusCode": status,
                "body": json.dumps(body),
                "headers": CORS_HEADERS,
            }

    groups = None
    if method == "GET":
        try:
            groups = get_auth_context(_headers_get(event))
        except JwtError as e:
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "unauthorized", "detail": str(e)}),
                "headers": CORS_HEADERS,
            }

    returnFromFunction = maps(payload, request, groups=groups)
    return {
        "statusCode": 200,
        "body": returnFromFunction,
        "headers": CORS_HEADERS,
    }
