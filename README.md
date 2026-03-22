# 🤖 Org Aware RAG Code Update Bot

**AI-powered code modification assistant that uses Retrieval-Augmented Generation (RAG) to intelligently update code files based on natural language instructions.**

[![AWS](https://img.shields.io/badge/AWS-Serverless-orange)](https://aws.amazon.com/)
[![Bedrock](https://img.shields.io/badge/Bedrock-Claude%204.5-blue)](https://aws.amazon.com/bedrock/)
[![Python](https://img.shields.io/badge/Python-3.11-green)](https://www.python.org/)

---

## 🎯 **What It Does**

Transform this:
```
/update terraform/main.tf add new EC2 instance usvatest01 similar to usvaghrorbb01
```

Into this in **2-3 minutes**:
- ✅ **Finds** similar code patterns across your indexed codebase
- ✅ **Generates** complete, working code following your patterns
- ✅ **Commits** changes directly to your PR
- ✅ **Provides** detailed code review analysis
- ✅ **Reverts** instantly with `/revert` if not satisfied

**Cost:** $0.015 per update (~$1.50/month for 100 updates)

---

## 🌟 **Key Features**

### **Intelligent Code Understanding**
- 🧠 **RAG-powered search** - Finds similar code across those indexed repositories
- 🎯 **Vector embeddings** - Semantic similarity, not just text matching
- 📚 **Context-aware** - Understands your coding patterns and standards
- 🔄 **Cross-repo learning** - Applies best practices from entire organization

### **Production-Grade Quality**
- 📊 **Detailed analysis** - What changed, what works, what needs review
- 🎲 **Confidence scores** - 90-95% accuracy on most updates
- ✅ **Complete preservation** - Never truncates or loses code
- 🎨 **Pattern matching** - Copies proven implementations

### **Enterprise-Ready**
- ⚡ **Async processing** - Handles any file size (tested: 2000+ lines)
- 📈 **Scalable** - Process multiple PRs simultaneously via SQS
- 🔒 **Secure** - VPC-isolated, API key auth, encrypted storage
- 📉 **Observable** - CloudWatch metrics, DynamoDB audit trail

---

## 🏗️ **Architecture**

```
Developer → GitHub PR → GitHub Actions → API Gateway → Lambda → SQS
                                                                   ↓
Developer ← GitHub ← GitHub Actions ← DynamoDB ← Lambda Worker → Aurora (RAG)
                                                        ↓
                                                   Bedrock Claude
```

**Key Components:**
- **Submit Lambda** - Creates job, returns in <1s
- **SQS Queue** - Decouples submission from processing  
- **Worker Lambda** - RAG search + Claude AI processing
- **Aurora pgvector** - Stores embeddings of 371+ files
- **DynamoDB** - Job state and results storage

---

## 🚀 **Quick Start**

### **1. Deploy Infrastructure (5 minutes)**

```bash
# Clone and deploy
git clone https://github.com/sunilp303/github-ai-assistant.git
cd github-ai-assistant/terraform
terraform init
terraform apply -auto-approve

# Get outputs
export SUBMIT_ENDPOINT=$(terraform output -raw submit_endpoint)
export STATUS_ENDPOINT=$(terraform output -raw status_endpoint_template)
export API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id github-ai-assistant/api-key \
  --query SecretString --output text)
```

### **2. Configure GitHub (2 minutes)**

```bash
# Add secrets
gh secret set SUBMIT_ENDPOINT -b"$SUBMIT_ENDPOINT"
gh secret set STATUS_ENDPOINT_TEMPLATE -b"$STATUS_ENDPOINT"
gh secret set MODEL_API_KEY -b"$API_KEY"

# Deploy workflow
cp .github/workflows/code-update-bot-async.yml .github/workflows/
git add .github/workflows/
git commit -m "Add AI code bot"
git push
```

### **3. Index Repositories (3 minutes)**

```bash
aws lambda invoke \
  --function-name rag-code-bot-code-indexer \
  --cli-binary-format raw-in-base64-out \
  --payload '{"repositories":[{"org":"sunilp303","name":"your-repo"}]}' \
  response.json
```

**Done!** Test with `/update` command in any PR.

---

## 💻 **Usage Examples**

### **Add New Resource**
```
/update terraform/environments/prod/ec2.tf
add new claude node uswest2testhc99 similar to uswest2testhc15
```

### **Update Configuration**
```
/update config/database.yaml
increase connection pool from 10 to 20
```

### **Refactor Code**
```
/update src/handlers/auth.py
add rate limiting to login endpoint similar to register endpoint
```

### **Expected Result**

**Within 2-3 minutes:**

```markdown
🤖 AI Code Update Results
✅ Successfully Updated
* File: terraform/environments/prod/ec2.tf  
* Confidence: 95%

Explanation:
# Code Review Analysis
Confidence: 0.95

## Assessment
Successfully added uswest2testhc99 instance copying uswest2testhc15 pattern.

## What was added:
1. ✅ EC2 instance with matching configuration
2. ✅ Security groups configured
3. ✅ Tags applied following standards

## Issues/Concerns:
1. Verify AMI ID is latest approved version

## Recommendation:
Code structurally correct. Review AMI before merge.
```

### **Revert Changes**

**Not satisfied? Instantly undo:**

```
/revert
```

**Revert multiple commits:**

```
/revert 3
```

**Expected Result:**

```markdown
## 🔄 Revert Commits

### ✅ Successfully Reverted

Reverted the last **3** commit(s):

abc1234 🤖 AI Code Update: Applied async job results
def5678 🤖 AI Code Update: Applied async job results
ghi9012 🤖 AI Code Update: Applied async job results
```

### **Iteration Workflow**

```
1. /update terraform/main.tf add resource X
   ↓
2. Review → Not quite right
   ↓
3. /revert
   ↓
4. /update terraform/main.tf add resource X with specific configuration
   ↓
5. Review → Perfect! Merge PR
```

### **Available Commands**

| Command | Description | Example |
|---------|-------------|---------|
| `/update <file> <instruction>` | AI updates code based on instruction | `/update main.tf add resource X` |
| `/revert` | Undo last commit | `/revert` |
| `/revert N` | Undo last N commits (max 10) | `/revert 3` |

---

## 📊 **Performance & Costs**

### **Performance**
- **Processing time:** 2-3 minutes average
- **Max file size:** 2000+ lines tested
- **Concurrent requests:** Unlimited (SQS-backed)
- **Accuracy:** 90-95% (based on confidence scores)

### **Cost Breakdown**
| Service | Cost/Request |
|---------|-------------|
| Bedrock Claude Opus | $0.015 |
| Lambda + API Gateway | $0.0001 |
| SQS + DynamoDB | $0.000001 |
| **Total** | **$0.015** |

**Monthly costs (100 updates):**
- Per-request: $1.50
- Aurora serverless: $43.80
- **Total: ~$45/month**

**ROI:** 1 engineer hour saved = $50-100 value

---

## 🔧 **Configuration**

### **Change Model (Cost Optimization)**

In `lambda/worker.py`:

```python
# Faster, cheaper (recommended)
self.model = 'us.anthropic.claude-sonnet-4-6-v1:0'  # $0.003/request

# Highest quality (current)
self.model = 'us.anthropic.claude-opus-4-5-v1:0'    # $0.015/request
```

### **Adjust Context**

```python
# More examples = better quality, slower, more expensive
self.max_context_files = 5

# Fewer examples = faster, cheaper
self.max_context_files = 3  # Current default
```

---

## 🔒 **Security**

- ✅ **VPC isolation** - Worker in private subnet
- ✅ **Encryption** - At rest (DynamoDB, Aurora) and in transit (TLS)
- ✅ **API authentication** - API Gateway with API key
- ✅ **Secrets management** - AWS Secrets Manager
- ✅ **Auto-expiry** - Job data deleted after 7 days
- ✅ **Audit trail** - All requests logged to CloudWatch

---

## 📈 **Monitoring**

```bash
# Worker logs
aws logs tail /aws/lambda/rag-code-bot-worker --follow

# Check job status
aws dynamodb get-item \
  --table-name rag-code-bot-index-state \
  --key '{"repo":{"S":"JOB"},"file_path":{"S":"<job-id>"}}'
```

---

## 🐛 **Troubleshooting**

### **File Not Found Error**
```bash
# Index the repository
aws lambda invoke \
  --function-name rag-code-bot-code-indexer \
  --cli-binary-format raw-in-base64-out \
  --payload '{"repositories":[{"org":"org","name":"repo"}]}' \
  response.json
```

### **Timeout**
- Check CloudWatch logs: `aws logs tail /aws/lambda/rag-code-bot-worker --since 10m`
- Increase timeout in `lambda/worker.py` if needed (current: 5 min)

### **Markers in File**
- Redeploy latest workflow from this repo
- Workflow should strip `===BEGIN CODE===` markers

### **Bot Made Wrong Changes**
```
/revert  # Instantly undo the last commit
```
Then try again with better/clearer instructions.

---

## 🗺️ **Roadmap**

**Q1 2026** ✅
- [x] /revert command for instant undo
- [x] Detailed code analysis in comments

**Q2 2026**
- [ ] Multi-file updates
- [ ] Auto-merge on high confidence (>85%)
- [ ] Slack integration

**Q3 2026**
- [ ] Jira/Confluence integration
- [ ] Interactive mode
- [ ] Team analytics

---

## 📚 **Documentation**

- [Quick Start Guide](QUICKSTART.md)
- [Use Cases & Examples](USE_CASES.md)
- [Monitoring & Troubleshooting](MONITORING.md)

---

## 📄 **License**

MIT License

---

**Made with ❤️ by cloudai Team**