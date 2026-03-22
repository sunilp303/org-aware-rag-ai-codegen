# 💡 Use Cases & Examples

**Real-world examples of using the RAG Code Bot based on actual implementations**

---

## 📋 Table of Contents

1. Infrastructure as Code (Terraform)
2. Configuration Management
3. Code Refactoring & Enhancement
4. Security Hardening
5. Multi-Environment Deployments
6. Database Schema Changes
7. API Development
8. Documentation Updates
9. Automated Dependabot Fixes

---

## 🏗️ Infrastructure as Code (Terraform)

### **Use Case 1: Add New EC2 Instance**

**Scenario:** You need to add a new claude node to production following the same pattern as existing nodes.

**Command:**

```bash
/update terraform/environments/sunilp303-aws-claude-usva/ec2.tf
add new claude node uswest2testhc99 similar to uswest2testhc15 configuration
```

**What the Bot Does:**

1. 🔍 Finds `uswest2testhc15` configuration in the file
2. 🔍 Searches similar EC2 configurations across 7 repositories
3. 🤖 Generates complete resource block:
   - EC2 instance with correct AMI
   - Security groups
   - Subnet assignment
   - KMS encryption
   - Tags following naming standards
   - Outputs for reference

**Expected Result:**

```hcl
# New resources added:

data "aws_subnet" "uswest2testhc99" {
  filter {
    name   = "tag:Name"
    values = ["subnet-claude-usva-private-1a"]
  }
}

data "aws_security_group" "uswest2testhc99" {
  filter {
    name   = "tag:Name"
    values = ["sg-claude-application"]
  }
}

module "elco_tools_cmk_uswest2testhc99" {
  source = "git::https://github.com/sunilp303/bedrock-claude-api.git//kms?ref=v1.2.0"
  
  kms_alias       = "elco_tools_uswest2testhc99"
  kms_description = "KMS key for uswest2testhc99 EBS encryption"
  kms_user_iam    = ["arn:aws:iam::012345678990:root"]
  
  tags = {
    Name        = "elco_tools_uswest2testhc99"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

module "uswest2testhc99-ec2" {
  source = "git::https://github.com/sunilp303/bedrock-claude-api.git//ec2?ref=v2.1.0"
  
  instance_name          = "uswest2testhc99"
  ami_id                = "ami-0abcdef1234567890"
  instance_type         = "t3.large"
  subnet_id             = data.aws_subnet.uswest2testhc99.id
  vpc_security_group_ids = [data.aws_security_group.uswest2testhc99.id]
  key_name              = "claude-prod-key"
  
  root_block_device = {
    encrypted   = true
    kms_key_id  = module.elco_tools_cmk_uswest2testhc99.kms_key_arn
    volume_size = 100
    volume_type = "gp3"
  }
  
  tags = {
    Name        = "uswest2testhc99"
    Environment = "production"
    Application = "claude"
    ManagedBy   = "terraform"
  }
}

output "uswest2testhc99_instance_id" {
  description = "Instance ID for uswest2testhc99"
  value       = module.uswest2testhc99-ec2.instance_id
}

output "uswest2testhc99_private_ip" {
  description = "Private IP for uswest2testhc99"
  value       = module.uswest2testhc99-ec2.private_ip
}
```

**Confidence:** 92-95%

**Analysis Provided:**

```text
# Code Review Analysis
Confidence: 0.95

## Assessment
Successfully added uswest2testhc99 EC2 instance following uswest2testhc15 pattern.

## What was added:
1. ✅ Data sources for subnet and security group lookup
2. ✅ KMS CMK module for EBS encryption
3. ✅ EC2 module with matching configuration
4. ✅ Outputs for instance ID and private IP
5. ✅ Consistent tagging across all resources

## Issues/Concerns:
1. Verify AMI ID is the latest approved version
2. Confirm subnet availability in target AZ

## Recommendation:
Code structurally correct. Review AMI and subnet before applying.
```

**When to Use:**

- ✅ Adding new servers to existing infrastructure
- ✅ Scaling horizontally (more instances of same type)
- ✅ Replicating proven configurations
- ✅ Maintaining consistency across fleet

**Tips for Best Results:**

