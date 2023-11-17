"""
Cosume the data from the Kafka topic map and make a map from the geotiff file
And into the database


"""
from kafka import KafkaConsumer

from saveEvents import *
from json import loads
import json



consumer = KafkaConsumer(
    'event',
     bootstrap_servers=['redpanda:9092'],
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