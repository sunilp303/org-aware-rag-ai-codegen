# 📊 Monitoring & Troubleshooting Guide

**Complete reference for monitoring, debugging, and triaging the RAG Code Bot**

---

## 🎯 Quick Health Check (30 seconds)

```bash
#!/bin/bash
# Quick system health check

echo "=== Lambda Functions ==="
aws lambda list-functions --query 'Functions[?contains(FunctionName, `rag-code-bot`)].{Name:FunctionName,Status:State,Modified:LastModified}' --output table

echo -e "\n=== Recent Errors (last 10 min) ==="
aws logs filter-pattern "ERROR" \
  --log-group-name /aws/lambda/rag-code-bot-worker \
  --start-time $(date -u -d '10 minutes ago' +%s)000 \
  | jq -r '.events[].message' | head -20

echo -e "\n=== Indexed Files Count ==="
aws dynamodb scan \
  --table-name rag-code-bot-index-state \
  --filter-expression "repo <> :job" \
  --expression-attribute-values '{":job":{"S":"JOB"}}' \
  --select COUNT \
  | jq '.Count'

echo -e "\n=== Pending Jobs ==="
aws dynamodb scan \
  --table-name rag-code-bot-index-state \
  --filter-expression "repo = :job AND #status = :pending" \
  --expression-attribute-names '{"#status":"status"}' \
  --expression-attribute-values '{":job":{"S":"JOB"},":pending":{"S":"pending"}}' \
  --select COUNT \
  | jq '.Count'

echo -e "\n✅ Health check complete"
```

---

## 📝 CloudWatch Logs

### **Real-Time Log Streaming**

```bash
# Worker Lambda (main processing)
aws logs tail /aws/lambda/rag-code-bot-worker --follow

# Submit Lambda (job creation)
aws logs tail /aws/lambda/rag-code-bot-submit-job --follow

# Status Lambda (job queries)
aws logs tail /aws/lambda/rag-code-bot-get-status --follow

# Indexer Lambda (repository scanning)
aws logs tail /aws/lambda/rag-code-bot-code-indexer --follow
```

### **Filter by Time Range**

```bash
# Last 10 minutes
aws logs tail /aws/lambda/rag-code-bot-worker --since 10m

# Last hour
aws logs tail /aws/lambda/rag-code-bot-worker --since 1h

# Last 24 hours
aws logs tail /aws/lambda/rag-code-bot-worker --since 24h

# Specific time range
aws logs tail /aws/lambda/rag-code-bot-worker \
  --since "2026-03-12T00:00:00" \
  --until "2026-03-12T23:59:59"
```

### **Search for Specific Job**

```bash
# Find all logs for a specific job ID
JOB_ID="abc123-def456"

aws logs tail /aws/lambda/rag-code-bot-worker \
  --since 1h \
  --filter-pattern "$JOB_ID"

# Get complete log stream for a job
aws logs filter-pattern "$JOB_ID" \
  --log-group-name /aws/lambda/rag-code-bot-worker \
  --start-time $(date -u -d '1 hour ago' +%s)000 \
  | jq -r '.events[].message'
```

### **Search for Errors**

```bash
# All errors in last hour
aws logs filter-pattern "ERROR" \
  --log-group-name /aws/lambda/rag-code-bot-worker \
  --start-time $(date -u -d '1 hour ago' +%s)000

# Specific error patterns
aws logs filter-pattern "list index out of range" \
  --log-group-name /aws/lambda/rag-code-bot-worker \
  --start-time $(date -u -d '1 day ago' +%s)000

# Bedrock timeouts
aws logs filter-pattern "ReadTimeoutError" \
  --log-group-name /aws/lambda/rag-code-bot-worker \
  --start-time $(date -u -d '1 hour ago' +%s)000

# Rate limiting errors
aws logs filter-pattern "403" \
  --log-group-name /aws/lambda/rag-code-bot-code-indexer \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

### **Get Full Traceback**

```bash
# Get complete error with stack trace
aws logs filter-pattern "Traceback" \
  --log-group-name /aws/lambda/rag-code-bot-worker \
  --start-time $(date -u -d '10 minutes ago' +%s)000 \
  | jq -r '.events[].message' | head -50
```

---

## 🗄️ DynamoDB Monitoring

### **Check Job Status**

```bash
# Get status of specific job
JOB_ID="abc123-def456"