- Specify the exact resource to copy from
- Include environment name if it matters
- Mention any differences (e.g., "but in us-west-2")
- Review AMI IDs and hardcoded values before applying

---

### **Use Case 2: Add S3 Bucket with Standard Configuration**

**Command:**

```bash
/update terraform/storage/s3.tf
add new S3 bucket for application-logs similar to analytics-data bucket
```

**Expected Result:**

```hcl
module "application_logs_bucket" {
  source = "terraform-aws-modules/s3-bucket/aws"
  version = "3.15.0"

  bucket = "company-application-logs-${data.aws_caller_identity.current.account_id}"
  
  versioning = {
    enabled = true
  }
  
  server_side_encryption_configuration = {
    rule = {
      apply_server_side_encryption_by_default = {
        sse_algorithm     = "aws:kms"
        kms_master_key_id = module.s3_kms_key.kms_key_arn
      }
    }
  }
  
  lifecycle_rule = [
    {
      id      = "transition-to-glacier"
      enabled = true
      
      transition = [
        {
          days          = 90
          storage_class = "GLACIER"
        }
      ]
      
      expiration = {
        days = 365
      }
    }
  ]
  
  tags = {
    Name        = "application-logs"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}
```

**Confidence:** 90-93%

---

### **Use Case 3: Add Security Group Rule**

**Command:**

```bash
/update terraform/networking/security_groups.tf
add ingress rule to web-tier-sg allowing HTTPS from load balancer security group
```

**Expected Result:**

```hcl
resource "aws_security_group_rule" "web_tier_https_from_alb" {
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.web_tier.id
  source_security_group_id = aws_security_group.application_load_balancer.id
  description              = "Allow HTTPS from ALB"
}
```

**Confidence:** 95%+

---

## ⚙️ Configuration Management

### **Use Case 4: Update Application Timeouts**

**Command:**

```bash
/update config/application.yaml
increase database connection timeout from 30s to 60s and query timeout from 10s to 30s
```

**Before:**

```yaml
database:
  connection:
    timeout: 30s
    pool_size: 10
  query:
    timeout: 10s
```

**After:**

```yaml
database:
  connection:
    timeout: 60s
    pool_size: 10
  query:
    timeout: 30s
```

**Confidence:** 98%+

**When to Use:**

- ✅ Tuning application parameters
- ✅ Adjusting thresholds
- ✅ Scaling configuration values
- ✅ Environment-specific tweaks

---

### **Use Case 5: Add Feature Flag**

**Command:**

```bash
/update config/features.yaml
add feature flag for new-checkout-flow defaulting to false with 10% rollout
```

**Expected Result:**

```yaml
features:
  new-checkout-flow:
    enabled: true
    default: false
    rollout:
      percentage: 10
      strategy: gradual
      environments:
        - staging
        - production
    description: "New streamlined checkout experience"
    owner: "payments-team"
```

**Confidence:** 85-90%

---

## 🔧 Code Refactoring & Enhancement

### **Use Case 6: Add Error Handling to Function**

**Command:**

```bash
/update src/api/handlers/auth.py
add error handling to login function similar to register function
```

**Before:**

```python
def login(username, password):
    user = db.get_user(username)
    if user.verify_password(password):
        return create_session(user)
    return None
```

**After:**

```python
def login(username, password):
    try:
        user = db.get_user(username)
        
        if not user:
            logger.warning(f"Login attempt for non-existent user: {username}")
            return {"error": "Invalid credentials"}, 401
        
        if not user.verify_password(password):
            logger.warning(f"Failed login attempt for user: {username}")
            user.increment_failed_attempts()
            return {"error": "Invalid credentials"}, 401
        
        if user.is_locked():
            logger.warning(f"Login attempt for locked account: {username}")
            return {"error": "Account locked"}, 403
        
        session = create_session(user)
        user.reset_failed_attempts()
        logger.info(f"Successful login for user: {username}")
        
        return {"session": session}, 200
        
    except DatabaseConnectionError as e:
        logger.error(f"Database error during login: {str(e)}")
        return {"error": "Service temporarily unavailable"}, 503
    
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}")
        return {"error": "Internal server error"}, 500
```

**Confidence:** 88-92%

