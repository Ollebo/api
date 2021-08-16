#
#
#
# File to start
#
# Lissen for events from the que
#!/usr/bin/env python
import pika
import time
import time
import json
from flask import Flask, request, render_template, url_for, redirect


##Backends
from backend.elastic.elastic import *

##For HRB
from articels.articels import *

app = Flask(__name__)
@app.route("/data/",methods = ['GET', 'POST'])
def getData():
	headers = request.headers
	auth = headers.get("X-Api-Key")
	if validateToken(auth) != False:
		if request.method == 'POST':
			#Get payload as text
			payload = request.get_data(as_text=True)
			#Convert paylaod to json
			json_payload = json.loads(payload)
			json_payload['user_id']=validateToken(auth)

			#Index to elastic
			es_index(json_payload)

			# influxdb
			if add_influxdb(json_payload):
				print("influx worked")

			print(json_payload)
			return "Data has bean accepted "	
		else:
			return "We got get"

	#The auth token was not accepted
	else:
		return "message ERROR: Unauthorized", 401




@app.route("/", methods = ['GET', 'POST'])
def home():
	if request.method == 'POST':
		return "Move along nothing to see"
	else:
		return "Get along nothing to see"

