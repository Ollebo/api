from influxdb import InfluxDBClient
import os
import json
#Inefluxdb settings

#client = InfluxDBClient(,os.environ['INDB_PORT'] , os.environ['INDB_USER'], os.environ['INDB_PASSWORD'], os.environ['INDB_DATABASE'])
from influxdb_client import InfluxDBClient
client = InfluxDBClient(url="http://influxdb:9999", token="yduilsJKTS576576ASD", org="ollebo")




def add_influxdb(data):
    #Adding data to influx
    write_api = client.write_api()
    #print(data)
    dataToWrite = {"measurement": 
        "h2o_feet", 
        "tags": {
          "location": "coyote_creek"
          }, 
        "fields": data, 
          }
    print(dataToWrite)
    write_api.write("iot", "Ollebo", [dataToWrite])