---

### **Use Case 7: Add Rate Limiting**

**Command:**

```bash
/update src/api/middleware/rate_limit.py
add rate limiting to API endpoints similar to authentication endpoints
```

**Expected Result:**

```python
from functools import wraps
from flask import request, jsonify
import redis
import time

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def rate_limit(max_requests=100, window=3600):
    """Rate limit decorator - allows max_requests per window (in seconds)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client identifier (IP or API key)
            client_id = request.headers.get('X-API-Key') or request.remote_addr
            key = f"rate_limit:{f.__name__}:{client_id}"
            
            try:
                # Get current request count
                current = redis_client.get(key)
                
                if current is None:
                    # First request in this window
                    redis_client.setex(key, window, 1)
                    return f(*args, **kwargs)
                
                current = int(current)
                
                if current >= max_requests:
                    # Rate limit exceeded
                    ttl = redis_client.ttl(key)
                    return jsonify({
                        "error": "Rate limit exceeded",
                        "retry_after": ttl
                    }), 429
                
                # Increment counter
                redis_client.incr(key)
                return f(*args, **kwargs)
                
            except redis.RedisError as e:
                # If Redis is down, allow the request (fail open)
                logger.error(f"Redis error in rate limiter: {str(e)}")
                return f(*args, **kwargs)
        
        return decorated_function
    return decorator
```

**Confidence:** 85-90%

---

## 🔒 Security Hardening

### **Use Case 8: Add IAM Policy**

**Command:**

```bash
/update terraform/iam/policies.tf
add IAM policy for Lambda function to access S3 bucket similar to existing data-processor policy
```

**Expected Result:**

```hcl
data "aws_iam_policy_document" "lambda_s3_access" {
  statement {
    sid    = "AllowS3Read"
    effect = "Allow"
    
    actions = [
      "s3:GetObject",
      "s3:ListBucket"
    ]
    
    resources = [
      aws_s3_bucket.application_logs.arn,
      "${aws_s3_bucket.application_logs.arn}/*"
    ]
  }
  
  statement {
    sid    = "AllowS3Write"
    effect = "Allow"
    
    actions = [
      "s3:PutObject",
      "s3:DeleteObject"
    ]
    
    resources = [
      "${aws_s3_bucket.application_logs.arn}/*"
    ]
  }
  
  statement {
    sid    = "AllowKMSDecrypt"
    effect = "Allow"
    
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey"
    ]
    
    resources = [
      module.s3_kms_key.kms_key_arn
    ]
  }
}

resource "aws_iam_policy" "lambda_s3_access" {
  name        = "lambda-s3-access-policy"
  description = "Allow Lambda to access S3 bucket"
  policy      = data.aws_iam_policy_document.lambda_s3_access.json
}
```

**Confidence:** 92-95%

---

### **Use Case 9: Add Security Group with Egress Rules**

**Command:**

```bash
/update terraform/networking/security_groups.tf
add security group for database tier allowing inbound from application tier on port 5432 and outbound HTTPS for updates
```

**Expected Result:**

```hcl
resource "aws_security_group" "database_tier" {
  name        = "database-tier-sg"
  description = "Security group for database tier"
  vpc_id      = aws_vpc.main.id
  
  ingress {
    description     = "PostgreSQL from application tier"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.application_tier.id]
  }
  
  egress {
    description = "HTTPS for package updates"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name        = "database-tier-sg"
    Environment = "production"
    Tier        = "database"
  }
}
```

**Confidence:** 93-96%

---

## 🌍 Multi-Environment Deployments

### **Use Case 10: Replicate Production Config to Staging**

**Command:**

```bash
/update terraform/environments/staging/main.tf
add all resources from production environment but with t3.medium instead of t3.large
```

**What the Bot Does:**

1. Reads production configuration
2. Finds all resource definitions
3. Replicates structure with environment-specific changes
4. Adjusts instance types as specified
5. Updates tags to reflect staging environment

**Confidence:** 80-85% (lower due to complexity, but still useful)

**Analysis:**

