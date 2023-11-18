from kafka import KafkaProducer
from time import sleep
from json import dumps
import os



producer = KafkaProducer(bootstrap_servers=[os.environ.get('KAFKA', 'redpanda:9092')],
                         value_serializer=lambda x: 
                         dumps(x).encode('utf-8'))
def addToKafka(data):
    print("Adding data to kafka")
    producer.send('map', value=data)

def addToKafkaEvent(data):
    producer.send('event', value=data)


def addToKafkaUserEvent(data):
    producer.send('user', value=data)