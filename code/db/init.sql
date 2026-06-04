-- Schema for local docker-compose testing.
-- Production schema lives in a sibling repo; keep this aligned with what
-- code/db/postgis.py reads and writes.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS maps (
    id          SERIAL PRIMARY KEY,
    creator_id  UUID,
    space_id    UUID,
    asset_id    UUID,
    name        VARCHAR(250),
    tags        TEXT[],
    status      VARCHAR(250),
    access      VARCHAR(250),
    originFile  VARCHAR(250),
    mapid       VARCHAR(250),
    accessid    VARCHAR(250),
    action      VARCHAR(250),
    location    geography(POINT),
    mapdata     JSONB,
    tilesurl    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS missions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(250),
    status      VARCHAR(250),
    space_id    UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mission_data (
    id              BIGSERIAL PRIMARY KEY,
    db_insert_time  TIMESTAMPTZ NOT NULL DEFAULT now(),
    mission         UUID,
    type            VARCHAR(250),
    temperature     DOUBLE PRECISION,
    humidity        DOUBLE PRECISION,
    location        geography(POINT),
    img             TEXT,
    x               DOUBLE PRECISION,
    y               DOUBLE PRECISION,
    z               DOUBLE PRECISION,
    data            DOUBLE PRECISION,
    jsonData        JSONB,
    device          VARCHAR(250),
    deviceJSON      JSONB
);

CREATE INDEX IF NOT EXISTS mission_data_mission_time_idx
    ON mission_data (mission, db_insert_time DESC);