```text
# Code Review Analysis
Confidence: 0.83

## Assessment
Replicated production infrastructure to staging with appropriate downsizing.

## What was added:
1. ✅ All EC2 instances with t3.medium type
2. ✅ Load balancers with reduced capacity
3. ✅ Auto-scaling groups with lower limits
4. ✅ Tags updated to Environment=staging

## Issues/Concerns:
1. Verify t3.medium is sufficient for staging workload
2. Review auto-scaling limits (min=1, max=3 vs prod min=3, max=10)
3. Database instance class still db.r5.xlarge - may want to downsize

## Recommendation:
Structure is correct. Review instance sizing and scaling limits before applying.
Test in staging thoroughly before promoting to production.
```

---

## 🗄️ Database Schema Changes

### **Use Case 11: Add Database Migration**

**Command:**

```bash
/update migrations/002_add_user_preferences.sql
add user_preferences table with user_id foreign key, preferences JSONB column, and created_at timestamp
```

**Expected Result:**

```sql
-- Migration: Add user_preferences table
-- Version: 002
-- Date: 2026-03-12

BEGIN;

CREATE TABLE IF NOT EXISTS user_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    preferences JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT user_preferences_unique_user UNIQUE(user_id)
);

CREATE INDEX idx_user_preferences_user_id ON user_preferences(user_id);
CREATE INDEX idx_user_preferences_updated_at ON user_preferences(updated_at);

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_user_preferences_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_user_preferences_updated_at();

COMMIT;
```

**Confidence:** 88-92%

---

## 🔌 API Development

### **Use Case 12: Add REST Endpoint**

**Command:**

```bash
/update src/api/routes/users.py
add GET endpoint for user profile similar to existing user list endpoint with authentication
```

**Expected Result:**

```python
@app.route('/api/users/<int:user_id>/profile', methods=['GET'])
@require_authentication
@rate_limit(max_requests=100, window=3600)
def get_user_profile(user_id):
    """Get user profile by ID
    
    Args:
        user_id: User ID to fetch
        
    Returns:
        JSON response with user profile data
        
    Raises:
        401: Unauthorized
        403: Forbidden (can only view own profile unless admin)
        404: User not found
    """
    try:
        # Get authenticated user from request context
        current_user = g.current_user
        
        # Check authorization
        if current_user.id != user_id and not current_user.is_admin:
            logger.warning(
                f"User {current_user.id} attempted to access profile {user_id}"
            )
            return jsonify({"error": "Forbidden"}), 403
        
        # Fetch user
        user = db.session.query(User).filter_by(id=user_id).first()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Build response
        profile = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "preferences": user.preferences or {}
        }
        
        logger.info(f"Profile accessed for user {user_id}")
        return jsonify(profile), 200
        
    except Exception as e:
        logger.error(f"Error fetching user profile {user_id}: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
```

**Confidence:** 85-89%

---

## 📚 Documentation Updates

### **Use Case 13: Add API Documentation**

**Command:**

```bash
/update docs/api/authentication.md
add documentation for new OAuth2 flow similar to existing API key documentation
```

**Expected Result:**

```markdown
## OAuth2 Authentication

### Overview

The API supports OAuth2 authentication for third-party applications. This allows users to grant limited access to their account without sharing credentials.

### Supported Flows

- **Authorization Code Flow**: For web applications with server-side component
- **Client Credentials Flow**: For service-to-service authentication

### Authorization Code Flow

**Step 1: Redirect user to authorization URL**

```text
GET https://api.example.com/oauth/authorize
  ?client_id={your_client_id}
  &redirect_uri={your_redirect_uri}
  &response_type=code
  &scope=read_profile,write_data
  &state={random_state_value}
```

**Step 2: Exchange authorization code for access token**

```bash
curl -X POST https://api.example.com/oauth/token \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "authorization_code",
    "code": "AUTH_CODE_FROM_STEP_1",
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "redirect_uri": "your_redirect_uri"
  }'
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "def50200..."
}
```

**Step 3: Use access token in API requests**

```bash
curl https://api.example.com/api/users/profile \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

### Security Best Practices