aws dynamodb get-item \
  --table-name rag-code-bot-index-state \
  --key "{\"repo\":{\"S\":\"JOB\"},\"file_path\":{\"S\":\"$JOB_ID\"}}" \
  | jq '{
    status: .Item.status.S,
    confidence: .Item.confidence.N,
    error: .Item.error.S,
    updated_at: .Item.updated_at.S
  }'
```

### **List All Jobs (Last 24h)**

```bash
# Get all jobs with their status
aws dynamodb scan \
  --table-name rag-code-bot-index-state \
  --filter-expression "repo = :job" \
  --expression-attribute-values '{":job":{"S":"JOB"}}' \
  --projection-expression "file_path, #status, confidence, updated_at" \
  --expression-attribute-names '{"#status":"status"}' \
  | jq -r '.Items[] | "\(.file_path.S) - \(.status.S) - \(.confidence.N // "N/A")% - \(.updated_at.S // "N/A")"'
```

### **Count Jobs by Status**

```bash
# Completed jobs
aws dynamodb scan \
  --table-name rag-code-bot-index-state \
  --filter-expression "repo = :job AND #status = :status" \
  --expression-attribute-names '{"#status":"status"}' \
  --expression-attribute-values '{":job":{"S":"JOB"},":status":{"S":"completed"}}' \
  --select COUNT

# Failed jobs
aws dynamodb scan \
  --table-name rag-code-bot-index-state \
  --filter-expression "repo = :job AND #status = :status" \
  --expression-attribute-names '{"#status":"status"}' \
  --expression-attribute-values '{":job":{"S":"JOB"},":status":{"S":"failed"}}' \
  --select COUNT

# Pending/Processing jobs
aws dynamodb scan \
  --table-name rag-code-bot-index-state \
  --filter-expression "repo = :job AND #status IN (:pending, :processing)" \
  --expression-attribute-names '{"#status":"status"}' \
  --expression-attribute-values '{":job":{"S":"JOB"},":pending":{"S":"pending"},":processing":{"S":"processing"}}' \
  --select COUNT
```

### **Check Indexed Files**

```bash
# Total indexed files
aws dynamodb scan \
  --table-name rag-code-bot-index-state \
  --filter-expression "repo <> :job" \
  --expression-attribute-values '{":job":{"S":"JOB"}}' \
  --select COUNT

# List indexed repositories
aws dynamodb scan \
  --table-name rag-code-bot-index-state \
  --filter-expression "repo <> :job" \
  --expression-attribute-values '{":job":{"S":"JOB"}}' \
  --projection-expression "repo" \
  | jq -r '.Items[].repo.S' | sort -u

# Files from specific repo
aws dynamodb query \
  --table-name rag-code-bot-index-state \
  --key-condition-expression "repo = :repo" \
  --expression-attribute-values '{":repo":{"S":"sunilp303/tenable-ai-remediation"}}' \
  --select COUNT

# Check if specific file is indexed
aws dynamodb get-item \
  --table-name rag-code-bot-index-state \
  --key '{
    "repo": {"S": "sunilp303/tenable-ai-remediation"},
    "file_path": {"S": "terraform/environments/prod/ec2.tf"}
  }' \
  | jq '{
    indexed: (.Item != null),
    sha: .Item.file_sha.S,
    chunks: .Item.chunk_count.N,
    indexed_at: .Item.indexed_at.S
  }'
```

---

## 🔍 Lambda Function Monitoring

### **Check Function Configuration**

```bash
# Worker Lambda config
aws lambda get-function-configuration \
  --function-name rag-code-bot-worker \
  | jq '{
    LastModified,
    Timeout,
    MemorySize,
    Runtime,
    VpcConfig: .VpcConfig.SubnetIds,
    Environment: .Environment.Variables
  }'

# Check when last deployed
aws lambda get-function-configuration \
  --function-name rag-code-bot-worker \
  --query 'LastModified' \
  --output text
```

### **Check Recent Invocations**

```bash
# Get recent invocations with errors
aws logs describe-log-streams \
  --log-group-name /aws/lambda/rag-code-bot-worker \
  --order-by LastEventTime \
  --descending \
  --max-items 10 \
  | jq -r '.logStreams[] | "\(.lastEventTime | tonumber / 1000 | strftime("%Y-%m-%d %H:%M:%S")) - \(.logStreamName)"'
