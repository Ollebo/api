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
from event import event, recent
from missions import missions, mission
from openapi import OPENAPI_SPEC
from sse_bridge import start_bridge, subscribe
from db.postgis import getRecentEvents, conn as pg_conn
from auth import verify_map_request

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
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


@app.route("/maps/",methods = ['GET', 'POST', 'PUT'])
def mapsRoute():
	payload = request.get_json(silent=True)
	if request.method in ('PUT', 'POST'):
		unauthorized = verify_map_request(request.method, payload, request.headers.get)
		if unauthorized is not None:
			body, status = unauthorized
			return jsonify(body), status
	return maps(payload,request)

@app.route("/search/",methods = ['POST'])
def searchRoute():
	payload = request.get_json(silent=True)
	return mapsSearch(payload)


@app.route("/missions/",methods = ['GET', 'POST', 'PUT'])
def missionsRoute():
	payload = request.get_json(silent=True)
	return missions(payload,request)

@app.route("/mission/<id>",methods = ['GET', 'POST', 'PUT'])
def missionRoute(id):
	payload = request.get_json(silent=True)
	return mission(id,request)



@app.route("/event/<mission_id>",methods = ['PUT'])
def eventsRoute(mission_id):
	payload = request.get_json(silent=True)
	return event(payload,request,mission_id)


@app.route("/event/<mission_id>/recent", methods=['GET'])
def eventRecentRoute(mission_id):
	try:
		minutes = int(request.args.get("minutes", 15))
	except (TypeError, ValueError):
		minutes = 15
	return recent(mission_id, minutes)


@app.route("/event/<mission_id>/stream", methods=['GET'])
def eventStreamRoute(mission_id):
	q, cancel = subscribe(mission_id)

	def gen():
		try:
			for row in getRecentEvents(mission_id, 15):
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
