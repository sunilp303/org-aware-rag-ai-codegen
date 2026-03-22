# QUICKSTART - Deploy in 30 Minutes

Complete setup guide for the RAG + Agentic Code Bot.

**What you'll deploy:**
- Aurora PostgreSQL with pgvector (vector database)
- Lambda functions (indexer + workflow)
- API Gateway with API key authentication
- Bedrock Claude 3.5 Haiku integration
- GitHub Action for PR comments

**Cost:** $36-41/month for 5 repositories

---

## ✅ Prerequisites Checklist

Before starting, ensure you have:

- [ ] AWS Account with admin access
- [ ] AWS CLI configured (`aws configure`)
- [ ] Terraform installed (`terraform --version`)
- [ ] GitHub Personal Access Token with `repo` scope
- [ ] 5 GitHub repositories to index
- [ ] Existing VPC with 2+ private subnets (or use default VPC)

---

## 🚀 Step-by-Step Setup

### Step 1: Enable AWS Bedrock Models (5 minutes)

**CRITICAL: Do this first or deployment will fail!**

1. Go to AWS Bedrock Console:
   ```
   https://console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess
   ```

2. Click **"Manage model access"** button

3. Enable these models:
   - ✅ **Claude 3.5 Haiku** (for code generation)
   - ✅ **Amazon Titan Embeddings G1 - Text** (for embeddings)

4. Click **"Save changes"**

5. Wait 1-2 minutes for approval (usually instant)

6. Verify models are enabled:
   ```bash
   aws bedrock list-foundation-models \
     --region us-east-1 \
     --by-provider anthropic \
     --query 'modelSummaries[?contains(modelId, `3-5-haiku`)].{Model:modelId,Status:modelLifecycle.status}' \
     --output table
   ```

   Expected output:
   ```
   |--------------------------------------------|--------|
   |                   Model                    | Status |
   |--------------------------------------------|--------|
   | anthropic.claude-3-5-haiku-20241022-v1:0  | ACTIVE |
   |--------------------------------------------|--------|
   ```

---

### Step 2: Set Environment Variables (2 minutes)

```bash
# AWS Configuration
export AWS_REGION="us-east-1"
export TF_VAR_project_name="rag-code-bot"

# Aurora Database Password (8+ characters, alphanumeric)
export TF_VAR_db_master_password="YourSecurePassword123!"

# Your 5 GitHub Repositories (format: "org/repo-name")
export TF_VAR_github_repos='[
  "your-org/backend-api",
  "your-org/frontend-app",
  "your-org/data-pipeline",
  "your-org/ml-models",
  "your-org/infrastructure"
]'

# Your existing VPC and subnets
export TF_VAR_vpc_id="vpc-xxxxxxxx"
export TF_VAR_private_subnet_ids='["subnet-xxxxxxxx","subnet-yyyyyyyy"]'

# Your GitHub Personal Access Token
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
```

