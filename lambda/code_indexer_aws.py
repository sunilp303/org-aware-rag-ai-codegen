"""
AWS-Native Code Indexer with Archive-Based Fetching
Uses Git archive to download entire repo in 1 API call
Avoids GitHub rate limiting issues
"""

import json
import os
import boto3
import requests
import tarfile
import io
from datetime import datetime
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor

# AWS clients
secretsmanager = boto3.client('secretsmanager')
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

TABLE_NAME = os.environ.get('TABLE_NAME', 'rag-code-bot-index-state')


class AWSNativeCodeIndexer:
    """
    Indexes code repositories into Aurora pgvector for RAG
    Uses archive download to avoid rate limiting
    """
    
    def __init__(self, force_reindex: bool = False):
        # Get GitHub token (handle both string and dict formats)
        github_secret = self._get_secret('github-token')
        if isinstance(github_secret, dict):
            self.github_token = github_secret.get('token', github_secret.get('github_token'))
        else:
            self.github_token = github_secret
        
        # Get DB credentials (must be dict)
        self.db_credentials = self._get_secret('aurora-credential-rag')
        
        self.table = dynamodb.Table(TABLE_NAME)
        self.force_reindex = force_reindex
        
        # Connect to Aurora
        self.conn = psycopg2.connect(
            host=self.db_credentials['host'],
            port=self.db_credentials['port'],
            database=self.db_credentials['database'],
            user=self.db_credentials['username'],
            password=self.db_credentials['password'],
            sslmode='require',
            cursor_factory=RealDictCursor
        )
        
        self._initialize_schema()
    
    def _get_secret(self, secret_name: str) -> Any:
        """Get secret from AWS Secrets Manager"""
        response = secretsmanager.get_secret_value(
            SecretId=f"rag-code-bot/{secret_name}"
        )
        secret_string = response['SecretString']
        
        # Try to parse as JSON
        try:
            return json.loads(secret_string)
        except json.JSONDecodeError:
            # If not JSON, return as plain string
            return secret_string
    
    def _initialize_schema(self):
        """Initialize Aurora pgvector schema with migration support"""
        with self.conn.cursor() as cursor:
            # Create extension
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # Create table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS code_embeddings (
                    id SERIAL PRIMARY KEY,
                    repo VARCHAR(255) NOT NULL,
                    file_path TEXT NOT NULL,
                    chunk_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    language VARCHAR(50),
                    embedding vector(1536),
                    file_sha VARCHAR(40),
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(repo, file_path, chunk_id)
                );
            """)
            
            # Add file_sha column if it doesn't exist (migration)
            cursor.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'code_embeddings' 
                        AND column_name = 'file_sha'
                    ) THEN
                        ALTER TABLE code_embeddings ADD COLUMN file_sha VARCHAR(40);
                    END IF;
                END $$;
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_vector 
                ON code_embeddings USING ivfflat (embedding vector_cosine_ops);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_repo 
                ON code_embeddings(repo);
            """)
            
            self.conn.commit()
        
        print("✓ Aurora pgvector schema initialized")
    
    def should_index_file(self, repo: str, file_path: str, github_sha: str) -> bool:
        """
        Determine if file should be indexed
        
        Returns True if:
        - force_reindex flag is set
        - File doesn't exist in DynamoDB
        - File SHA has changed (PR merged with updates)
        """
        # Force reindex overrides everything
        if self.force_reindex:
            print(f"  ↻ Force reindex: {file_path}")
            return True
        
        # Check DynamoDB for existing entry
        try:
            response = self.table.get_item(
                Key={'repo': repo, 'file_path': file_path}
            )
            
            if 'Item' not in response:
                print(f"  + New file: {file_path}")
                return True  # New file
            
            stored_sha = response['Item'].get('file_sha')
            
            # If no SHA stored (old schema), re-index
            if not stored_sha:
                print(f"  ↻ No SHA stored: {file_path} (updating to new schema)")
                return True
            
            # Compare SHAs
            if stored_sha != github_sha:
                # Safe slicing with None check
                stored_short = stored_sha[:7] if stored_sha else 'none'
                github_short = github_sha[:7] if github_sha else 'none'
                print(f"  ↻ Changed: {file_path} (SHA: {stored_short} → {github_short})")
                return True  # File changed
            
            # File unchanged, skip
            return False
            
        except Exception as e:
            print(f"  ⚠ Error checking {file_path}: {e}")
            return True  # Index on error to be safe
    
    def get_repository_files(self, org: str, repo_name: str) -> List[Dict[str, str]]:
        """
        Fetch all code files from GitHub repository
        Returns list of {path, sha} dicts
        """
        print(f"📥 Fetching repository tree from GitHub...")
        
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Get default branch first
        repo_info = requests.get(
            f'https://api.github.com/repos/{org}/{repo_name}',
            headers=headers
        ).json()
        
        default_branch = repo_info.get('default_branch', 'main')
        print(f"📌 Default branch: {default_branch}")
        
        # Get repository tree
        url = f'https://api.github.com/repos/{org}/{repo_name}/git/trees/{default_branch}?recursive=1'
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ GitHub API error: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return []
        
        tree = response.json()
        
        if 'tree' not in tree:
            print(f"❌ No 'tree' in response")
            return []
        
        print(f"📊 Total items in tree: {len(tree['tree'])}")
        
        # Filter for code files with SHA tracking
        code_extensions = {'.py', '.js', '.ts', '.java', '.go', '.rb', '.sh', 
                          '.tf', '.tfvars', '.yaml', '.yml', '.hcl', '.json'}
        
        files = []
        for item in tree['tree']:
            if item['type'] == 'blob':  # It's a file
                ext = os.path.splitext(item['path'])[1].lower()
                if ext in code_extensions:
                    files.append({
                        'path': item['path'],
                        'sha': item['sha']
                    })
        
        print(f"✓ Found {len(files)} code files")
        return files, default_branch
    
    def fetch_repo_archive(self, org: str, repo_name: str, default_branch: str) -> Dict[str, str]:
        """
        Download entire repo as tarball (1 API call!)
        Returns dict of {file_path: content}
        """
        print(f"📦 Downloading repository archive...")
        
        headers = {'Authorization': f'token {self.github_token}'}
        
        # Download tarball - ONLY 1 API CALL!
        url = f'https://api.github.com/repos/{org}/{repo_name}/tarball/{default_branch}'
        response = requests.get(url, headers=headers, stream=True, timeout=300)
        
        if response.status_code != 200:
            print(f"❌ Failed to download archive: {response.status_code}")
            return {}
        
        files = {}
        
        try:
            # Extract tarball
            with tarfile.open(fileobj=io.BytesIO(response.content), mode='r:gz') as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        # Remove the root directory from path
                        # GitHub tarballs have format: org-repo-commitsha/path/to/file
                        path_parts = member.name.split('/', 1)
                        if len(path_parts) > 1:
                            file_path = path_parts[1]
                            
                            # Read file content
                            file_obj = tar.extractfile(member)
                            if file_obj:
                                try:
                                    content = file_obj.read().decode('utf-8')
                                    files[file_path] = content
                                except UnicodeDecodeError:
                                    # Skip binary files
                                    pass
            
            print(f"✓ Extracted {len(files)} files from archive")
            
        except Exception as e:
            print(f"❌ Error extracting archive: {e}")
            return {}
        
        return files
    
    def chunk_code(self, code: str, chunk_size: int = 50) -> List[str]:
        """Split code into overlapping chunks"""
        lines = code.split('\n')
        chunks = []
        
        for i in range(0, len(lines), chunk_size):
            chunk = '\n'.join(lines[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        
        return chunks
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using AWS Bedrock Titan"""
        # Truncate if too long for Titan (8192 token limit)
        estimated_tokens = len(text) / 4
        if estimated_tokens > 8000:
            text = text[:32000]
        
        try:
            response = bedrock.invoke_model(
                modelId='amazon.titan-embed-text-v1',
                contentType='application/json',
                accept='application/json',
                body=json.dumps({'inputText': text})
            )
            
            response_body = json.loads(response['body'].read())
            return response_body.get('embedding')
        except Exception as e:
            print(f"⚠ Embedding generation failed: {e}")
            return None
    
    def index_file(self, repo: str, file_info: Dict[str, str], content: str, language: str):
        """
        Index a single file with SHA tracking
        Deletes old chunks and inserts new ones
        Each file gets its own transaction for isolation
        """
        file_path = file_info['path']
        file_sha = file_info['sha']
        
        try:
            # Delete existing chunks for this file from Aurora
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM code_embeddings WHERE repo = %s AND file_path = %s",
                    (repo, file_path)
                )
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    print(f"    🗑 Deleted {deleted_count} old chunks")
            
            # Chunk the code
            chunks = self.chunk_code(content)
            
            if not chunks:
                print(f"    ⚠ No chunks created for {file_path}")
                self.conn.commit()  # Commit the delete even if no new chunks
                return
            
            # Generate embeddings and store
            embeddings_data = []
            
            for chunk_id, chunk in enumerate(chunks):
                embedding = self.generate_embedding(chunk)
                
                if not embedding:
                    print(f"    ⚠ Skipping chunk {chunk_id} - no embedding")
                    continue
                
                embeddings_data.append((
                    repo,
                    file_path,
                    chunk_id,
                    chunk,
                    language,
                    str(embedding),
                    file_sha
                ))
            
            # Bulk insert into Aurora
            if embeddings_data:
                with self.conn.cursor() as cursor:
                    execute_values(
                        cursor,
                        """
                        INSERT INTO code_embeddings 
                        (repo, file_path, chunk_id, code, language, embedding, file_sha)
                        VALUES %s
                        ON CONFLICT (repo, file_path, chunk_id) 
                        DO UPDATE SET 
                            code = EXCLUDED.code,
                            embedding = EXCLUDED.embedding,
                            file_sha = EXCLUDED.file_sha,
                            indexed_at = CURRENT_TIMESTAMP
                        """,
                        embeddings_data
                    )
                
                print(f"    ✓ Stored {len(embeddings_data)} chunks in Aurora")
            
            # Commit the transaction for this file
            self.conn.commit()
            
            # Update DynamoDB index state with SHA
            self.table.put_item(
                Item={
                    'repo': repo,
                    'file_path': file_path,
                    'file_sha': file_sha,
                    'language': language,
                    'chunk_count': len(embeddings_data),
                    'indexed_at': datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            # Rollback the transaction on error
            self.conn.rollback()
            print(f"    ❌ Error indexing {file_path}: {e}")
            raise  # Re-raise to be caught by caller
    
    def index_repository(self, org: str, repo_name: str):
        """Index all files from a repository using archive download"""
        repo_full_name = f"{org}/{repo_name}"
        print(f"\n📚 Indexing repository: {repo_full_name}")
        
        # Get all files with SHAs and default branch
        files_result = self.get_repository_files(org, repo_name)
        
        if not files_result:
            print(f"⚠ No files found in {repo_full_name}")
            return
        
        files, default_branch = files_result
        
        # Download entire repo as archive (1 API call!)
        repo_contents = self.fetch_repo_archive(org, repo_name, default_branch)
        
        if not repo_contents:
            print(f"❌ Failed to download repository archive")
            return
        
        # Filter files that need indexing
        files_to_index = []
        for file_info in files:
            if self.should_index_file(repo_full_name, file_info['path'], file_info['sha']):
                files_to_index.append(file_info)
        
        print(f"📋 Files to index: {len(files_to_index)} (total: {len(files)})")
        
        if not files_to_index:
            print("✓ All files up to date")
            return
        
        # Index each file using pre-downloaded content
        indexed_count = 0
        failed_count = 0
        
        for file_info in files_to_index:
            try:
                print(f"  📄 {file_info['path']}")
                
                # Get content from archive (NO API CALL!)
                content = repo_contents.get(file_info['path'], '')
                
                if not content:
                    print(f"    ⚠ Not found in archive, skipping")
                    continue
                
                # Detect language
                ext = os.path.splitext(file_info['path'])[1]
                lang_map = {
                    '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                    '.java': 'java', '.go': 'go', '.rb': 'ruby', '.sh': 'bash',
                    '.tf': 'terraform', '.tfvars': 'terraform', '.hcl': 'hcl',
                    '.yaml': 'yaml', '.yml': 'yaml', '.json': 'json'
                }
                language = lang_map.get(ext, 'text')
                
                # Index the file (has its own transaction)
                self.index_file(repo_full_name, file_info, content, language)
                indexed_count += 1
                
            except Exception as e:
                failed_count += 1
                print(f"    ❌ Failed to index {file_info['path']}: {e}")
                # Continue with next file (transaction already rolled back)
                continue
        
        print(f"✓ Indexed {indexed_count} files, {failed_count} failed for {repo_full_name}")
    
    def cleanup(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def lambda_handler(event, context):
    """
    Lambda handler for AWS-native code indexing
    
    Event format:
    {
        "repositories": [
            {"org": "org-name", "name": "repo-name"}
        ],
        "force_reindex": false  # Optional - reindex all files regardless of SHA
    }
    """
    
    try:
        # Parse event
        if 'Records' in event:
            body = json.loads(event['Records'][0]['body'])
        else:
            body = event
        
        repositories = body.get('repositories', [])
        force_reindex = body.get('force_reindex', False)
        
        if not repositories:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No repositories specified'})
            }
        
        print(f"🚀 Starting indexing job")
        print(f"   Repositories: {len(repositories)}")
        print(f"   Force reindex: {force_reindex}")
        print(f"   Method: Archive download (1 API call per repo)")
        
        # Initialize indexer with force flag
        indexer = AWSNativeCodeIndexer(force_reindex=force_reindex)
        
        results = []
        for repo in repositories:
            try:
                indexer.index_repository(repo['org'], repo['name'])
                results.append({
                    'repo': f"{repo['org']}/{repo['name']}",
                    'status': 'success'
                })
            except Exception as e:
                print(f"❌ Error indexing {repo['org']}/{repo['name']}: {e}")
                import traceback
                traceback.print_exc()
                results.append({
                    'repo': f"{repo['org']}/{repo['name']}",
                    'status': 'error',
                    'error': str(e)
                })
        
        # Cleanup
        indexer.cleanup()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Indexing complete',
                'results': results
            })
        }
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }