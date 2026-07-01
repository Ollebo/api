#!/usr/bin/env python3
"""End-to-end test: mock a drone flight into a PUBLIC mission and verify the SSE stream.

Runs against a *live* API (docker-compose default: http://localhost:8888). Pure
stdlib — no pip installs — so it runs straight from a dev machine:

    python3 test/e2e_mission_stream.py

What it validates (the mission-data retrieval feature):
  1. GET /healthz                                  -> API reachable
  2. Private mission stream/recent WITHOUT a JWT   -> 403 (the auth gate works)
  3. Warmup events on the public mission           -> land in Postgres
  4. Open the SSE stream with NO auth              -> public topic is open
     - backfill frames replay the warmup rows
     - `ready` is emitted
  5. "Fly the drone": stream N telemetry events    -> each arrives as a `live`
     frame with the exact payload we sent (altitude/seq verified end to end)
  6. GET /recent                                   -> all events (warmup+flight)
     persisted and queryable

Config (env vars):
  API_BASE            default http://localhost:8888
  MISSION_KEY         public mission key   (default matches code/db/init.sql seed)
  PRIVATE_MISSION_KEY private mission key  (default matches code/db/init.sql seed)
  WARMUP_EVENTS       default 3
  FLIGHT_EVENTS       default 8

Exit code 0 = PASS, 1 = FAIL.
"""
import json
import os
import queue
import random
import sys
import threading
import time
import urllib.error
import urllib.request

API_BASE = os.environ.get("API_BASE", "http://localhost:8888").rstrip("/")
PUBLIC_KEY = os.environ.get("MISSION_KEY", "dddddddd-dddd-dddd-dddd-dddddddddddd")
PRIVATE_KEY = os.environ.get("PRIVATE_MISSION_KEY", "ffffffff-ffff-ffff-ffff-ffffffffffff")
WARMUP = int(os.environ.get("WARMUP_EVENTS", "3"))
FLIGHT = int(os.environ.get("FLIGHT_EVENTS", "8"))

# Stockholm center; the drone climbs and drifts NE over the flight.
_ORIGIN_LON, _ORIGIN_LAT = 18.0686, 59.3293


def _expected_alt(seq):
    return min(120.0, 10.0 + seq * 12.0)


def drone_event(run_id, seq, phase):
    """One telemetry sample. run_id/seq/phase ride inside `jsonData` so they
    survive into the Postgres `jsondata` column (backfill/recent) AND come back
    verbatim in the live SSE payload."""
    lon = _ORIGIN_LON + seq * 0.0002
    lat = _ORIGIN_LAT + seq * 0.0001
    alt = _expected_alt(seq)
    return {
        "type": "telemetry",
        "temp": round(21.0 - seq * 0.1, 2),
        "humidity": round(45.0 + seq * 0.5, 2),
        "geopoint": [lon, lat],
        "x": lon,
        "y": lat,
        "z": alt,
        "data": alt,
        "device": "drone-" + run_id,
        "jsonData": {
            "run_id": run_id,
            "seq": seq,
            "phase": phase,
            "battery": max(0, 100 - seq * 3),
            "heading": (seq * 15) % 360,
            "speed": 8.0,
        },
    }


# ---- tiny HTTP helpers (stdlib only) ---------------------------------------