- Always use HTTPS
- Validate redirect_uri to prevent open redirects
- Store client_secret securely (environment variables, secrets manager)
- Implement token rotation
- Set appropriate token expiration times
```

**Confidence:** 82-87%

---

## 🎯 Best Practices for All Use Cases

### ✅ **Write Clear Instructions**

**Good:**

```bash
/update terraform/main.tf
add new S3 bucket for audit-logs with versioning enabled, 
lifecycle policy to transition to Glacier after 90 days, 
and KMS encryption similar to compliance-data bucket
```

**Bad:**

```bash
/update terraform/main.tf
add S3 bucket
```

---

### ✅ **Reference Existing Patterns**

**Good:**

```bash
/update src/handlers/payment.py
add retry logic similar to order_processing handler
```

**Bad:**

```bash
/update src/handlers/payment.py
add retry logic
```

---

### ✅ **Specify Exact Locations**

**Good:**

```bash
/update config/environments/production/app.yaml
increase worker pool size from 10 to 20
```

**Bad:**

```bash
/update app.yaml
increase workers
```

---

### ✅ **Mention Important Constraints**

**Good:**

```bash
/update terraform/networking/vpc.tf
add new subnet in us-east-1a for database tier with CIDR 10.0.4.0/24
```

**Bad:**

```bash
/update terraform/networking/vpc.tf
add database subnet
```

---

## 📊 Confidence Score Interpretation

| Score | Meaning | Action |
|-------|---------|--------|
| **95-100%** | Exact pattern match, high confidence | ✅ Safe to merge after basic review |
| **85-94%** | Strong pattern match, minor variations | ⚠️ Review carefully, test in non-prod |
| **70-84%** | Partial pattern match, some assumptions | 🔍 Detailed review required, verify logic |
| **<70%** | Weak pattern match, significant uncertainty | ❌ Use as starting point, manual refinement needed |

---

## 🚀 Advanced Use Cases

### **Use Case 14: Complex Multi-File Change**

**Scenario:** Add a new feature that touches multiple files

**Approach:** Use multiple `/update` commands in sequence:

```bash
1. /update src/models/user.py
   add preferences field to User model

2. /update migrations/003_add_user_preferences.sql
   add migration for preferences column

3. /update src/api/routes/users.py
   add endpoint to update user preferences

4. /update tests/test_user_preferences.py
   add tests for new preferences functionality
```

**Why Sequential:** Bot focuses on one file at a time with full context, ensuring quality for each change.

---

### **Use Case 15: Gradual Refactoring**

**Scenario:** Refactor legacy code incrementally

**Command:**

```bash
/update src/legacy/payment_processor.py
extract database operations into separate repository class 
similar to modern order_service.py pattern
```

**Confidence:** 75-85% (refactoring is harder, but bot provides good starting point)

---

## 🔒 Automated Dependabot Fixes

### **Use Case 16: Automated Security Vulnerability Fixes**

**Scenario:** Your repository has multiple Dependabot security alerts that need fixing. Instead of manually creating PRs and running updates, automate the entire process.

**Three Automation Options:**

| Feature | Option 1: Auto-Comment | Option 2: Weekly Scan | Option 3: Enhanced Worker |
|---------|----------------------|---------------------|------------------------|
| **Setup Time** | 5 minutes | 10 minutes | 30 minutes |
| **Triggers** | When Dependabot creates PR | Weekly schedule | Every `/update` |
| **Context Passed** | From PR title/body | All open alerts | Real-time alert fetch |
| **Best For** | Quick wins | Consolidation | Maximum intelligence |
| **Automation Level** | Semi-auto | Semi-auto | Fully auto |
| **Maintenance** | Low | Low | Medium |

---

#### **Option 1: Auto-Comment on Dependabot PRs** ⭐ **Easiest - 5 min setup**

**What it does:** Automatically posts `/update` commands when Dependabot creates PRs

**Deploy:**

```bash
cp auto-dependabot-trigger.yml .github/workflows/
git add .github/workflows/auto-dependabot-trigger.yml
git commit -m "feat: Auto-trigger bot on Dependabot PRs"
git push
```

**Workflow:**

```text
Dependabot creates PR: "Bump axios from 0.21.0 to 0.21.4"
  ↓ (5 seconds)
Workflow auto-posts: "/update package.json upgrade axios from 0.21.0 to 0.21.4 to fix CVE-2021-3749"
  ↓ (2 minutes)
