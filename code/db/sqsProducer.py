import boto3
import json
import os

# Create SQS client
LOCALSTACK = os.environ.get('LOCALSTACK', False)
MAPS_SQS = os.environ.get('MAPS_SQS', 'http://localhost:4566/000000000000/maps')
EVENTS_SQS = os.environ.get('EVENTS_SQS', 'http://localhost:4566/000000000000/events')
AWS_ACCESS_KEY_ID_l = os.environ.get('AWS_ACCESS_KEY_ID', 'FAKE')
AWS_SECRET_ACCESS_KEY_l = os.environ.get('AWS_SECRET_ACCESS_KEY', 'FAKE')
AWS_REGION = os.environ.get('AWS_REGION', 'us-north-1')

                        
#if LOCALSTACK:
#    sqs = boto3.client('sqs',endpoint_url='http://192.168.1.130:4566',region_name=AWS_REGION,aws_access_key_id=AWS_ACCESS_KEY_ID_l, aws_secret_access_key=AWS_SECRET_ACCESS_KEY_l)
#else:


#Set Que URL



def addToSQS(data):
# Send message to SQS queue
    sqs = boto3.client('sqs',endpoint_url='https://vpce-01ce2f6111533ed3b-lhzab6vc.sqs.eu-north-1.vpce.amazonaws.com')
    print("Connect to SQS" + MAPS_SQS)
    print("Sending the message")

    response = sqs.send_message(
        QueueUrl=MAPS_SQS,
        DelaySeconds=2,
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
    sqs = boto3.client('sqs',endpoint_url='https://vpce-01ce2f6111533ed3b-lhzab6vc.sqs.eu-north-1.vpce.amazonaws.com')
    print("Connect to SQS" + EVENTS_SQS)
    print("Sending the message")
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