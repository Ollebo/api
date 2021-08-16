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




@app.route("/", methods = ['GET', 'POST'])
def home():
	if request.method == 'POST':
		return "Move along nothing to see"
	else:
		return "Get along nothing to see"