Bot commits fix with CVE in message
  ↓
Review and merge ✅
```

**Example Result:**

```text
🤖 Update package.json: upgrade axios from 0.21.0 to 0.21.4 to fix CVE-2021-3749 (96%)
```

**Benefits:**

- ✅ Zero manual work per alert
- ✅ Instant response when PR created
- ✅ CVE numbers in commit messages
- ✅ Clear audit trail

**When to use:** You want automatic responses to each Dependabot PR

---

#### **Option 2: Weekly Security Scan** ⭐⭐ **Most Complete - 10 min setup**

**What it does:** Scans all Dependabot alerts weekly and creates consolidated PR with ready-to-run commands

**Deploy:**

```bash
cp weekly-security-scan.yml .github/workflows/
git add .github/workflows/weekly-security-scan.yml
git commit -m "feat: Add weekly security scan"
git push

# Test now:
gh workflow run "Weekly Dependabot Security Scan"
```

**Workflow:**

```text
Every Monday 9 AM UTC
  ↓
Fetches ALL Dependabot alerts via GitHub GraphQL
  ↓
Creates PR: "🔒 Security: Fix 15 Dependabot alerts"
  ↓
Includes /update commands for each file:
  - /update package.json upgrade axios, lodash, minimist
  - /update requirements.txt upgrade Django, requests
  - /update Gemfile upgrade rails, nokogiri
  ↓
You copy/paste commands as PR comments
  ↓
Bot fixes all → Merge one PR ✅
```

**Example PR Body:**

```markdown
## 🔒 Automated Security Fixes

Found **15** Dependabot alerts.

### Bot Commands

#### package.json

```bash
/update package.json
upgrade axios to 0.21.4 (fix CVE-2021-3749 - HIGH), 
lodash to 4.17.21 (fix CVE-2021-23337 - HIGH), 
minimist to 1.2.6 (fix CVE-2021-44906 - MODERATE)
```

<details>
<summary>Alert Details</summary>

- **axios**: CVE-2021-3749, SSRF vulnerability, upgrade 0.21.0 → 0.21.4
- **lodash**: CVE-2021-23337, Prototype Pollution, upgrade 4.17.15 → 4.17.21
- **minimist**: CVE-2021-44906, Prototype Pollution, upgrade 0.0.8 → 1.2.6

</details>
```

**Benefits:**

- ✅ One PR for all alerts (easier review)
- ✅ Complete context (CVE, severity, versions)
- ✅ Scheduled (predictable)
- ✅ Ready-to-run commands

**When to use:** You want weekly security reviews with all alerts consolidated

---

#### **Option 3: Enhanced Worker** ⭐⭐⭐ **Most Intelligent - 30 min setup**

**What it does:** Worker automatically fetches Dependabot alerts and uses them as context for ANY `/update` command

**Setup:** See `WORKER_DEPENDABOT_ENHANCEMENT.md` for code changes

**Workflow:**

```text
User: /update package.json upgrade vulnerable dependencies
  ↓
Worker fetches Dependabot alerts from GitHub API
  ↓
Finds: axios (CVE-2021-3749), lodash (CVE-2021-23337)
  ↓
Adds to Claude prompt:
  "Security Alerts:
   - axios vulnerable in >= 0.8.1 < 0.21.4, fix: 0.21.4, CVE-2021-3749
   - lodash vulnerable in < 4.17.21, fix: 4.17.21, CVE-2021-23337"
  ↓
Claude sees security context → upgrades to exact versions
  ↓