```

### **Test Lambda Directly**

```bash
# Test submit Lambda
aws lambda invoke \
  --function-name rag-code-bot-submit-job \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "comment": "test instruction",
    "code": "# test code",
    "file_path": "test.py",
    "language": "python",
    "repo": "test/repo"
  }' \
  test-response.json && cat test-response.json

# Test status Lambda
aws lambda invoke \
  --function-name rag-code-bot-get-status \
  --cli-binary-format raw-in-base64-out \
  --payload '{"job_id": "test-job-id"}' \
  status-response.json && cat status-response.json
```

---

## 🔄 SQS Queue Monitoring

### **Check Queue Depth**

```bash
# Get queue attributes
aws sqs get-queue-attributes \
  --queue-url $(aws sqs get-queue-url --queue-name rag-code-bot-jobs --query 'QueueUrl' --output text) \
  --attribute-names All \
  | jq '{
    ApproximateNumberOfMessages,
    ApproximateNumberOfMessagesNotVisible,
    ApproximateNumberOfMessagesDelayed
  }'
```

### **Peek at Messages (without removing)**

```bash
# Receive messages without deleting
QUEUE_URL=$(aws sqs get-queue-url --queue-name rag-code-bot-jobs --query 'QueueUrl' --output text)

aws sqs receive-message \
  --queue-url "$QUEUE_URL" \
  --max-number-of-messages 10 \
  --visibility-timeout 0 \
  --wait-time-seconds 0 \
  | jq '.Messages[] | {
    MessageId,
    Body: (.Body | fromjson)
  }'
```

---

## 🗃️ Aurora Database Monitoring

### **Check Aurora Status**

```bash
# Get Aurora cluster status
aws rds describe-db-clusters \
  --db-cluster-identifier rag-code-bot-aurora \
  | jq '{
    Status: .DBClusters[0].Status,
    Engine: .DBClusters[0].Engine,
    EngineVersion: .DBClusters[0].EngineVersion,
    Capacity: .DBClusters[0].ServerlessV2ScalingConfiguration,
    Endpoint: .DBClusters[0].Endpoint
  }'
```

### **Query Aurora via Debug Lambda**

**Deploy debug Lambda first:**

```python
# debug_lambda.py
import json
import psycopg2
import boto3

secretsmanager = boto3.client('secretsmanager')

def lambda_handler(event, context):
    # Get credentials
    response = secretsmanager.get_secret_value(
        SecretId='rag-code-bot/aurora-credential-rag'
    )
    creds = json.loads(response['SecretString'])
    
    # Connect to Aurora
    conn = psycopg2.connect(
        host=creds['host'],
        port=creds['port'],
        database=creds['database'],
        user=creds['username'],
        password=creds['password'],
        sslmode='require'
    )
    
    # Run query
    query = event.get('query', 'SELECT COUNT(*) FROM code_embeddings')
    
    with conn.cursor() as cursor:
        cursor.execute(query)
        results = cursor.fetchall()
    
    conn.close()
    
    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }
```

**Use it:**

```bash
# Count embeddings
aws lambda invoke \
  --function-name aurora-debug \
  --cli-binary-format raw-in-base64-out \
  --payload '{"query": "SELECT COUNT(*) FROM code_embeddings"}' \
  response.json && cat response.json

# Count embeddings by repo
aws lambda invoke \
  --function-name aurora-debug \
  --cli-binary-format raw-in-base64-out \
  --payload '{"query": "SELECT repo, COUNT(*) FROM code_embeddings GROUP BY repo"}' \
  response.json && cat response.json

# Check specific file
aws lambda invoke \
  --function-name aurora-debug \
  --cli-binary-format raw-in-base64-out \
  --payload '{"query": "SELECT file_path, chunk_id, file_sha FROM code_embeddings WHERE file_path LIKE '\''%ec2.tf%'\'' LIMIT 5"}' \
  response.json && cat response.json
```

### **Alternative: SSM Port Forwarding**

```bash
# Find an EC2 instance in same VPC
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=*bastion*" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text)

# Get Aurora endpoint
AURORA_ENDPOINT=$(aws rds describe-db-clusters \
  --db-cluster-identifier rag-code-bot-aurora \
  --query 'DBClusters[0].Endpoint' \
  --output text)

# Start port forwarding
aws ssm start-session \
  --target "$INSTANCE_ID" \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "{\"portNumber\":[\"5432\"],\"localPortNumber\":[\"5432\"],\"host\":[\"$AURORA_ENDPOINT\"]}"

