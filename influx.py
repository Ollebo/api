from influxdb import InfluxDBClient
import os
import json
#Inefluxdb settings

#client = InfluxDBClient(,os.environ['INDB_PORT'] , os.environ['INDB_USER'], os.environ['INDB_PASSWORD'], os.environ['INDB_DATABASE'])
from influxdb_client import InfluxDBClient
in_url =  os.environ.get('INDB', 'influxdb')
in_token =  os.environ.get('INDB_TOKEN', '1234')
in_org =  os.environ.get('INDB_ORG', 'ollebo')
client = InfluxDBClient(url="http://{0}:9999".format(in_url), token=in_token, org=in_org)




def add_influxdb(data):
    #Adding data to influx
    write_api = client.write_api()
    #print(data)
    write_api.write("iot", "Ollebo", [data])