Commit includes CVE numbers automatically
```

**Example:**

**Vague command:**

```bash
/update package.json
upgrade dependencies to fix security issues
```

**Without enhancement:** Bot guesses versions (~85% confidence)

**With enhancement:** Bot knows exact CVEs and versions (~96% confidence)

**Commit:**

```text
🤖 Update package.json: upgrade axios to 0.21.4 (CVE-2021-3749), lodash to 4.17.21 (CVE-2021-23337) to fix security vulnerabilities (96%)
```

**Benefits:**

- ✅ Bot automatically knows about security issues
- ✅ Works with ANY `/update` command
- ✅ Higher confidence scores
- ✅ Specific CVE mentions in commits
- ✅ No extra workflows needed

**When to use:** You want maximum automation and intelligence

---

### **Real-World Examples**

#### **Example 1: Node.js Security Update**

**Dependabot Alert:**

```text
⚠️ High severity vulnerability in lodash
Prototype Pollution in lodash
CVE-2021-23337
Affected: < 4.17.21
```

**With Option 1 (Auto-Comment):**

```text
1. Dependabot creates PR
2. Workflow auto-posts: "/update package.json upgrade lodash to 4.17.21 to fix CVE-2021-23337"
3. Bot commits in 2 minutes
4. Merge PR
```

**Time saved:** 25 minutes

---

#### **Example 2: Multiple Alerts Weekly**

**Scenario:** 15 Dependabot alerts across package.json, requirements.txt, Gemfile

**With Option 2 (Weekly Scan):**

```text
1. Monday 9 AM: Workflow creates consolidated PR
2. You see: "Fix 15 alerts" with all /update commands ready
3. Copy/paste 3 commands (one per file)
4. Bot fixes all
5. Merge one PR
```

**Before:** 15 PRs × 5 minutes = 75 minutes  
**After:** 1 PR × 10 minutes = 10 minutes  
**Saved:** 65 minutes

---

#### **Example 3: Intelligent Upgrades**

**Command (vague):**

```bash
/update package.json
fix security vulnerabilities
```

**With Option 3 (Enhanced Worker):**

- Bot fetches alerts automatically
- Sees axios (CVE-2021-3749), lodash (CVE-2021-23337), minimist (CVE-2021-44906)
- Upgrades all to exact secure versions
- Includes all CVEs in commit message
- 96% confidence (vs 85% without context)

---

### **Cost Impact**

**Option 1:**

- 10 Dependabot PRs/month × $0.015 = **$0.15/month**

**Option 2:**

- 4 weekly scans × 3 files × $0.015 = **$0.18/month**

**Option 3:**

- Negligible (~$0.01/month)

**Total all options:** ~**$0.35/month** for automated security fixes 💰

---

### **Quick Start**

**Recommended approach:**

**Week 1: Deploy Option 1**

```bash
cp auto-dependabot-trigger.yml .github/workflows/
git commit -m "feat: Auto Dependabot fixes" && git push
```

**Week 2: Add Option 2**

```bash
cp weekly-security-scan.yml .github/workflows/
git commit -m "feat: Weekly security scan" && git push
```

**Week 3: Consider Option 3** (if you want maximum intelligence)

**Result:** Complete automation with instant response + weekly overview + intelligent context! 🎉

## ⚠️ Known Limitations

### **What Works Well:**

- ✅ Copying existing patterns
- ✅ Adding similar resources
- ✅ Updating configuration values
- ✅ Adding standard error handling
- ✅ Following established conventions

### **What Needs Manual Review:**

- ⚠️ Business logic changes
- ⚠️ Complex algorithms
- ⚠️ Performance optimizations
- ⚠️ Breaking changes to APIs
- ⚠️ Security-critical code

### **What Doesn't Work:**

- ❌ Inventing new patterns (needs existing example)
- ❌ Understanding organizational policies (document them in code)
- ❌ Making judgment calls on trade-offs (use confidence score)

---

## 💡 Pro Tips

1. **Build a Pattern Library:** Keep exemplar files that demonstrate best practices
2. **Use Descriptive Names:** File names and variable names help the bot understand context
3. **Document Patterns:** Comments explaining "why" help bot make better decisions
4. **Start Small:** Test on simple changes before complex refactoring
5. **Review Carefully:** Bot is a tool, not a replacement for code review
6. **Iterate:** Use bot output as starting point, refine as needed

---

## 📈 Success Metrics

Based on real usage:

- **90%+ success rate** for infrastructure additions
- **85%+ success rate** for configuration updates
- **80%+ success rate** for code refactoring
- **95%+ success rate** for Dependabot security fixes
- **Average time saved:** 30-60 minutes per change
- **Security fixes:** 25 minutes → 2 minutes (with automation)
- **Average cost:** $0.015 per update

---

**Questions?** See [README.md](README.md) or ask in #rag-code-bot