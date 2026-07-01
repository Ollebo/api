---
name: e2e-mission-stream
description: Run the end-to-end mission-data retrieval test — mocks a drone flying into the PUBLIC mission, publishes to NATS, and verifies the events come back over the SSE stream (plus that private missions stay auth-gated). Use to validate changes to the event ingest/stream path (event.py, sse_bridge.py, start.py, initNats.py, postgis mission funcs). Requires the local docker-compose stack running.
---

# E2E mission-stream validation

Drives the live API to prove the mission-data retrieval feature works end to end:
a mocked drone flight is PUT into the **public** mission, published to the split
NATS subject `events.public.<id>`, and read back over the SSE stream — while a
**private** mission stays 403 without a JWT.

The test itself is `test/e2e_mission_stream.py` (pure stdlib, no pip installs).

## Steps

1. **Check the API is up** (docker-compose serves it at `localhost:8888`):
   ```bash
   curl -fsS http://localhost:8888/healthz && echo
   ```
   If this fails, the stack isn't running. Bring it up (see Prerequisites) before
   continuing — do not proceed on a dead API.

2. **Ensure the JetStream `events` stream is bound to the split subjects.**
   `code/db/initNats.py` is idempotent and (re)binds it to `events.>`:
   ```bash
   docker compose exec -T api python code/db/initNats.py
   ```
   This is REQUIRED after any change to subjects — without an `events.>` stream,
   publishes/reads on `events.public.*` / `events.private.*.*` silently no-op and
   the test's live-frame checks will fail.

3. **Run the test:**
   ```bash
   python3 test/e2e_mission_stream.py
   ```
   Exit code `0` = all checks passed, `1` = a failure. Each check prints
   `[PASS]`/`[FAIL]`.

4. **Report the result.** On failure, read the failing check line and map it:
   - `private stream/recent without JWT -> 403` failing → the auth gate in
     `event.py:authorize_mission_read` / `start.py` routes regressed.
   - `backfill replayed warmup rows` failing → Postgres write/read path
     (`addEvent` / `getRecentEvents`) or the canonical-id backfill in `start.py`.
   - `all live flight frames received` failing → NATS path: `initNats.py` subjects,
     `event.py:subject_for` publish, or `sse_bridge.subscribe`. Re-run step 2 first.
   - `recent shows all persisted events` failing → Postgres persistence / mission
     resolution (`resolve_mission`, `getMissionByKey`).

## Prerequisites

- `docker network create base` (one-time) and the sibling Postgres reachable on
  that network, seeded from `code/db/init.sql` (which seeds a public mission key
  `dddddddd-…` and a private one `ffffffff-…`).
- `docker-compose up` running the `api` + `nats` services.
- The test hits the seeded public/private mission keys by default. Override with
  env vars if your local seed differs:
  `API_BASE`, `MISSION_KEY`, `PRIVATE_MISSION_KEY`, `WARMUP_EVENTS`, `FLIGHT_EVENTS`.

## Notes

- The test is safe to re-run: each run uses a fresh `run_id` and only appends
  events to the public mission's TimescaleDB rows (aged out after 15 min).
- It does not exercise a *valid* private-mission JWT (needs a real JWKS/token);
  it only asserts private missions are denied without one. Mint a token and hit
  `/event/<privateKey>/stream` with `Authorization: Bearer …` to test the allow path.
