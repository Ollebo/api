import boto3
import json
import os

# Create SQS client
LOCALSTACK = os.environ.get('LOCALSTACK', False)
MAPS_SQS = os.environ.get('MAPS_SQS', 'http://localhost:4566/000000000000/maps')
EVENTS_SQS = os.environ.get('EVENTS_SQS', 'http://localhost:4566/000000000000/events')
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', 'FAKE')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', 'FAKE')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

                        
if LOCALSTACK:
    sqs = boto3.client('sqs',endpoint_url='http://192.168.1.130:4566',region_name=AWS_REGION,aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
else:
    sqs = boto3.client('sqs',region_name=AWS_REGION,aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

#Set Que URL



def addToSQS(data):
# Send message to SQS queue
    response = sqs.send_message(
        QueueUrl=MAPS_SQS,
        DelaySeconds=10,
        MessageAttributes={
            'Title': {
                'DataType': 'String',
                'StringValue': 'maps'
            },

        },
        MessageBody=(
                json.dumps(data)
        )
    )

    print(response['MessageId'])



def addToSQSEvent(data):
# Send message to SQS queue
    response = sqs.send_message(
        QueueUrl=EVENTS_SQS,
        DelaySeconds=10,
        MessageAttributes={
            'Title': {
                'DataType': 'String',
                'StringValue': 'events'
            },

        },
        MessageBody=(
                json.dumps(data)
        )
    )

    print(response['MessageId'])