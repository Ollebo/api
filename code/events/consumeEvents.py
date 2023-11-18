"""
Cosume the data from the Kafka topic map and make a map from the geotiff file
And into the database


"""
from kafka import KafkaConsumer

from saveEvents import *
from json import loads
import json
import os

kafka_servers=str(os.environ.get('KAFKA', "['redpanda:9092']"))
print("Connect to kafka servers: ", kafka_servers)

consumer = KafkaConsumer(
    'event',
    security_protocol='SSL',
    ssl_check_hostname=False,
     bootstrap_servers=kafka_servers,
     auto_offset_reset='earliest',
     enable_auto_commit=True,
     group_id='event-group',
     value_deserializer=lambda x: loads(x.decode('utf-8')))
print('Connected to Kafka')
for msg in consumer:
    #print ('######################################################################################################################3')
    print(msg.value)
    key_values = json.loads(json.dumps(msg.value))
    saveEvent(key_values)