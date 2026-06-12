# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python/Flask HTTP API for `ollebo.com` that manages drone-style "maps" (orthophotos/geotiffs), "missions", and time-series "events". The same `code/` tree is built into two deployment shapes:

- **Local / Kubernetes**: Flask app served by `code/start.py` (entry script `code/start.sh`, port 8080). Built from `Dockerfile`.
- **AWS Lambda**: `code/lambda_function.py:handler` invoked via API Gateway; runs under `awslambdaric`. Built from `Dockerfile_aws` and pushed to ECR by `deploy.sh`.

`lambda_function.handler` is a thin shim that adapts the API Gateway event shape into a fake `request` dict and reuses `maps.maps()` — so the business logic in `code/` is shared between both runtimes.

## Backends

Only two backends are used:

- **PostGIS / Postgres** (`code/db/postgis.py`) — primary store for `maps`, `missions`, and the `mission_data` event table. Geometry is stored as `geography(POINT)` using `ST_MakePoint` / `ST_AsGeoJSON`. Map search (`/search/`) is also served from Postgres (ILIKE on `name` / `ANY(tags)` / `created_at` range).
- **NATS JetStream** (`code/db/natsQue.py`) — event bus. `addToNats(subject, payload)` publishes to JetStream. Used opportunistically by `/maps/` (PUT) and `/event/<mission_id>` (PUT); publish failures are logged but do not fail the request.

The PostGIS module opens a single module-level `conn` at import time and `sys.exit()`s if the connection fails — importing `db/postgis.py` has side effects.

## Common commands

```bash
# Local dev (docker-compose); requires an external docker network named "base"
docker network create base       # one-time
docker-compose build
docker-compose up                # serves API at localhost:8888 -> container 8080
docker compose run api /bin/bash # shell inside the container

# Deploy the Lambda image to ECR (eu-north-1)
./deploy.sh                      # uses Dockerfile (NOT Dockerfile_aws); see "Gotchas"
```

There is no test runner, linter, or formatter wired up. The `test/` directory only contains sample input (`test/maps`), not executable tests. CI (`.github/workflows/docker-image.yml`) only builds the Docker image, pushes to Docker Hub (`ollebo/api`), templates `chart/` into the `Ollebo/manifests` repo, and notifies Slack — no test or lint step runs.

## Architecture

### Request routing (Flask path)
`code/start.py` is the Flask app and only has five routes:

- `PUT/POST/GET /maps/` → `maps.maps(payload, request)` (create / update / list-or-geo-search)
- `POST /search/` → `maps.mapsSearch(payload)` (Postgres ILIKE / tag filter)
- `GET/POST/PUT /missions/` and `/mission/<id>` → `missions.py`
- `PUT /event/<mission_id>` → `event.event(...)` which calls `addEvent` (Postgres `mission_data`) and publishes to NATS `events`

`maps.py:maps()` dispatches on HTTP method: `PUT` inserts via `db.postgis.addDataDb` and publishes to NATS `maps`, `POST` updates via `updateMapDataDb` (requires `mapKey`), `GET` either dumps all maps or runs a PostGIS distance query (`getDataDbMaps` / `getDataDbMapsPoints`).

### Configuration
Everything is via env vars, read with `os.environ.get(..., <default>)`. Key ones (see `docker-compose.yaml` and `chart/templates/api.yaml` for the canonical sets):

- `POSTGRES_DB / POSTGRES_HOST / POSTGRES_USER / POSTGRES_PASSWORD` — PostGIS
- `NATS` — NATS server URL (e.g. `nats://nats:4222`)

`config.yaml` at the repo root is Lambda metadata (function name, runtime, region) — not application config.

## Gotchas

- **Two Dockerfiles, deploy.sh uses the wrong one.** `deploy.sh` runs `docker build -t api .` which picks up the plain `Dockerfile` (Flask entrypoint), not `Dockerfile_aws` (Lambda runtime client). If you push to ECR for Lambda, build `Dockerfile_aws` explicitly: `docker build -f Dockerfile_aws -t api .`.
- **`docker-compose.yaml` only starts `api` + `nats`.** Postgres is expected on the external `base` network — `docker network create base` first, and bring Postgres up separately (it lives in a sibling repo).
- **Import-time side effects.** `db/postgis.py` opens a connection at import time and exits the process on failure. Don't import it in tooling that shouldn't touch the live DB.
- **Stale / unused trees.** `code_old/` and `old/` are previous iterations kept on disk; ignore them. `Pipfile` pins Python 3.7 but the actual containers use 3.9 (`Dockerfile`) or 3.12 (`Dockerfile_aws`) — `requirements.txt` is the source of truth for dependencies.
- **CI deploys via a separate manifests repo.** The GitHub Action templates `chart/` into `Ollebo/manifests` and pushes — the cluster picks up the new image from that repo, not directly from this one.
- **README quickstart is out of date** (refers to a "fins" folder workflow and old Meilisearch/Mongo backends); prefer the commands above.