# In another terminal, connect
psql -h localhost -p 5432 -U postgres -d vectordb
```

---

## 🐙 GitHub Integration Monitoring

### **Check GitHub Rate Limit**

```bash
# Get GitHub token
TOKEN=$(aws secretsmanager get-secret-value \
  --secret-id rag-code-bot/github-token \
  --query 'SecretString' \
  --output text)

# Check rate limit
curl -H "Authorization: token $TOKEN" \
  https://api.github.com/rate_limit | jq '{
    core: .resources.core,
    reset_at: (.resources.core.reset | strftime("%Y-%m-%d %H:%M:%S UTC"))
  }'
```

### **Test GitHub API Access**

```bash
# Test access to specific repo
curl -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/sunilp303/tenable-ai-remediation" \
  | jq '{
    name,
    default_branch,
    private,
    permissions
  }'

# Test file fetch
curl -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/sunilp303/tenable-ai-remediation/contents/terraform/main.tf" \
  | jq '{size, name, sha}'
```

---

## 🤖 Bedrock Monitoring

### **Check Model Access**

```bash
# List available models
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `claude`)]' \
  | jq '.[] | {modelId, modelName, outputModalities}'

# Test Bedrock invocation
aws bedrock-runtime invoke-model \
  --model-id us.anthropic.claude-sonnet-4-20250514-v1:0 \
  --region us-east-1 \
  --content-type application/json \
  --accept application/json \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":100,"messages":[{"role":"user","content":"Hello"}]}' \
  output.json && cat output.json
```

### **Check Bedrock Invocation Metrics**

```bash
# Get invocation count (last hour)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Bedrock \
  --metric-name Invocations \
  --dimensions Name=ModelId,Value=us.anthropic.claude-opus-4-5-20251101-v1:0 \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum

# Get error count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Bedrock \
  --metric-name InvocationErrors \
  --dimensions Name=ModelId,Value=us.anthropic.claude-opus-4-5-20251101-v1:0 \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

---

## 💰 Cost Monitoring

### **Get Daily Costs**

```bash
# Last 7 days cost
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --filter '{
    "Tags": {
      "Key": "Project",
      "Values": ["rag-code-bot"]
    }
  }' \
  | jq '.ResultsByTime[] | {
    Date: .TimePeriod.Start,
    Cost: .Total.BlendedCost.Amount
  }'
```

### **Cost by Service**

```bash
# Last 30 days by service
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '30 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --filter '{
    "Tags": {
      "Key": "Project",
      "Values": ["rag-code-bot"]
    }
  }' \
  | jq '.ResultsByTime[0].Groups[] | {
    Service: .Keys[0],
    Cost: .Metrics.BlendedCost.Amount
  }' | sort -k2 -nr
```

### **Estimate Cost per Request**

```bash
# Get Bedrock input/output tokens from last request
aws logs filter-pattern "usage" \
  --log-group-name /aws/lambda/rag-code-bot-worker \
  --start-time $(date -u -d '10 minutes ago' +%s)000 \
  | jq -r '.events[].message' | grep -A 5 "usage"

# Calculate cost
# Claude Opus: $15/1M input tokens, $75/1M output tokens
# Claude Sonnet: $3/1M input tokens, $15/1M output tokens
```

---

## 🔥 Common Issues & Triage

### **Issue: "list index out of range"**

**Diagnosis:**
```bash
# Check if file is indexed
aws dynamodb get-item \
  --table-name rag-code-bot-index-state \
  --key '{
    "repo": {"S": "sunilp303/tenable-ai-remediation"},
    "file_path": {"S": "terraform/main.tf"}
  }'

# If empty, file not indexed
```

**Solution:**
```bash
# Reindex the repository
aws lambda invoke \
  --function-name rag-code-bot-code-indexer \
  --cli-binary-format raw-in-base64-out \
  --payload '{"repositories":[{"org":"sunilp303","name":"tenable-ai-remediation"}]}' \
  response.json
```

---

### **Issue: Bedrock Timeout**

**Diagnosis:**
```bash
# Check for timeout errors
aws logs filter-pattern "ReadTimeoutError" \
  --log-group-name /aws/lambda/rag-code-bot-worker \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

**Solution:**
Already handled with 5-minute timeout. If still occurring, check file size:
```bash
# Check prompt size from logs
aws logs filter-pattern "Prompt built" \
  --log-group-name /aws/lambda/rag-code-bot-worker \
  --start-time $(date -u -d '10 minutes ago' +%s)000 \
  | jq -r '.events[].message'

