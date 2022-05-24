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
import os
from flask import Flask, request, render_template, url_for, redirect
from auth import validateToken
from elastic import es_index
from influx import add_influxdb
from indexMelis import addMeilsearch
from mongoclient import getUserId, saveEvent, getProjectID



#Our own data
from storageFile import writeDataToFile
path=os.getenv('VSTECH_URL', '/vstech/data/')

app = Flask(__name__)

@app.route("/data/",methods = ['GET', 'POST'])
def getData():
	headers = request.headers
	auth = headers.get("X-Api-Key")
	userid = getUserId(auth)
	print(userid)
	if userid != False:
		if request.method == 'POST':
			#Get payload as text
			payload = request.get_data(as_text=True)
			#Convert paylaod to json
			json_payload = json.loads(payload)
			json_payload['user_id']=userid

			#Index to elastic
			#es_index(json_payload)

			# influxdb
			#if add_influxdb(json_payload):
			#	print("influx worked")

			
			projectID = getProjectID(userid,json_payload['project'])
			json_payload['projectID']=projectID
			mongoid = saveEvent(json_payload)
			json_payload['id'] = str(mongoid)
			json_payload['_id'] = str(mongoid)
			addMeilsearch(json_payload)
			#print(json_payload)
			return "Data has bean accepted "	
		else:
			return "We got get"

	#The auth token was not accepted
	else:
		return "message ERROR: Unauthorized", 401

@app.route('/image/', methods=['POST'])
def upload_image():
    uploaded_file = request.files['file']
    if uploaded_file.filename != '':
        uploaded_file.save(path+"/images/"+uploaded_file.filename)
    return "Images Saved"



@app.route('/files', methods=['POST'])
def upload_file():
    uploaded_file = request.files['file']
    if uploaded_file.filename != '':
        uploaded_file.save(path+"/files/"+uploaded_file.filename)
    return "file Saved"



@app.route("/", methods = ['GET', 'POST'])
def home():
	if request.method == 'POST':
		return "Move along nothing to see"
	else:
		return "Get along nothing to see"

