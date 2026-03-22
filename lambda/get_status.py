"""
Get Status Lambda
Returns job status from DynamoDB
"""

import json
import os
import boto3
from decimal import Decimal

# Add this helper function
def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ['TABLE_NAME']

def lambda_handler(event, context):
    """
    Get job status from DynamoDB
    """
    try:
        # Get job_id from path parameters
        job_id = event.get('pathParameters', {}).get('id')
        
        if not job_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Missing job_id in path'
                })
            }
        
        # Get job from DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(
            Key={
                'repo': 'JOB',
                'file_path': job_id
            }
        )
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Job not found',
                    'job_id': job_id
                })
            }
        
        job = response['Item']
        
        # Build response based on status
        result = {
            'job_id': job_id,
            'status': job['status'],
            'file_path': job.get('actual_file_path'),  # ← Use actual values
            'repo': job.get('actual_repo'),
            'created_at': job.get('created_at')
        }
        
        # Add status-specific fields
        if job['status'] == 'queued':
            result['message'] = 'Job is queued for processing'
            
        elif job['status'] == 'processing':
            result['message'] = 'Job is currently being processed'
            result['started_at'] = job.get('started_at')
            
        elif job['status'] == 'completed':
            result['message'] = 'Job completed successfully'
            result['completed_at'] = job.get('completed_at')
            result['confidence'] = job.get('confidence', 0.0)
            result['updated_code'] = job.get('updated_code')
            result['explanation'] = job.get('explanation')
            
        elif job['status'] == 'failed':
            result['message'] = 'Job failed'
            result['error'] = job.get('error', 'Unknown error')
            result['failed_at'] = job.get('failed_at')
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error in get_status: {e}")
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