# If >200KB, reduce context files in worker.py
```

---

### **Issue: GitHub Rate Limiting (403)**

**Diagnosis:**
```bash
# Check rate limit
TOKEN=$(aws secretsmanager get-secret-value \
  --secret-id rag-code-bot/github-token \
  --query 'SecretString' --output text)

curl -H "Authorization: token $TOKEN" \
  https://api.github.com/rate_limit | jq '.resources.core'
```

**Solution:**
```bash
# Wait for reset or use archive method (already implemented)
# Archive method uses only 2 API calls instead of N
```

---

### **Issue: Markers in Committed File**

**Diagnosis:**
```bash
# Check recent commit
git log -1 --name-only
git show HEAD:terraform/main.tf | head -20

# If you see "===BEGIN CODE===", workflow cleaning failed
```

**Solution:**
```bash
# Redeploy fixed workflow
cp /path/to/fixed/code-update-bot-async.yml .github/workflows/
git add .github/workflows/
git commit -m "Fix marker stripping"
git push
```

---

### **Issue: High Confidence Display (9200%)**

**Diagnosis:**
```bash
# Check workflow file line 254
grep "confidence.*100" .github/workflows/code-update-bot-async.yml
```

**Solution:**
```bash
# Should NOT multiply by 100
# Change: ${(result.confidence * 100)}
# To: ${result.confidence}
```

---

## 📊 Performance Metrics Dashboard

### **Create CloudWatch Dashboard**

```bash
# Create dashboard with key metrics
aws cloudwatch put-dashboard \
  --dashboard-name rag-code-bot-metrics \
  --dashboard-body '{
    "widgets": [
      {
        "type": "metric",
        "properties": {
          "metrics": [
            ["AWS/Lambda", "Invocations", {"stat": "Sum"}],
            [".", "Errors", {"stat": "Sum"}],
            [".", "Duration", {"stat": "Average"}]
          ],
          "period": 300,
          "stat": "Average",
          "region": "us-east-1",
          "title": "Lambda Metrics"
        }
      }
    ]
  }'
```

---

## 🚨 Alerts & Notifications

### **Create CloudWatch Alarms**

```bash
# High error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name rag-code-bot-high-errors \
  --alarm-description "Alert when error rate > 5%" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold

# Long duration alarm
aws cloudwatch put-metric-alarm \
  --alarm-name rag-code-bot-slow-processing \
  --alarm-description "Alert when processing > 5 minutes" \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Maximum \
  --period 60 \
  --evaluation-periods 1 \
  --threshold 300000 \
  --comparison-operator GreaterThanThreshold
```

---

## 📖 Useful Shortcuts

```bash
# Add to ~/.bashrc or ~/.zshrc

# Tail worker logs
alias bot-logs='aws logs tail /aws/lambda/rag-code-bot-worker --follow'

# Check job status
bot-status() {
  aws dynamodb get-item \
    --table-name rag-code-bot-index-state \
    --key "{\"repo\":{\"S\":\"JOB\"},\"file_path\":{\"S\":\"$1\"}}" \
    | jq '{status: .Item.status.S, confidence: .Item.confidence.N}'
}

# Count indexed files
alias bot-count='aws dynamodb scan --table-name rag-code-bot-index-state --filter-expression "repo <> :job" --expression-attribute-values '"'"'{":job":{"S":"JOB"}}'"'"' --select COUNT | jq .Count'

# Recent errors
alias bot-errors='aws logs filter-pattern "ERROR" --log-group-name /aws/lambda/rag-code-bot-worker --start-time $(date -u -d "10 minutes ago" +%s)000 | jq -r ".events[].message"'
```

---

## 🎯 Monitoring Checklist

**Daily:**
- [ ] Check error count: `bot-errors`
- [ ] Verify no stuck jobs: Check pending count
- [ ] Review CloudWatch alarms

**Weekly:**
- [ ] Review cost trends
- [ ] Check indexer ran successfully
- [ ] Verify Aurora capacity usage

**Monthly:**
- [ ] Review job success rate
- [ ] Optimize Lambda memory/timeout if needed
- [ ] Update indexed repositories list

---

**Need help?** Check [README.md](README.md) or ask in #rag-code-bot
