from kafka import KafkaProducer  ,NewTopic
from time import sleep
from json import dumps
import os

kafka_servers=str(os.environ.get('KAFKA', "['redpanda:9092']"))
kafka_tls=str(os.environ.get('KAFKA_TLS', "none"))
print("Connect to kafka servers: ", kafka_servers)
if kafka_tls == "none":
    producer = KafkaProducer(bootstrap_servers=kafka_servers,
                        value_serializer=lambda x: 
                        dumps(x).encode('utf-8'))
else:
    producer = KafkaProducer(bootstrap_servers=kafka_servers,
                            security_protocol="SSL",
                            ssl_check_hostname=False,
                            ssl_cafile='/tls/ca.crt',
                             value_serializer=lambda x: 
                             dumps(x).encode('utf-8'))
    
#makin topic
topic_list = [NewTopic(name="map", num_partitions=1, replication_factor=1)]
producer.create_topics(new_topics=topic_list, validate_only=False)

topic_list = [NewTopic(name="event", num_partitions=1, replication_factor=1)]
producer.create_topics(new_topics=topic_list, validate_only=False)

topic_list = [NewTopic(name="user", num_partitions=1, replication_factor=1)]
producer.create_topics(new_topics=topic_list, validate_only=False)

def addToKafka(data):
    print("Adding data to kafka")
    producer.send('map', value=data)

def addToKafkaEvent(data):
    producer.send('event', value=data)


def addToKafkaUserEvent(data):
    producer.send('user', value=data)