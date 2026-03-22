#!/usr/bin/env python3
"""
Code Update Bot - Async Version
Submits jobs and polls for results
"""

import os
import sys
import json
import time
import requests
from typing import Dict, Optional

class AsyncCodeUpdateBot:
    """Bot that uses async job submission and polling"""
    
    def __init__(self):
        self.submit_endpoint = os.environ.get('SUBMIT_ENDPOINT')
        self.status_endpoint_template = os.environ.get('STATUS_ENDPOINT_TEMPLATE')
        self.api_key = os.environ.get('MODEL_API_KEY')
        
        if not all([self.submit_endpoint, self.status_endpoint_template, self.api_key]):
            raise ValueError("Missing required environment variables: SUBMIT_ENDPOINT, STATUS_ENDPOINT_TEMPLATE, MODEL_API_KEY")
        
        self.max_poll_time = 300  # 5 minutes max
        self.poll_interval = 10    # Poll every 10 seconds
    
    def submit_job(self, comment: str, code: str, file_path: str, language: str, repo: str) -> Optional[str]:
        """
        Submit job to async queue
        Returns job_id if successful
        """
        try:
            payload = {
                'comment': comment,
                'code': code,
                'file_path': file_path,
                'language': language,
                'repo': repo
            }
            
            print(f"Submitting job for {file_path}...")
            
            response = requests.post(
                self.submit_endpoint,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': self.api_key
                },
                json=payload,
                timeout=30
            )
            
            if response.status_code == 202:
                result = response.json()
                job_id = result.get('job_id')
                print(f"✓ Job submitted: {job_id}")
                print(f"  Status: {result.get('status')}")
                print(f"  Estimated time: {result.get('estimated_time')}")
                return job_id
            else:
                print(f"✗ Failed to submit job: {response.status_code}")
                print(f"  Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"✗ Error submitting job: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """
        Get job status from API
        Returns job status dict
        """
        try:
            status_url = self.status_endpoint_template.replace('{id}', job_id)
            
            response = requests.get(
                status_url,
                headers={'x-api-key': self.api_key},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"✗ Failed to get status: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"✗ Error getting status: {e}")
            return None
    
    def poll_until_complete(self, job_id: str) -> Optional[Dict]:
        """
        Poll job status until completed or failed
        Returns final result
        """
        start_time = time.time()
        attempt = 0
        
        print(f"\nPolling for results (max {self.max_poll_time}s)...")
        
        while time.time() - start_time < self.max_poll_time:
            attempt += 1
            
            status = self.get_job_status(job_id)
            
            if not status:
                print(f"  [{attempt}] Failed to get status, retrying...")
                time.sleep(self.poll_interval)
                continue
            
            current_status = status.get('status')
            
            if current_status == 'queued':
                print(f"  [{attempt}] Queued... waiting")
            elif current_status == 'processing':
                elapsed = int(time.time() - start_time)
                print(f"  [{attempt}] Processing... ({elapsed}s elapsed)")
            elif current_status == 'completed':
                print(f"  [{attempt}] ✓ Completed!")
                return status
            elif current_status == 'failed':
                print(f"  [{attempt}] ✗ Failed: {status.get('error')}")
                return status
            else:
                print(f"  [{attempt}] Unknown status: {current_status}")
            
            time.sleep(self.poll_interval)
        
        print(f"\n✗ Timeout after {self.max_poll_time}s")
        return None
    
    def process_file(self, comment: str, code: str, file_path: str, language: str, repo: str) -> Dict:
        """
        Complete flow: Submit job, poll for results
        Returns result dict
        """
        # Submit job
        job_id = self.submit_job(comment, code, file_path, language, repo)
        
        if not job_id:
            return {
                'success': False,
                'error': 'Failed to submit job',
                'file_path': file_path
            }
        
        # Poll for results
        result = self.poll_until_complete(job_id)
        
        if not result:
            return {
                'success': False,
                'error': 'Timeout waiting for results',
                'job_id': job_id,
                'file_path': file_path
            }
        
        # Check if successful
        if result.get('status') == 'completed':
            return {
                'success': True,
                'job_id': job_id,
                'file_path': file_path,
                'updated_code': result.get('updated_code'),
                'confidence': result.get('confidence', 0.0),
                'explanation': result.get('explanation', '')
            }
        else:
            return {
                'success': False,
                'error': result.get('error', 'Unknown error'),
                'job_id': job_id,
                'file_path': file_path
            }


def main():
    """Test the async bot"""
    try:
        bot = AsyncCodeUpdateBot()
        
        # Test with sample code
        result = bot.process_file(
            comment="Add error handling and logging",
            code="def test():\n    print(1)",
            file_path="test.py",
            language="python",
            repo="test/repo"
        )
        
        print("\n" + "="*60)
        print("FINAL RESULT")
        print("="*60)
        print(json.dumps(result, indent=2))
        
        if result['success']:
            print("\n✓ SUCCESS!")
            print(f"Confidence: {result['confidence']}")
            print(f"\nUpdated code:\n{result['updated_code']}")
        else:
            print("\n✗ FAILED!")
            print(f"Error: {result['error']}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
