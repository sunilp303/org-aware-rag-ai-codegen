"""
Submit Job Lambda
Receives request, creates job in DynamoDB, sends to SQS, returns job_id immediately
"""

import json
import os
import boto3
import uuid
from datetime import datetime

sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')

QUEUE_URL = os.environ['QUEUE_URL']
TABLE_NAME = os.environ['TABLE_NAME']

def lambda_handler(event, context):
    """
    Receive code update request and queue it for async processing
    Returns job_id immediately
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        required = ['comment', 'code', 'file_path', 'language', 'repo']
        missing = [f for f in required if not body.get(f)]
        
        if missing:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing required fields',
                    'missing': missing
                })
            }
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        timestamp = int(datetime.utcnow().timestamp())
        
        # Create job record in DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        table.put_item(
            Item={
                'repo': 'JOB',                          # ← Fixed partition key
                'file_path': job_id,                    # ← job_id as sort key
                'job_id': job_id,
                'status': 'queued',
                'created_at': timestamp,
                'ttl': timestamp + (7 * 24 * 60 * 60),
                'actual_file_path': body['file_path'], # ← Store real file path
                'actual_repo': body['repo'],           # ← Store real repo
                'comment': body['comment'],
                'code_length': len(body['code']),
                'language': body['language']
            }
        )
        
        # Send job to SQS queue
        message = {
            'job_id': job_id,
            'comment': body['comment'],
            'code': body['code'],
            'file_path': body['file_path'],
            'language': body['language'],
            'repo': body['repo']
        }
        
        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(message),
            MessageAttributes={
                'job_id': {
                    'StringValue': job_id,
                    'DataType': 'String'
                }
            }
        )
        
        print(f"Job {job_id} queued for {body['file_path']}")
        
        # Return job_id immediately
        return {
            'statusCode': 202,  # Accepted
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'job_id': job_id,
                'status': 'queued',
                'message': 'Job submitted for processing',
                'file_path': body['file_path'],
                'estimated_time': '30-90 seconds'
            })
        }
        
    except Exception as e:
        print(f"Error in submit_job: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }
