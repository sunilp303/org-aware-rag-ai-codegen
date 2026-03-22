# AWS-Native RAG + Agentic Architecture
# API Key Authentication (No IAM Users Required)
# Cost: ~$54-75/month for 5 repos

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      team        = "sunilp@example.com"
      environment = "development"
      terraform   = "true"
      application = "github-rag-action"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "rag-code-bot"
}

variable "github_repos" {
  type    = list(string)
  default = []
}

variable "db_master_username" {
  type    = string
  default = "postgres"
}

variable "db_master_password" {
  type      = string
  sensitive = true
}

variable "vpc_id" {
  type        = string
  description = "ID of the existing VPC to deploy resources into"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "List of at least 2 private subnet IDs in different AZs for Aurora and Lambda"

  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "At least 2 private subnet IDs must be provided (Aurora requires multi-AZ subnet group)."
  }
}

locals {
  common_tags = {
    Project    = var.project_name
    ManagedBy  = "Terraform"
    CostCenter = "CloudSec"
  }
}

data "aws_caller_identity" "current" {}

data "aws_vpc" "selected" {
  id = var.vpc_id
}

#######################
# Generate API Key
#######################

resource "random_password" "api_key" {
  length  = 32
  special = false
}

#######################
# Security Groups
#######################

resource "aws_security_group" "aurora" {
  name        = "${var.project_name}-aurora-sg"
  description = "Security group for Aurora PostgreSQL"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.selected.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_security_group" "lambda" {
  name        = "${var.project_name}-lambda-sg"
  description = "Security group for Lambda functions"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

#######################
# Aurora PostgreSQL Serverless v2 with pgvector
#######################

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet"
  subnet_ids = var.private_subnet_ids

  tags = local.common_tags
}

resource "aws_rds_cluster" "vector_db" {
  cluster_identifier = "${var.project_name}-vector-db"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = "17.4"
  database_name      = "vectordb"
  master_username    = var.db_master_username
  master_password    = var.db_master_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.aurora.id]

  serverlessv2_scaling_configuration {
    max_capacity = 1.0
    min_capacity = 0.5
  }

  backup_retention_period = 7
  preferred_backup_window = "03:00-04:00"

  skip_final_snapshot = true

  enable_http_endpoint = true

  tags = local.common_tags
}

resource "aws_rds_cluster_instance" "vector_db" {
  identifier         = "${var.project_name}-instance-1"
  cluster_identifier = aws_rds_cluster.vector_db.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.vector_db.engine
  engine_version     = aws_rds_cluster.vector_db.engine_version

  tags = local.common_tags
}

#######################
# Secrets Manager
#######################

resource "aws_secretsmanager_secret" "github_token" {
  name                    = "${var.project_name}/github-token"
  recovery_window_in_days = 7

  tags = local.common_tags

  lifecycle {
    ignore_changes = all
  }
}

resource "aws_secretsmanager_secret" "aurora_credentials" {
  name                    = "${var.project_name}/aurora-credential-rag"
  recovery_window_in_days = 7

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "aurora_credentials" {
  secret_id = aws_secretsmanager_secret.aurora_credentials.id
  secret_string = jsonencode({
    host     = aws_rds_cluster.vector_db.endpoint
    port     = 5432
    database = aws_rds_cluster.vector_db.database_name
    username = aws_rds_cluster.vector_db.master_username
    password = var.db_master_password
  })
}

resource "aws_secretsmanager_secret" "api_key" {
  name                    = "${var.project_name}/api-key"
  recovery_window_in_days = 7

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "api_key" {
  secret_id     = aws_secretsmanager_secret.api_key.id
  secret_string = random_password.api_key.result
}

#######################
# DynamoDB for State
#######################

resource "aws_dynamodb_table" "index_state" {
  name         = "${var.project_name}-index-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "repo"
  range_key    = "file_path"

  attribute {
    name = "repo"
    type = "S"
  }

  attribute {
    name = "file_path"
    type = "S"
  }

  ttl {
    enabled        = true
    attribute_name = "expires_at"
  }

  tags = local.common_tags
}

#######################
# IAM Roles
#######################

resource "aws_iam_role" "lambda_execution" {
  name = "${var.project_name}-lambda-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "lambda_custom" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          aws_secretsmanager_secret.github_token.arn,
          aws_secretsmanager_secret.aurora_credentials.arn,
          aws_secretsmanager_secret.api_key.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query"
        ]
        Resource = aws_dynamodb_table.index_state.arn
      },
      {
        Effect   = "Allow"
        Action   = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
          "arn:aws:bedrock:*::foundation-model/amazon.titan-*",
          "arn:aws:bedrock:us-east-1:*:inference-profile/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = [
          "bedrock:ListFoundationModels",
          "bedrock:GetFoundationModel",
          "bedrock:ListInferenceProfiles",
          "bedrock:GetInferenceProfile"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "rds-data:ExecuteStatement",
          "rds-data:BatchExecuteStatement"
        ]
        Resource = aws_rds_cluster.vector_db.arn
      }
    ]
  })
}

#######################
# Lambda Layer for Dependencies
#######################

resource "aws_lambda_layer_version" "dependencies" {
  filename            = "lambda_layers/dependencies.zip"
  source_code_hash    = filebase64sha256("lambda_layers/dependencies.zip")
  layer_name          = "${var.project_name}-dependencies"
  compatible_runtimes = ["python3.11"]

  description = "psycopg2, requests, and other dependencies"
}

#######################
# Lambda Functions
#######################

resource "aws_lambda_function" "code_indexer" {
  filename         = "lambda_packages/code_indexer_aws.zip"
  source_code_hash = filebase64sha256("lambda_packages/code_indexer_aws.zip")
  function_name    = "${var.project_name}-code-indexer"
  role             = aws_iam_role.lambda_execution.arn
  handler          = "code_indexer_aws.lambda_handler"
  runtime          = "python3.11"
  timeout          = 900
  memory_size      = 1024

  layers = [aws_lambda_layer_version.dependencies.arn]

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.index_state.name
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "agentic_workflow" {
  filename         = "lambda_packages/agentic_workflow_aws.zip"
  source_code_hash = filebase64sha256("lambda_packages/agentic_workflow_aws.zip")
  function_name    = "${var.project_name}-agentic-workflow"
  role             = aws_iam_role.lambda_execution.arn
  handler          = "agentic_workflow_aws.lambda_handler"
  runtime          = "python3.11"
  timeout          = 900
  memory_size      = 1024

  layers = [aws_lambda_layer_version.dependencies.arn]

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      API_KEY_SECRET = aws_secretsmanager_secret.api_key.name
    }
  }

  tags = local.common_tags
}

#######################
# API Gateway with API Key Authentication
#######################

resource "aws_api_gateway_rest_api" "api" {
  name        = "${var.project_name}-api"
  description = "RAG Code Bot API with API Key authentication"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = local.common_tags
}

# /api
resource "aws_api_gateway_resource" "api" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "api"
}

# /api/v1
resource "aws_api_gateway_resource" "v1" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.api.id
  path_part   = "v1"
}

# /api/v1/code-update
resource "aws_api_gateway_resource" "code_update" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "code-update"
}

# POST Method with API Key Required
resource "aws_api_gateway_method" "code_update_post" {
  rest_api_id      = aws_api_gateway_rest_api.api.id
  resource_id      = aws_api_gateway_resource.code_update.id
  http_method      = "POST"
  authorization    = "NONE"
  api_key_required = true  # Require API key
}

# Lambda Integration
resource "aws_api_gateway_integration" "lambda" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.code_update.id
  http_method = aws_api_gateway_method.code_update_post.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.agentic_workflow.invoke_arn
}

# CORS - OPTIONS Method
resource "aws_api_gateway_method" "code_update_options" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.code_update.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "code_update_options" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.code_update.id
  http_method = aws_api_gateway_method.code_update_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "code_update_options" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.code_update.id
  http_method = aws_api_gateway_method.code_update_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "code_update_options" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.code_update.id
  http_method = aws_api_gateway_method.code_update_options.http_method
  status_code = aws_api_gateway_method_response.code_update_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# API Deployment
resource "aws_api_gateway_deployment" "prod" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.code_update.id,
      aws_api_gateway_method.code_update_post.id,
      aws_api_gateway_integration.lambda.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.lambda,
    aws_api_gateway_integration.code_update_options
  ]
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.prod.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = "prod"

  tags = local.common_tags
}

# API Key
resource "aws_api_gateway_api_key" "code_bot" {
  name    = "${var.project_name}-api-key"
  enabled = true
  value   = random_password.api_key.result

  tags = local.common_tags
}

# Usage Plan
resource "aws_api_gateway_usage_plan" "code_bot" {
  name = "${var.project_name}-usage-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.api.id
    stage  = aws_api_gateway_stage.prod.stage_name
  }

  quota_settings {
    limit  = 10000
    period = "MONTH"
  }

  throttle_settings {
    burst_limit = 100
    rate_limit  = 50
  }

  tags = local.common_tags
}

# Associate API Key with Usage Plan
resource "aws_api_gateway_usage_plan_key" "code_bot" {
  key_id        = aws_api_gateway_api_key.code_bot.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.code_bot.id
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.agentic_workflow.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

#######################
# EventBridge for Scheduled Indexing
#######################

resource "aws_cloudwatch_event_rule" "daily_index" {
  name                = "${var.project_name}-daily-index"
  schedule_expression = "cron(0 2 * * ? *)"

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "indexer" {
  rule      = aws_cloudwatch_event_rule.daily_index.name
  target_id = "CodeIndexer"
  arn       = aws_lambda_function.code_indexer.arn

  input = jsonencode({
    repositories = var.github_repos
  })
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.code_indexer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_index.arn
}

#######################
# CloudWatch Logs
#######################

resource "aws_cloudwatch_log_group" "indexer_logs" {
  name              = "/aws/lambda/${aws_lambda_function.code_indexer.function_name}"
  retention_in_days = 7

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "workflow_logs" {
  name              = "/aws/lambda/${aws_lambda_function.agentic_workflow.function_name}"
  retention_in_days = 7

  tags = local.common_tags
}

#######################
# Cost Monitoring Alarm
#######################

resource "aws_cloudwatch_metric_alarm" "high_usage" {
  alarm_name          = "${var.project_name}-high-lambda-usage"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Invocations"
  namespace           = "AWS/Lambda"
  period              = "86400"
  statistic           = "Sum"
  threshold           = "5000"
  alarm_description   = "Alert on unusually high Lambda usage"

  dimensions = {
    FunctionName = aws_lambda_function.agentic_workflow.function_name
  }

  tags = local.common_tags
}

#######################
# Outputs
#######################

output "api_endpoint" {
  value       = "https://${aws_api_gateway_rest_api.api.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.prod.stage_name}"
  description = "API Gateway endpoint URL"
}

output "api_key" {
  value       = random_password.api_key.result
  sensitive   = true
  description = "API Key for authentication (add to GitHub Secrets as MODEL_API_KEY)"
}

output "aurora_endpoint" {
  value = aws_rds_cluster.vector_db.endpoint
}

output "indexer_function_name" {
  value = aws_lambda_function.code_indexer.function_name
}

output "workflow_function_name" {
  value = aws_lambda_function.agentic_workflow.function_name
}

output "setup_instructions" {
  value = <<-EOT
    
    ═══════════════════════════════════════════════════════════
    GitHub Secrets Configuration
    ═══════════════════════════════════════════════════════════
    
    Add these secrets to your GitHub repositories:
    
    1. MODEL_API_ENDPOINT
       Value: https://${aws_api_gateway_rest_api.api.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.prod.stage_name}/api/v1/code-update
    
    2. MODEL_API_KEY
       Value: (Run: terraform output -raw api_key)
    
    That's it! No AWS credentials needed. ✅
    
    ═══════════════════════════════════════════════════════════
    Testing the API
    ═══════════════════════════════════════════════════════════
    
    curl -X POST https://${aws_api_gateway_rest_api.api.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.prod.stage_name}/api/v1/code-update \
      -H "x-api-key: YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"comment":"test","code":"print(1)","file_path":"test.py","language":"python","repo":"test/repo"}'
    
  EOT
}

output "cost_estimate" {
  value = <<-EOT
    Estimated Monthly Cost (5 repos):
    
    Aurora Serverless v2 (0.5-1 ACU):  ~$18/month
    Bedrock Titan embeddings:          ~$1/month
    Bedrock Claude 3.5:                ~$35/month
    Lambda (100k invocations):         ~$0.20/month
    DynamoDB (on-demand):              ~$5/month
    API Gateway:                       ~$0.10/month
    
    Total: $59-60/month
    
    ✅ No IAM users required
    ✅ Single AWS bill
    ✅ Simple API key authentication
  EOT
}


################ ASYNC ################

# ============================================================================
# COPY THIS TO THE END OF YOUR terraform/main.tf FILE
# ============================================================================

#-----------------------------------------------------------------------------
# SQS QUEUE FOR ASYNC PROCESSING
#-----------------------------------------------------------------------------

resource "aws_sqs_queue" "code_bot_queue" {
  name                       = "${var.project_name}-code-bot-queue"
  visibility_timeout_seconds = 900
  message_retention_seconds  = 86400
  receive_wait_time_seconds  = 20
  
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.code_bot_dlq.arn
    maxReceiveCount     = 3
  })
  
  tags = local.common_tags
}

resource "aws_sqs_queue" "code_bot_dlq" {
  name                      = "${var.project_name}-code-bot-dlq"
  message_retention_seconds = 1209600
  tags = local.common_tags
}

#-----------------------------------------------------------------------------
# SUBMIT LAMBDA
#-----------------------------------------------------------------------------

resource "aws_lambda_function" "submit_job" {
  filename         = "lambda_packages/submit_job.zip"
  source_code_hash = filebase64sha256("lambda_packages/submit_job.zip")
  function_name    = "${var.project_name}-submit-job"
  role             = aws_iam_role.submit_lambda.arn
  handler          = "submit_job.lambda_handler"
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 512
  
  environment {
    variables = {
      QUEUE_URL  = aws_sqs_queue.code_bot_queue.url
      TABLE_NAME = aws_dynamodb_table.index_state.name
    }
  }
  
  tags = local.common_tags
}

resource "aws_iam_role" "submit_lambda" {
  name = "${var.project_name}-submit-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy" "submit_lambda" {
  name = "${var.project_name}-submit-lambda-policy"
  role = aws_iam_role.submit_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.code_bot_queue.arn
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = aws_dynamodb_table.index_state.arn
      }
    ]
  })
}

#-----------------------------------------------------------------------------
# WORKER LAMBDA
#-----------------------------------------------------------------------------

resource "aws_lambda_function" "worker" {
  filename         = "lambda_packages/worker.zip"
  source_code_hash = filebase64sha256("lambda_packages/worker.zip")
  function_name    = "${var.project_name}-worker"
  role             = aws_iam_role.worker_lambda.arn
  handler          = "worker.lambda_handler"
  runtime          = "python3.11"
  timeout          = 900
  memory_size      = 3008
  
  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }
  
  environment {
    variables = {
      TABLE_NAME    = aws_dynamodb_table.index_state.name
      CLAUDE_MODEL  = "us.anthropic.claude-opus-4-5-20251101-v1:0"
    }
  }
  
  layers = [aws_lambda_layer_version.dependencies.arn]
  tags = local.common_tags
}

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.code_bot_queue.arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 1
  enabled          = true
}

resource "aws_iam_role" "worker_lambda" {
  name = "${var.project_name}-worker-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy" "worker_lambda" {
  name = "${var.project_name}-worker-lambda-policy"
  role = aws_iam_role.worker_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DeleteNetworkInterface"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.code_bot_queue.arn
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:UpdateItem", "dynamodb:GetItem", "dynamodb:PutItem"]
        Resource = aws_dynamodb_table.index_state.arn
      },
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:rag-code-bot/*"
      }
    ]
  })
}

#-----------------------------------------------------------------------------
# STATUS LAMBDA
#-----------------------------------------------------------------------------

resource "aws_lambda_function" "get_status" {
  filename         = "lambda_packages/get_status.zip"
  source_code_hash = filebase64sha256("lambda_packages/get_status.zip")
  function_name    = "${var.project_name}-get-status"
  role             = aws_iam_role.status_lambda.arn
  handler          = "get_status.lambda_handler"
  runtime          = "python3.11"
  timeout          = 10
  memory_size      = 256
  
  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.index_state.name
    }
  }
  
  tags = local.common_tags
}

resource "aws_iam_role" "status_lambda" {
  name = "${var.project_name}-status-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy" "status_lambda" {
  name = "${var.project_name}-status-lambda-policy"
  role = aws_iam_role.status_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem"]
        Resource = aws_dynamodb_table.index_state.arn
      }
    ]
  })
}

#-----------------------------------------------------------------------------
# API GATEWAY ROUTES
#-----------------------------------------------------------------------------

resource "aws_api_gateway_resource" "submit" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "submit"
}

resource "aws_api_gateway_method" "submit_post" {
  rest_api_id      = aws_api_gateway_rest_api.api.id
  resource_id      = aws_api_gateway_resource.submit.id
  http_method      = "POST"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "submit_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.submit.id
  http_method             = aws_api_gateway_method.submit_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.submit_job.invoke_arn
}

resource "aws_lambda_permission" "submit_api_gateway" {
  statement_id  = "AllowAPIGatewayInvokeSubmit"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.submit_job.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

resource "aws_api_gateway_resource" "status" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "status"
}

resource "aws_api_gateway_resource" "status_id" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.status.id
  path_part   = "{id}"
}

resource "aws_api_gateway_method" "status_get" {
  rest_api_id      = aws_api_gateway_rest_api.api.id
  resource_id      = aws_api_gateway_resource.status_id.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "status_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.status_id.id
  http_method             = aws_api_gateway_method.status_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.get_status.invoke_arn
}

resource "aws_lambda_permission" "status_api_gateway" {
  statement_id  = "AllowAPIGatewayInvokeStatus"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.get_status.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

#-----------------------------------------------------------------------------
# OUTPUTS
#-----------------------------------------------------------------------------

output "submit_endpoint" {
  value = "https://${aws_api_gateway_rest_api.api.id}.execute-api.${var.aws_region}.amazonaws.com/prod/submit"
}

output "status_endpoint_template" {
  value = "https://${aws_api_gateway_rest_api.api.id}.execute-api.${var.aws_region}.amazonaws.com/prod/status/{id}"
}


# Force redeployment when routes change
resource "aws_api_gateway_deployment" "prod_async" {
  depends_on = [
    aws_api_gateway_integration.submit_lambda,
    aws_api_gateway_integration.status_lambda,
    aws_api_gateway_method.submit_post,
    aws_api_gateway_method.status_get
  ]

  rest_api_id = aws_api_gateway_rest_api.api.id
  stage_name  = "prod"

  lifecycle {
    create_before_destroy = true
  }

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.submit.id,
      aws_api_gateway_method.submit_post.id,
      aws_api_gateway_integration.submit_lambda.id,
      aws_api_gateway_resource.status.id,
      aws_api_gateway_method.status_get.id,
      aws_api_gateway_integration.status_lambda.id,
    ]))
  }
}