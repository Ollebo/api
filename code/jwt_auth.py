import hashlib
import json
import os
import threading
import time
import urllib.request
import uuid

import jwt
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from db.redisCache import client as redis_client


JWT_JWKS_URL = os.environ.get("JWT_JWKS_URL")
JWT_ISSUER = os.environ.get("JWT_ISSUER")
JWT_AUDIENCE = os.environ.get("JWT_AUDIENCE")


def _kc_realm_url():
    # Build the Keycloak realm base URL from the same KC_* env vars dw uses
    # (KC_HOST/KC_PORT/KC_PROTOCOL/KC_REALM), so the api shares dw's config.
    # Standard ports (443/https, 80/http) are omitted to match the token issuer.
    host = os.environ.get("KC_HOST")
    realm = os.environ.get("KC_REALM")
    if not host or not realm:
        return None
    proto = os.environ.get("KC_PROTOCOL", "https")
    port = os.environ.get("KC_PORT", "")
    netloc = host
    if port and not ((proto == "https" and port == "443") or (proto == "http" and port == "80")):
        netloc = "{}:{}".format(host, port)
    return "{}://{}/realms/{}".format(proto, netloc, realm)


# Fall back to KC_* (dw's config) when the JWKS URL isn't set explicitly.
if not JWT_JWKS_URL:
    _realm_url = _kc_realm_url()
    if _realm_url:
        JWT_JWKS_URL = _realm_url + "/protocol/openid-connect/certs"

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


def _as_space_uuid(s):
    # Keycloak group ids (== space.id) arrive in the `groups` claim. Canonicalize
    # to a lowercase hyphenated UUID; return None for anything that isn't a UUID
    # (legacy group paths, default Keycloak groups) so it's dropped rather than
    # breaking the maps `::uuid[]` cast or matching a space_id by accident.
    if not isinstance(s, str):
        return None
    try:
        return str(uuid.UUID(s.strip())).lower()
    except (ValueError, AttributeError):
        return None


def get_auth_context(headers_get):
    """Return the caller's authorized space_ids (validated Keycloak group UUIDs).

    None when there's no Bearer token or JWT is disabled; otherwise a de-duped
    list of canonical lowercase UUID strings taken from the `groups` claim
    (non-UUID entries are dropped). Raises JwtError on an invalid token.
    """
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
    out, seen = [], set()
    for g in groups_raw:
        gid = _as_space_uuid(g)
        if gid and gid not in seen:
            seen.add(gid)
            out.append(gid)
    return out
