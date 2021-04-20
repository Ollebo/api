from influxdb import InfluxDBClient
import os
#Inefluxdb settings
client = InfluxDBClient(os.environ['INDB'],os.environ['INDB_PORT'] , os.environ['INDB_USER'], os.environ['INDB_PASSWORD'], os.environ['INDB_DATABASE'])
#client.create_database(os.environ['INDB_DATABASE'])




def add_influxdb(data):
    #Adding data to influx
    json_data = [
           {
             "measurement": data['type'],
             "tags": {
                      "host": data['from'],
                      "client": data['client']
                      },
             "time": data['timestamp'],
             "fields": data['data']
                   }
                 ]

    client.write_points(json_data)