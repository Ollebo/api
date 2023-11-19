from kafka import KafkaProducer
from time import sleep
from json import dumps
import os

kafka_servers=str(os.environ.get('KAFKA', "['redpanda:9092']"))
print("Connect to kafka servers: ", kafka_servers)

producer = KafkaProducer(bootstrap_servers=kafka_servers,
                             security_protocol='SSL',
                             ssl_check_hostname='False',
                         value_serializer=lambda x: 
                         dumps(x).encode('utf-8'))
def addToKafka(data):
    print("Adding data to kafka")
    producer.send('map', value=data)

def addToKafkaEvent(data):
    producer.send('event', value=data)


def addToKafkaUserEvent(data):
    producer.send('user', value=data)