**To create GitHub token:**
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scope: `repo` (Full control of private repositories)
4. Click "Generate token"
5. Copy the token (you won't see it again!)

---

### Step 3: Deploy Infrastructure (10 minutes)

```bash
# Navigate to terraform directory
cd terraform

# Rename API key version to main.tf
mv main_with_apikey.tf main.tf

# Initialize Terraform
terraform init

# Review what will be created
terraform plan

# Deploy (takes ~10-15 minutes)
terraform apply

# Type 'yes' when prompted
```

**What gets created:**
- Aurora PostgreSQL Serverless v2 cluster
- 2 Lambda functions (indexer + workflow)
- API Gateway REST API with API key
- DynamoDB table for state tracking
- Security groups, IAM roles, CloudWatch logs
- EventBridge rule for daily indexing

**Save these outputs:**
```bash
# API endpoint
terraform output api_endpoint
# Example: https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod

# API key (keep this secret!)
terraform output -raw api_key
# Example: dGhpc2lzYXJhbmRvbWFwaWtleQ

# Aurora endpoint
terraform output aurora_endpoint
# Example: rag-code-bot-vector-db.cluster-xxx.us-east-1.rds.amazonaws.com
```

---

### Step 4: Store GitHub Token (1 minute)

```bash
# Store GitHub token in AWS Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id rag-code-bot/github-token \
  --secret-string "{\"token\":\"$GITHUB_TOKEN\"}" \
  --region us-east-1

# Verify it was stored
aws secretsmanager get-secret-value \
  --secret-id rag-code-bot/github-token \
  --region us-east-1 \
  --query 'SecretString' \
  --output text
```

---

### Step 5: Run Initial Code Indexing (5 minutes)

```bash
# Get the indexer function name
INDEXER_FUNCTION=$(terraform output -raw indexer_function_name)

# Trigger indexing for all 5 repos
aws lambda invoke \
  --function-name $INDEXER_FUNCTION \
  --payload "{\"repositories\":$TF_VAR_github_repos}" \
  --region us-east-1 \
  response.json

# Check the response
cat response.json | jq '.'
```

**Expected output:**
```json
{
  "message": "Indexing complete",
  "results": [
    {"repo": "your-org/backend-api", "status": "success"},
    {"repo": "your-org/frontend-app", "status": "success"},
    {"repo": "your-org/data-pipeline", "status": "success"},
    {"repo": "your-org/ml-models", "status": "success"},
    {"repo": "your-org/infrastructure", "status": "success"}
  ],
  "stats": {
    "total_repos": 5,
    "total_files": 247,
    "total_chunks": 1543,
    "database_size": "12 MB"
  }
}
```

**This indexes all your code into Aurora PostgreSQL for RAG retrieval.**

---

### Step 6: Setup GitHub Actions (5 minutes per repo)

Do this for **each** of your 5 repositories:

#### A. Copy GitHub Action Files

```bash
# Clone your repo
git clone https://github.com/your-org/backend-api
cd backend-api

# Create directories
mkdir -p .github/workflows .github/scripts

# Copy workflow file (rename to remove -apikey suffix)
cp /path/to/clean-rag-solution/.github/workflows/code-update-bot-apikey.yml \
   .github/workflows/code-update-bot.yml

# Copy bot script
cp /path/to/clean-rag-solution/.github/scripts/code_update_bot.py \
   .github/scripts/
```

#### B. Add GitHub Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**

Add these **2 secrets:**

**Secret 1:**
```
Name:  MODEL_API_ENDPOINT
Value: https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/api/v1/code-update
```
(Get from: `terraform output api_endpoint` and append `/api/v1/code-update`)

**Secret 2:**
```
Name:  MODEL_API_KEY
Value: dGhpc2lzYXJhbmRvbWFwaWtleQ
```
(Get from: `terraform output -raw api_key`)

#### C. Commit and Push

```bash
# Add files
git add .github/

# Commit
git commit -m "Add AI code update bot"

# Push
git push origin main
```

#### D. Repeat for Other 4 Repos

Repeat steps A-C for:
- `your-org/frontend-app`
- `your-org/data-pipeline`
- `your-org/ml-models`
- `your-org/infrastructure`

---

### Step 7: Test the Bot (2 minutes)

1. **Create a test PR** in one of your repos:
   ```bash
   git checkout -b test-ai-bot
   echo "def test():\n    print(1)" > test.py
   git add test.py
   git commit -m "Add test file"
   git push origin test-ai-bot
   ```

2. **Open PR on GitHub**

3. **Add a comment:**
   ```
   /update test.py
   Add error handling and logging
   ```

4. **Watch the magic happen!**
   - GitHub Action triggers
   - Bot calls Lambda workflow
   - Claude analyzes code with RAG
   - Bot commits updated code
   - Bot posts summary comment

**Expected bot response:**
```markdown
## 🤖 AI Code Update Results (RAG + Agentic)

### ✅ Successfully Updated
- **`test.py`**
  - Confidence: 87%
  - Added try-except error handling
  - Added logging with proper formatting
  - Found similar patterns in src/utils.py

**Summary**: 1/1 files updated successfully

---
_Powered by RAG + AWS Bedrock Claude 3.5 • Confidence threshold: 75% • Review changes carefully before merging_
```

---

## 🎯 Quick Verification Checklist

After setup, verify everything works:

- [ ] Bedrock models are enabled (Claude 3.5 Haiku + Titan)
- [ ] Terraform deployed successfully
- [ ] API key is saved (`terraform output -raw api_key`)
- [ ] GitHub token stored in Secrets Manager
- [ ] Initial indexing completed (check `response.json`)
- [ ] GitHub Actions added to all 5 repos
- [ ] GitHub Secrets set (MODEL_API_ENDPOINT, MODEL_API_KEY)
- [ ] Test PR comment works and bot responds

---

## 🔧 Post-Deployment Configuration

### Optional: Adjust Confidence Threshold

Edit `lambda/agentic_workflow_aws.py` line ~58:

```python
# Default: 75% - only high-confidence changes
self.confidence_threshold = 0.75

# Stricter: 85% - fewer but more accurate
self.confidence_threshold = 0.85

# Looser: 65% - more changes, review carefully
self.confidence_threshold = 0.65
```

Then redeploy:
```bash
cd lambda
zip -r ../terraform/lambda_packages/agentic_workflow_aws.zip agentic_workflow_aws.py
cd ../terraform
terraform apply
```

### Optional: Change Indexing Schedule

Edit `terraform/main.tf` line ~460:

```hcl
# Daily at 2 AM UTC
schedule_expression = "cron(0 2 * * ? *)"

# Weekly on Monday at 2 AM
schedule_expression = "cron(0 2 * * 1 *)"

# Every 6 hours
schedule_expression = "rate(6 hours)"
```

Apply changes:
```bash
terraform apply
```

---

## 📊 Monitor Your Deployment

### Check Lambda Logs

```bash
# Indexer logs
aws logs tail /aws/lambda/rag-code-bot-code-indexer --follow

# Workflow logs
aws logs tail /aws/lambda/rag-code-bot-agentic-workflow --follow
```

### Check Database Stats

```bash
# Get Aurora endpoint
AURORA_ENDPOINT=$(terraform output -raw aurora_endpoint)

# Connect
psql -h $AURORA_ENDPOINT -U postgres -d vectordb

# Check stats
SELECT 
  COUNT(DISTINCT repo) as repos,
  COUNT(DISTINCT file_path) as files,
  COUNT(*) as chunks,
  pg_size_pretty(pg_total_relation_size('code_embeddings')) as size
FROM code_embeddings;
```

### Monitor Costs

```bash
# Check current month costs
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=SERVICE
```

---

## 🐛 Troubleshooting

### Issue: API returns 403 Forbidden

**Fix:**
```bash
cd terraform
terraform apply  # Re-apply to fix API key associations
```

### Issue: Bedrock Access Denied

**Cause:** Models not enabled or wrong model ID

**Fix:**
1. Verify Claude 3.5 Haiku is enabled in Bedrock Console
2. Check model ID in Lambda is: `anthropic.claude-3-5-haiku-20241022-v1:0`
3. Add marketplace permissions:
   ```bash
   ROLE=$(aws lambda get-function \
     --function-name rag-code-bot-agentic-workflow \
     --query 'Configuration.Role' --output text | cut -d'/' -f2)
   
   aws iam put-role-policy --role-name $ROLE \
     --policy-name BedrockAccess \
     --policy-document '{
       "Version": "2012-10-17",
       "Statement": [{
         "Effect": "Allow",
         "Action": ["bedrock:InvokeModel", "aws-marketplace:ViewSubscriptions"],
         "Resource": "*"
       }]
     }'
   ```

### Issue: "Model is Legacy" Error

**Cause:** Using old Claude 3 Haiku instead of Claude 3.5 Haiku

**Fix:** Update Lambda to use correct model:
```python
# In lambda/agentic_workflow_aws.py line ~50
self.claude_model = 'anthropic.claude-3-5-haiku-20241022-v1:0'
```

### Issue: GitHub Action Not Triggering

**Checks:**
1. Workflow file exists: `.github/workflows/code-update-bot.yml`
2. Secrets are set: `MODEL_API_ENDPOINT`, `MODEL_API_KEY`
3. Comment includes `/update` or `@code-bot`
4. PR is from a branch (not main)

**View logs:**
- Go to GitHub → Actions tab
- Check the workflow run for errors

---

## 🎉 Success!

You now have:
- ✅ RAG-powered code bot running on AWS
- ✅ 5 repositories indexed and searchable
- ✅ GitHub Actions responding to PR comments
- ✅ Claude 3.5 Haiku analyzing and updating code
- ✅ All on single AWS bill (~$36-41/month)

**Next steps:**
1. Use the bot on real PRs
2. Monitor costs weekly
3. Collect team feedback
4. Adjust confidence threshold based on results
5. Expand to more repos as needed

---

**Questions?**
- Check logs: `aws logs tail /aws/lambda/rag-code-bot-agentic-workflow --follow`
- Run diagnostics: `./diagnose_bedrock.sh`
- Review GitHub Action logs in the Actions tab

🚀 **Happy coding with AI!**