def put_json(path, body):
    req = urllib.request.Request(
        API_BASE + path,
        data=json.dumps(body).encode("utf-8"),
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def get(path, timeout=10):
    """GET that never hangs: reads a bounded amount so it returns even if the
    server (mis)handed us a stream. Returns (status, body). status == -1 on a
    transport error / timeout."""
    req = urllib.request.Request(API_BASE + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(8192).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # URLError, socket timeout, etc.
        return -1, str(e)


def _jd(obj):
    """Fetch the jsonData dict case-insensitively (Postgres lowercases the
    column to `jsondata`; the raw SSE payload keeps our `jsonData`)."""
    if not isinstance(obj, dict):
        return {}
    for k in ("jsonData", "jsondata"):
        if k in obj and isinstance(obj[k], dict):
            return obj[k]
    return {}


# ---- SSE reader thread ------------------------------------------------------

class SSEReader(threading.Thread):
    def __init__(self, url):
        super().__init__(daemon=True)
        self.url = url
        self.frames = queue.Queue()
        self._resp = None

    def run(self):
        try:
            req = urllib.request.Request(self.url, method="GET")
            self._resp = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            self.frames.put(("__status__", e.code))
            return
        except Exception as e:
            self.frames.put(("__error__", str(e)))
            return
        self.frames.put(("__status__", self._resp.status))
        event, data_lines = None, []
        try:
            for raw in self._resp:
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if line == "":
                    if event is not None:
                        self.frames.put((event, "\n".join(data_lines)))
                    event, data_lines = None, []
                elif line.startswith(":"):
                    continue  # comment / keepalive ping
                elif line.startswith("event:"):
                    event = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:"):].strip())
        except Exception as e:
            self.frames.put(("__error__", str(e)))

    def close(self):
        try:
            if self._resp:
                self._resp.close()
        except Exception:
            pass


# ---- test harness -----------------------------------------------------------

_results = []


def check(name, ok, detail=""):
    _results.append(ok)
    mark = "PASS" if ok else "FAIL"
    line = "  [{}] {}".format(mark, name)
    if detail:
        line += " -- " + detail
    print(line, flush=True)
    return ok


def fatal(msg):
    print("\nFATAL: {}\n".format(msg), flush=True)
    _summary_and_exit()


def _summary_and_exit():
    total = len(_results)
    passed = sum(1 for r in _results if r)
    print("\n{} / {} checks passed".format(passed, total), flush=True)
    sys.exit(0 if total and passed == total else 1)


def main():
    print("E2E mission-stream test against {}".format(API_BASE))
    print("public key={}  private key={}  warmup={} flight={}\n".format(
        PUBLIC_KEY, PRIVATE_KEY, WARMUP, FLIGHT))

    # 1. reachability
    status, _ = get("/healthz", timeout=5)
    if not check("API /healthz reachable", status == 200, "status={}".format(status)):
        fatal("API not reachable at {} -- is docker-compose up?".format(API_BASE))

    # 2. auth gate: private mission must be closed without a JWT
    ps, _ = get("/event/{}/stream".format(PRIVATE_KEY), timeout=8)
    check("private stream without JWT -> 403", ps == 403, "status={}".format(ps))
    pr, _ = get("/event/{}/recent".format(PRIVATE_KEY), timeout=8)
    check("private recent without JWT -> 403", pr == 403, "status={}".format(pr))

    run_id = "{:x}{:04x}".format(int(time.time()), random.randint(0, 0xFFFF))
    print("\nrun_id={}\n".format(run_id))

    # 3. warmup events (these become SSE backfill + show up in /recent)
    warmup_ok = True
    for i in range(WARMUP):
        st, body = put_json("/event/{}".format(PUBLIC_KEY), drone_event(run_id, -1 - i, "warmup"))
        warmup_ok = warmup_ok and st == 200
    if not check("warmup events accepted", warmup_ok):
        fatal("warmup PUT failed -- does the public mission exist? (seed code/db/init.sql)")
    time.sleep(0.5)  # let commits land so backfill can see them

    # 4. open the public stream with NO auth, collect backfill until `ready`
    reader = SSEReader(API_BASE + "/event/{}/stream".format(PUBLIC_KEY))
    reader.start()
    backfill = []
    ready = False
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            kind, data = reader.frames.get(timeout=max(0.1, deadline - time.time()))
        except queue.Empty:
            break
        if kind == "__status__":
            if not check("public stream opens without JWT -> 200", data == 200, "status={}".format(data)):
                reader.close()
                fatal("public stream did not open (status {})".format(data))
            continue
        if kind == "__error__":
            reader.close()
            fatal("stream error: {}".format(data))
        if kind == "backfill":
            backfill.append(data)
        elif kind == "ready":
            ready = True
            break
    check("stream reached `ready`", ready)

    warm_in_backfill = 0
    for d in backfill:
        try:
            if _jd(json.loads(d)).get("run_id") == run_id:
                warm_in_backfill += 1
        except Exception:
            pass
    check("backfill replayed warmup rows", warm_in_backfill >= WARMUP,
          "got {}/{}".format(warm_in_backfill, WARMUP))

    # 5. fly the drone -- events sent now must arrive as `live` frames
    for seq in range(FLIGHT):
        st, _ = put_json("/event/{}".format(PUBLIC_KEY), drone_event(run_id, seq, "flight"))
        if st != 200:
            check("flight event {} accepted".format(seq), False, "status={}".format(st))

    seen = {}
    live_deadline = time.time() + 30
    while len(seen) < FLIGHT and time.time() < live_deadline:
        try:
            kind, data = reader.frames.get(timeout=max(0.1, live_deadline - time.time()))
        except queue.Empty:
            break
        if kind != "live":
            continue
        try:
            frame = json.loads(data)
        except Exception:
            continue
        payload = frame.get("payload") or {}
        jd = _jd(payload)
        if jd.get("run_id") == run_id and jd.get("phase") == "flight":
            seen[jd.get("seq")] = payload

    check("all {} live flight frames received".format(FLIGHT),
          set(seen.keys()) == set(range(FLIGHT)),
          "got seqs {}".format(sorted(k for k in seen.keys() if k is not None)))

    # verify the payload survived the pipe intact (altitude per seq)
    alt_ok = True
    for seq, payload in seen.items():
        if seq is None:
            continue
        if abs(float(payload.get("z", -999)) - _expected_alt(seq)) > 1e-6:
            alt_ok = False
    check("live payload data intact (altitude matches)", alt_ok)

    reader.close()

    # 6. everything persisted -> /recent
    st, body = get("/event/{}/recent?minutes=5".format(PUBLIC_KEY), timeout=10)
    persisted = 0
    if st == 200:
        try:
            for row in json.loads(body):
                if _jd(row).get("run_id") == run_id:
                    persisted += 1
        except Exception:
            pass
    check("recent shows all persisted events", persisted >= WARMUP + FLIGHT,
          "got {}/{} (status {})".format(persisted, WARMUP + FLIGHT, st))

    _summary_and_exit()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
