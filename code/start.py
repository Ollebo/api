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
from maps import maps
from event import event
#from project import project
#from people import people
#from places import places

app = Flask(__name__)
CORS(app ,resources={r"/maps/*": {"origins": "*"}})


@app.route("/maps/",methods = ['GET', 'POST', 'PUT'])
def mapsRoute():
	payload = request.get_json(silent=True)
	return maps(payload,request)

#@app.route("/people/",methods = ['GET', 'POST', 'PUT'])
#def peopleRoute():
#	payload = request.get_json(silent=True)
#	#print(payload)
#	return people(payload,request)
#
#@app.route("/places/",methods = ['GET', 'POST', 'PUT'])
#def placesRoute():
#	payload = request.get_json(silent=True)
#	#print(payload)
#	return places(payload,request)
#
#
#@app.route("/project/",methods = ['GET', 'POST', 'PUT'])
#def projectRoute():
#	payload = request.get_json(silent=True)
#	#print(payload)
#	return project(payload,request)


@app.route("/event/",methods = ['GET', 'PUT'])
def eventsRoute():
	payload = request.get_json(silent=True)
	#print(payload)
	return event(payload,request)



@app.route("/", methods = ['GET', 'POST'])
def start():
	if request.method == 'POST':
		print(request.get_data(as_text=True))
		return "Move along nothing to see"
	else:
		return "Get along nothing to see"

