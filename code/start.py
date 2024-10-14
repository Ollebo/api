#
#
#
# File to start
#
# Lissen for events from the que
#!/usr/bin/env python
import time
import time
import json
from flask import Flask, request, render_template, url_for, redirect, jsonify
from flask_cors import CORS
from maps import maps, mapsSearch
from event import event
from missions import missions, mission
#from people import people
#from places import places

app = Flask(__name__)
CORS(app ,resources={r"/maps/*": {"origins": "*"}})


@app.route("/maps/",methods = ['GET', 'POST', 'PUT'])
def mapsRoute():
	payload = request.get_json(silent=True)
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
	#print(payload)
	return event(payload,request,mission_id)



@app.route("/", methods = ['GET', 'POST'])
def start():
	if request.method == 'POST':
		print(request.get_data(as_text=True))
		return "Move along nothing to see"
	else:
		return "Get along nothing to see"

