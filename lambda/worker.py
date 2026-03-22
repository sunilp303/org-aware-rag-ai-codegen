"""
Ultra-defensive worker with extensive logging
Every list access is protected
"""

import json
import os
import boto3
from botocore.config import Config
import traceback
import sys
import re
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor

# AWS clients
secretsmanager = boto3.client('secretsmanager')
dynamodb = boto3.resource('dynamodb')

# Bedrock with longer timeout for large prompts
bedrock_config = Config(
    read_timeout=300,
    connect_timeout=10,
    retries={'max_attempts': 2}
)

bedrock = boto3.client(
    'bedrock-runtime',
    region_name='us-east-1',
    config=bedrock_config
)

TABLE_NAME = os.environ.get('TABLE_NAME', 'rag-code-bot-index-state')


class CodeUpdateBot:
    """RAG-powered code update bot with ultra-defensive error handling"""
    
    def __init__(self):
        print("Initializing CodeUpdateBot...")
        
        # Get DB credentials
        db_creds = self._get_secret('aurora-credential-rag')
        print(f"DB credentials retrieved: {db_creds.get('host', 'unknown')[:20]}...")
        
        # Connect to Aurora
        self.conn = psycopg2.connect(
            host=db_creds['host'],
            port=db_creds['port'],
            database=db_creds['database'],
            user=db_creds['username'],
            password=db_creds['password'],
            sslmode='require',
            cursor_factory=RealDictCursor
        )
        print("✓ Connected to Aurora")
        
        self.table = dynamodb.Table(TABLE_NAME)
        self.max_context_files = 3  # Reduced from 5 for faster responses
        self.model = 'us.anthropic.claude-opus-4-5-20251101-v1:0'
    
    def _get_secret(self, secret_name: str) -> Dict:
        """Get secret from Secrets Manager"""
        response = secretsmanager.get_secret_value(
            SecretId=f'rag-code-bot/{secret_name}'
        )
        return json.loads(response['SecretString'])
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding with error handling"""
        try:
            print(f"Generating embedding for text (length: {len(text)})...")
            
            # Truncate if needed
            if len(text) > 32000:
                text = text[:32000]
                print("  Truncated text to 32000 chars")
            
            response = bedrock.invoke_model(
                modelId='amazon.titan-embed-text-v1',
                contentType='application/json',
                accept='application/json',
                body=json.dumps({'inputText': text})
            )
            
            response_body = json.loads(response['body'].read())
            embedding = response_body.get('embedding')
            
            if embedding:
                print(f"✓ Embedding generated (dimension: {len(embedding)})")
            else:
                print("⚠ No embedding in response")
            
            return embedding
            
        except Exception as e:
            print(f"❌ Embedding generation failed: {e}")
            traceback.print_exc()
            return None
    
    def retrieve_context(self, query: str, file_path: str, repo: str) -> List[Dict[str, str]]:
        """
        Retrieve similar code from Aurora with ultra-defensive error handling
        """
        print("="*60)
        print("RETRIEVE_CONTEXT called")
        print(f"  Query: {query[:100]}...")
        print(f"  File: {file_path}")
        print(f"  Repo: {repo}")
        print("="*60)
        
        try:
            # Step 1: Generate embedding
            print("Step 1: Generating query embedding...")
            query_embedding = self.generate_embedding(query)
            
            if not query_embedding:
                print("❌ Failed to generate embedding - returning empty context")
                return []
            
            print(f"✓ Query embedding generated (dim: {len(query_embedding)})")
            
            # Step 2: Search Aurora
            print("Step 2: Searching Aurora for similar code...")
            
            sql = """
                SELECT file_path, code, chunk_id, repo
                FROM code_embeddings
                ORDER BY embedding <-> %s::vector
                LIMIT %s
            """
            
            print(f"  SQL: {sql.strip()}")
            print(f"  Params: [embedding_vector, limit={self.max_context_files}]")
            
            with self.conn.cursor() as cursor:
                cursor.execute(sql, (str(query_embedding), self.max_context_files))
                results = cursor.fetchall()
            
            print(f"✓ Aurora returned {len(results) if results else 0} results")
            
            if not results:
                print("⚠ No results from Aurora - returning empty context")
                return []
            
            # Step 3: Format results defensively
            print("Step 3: Formatting results...")
            formatted = []
            
            for idx, row in enumerate(results):
                print(f"  Processing result {idx + 1}/{len(results)}...")
                
                try:
                    # Defensive access to row data
                    file_path_val = row.get('file_path', '') if row else ''
                    code_val = row.get('code', '') if row else ''
                    chunk_id_val = row.get('chunk_id', '') if row else ''
                    repo_val = row.get('repo', '') if row else ''
                    
                    formatted_item = {
                        'file_path': file_path_val,
                        'content': code_val,  # Map 'code' to 'content'
                        'chunk_id': chunk_id_val,
                        'repo': repo_val
                    }
                    
                    formatted.append(formatted_item)
                    print(f"    ✓ Added: {file_path_val[:50]}... from {repo_val}")
                    
                except Exception as e:
                    print(f"    ⚠ Error formatting row {idx}: {e}")
                    continue
            
            print(f"✓ Successfully formatted {len(formatted)} context items")
            return formatted
            
        except Exception as e:
            print(f"❌ Error in retrieve_context: {e}")
            traceback.print_exc()
            return []
    
    def execute_workflow(self, comment: str, code: str, file_path: str, language: str, repo: str) -> Dict[str, Any]:
        """Execute code update with ultra-defensive error handling"""
        
        print("\n" + "="*60)
        print("EXECUTE_WORKFLOW STARTING")
        print("="*60)
        print(f"Comment: {comment[:100]}...")
        print(f"File: {file_path}")
        print(f"Language: {language}")
        print(f"Repo: {repo}")
        print(f"Code length: {len(code)} chars")
        print("="*60 + "\n")
        
        try:
            # STEP 1: Retrieve context
            print("\n### STEP 1: Retrieve Context ###")
            try:
                similar_code = self.retrieve_context(comment, file_path, repo)
                print(f"Retrieved context items: {len(similar_code) if similar_code else 0}")
            except Exception as e:
                print(f"❌ Context retrieval failed: {e}")
                traceback.print_exc()
                similar_code = []
            
            # STEP 2: Build context string
            print("\n### STEP 2: Build Context String ###")
            try:
                context_str = ""
                
                if similar_code and len(similar_code) > 0:
                    print(f"Building context from {len(similar_code)} items...")
                    
                    for idx, item in enumerate(similar_code):
                        print(f"  Processing item {idx + 1}...")
                        
                        try:
                            # Ultra-defensive access
                            item_file = item.get('file_path', 'unknown') if isinstance(item, dict) else 'unknown'
                            item_repo = item.get('repo', 'unknown') if isinstance(item, dict) else 'unknown'
                            item_content = item.get('content', '') if isinstance(item, dict) else ''
                            
                            context_str += f"\n### Similar code from {item_file} ({item_repo}):\n```\n{item_content}\n```\n"
                            print(f"    ✓ Added context from {item_file[:50]}...")
                            
                        except Exception as e:
                            print(f"    ⚠ Error processing context item {idx}: {e}")
                            continue
                    
                    print(f"✓ Context string built: {len(context_str)} chars")
                else:
                    print("⚠ No similar code found - proceeding without context")
                    context_str = "(No similar code examples found in repository)"
                
            except Exception as e:
                print(f"❌ Context building failed: {e}")
                traceback.print_exc()
                context_str = "(Error retrieving context)"
            
            # STEP 3: Build prompt
            print("\n### STEP 3: Build Prompt ###")
            try:
                prompt = f"""You are a code modification assistant. 

