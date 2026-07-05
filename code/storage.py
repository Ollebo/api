"""S3-compatible object storage for mission pictures.

Uses the SAME backend and env conventions as the sibling `dw` app: an
S3-compatible endpoint (Hetzner Object Storage in prod) addressed path-style,
with static credentials from the `ollebo` k8s Secret. This lets picture objects
live in the same bucket alongside dw's map assets.

Env (matches dw's src/plugins/s3.js + chart):
    AWS_ENDPOINT          e.g. https://hel1.your-objectstorage.com  (MinIO locally)
    AWS_BUCKET            default map-storage
    AWS_REGION            default hel1
    AWS_ACCESS_KEY_ID     from Secret ollebo/AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY from Secret ollebo/AWS_SECRET_ACCESS_KEY
    AWS_PUBLIC_ENDPOINT   base used to build browser-facing URLs; defaults to
                          AWS_ENDPOINT. Set to e.g. http://localhost:9000 for
                          local MinIO where the in-container endpoint differs.
    KC_REALM              default master — object keys are realm-prefixed so one
                          shared bucket can host multiple sites (dw convention).

Like dw, objects are served back directly from {AWS_PUBLIC_ENDPOINT}/{bucket}/{key}.
This module has NO import-time side effects: the boto3 client is built lazily on
first use, so importing it never requires live credentials or a reachable bucket.
"""
import os

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

AWS_ENDPOINT = os.environ.get("AWS_ENDPOINT", "http://minio:9000")
AWS_BUCKET = os.environ.get("AWS_BUCKET", "map-storage")
AWS_REGION = os.environ.get("AWS_REGION", "hel1")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin")
AWS_PUBLIC_ENDPOINT = os.environ.get("AWS_PUBLIC_ENDPOINT", AWS_ENDPOINT).rstrip("/")
KC_REALM = os.environ.get("KC_REALM", "master")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=AWS_ENDPOINT or None,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
            # forcePathStyle: true (dw) — required for Hetzner/MinIO-style endpoints.
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
    return _client


def _key(mission_id, picture_id):
    # Realm-prefixed so picture objects coexist with dw's assets in the shared
    # bucket (dw: {realm}/spaces/...; here: {realm}/missions/.../pictures/...).
    return "{}/missions/{}/pictures/{}".format(KC_REALM, mission_id, picture_id)


def put_picture(mission_id, picture_id, content_type, data):
    """Store image bytes and return the public URL they're served from.

    Raises on failure (caller turns that into a 500) so a broken store never
    silently marks a picture uploaded.
    """
    key = _key(mission_id, picture_id)
    _get_client().put_object(
        Bucket=AWS_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type or "application/octet-stream",
    )
    return "{}/{}/{}".format(AWS_PUBLIC_ENDPOINT, AWS_BUCKET, key)


def get_picture(mission_id, picture_id):
    """Fetch stored image bytes. Returns (data, content_type) or None if absent.

    Lets the API serve a picture back later regardless of bucket ACL — the
    retrieval half of the store/retrieve pair.
    """
    key = _key(mission_id, picture_id)
    try:
        obj = _get_client().get_object(Bucket=AWS_BUCKET, Key=key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404", "NotFound"):
            return None
        raise
    return obj["Body"].read(), obj.get("ContentType")
