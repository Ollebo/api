#
#
#
# File to start
#
# Lissen for events from the que
#!/usr/bin/env python
import json
import os
import queue

from flask import Flask, Response, request, render_template, url_for, redirect, jsonify, stream_with_context
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from prometheus_flask_exporter import PrometheusMetrics
from maps import maps, mapsSearch
from event import event, recent, authorize_mission_read
from missions import missions, mission, missionValidate
from openapi import OPENAPI_SPEC
from sse_bridge import start_bridge, subscribe
from db.postgis import getRecentEvents, conn as pg_conn
from auth import verify_map_request
from jwt_auth import get_auth_context, JwtError

app = Flask(__name__)
# The dashboard opens the SSE stream with EventSource {withCredentials: true},
# so responses must carry Access-Control-Allow-Credentials: true — which in turn
# forbids a wildcard Access-Control-Allow-Origin. Allowlist specific origins
# (override via CORS_ORIGINS, comma-separated) and enable credentials.
_default_cors = (
    "https://dash.ollebo.com,https://ollebo.com,https://www.ollebo.com,"
    "http://localhost:5173,http://localhost:3000,http://localhost:8888"
)
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_cors).split(",") if o.strip()]
CORS(app, resources={r"/*": {"origins": _cors_origins}}, supports_credentials=True)
metrics = PrometheusMetrics(app, path="/metrics")

start_bridge()


if not os.environ.get("API_KEY"):
    print("WARN: API_KEY admin override env var not set")


SWAGGER_URL = "/doc"
API_SPEC_URL = "/doc/openapi.json"
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_SPEC_URL,
    config={"app_name": "Ollebo API"},
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)


@app.route(API_SPEC_URL, methods=["GET"])
def openapiSpec():
    return jsonify(OPENAPI_SPEC)


def _log_jwt_failure(route, reason):
	fwd = request.headers.get("X-Forwarded-For") or request.headers.get("X-Real-Ip") or "?"
	print("ERROR {} unauthorized: reason={} ip={}".format(route, reason, fwd))


@app.route("/maps/",methods = ['GET', 'POST', 'PUT'])
def mapsRoute():
	payload = request.get_json(silent=True)
	if request.method in ('PUT', 'POST'):
		unauthorized = verify_map_request(request.method, payload, request.headers.get)
		if unauthorized is not None:
			body, status = unauthorized
			return jsonify(body), status
		return maps(payload, request)
	try:
		groups = get_auth_context(request.headers.get)
	except JwtError as e:
		_log_jwt_failure("GET /maps/", str(e))
		return jsonify({"error": "unauthorized", "detail": str(e)}), 401
	return maps(payload, request, groups=groups)

@app.route("/search/",methods = ['POST'])
def searchRoute():
	payload = request.get_json(silent=True)
	try:
		groups = get_auth_context(request.headers.get)
	except JwtError as e:
		_log_jwt_failure("POST /search/", str(e))
		return jsonify({"error": "unauthorized", "detail": str(e)}), 401
	return mapsSearch(payload, groups=groups)


@app.route("/missions/",methods = ['GET', 'POST', 'PUT'])
def missionsRoute():
	payload = request.get_json(silent=True)
	return missions(payload,request)

@app.route("/mission/<id>",methods = ['GET', 'POST', 'PUT'])
def missionRoute(id):
	payload = request.get_json(silent=True)
	return mission(id,request)

@app.route("/mission/validate/<key>",methods = ['GET'])
def missionValidateRoute(key):
	return missionValidate(key, request)



@app.route("/event/<mission_id>",methods = ['PUT'])
def eventsRoute(mission_id):
	payload = request.get_json(silent=True)
	return event(payload,request,mission_id)


@app.route("/event/<mission_id>/recent", methods=['GET'])
def eventRecentRoute(mission_id):
	mission, _subject, denied = authorize_mission_read(mission_id, request.headers.get)
	if denied is not None:
		body, status = denied
		if status in (401, 403):
			_log_jwt_failure("GET /event/{}/recent".format(mission_id), body.get("detail", body.get("error")))
		return jsonify(body), status
	try:
		minutes = int(request.args.get("minutes", 15))
	except (TypeError, ValueError):
		minutes = 15
	return recent(mission["id"], minutes)


@app.route("/event/public/stream", methods=['GET'])
def eventPublicStreamRoute():
	# Firehose of ALL public missions (NATS subject events.public.>). No auth —
	# public by definition. Live-only (no cross-mission backfill); each `live`
	# frame carries mission_id so consumers know which mission it came from.
	# Static path is ranked above the dynamic /event/<mission_id>/stream rule.
	q, cancel = subscribe("events.public.>")

	def gen():
		try:
			yield "event: ready\ndata: {}\n\n"
			while True:
				try:
					item = q.get(timeout=15)
					yield "event: live\ndata: " + json.dumps(item, default=str) + "\n\n"
				except queue.Empty:
					yield ": ping\n\n"
		finally:
			cancel()

	return Response(
		stream_with_context(gen()),
		mimetype="text/event-stream",
		headers={
			"Cache-Control": "no-cache",
			"X-Accel-Buffering": "no",
			"Connection": "keep-alive",
		},
	)


@app.route("/event/<mission_id>/stream", methods=['GET'])
def eventStreamRoute(mission_id):
	mission, subject, denied = authorize_mission_read(mission_id, request.headers.get)
	if denied is not None:
		body, status = denied
		if status in (401, 403):
			_log_jwt_failure("GET /event/{}/stream".format(mission_id), body.get("detail", body.get("error")))
		return jsonify(body), status

	canonical_id = mission["id"]
	q, cancel = subscribe(subject)

	def gen():
		try:
			for row in getRecentEvents(canonical_id, 15):
				yield "event: backfill\ndata: " + json.dumps(row, default=str) + "\n\n"
			yield "event: ready\ndata: {}\n\n"
			while True:
				try:
					item = q.get(timeout=15)
					yield "event: live\ndata: " + json.dumps(item, default=str) + "\n\n"
				except queue.Empty:
					yield ": ping\n\n"
		finally:
			cancel()

	return Response(
		stream_with_context(gen()),
		mimetype="text/event-stream",
		headers={
			"Cache-Control": "no-cache",
			"X-Accel-Buffering": "no",
			"Connection": "keep-alive",
		},
	)



@app.route("/version", methods=["GET"])
@metrics.do_not_track()
def version():
	# APP_VERSION is baked into the image at build time from the commit SHA
	# (see Dockerfile / CI). "dev" for local/unstamped builds.
	return jsonify({"name": "ollebo-api", "version": os.environ.get("APP_VERSION", "dev")}), 200


@app.route("/healthz", methods=["GET"])
@metrics.do_not_track()
def healthz():
	return "ok", 200


@app.route("/readyz", methods=["GET"])
@metrics.do_not_track()
def readyz():
	try:
		with pg_conn.cursor() as cur:
			cur.execute("SELECT 1")
			cur.fetchone()
		return "ok", 200
	except Exception as e:
		try:
			pg_conn.rollback()
		except Exception:
			pass
		return "not ready: {}".format(e), 503


@app.route("/", methods = ['GET', 'POST'])
def start():
	if request.method == 'POST':
		print(request.get_data(as_text=True))
		return "Move along nothing to see"
	else:
		return "Get along nothing to see"