CRITICAL: You must return the COMPLETE, ENTIRE file with ALL existing code preserved. Do not truncate or shorten the file.

User instruction: {comment}

Current COMPLETE file ({len(code.split(chr(10)))} lines):
```{language}
{code}
```

Similar code examples from the repository for reference:
{context_str}

Your task:
1. Take the COMPLETE file above
2. Make ONLY the changes requested in the user instruction
3. Keep ALL other code exactly as is
4. Return the COMPLETE modified file

Response format:
CONFIDENCE: <0-100>
EXPLANATION: 
# Code Review Analysis
Confidence: <0.00-1.00>

## Assessment
<Brief summary of what was changed and why>

## What was added/changed:
1. ✅ <First major change>
2. ✅ <Second major change>
3. ✅ <Third major change>
...

## Issues/Concerns (if any):
1. <Issue 1 with explanation>
2. <Issue 2 with explanation>
...

## Recommendation:
<Final assessment and any actions needed before deployment>

===BEGIN CODE===
<paste the COMPLETE file here with your changes>
===END CODE===
"""
                print(f"✓ Prompt built: {len(prompt)} chars")
                
            except Exception as e:
                print(f"❌ Prompt building failed: {e}")
                traceback.print_exc()
                raise
            
            # STEP 4: Call Bedrock
            print("\n### STEP 4: Call Bedrock ###")
            try:
                print(f"Calling model: {self.model}")
                
                response = bedrock.invoke_model(
                    modelId=self.model,
                    contentType='application/json',
                    accept='application/json',
                    body=json.dumps({
                        'anthropic_version': 'bedrock-2023-05-31',
                        'max_tokens': 16000,
                        'messages': [
                            {'role': 'user', 'content': prompt}
                        ]
                    })
                )
                
                print("✓ Bedrock response received")
                
            except Exception as e:
                print(f"❌ Bedrock call failed: {e}")
                traceback.print_exc()
                raise
            
            # STEP 5: Parse response
            print("\n### STEP 5: Parse Response ###")
            try:
                response_body = json.loads(response['body'].read())
                print(f"Response body keys: {list(response_body.keys())}")
                
                # Defensive content extraction
                content = response_body.get('content', [])
                print(f"Content blocks: {len(content) if content else 0}")
                
                if not content or len(content) == 0:
                    raise ValueError("No content blocks in response")
                
                # Get first content block
                first_block = content[0] if len(content) > 0 else {}
                text = first_block.get('text', '') if isinstance(first_block, dict) else ''
                
                if not text:
                    raise ValueError("No text in first content block")
                
                print(f"Response text length: {len(text)} chars")
                
                # Extract using markers instead of JSON
                import re
                
                # Extract confidence
                confidence_match = re.search(r'CONFIDENCE:\s*(\d+)', text)
                confidence = int(confidence_match.group(1)) if confidence_match else 50
                
                # Extract explanation
                #explanation_match = re.search(r'EXPLANATION:\s*(.+?)(?=\n|===BEGIN CODE===)', text, re.DOTALL)
                explanation_match = re.search(r'EXPLANATION:\s*(.+?)===BEGIN CODE===', text, re.DOTALL)
                explanation = explanation_match.group(1).strip() if explanation_match else "Code updated"
                
                
                # Extract code between markers
                code_match = re.search(r'===BEGIN CODE===\s*(.+?)\s*===END CODE===', text, re.DOTALL)
                
                if code_match:
                    updated_code = code_match.group(1).strip()
                    print(f"✓ Extracted code: {len(updated_code)} chars")
                else:
                    print("⚠ No code markers found, using full response")
                    updated_code = text
                
                print(f"✓ Confidence: {confidence}%")
                print(f"✓ Explanation: {explanation[:100]}...")
                
                return {
                    'confidence': confidence,
                    'explanation': explanation,
                    'updated_code': updated_code
                }
                
            except Exception as e:
                print(f"❌ Response parsing failed: {e}")
                traceback.print_exc()
                raise
            
        except Exception as e:
            print("\n" + "="*60)
            print("EXECUTE_WORKFLOW FAILED")
            print("="*60)
            print(f"Error: {e}")
            print("\nFull traceback:")
            traceback.print_exc(file=sys.stdout)
            print("="*60 + "\n")
            raise


def update_job_status(job_id: str, status: str, data: Dict = None):
    """Update job status in DynamoDB"""
    table = dynamodb.Table(TABLE_NAME)
    
    item = {
        'repo': 'JOB',
        'file_path': job_id,
        'status': status
    }
    
    if data:
        item.update(data)
    
    table.put_item(Item=item)
    print(f"✓ Job {job_id} status updated: {status}")


def lambda_handler(event, context):
    """Lambda handler with extensive logging"""
    
    job_id = None
    
    try:
        print("\n" + "="*60)
        print("LAMBDA HANDLER STARTED")
        print("="*60)
        print(f"Event: {json.dumps(event, indent=2)}")
        print("="*60 + "\n")
        
        # Parse SQS message
        if 'Records' in event and len(event['Records']) > 0:
            record = event['Records'][0]
            body = json.loads(record['body'])
        else:
            body = event
        
        print(f"Message body: {json.dumps(body, indent=2)}")
        
        # Extract job data
        job_id = body.get('job_id')
        comment = body.get('comment')
        code = body.get('code')
        file_path = body.get('file_path')
        language = body.get('language')
        repo = body.get('repo')
        
        print(f"\nJob ID: {job_id}")
        print(f"File: {file_path}")
        print(f"Language: {language}")
        print(f"Repo: {repo}")
        
        if not all([job_id, comment, code, file_path, language, repo]):
            raise ValueError("Missing required fields")
        
        # Update status to processing
        update_job_status(job_id, 'processing')
        
        # Execute workflow
        bot = CodeUpdateBot()
        result = bot.execute_workflow(comment, code, file_path, language, repo)
        
        # Update status to completed
        update_job_status(job_id, 'completed', result)
        
        print("\n" + "="*60)
        print("LAMBDA HANDLER COMPLETED SUCCESSFULLY")
        print("="*60 + "\n")
        
        return {'statusCode': 200, 'body': json.dumps({'job_id': job_id})}
        
    except Exception as e:
        print("\n" + "="*60)
        print("LAMBDA HANDLER FAILED")
        print("="*60)
        print(f"Error: {e}")
        print("\nFull traceback:")
        traceback.print_exc(file=sys.stdout)
        print("="*60 + "\n")
        
        if job_id:
            update_job_status(job_id, 'failed', {
                'error': str(e),
                'traceback': traceback.format_exc()
            })
        
        raise