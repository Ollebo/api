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
from maps import maps
from events import event

app = Flask(__name__)

@app.route("/sweden/towns",methods = ['GET'])
def sweden_towns():
	payload = request.get_data(as_text=True)
    #Convert paylaod to json



@app.route("/maps/",methods = ['GET', 'POST', 'PUT'])
def mapsRoute():
	payload = request.get_json(silent=True)
	#print(payload)
	return maps(payload,request)

@app.route("/event/",methods = ['GET', 'PUT'])
def eventsRoute():
	payload = request.get_json(silent=True)
	#print(payload)
	return event(payload,request)



@app.route("/", methods = ['GET', 'POST'])
def start():
	if request.method == 'POST':
		return "Move along nothing to see"
	else:
		return "Get along nothing to see"

