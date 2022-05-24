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
write_api = client.write_api()


def flatten_json(nested_json):
    """
        Flatten json object with nested keys into a single level.
        Args:
            nested_json: A nested json object.
        Returns:
            The flattened json object if successful, None otherwise.
    """
    out = {}

    def flatten(x, name=''):
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + '_')
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + '_')
                i += 1
        else:
            out[name[:-1]] = x

    flatten(nested_json)
    return out



def add_influxdb(data):
    #Adding data to influx
    #out = flatten_json(data)

    #Flatten the data part out 
    flatten= flatten_json(data["data"])
    data["data"] = ""
    for mesurment in flatten:
        json_point={
            mesurment : flatten[mesurment]
        } 

    #Flatten the Network part out 
    netflatten= flatten_json(data["device"]["network"])
    data["network"] = ""
    for network in netflatten:
        json_point_network={
            network : netflatten[network]
        } 
        #Convert the data to be used an influxdb
        data["measurement"]=mesurment
        data["fields"] = json_point
        data["network"]= json_point_network
        print(data)
    #try:
        write_api.write("iot", "Ollebo", [data])
    #    return True
    #except:
    #    return False


