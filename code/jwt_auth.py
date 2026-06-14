import hashlib
import json
import os
import threading
import time
import urllib.request

import jwt
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from db.redisCache import client as redis_client


JWT_JWKS_URL = os.environ.get("JWT_JWKS_URL")
JWT_ISSUER = os.environ.get("JWT_ISSUER")
JWT_AUDIENCE = os.environ.get("JWT_AUDIENCE")

_JWKS_TTL = 300
_JWKS_FETCH_TIMEOUT = 3
_LEEWAY = 30

if not JWT_JWKS_URL:
    print("WARN: JWT_JWKS_URL not set; Bearer tokens will be ignored")


class JwtError(Exception):
    pass


_local_cache = {"jwks": None, "expires": 0}
_local_lock = threading.Lock()


def _jwks_cache_key():
    digest = hashlib.sha256(JWT_JWKS_URL.encode("utf-8")).hexdigest()[:16]
    return "jwt_jwks:" + digest


def _fetch_jwks():
    req = urllib.request.Request(JWT_JWKS_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=_JWKS_FETCH_TIMEOUT) as resp:
        raw = resp.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("keys"), list):
        raise JwtError("malformed JWKS")
    return raw, parsed


def _get_jwks(force_refresh=False):
    if not force_refresh and redis_client is not None:
        try:
            cached = redis_client.get(_jwks_cache_key())
            if cached:
                return json.loads(cached)
        except Exception as e:
            print("Redis GET (jwks) failed: {}".format(e))

    if not force_refresh:
        with _local_lock:
            if _local_cache["jwks"] is not None and _local_cache["expires"] > time.time():
                return _local_cache["jwks"]

    try:
        raw, parsed = _fetch_jwks()
    except Exception as e:
        raise JwtError("jwks fetch failed: {}".format(e))

    if redis_client is not None:
        try:
            redis_client.set(_jwks_cache_key(), raw, ex=_JWKS_TTL)
        except Exception as e:
            print("Redis SET (jwks) failed: {}".format(e))

    with _local_lock:
        _local_cache["jwks"] = parsed
        _local_cache["expires"] = time.time() + _JWKS_TTL

    return parsed


def _find_jwk(jwks, kid):
    for jwk in jwks.get("keys", []):
        if jwk.get("kid") == kid:
            return jwk
    return None


def _build_key(jwk):
    kty = jwk.get("kty")
    if kty == "RSA":
        return RSAAlgorithm.from_jwk(json.dumps(jwk))
    if kty == "EC":
        return ECAlgorithm.from_jwk(json.dumps(jwk))
    raise JwtError("unsupported kty: {}".format(kty))


def _extract_bearer(headers_get):
    raw = headers_get("Authorization")
    if not raw:
        return None
    parts = raw.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise JwtError("malformed Authorization header")
    token = parts[1].strip()
    if not token:
        raise JwtError("empty bearer token")
    return token


def get_auth_context(headers_get):
    token = _extract_bearer(headers_get)
    if token is None:
        return None
    if not JWT_JWKS_URL:
        print("WARN: JWT disabled; ignoring Bearer token")
        return None

    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
        raise JwtError("bad token header: {}".format(e))

    kid = unverified_header.get("kid")
    if not kid:
        raise JwtError("token missing kid")

    jwks = _get_jwks()
    jwk = _find_jwk(jwks, kid)
    if jwk is None:
        jwks = _get_jwks(force_refresh=True)
        jwk = _find_jwk(jwks, kid)
        if jwk is None:
            raise JwtError("unknown kid")

    public_key = _build_key(jwk)

    options = {
        "require": ["exp"],
        "verify_aud": bool(JWT_AUDIENCE),
        "verify_iss": bool(JWT_ISSUER),
    }
    try:
        payload = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256", "ES256"],
            audience=JWT_AUDIENCE or None,
            issuer=JWT_ISSUER or None,
            leeway=_LEEWAY,
            options=options,
        )
    except jwt.PyJWTError as e:
        raise JwtError("verify failed: {}".format(e))

    groups_raw = payload.get("groups") or []
    if not isinstance(groups_raw, list):
        return []
    return [g for g in groups_raw if isinstance(g, str)]
