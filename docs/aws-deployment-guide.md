# AWS Deployment Guide — Módulo 9: Monitoreo de Pacientes

## Architecture Decision: ECS Fargate vs Lambda

### Why NOT Lambda for M9

Lambda seems appealing (no server management, pay-per-invocation), but M9 has characteristics that make it a poor fit:

| Concern | Lambda Limitation | M9 Requirement |
|---------|-------------------|----------------|
| **WebSocket** | Lambda cannot hold persistent connections. API Gateway WebSocket API exists but adds significant complexity and cost for high-frequency telemetry updates. | Nursing dashboard needs real-time push via WebSocket/SSE. |
| **Cold starts** | Lambda cold starts (0.5–2s for Python) are unacceptable for a patient monitoring system where alerts must fire in near real-time. | Rule engine must evaluate telemetry immediately on arrival. |
| **Execution time** | 15-minute max timeout. | SQS consumer needs to poll continuously. |
| **Concurrency** | Each invocation is isolated — no shared in-memory state across requests. | FastAPI app holds connection state, WebSocket clients, and in-memory rule evaluation context. |

### Recommended: ECS Fargate (Primary) + Lambda (Event Handlers)

Use **ECS Fargate** for the main FastAPI application and optionally **Lambda** for isolated event-driven tasks.

| Component | Compute | Reason |
|-----------|---------|--------|
| FastAPI API + WebSocket | **ECS Fargate** | Long-running, persistent connections, low latency |
| SQS telemetry consumer | **ECS Fargate** (background task) | Continuous polling, shares process with rule engine |
| SNS → SQS dead-letter reprocessing | **Lambda** (optional) | Infrequent, event-driven, stateless |

---

## Target Architecture

```
                    ┌─────────────────┐
                    │   Route 53      │
                    │  (DNS)          │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  ALB            │
                    │  (Application   │
                    │   Load Balancer)│
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  ECS Fargate    │
                    │  ┌────────────┐ │
                    │  │ FastAPI    │ │──── POST /telemetry
                    │  │ + Uvicorn  │ │──── GET  /patients
                    │  │ + WS       │ │──── GET  /alerts
                    │  │ + SQS Poll │ │──── WS   /ws/monitoring
                    │  └─────┬──────┘ │
                    └────────┼────────┘
                             │
               ┌─────────────┼─────────────┐
               │             │             │
      ┌────────▼───┐  ┌─────▼──────┐  ┌───▼──────────┐
      │ RDS        │  │ SNS Topic  │  │ SQS Queue    │
      │ PostgreSQL │  │ monitoring │  │ telemetry-in │
      └────────────┘  │ -events    │  └──────────────┘
                      └─────┬──────┘
                            │
                  ┌─────────┼─────────┐
                  │                   │
          ┌───────▼──────┐  ┌────────▼─────┐
          │ SQS Queue    │  │ SQS Queue    │
          │ m6-sub       │  │ m8-sub       │
          │ (Internación)│  │ (Portal)     │
          └──────────────┘  └──────────────┘
```

---

## Step-by-Step Deployment

### Step 1: Containerize the Application

Create a `Dockerfile` in the `app/` directory:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Copy data files
COPY data/ data/

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run with uvicorn
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

Build and test locally:

```bash
docker build -t m9-monitoring ./app
docker run -p 8000:8000 m9-monitoring
```

### Step 2: Push Image to ECR

```bash
# Create ECR repository
aws ecr create-repository --repository-name health-grid/m9-monitoring

# Authenticate Docker with ECR
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag m9-monitoring:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/health-grid/m9-monitoring:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/health-grid/m9-monitoring:latest
```

### Step 3: Create the Database (RDS PostgreSQL)

```bash
aws rds create-db-instance \
    --db-instance-identifier m9-monitoring-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version 16.4 \
    --master-username m9admin \
    --master-user-password <SECURE_PASSWORD> \
    --allocated-storage 20 \
    --vpc-security-group-ids <SG_ID> \
    --db-subnet-group-name <SUBNET_GROUP> \
    --no-publicly-accessible \
    --storage-encrypted
```

Store credentials in Secrets Manager:

```bash
aws secretsmanager create-secret \
    --name health-grid/m9/db-credentials \
    --secret-string '{"username":"m9admin","password":"<SECURE_PASSWORD>","host":"<RDS_ENDPOINT>","port":"5432","dbname":"m9monitoring"}'
```

### Step 4: Create SNS Topics and SQS Queues

```bash
# SNS topic for emergency events
aws sns create-topic --name monitoring-events
# Save the TopicArn from the output

# SQS queues for subscribers
aws sqs create-queue --queue-name m6-monitoring-sub \
    --attributes '{"MessageRetentionPeriod":"86400","VisibilityTimeout":"60"}'

aws sqs create-queue --queue-name m8-monitoring-sub \
    --attributes '{"MessageRetentionPeriod":"86400","VisibilityTimeout":"60"}'

# Dead-letter queues
aws sqs create-queue --queue-name m6-monitoring-sub-dlq
aws sqs create-queue --queue-name m8-monitoring-sub-dlq

# Subscribe SQS queues to SNS topic
aws sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:<ACCOUNT_ID>:monitoring-events \
    --protocol sqs \
    --notification-endpoint arn:aws:sqs:us-east-1:<ACCOUNT_ID>:m6-monitoring-sub

aws sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:<ACCOUNT_ID>:monitoring-events \
    --protocol sqs \
    --notification-endpoint arn:aws:sqs:us-east-1:<ACCOUNT_ID>:m8-monitoring-sub

# Optional: telemetry ingestion queue (if devices publish to SQS instead of REST)
aws sqs create-queue --queue-name m9-telemetry-ingest \
    --attributes '{"MessageRetentionPeriod":"3600","VisibilityTimeout":"30"}'
```

### Step 5: Create the ECS Cluster and Task Definition

```bash
# Create cluster
aws ecs create-cluster --cluster-name health-grid --capacity-providers FARGATE

# Register task definition (see JSON below)
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

**task-definition.json:**

```json
{
  "family": "m9-monitoring",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/m9-monitoring-task-role",
  "containerDefinitions": [
    {
      "name": "m9-monitoring",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/health-grid/m9-monitoring:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        { "name": "APP_ENV", "value": "production" },
        { "name": "SNS_TOPIC_ARN", "value": "arn:aws:sns:us-east-1:<ACCOUNT_ID>:monitoring-events" },
        { "name": "SQS_TELEMETRY_QUEUE_URL", "value": "https://sqs.us-east-1.amazonaws.com/<ACCOUNT_ID>/m9-telemetry-ingest" },
        { "name": "AWS_DEFAULT_REGION", "value": "us-east-1" }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:health-grid/m9/db-credentials"
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\""],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/m9-monitoring",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "m9"
        }
      }
    }
  ]
}
```

### Step 6: Create the Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
    --name m9-monitoring-alb \
    --subnets <SUBNET_1> <SUBNET_2> \
    --security-groups <ALB_SG_ID> \
    --scheme internet-facing \
    --type application

# Create target group (supports HTTP and WebSocket)
aws elbv2 create-target-group \
    --name m9-monitoring-tg \
    --protocol HTTP \
    --port 8000 \
    --vpc-id <VPC_ID> \
    --target-type ip \
    --health-check-path /health \
    --health-check-interval-seconds 30 \
    --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2

# Create listener (HTTPS — requires ACM certificate)
aws elbv2 create-listener \
    --load-balancer-arn <ALB_ARN> \
    --protocol HTTPS \
    --port 443 \
    --certificates CertificateArn=<ACM_CERT_ARN> \
    --default-actions Type=forward,TargetGroupArn=<TG_ARN>
```

> **Note:** ALB natively supports WebSocket connections. No special configuration needed — WebSocket upgrades pass through automatically.

### Step 7: Create the ECS Service

```bash
aws ecs create-service \
    --cluster health-grid \
    --service-name m9-monitoring \
    --task-definition m9-monitoring \
    --desired-count 2 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[<SUBNET_1>,<SUBNET_2>],securityGroups=[<SG_ID>],assignPublicIp=DISABLED}" \
    --load-balancers "targetGroupArn=<TG_ARN>,containerName=m9-monitoring,containerPort=8000" \
    --health-check-grace-period-seconds 60
```

### Step 8: Configure Auto Scaling

```bash
# Register scalable target
aws application-autoscaling register-scalable-target \
    --service-namespace ecs \
    --scalable-dimension ecs:service:DesiredCount \
    --resource-id service/health-grid/m9-monitoring \
    --min-capacity 2 \
    --max-capacity 6

# Scale on CPU utilization
aws application-autoscaling put-scaling-policy \
    --service-namespace ecs \
    --scalable-dimension ecs:service:DesiredCount \
    --resource-id service/health-grid/m9-monitoring \
    --policy-name m9-cpu-scaling \
    --policy-type TargetTrackingScaling \
    --target-tracking-scaling-policy-configuration '{
        "TargetValue": 70.0,
        "PredefinedMetricSpecification": {
            "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
        },
        "ScaleInCooldown": 300,
        "ScaleOutCooldown": 60
    }'
```

---

## IAM Roles

### ECS Task Role (`m9-monitoring-task-role`)

The application container needs permissions to interact with AWS services:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SNSPublish",
      "Effect": "Allow",
      "Action": "sns:Publish",
      "Resource": "arn:aws:sns:us-east-1:<ACCOUNT_ID>:monitoring-events"
    },
    {
      "Sid": "SQSConsume",
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:us-east-1:<ACCOUNT_ID>:m9-telemetry-ingest"
    },
    {
      "Sid": "SecretsRead",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:health-grid/m9/*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:<ACCOUNT_ID>:log-group:/ecs/m9-monitoring:*"
    }
  ]
}
```

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_ENV` | Environment name | `production` |
| `DATABASE_URL` | PostgreSQL connection string (from Secrets Manager) | `postgresql+asyncpg://user:pass@host:5432/m9monitoring` |
| `SNS_TOPIC_ARN` | ARN for the monitoring-events SNS topic | `arn:aws:sns:us-east-1:123456:monitoring-events` |
| `SQS_TELEMETRY_QUEUE_URL` | URL for telemetry ingestion queue | `https://sqs.us-east-1.amazonaws.com/123456/m9-telemetry-ingest` |
| `AWS_DEFAULT_REGION` | AWS region | `us-east-1` |
| `ALLOWED_ORIGINS` | CORS origins for WebSocket/dashboard | `https://dashboard.healthgrid.com` |
| `JWT_PUBLIC_KEY_URL` | M10 Core JWKS endpoint for token validation | `https://core.healthgrid.com/.well-known/jwks.json` |

---

## Security Checklist

- [ ] RDS is in a private subnet, not publicly accessible
- [ ] ECS tasks run in private subnets, only ALB is internet-facing
- [ ] All traffic is HTTPS (ACM certificate on ALB)
- [ ] Security groups: ALB allows 443 inbound; ECS allows 8000 only from ALB SG; RDS allows 5432 only from ECS SG
- [ ] Secrets stored in AWS Secrets Manager, not environment variables
- [ ] Task role follows least-privilege principle
- [ ] CloudWatch alarms configured for error rates and latency

---

## CI/CD Pipeline (GitHub Actions)

A basic pipeline to build, push, and deploy on every push to `main`:

```yaml
# .github/workflows/deploy.yml
name: Deploy M9 to ECS

on:
  push:
    branches: [main]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: health-grid/m9-monitoring
  ECS_CLUSTER: health-grid
  ECS_SERVICE: m9-monitoring

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::<ACCOUNT_ID>:role/github-actions-deploy
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: ecr-login
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, tag, and push image
        env:
          ECR_REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG ./app
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster $ECS_CLUSTER \
            --service $ECS_SERVICE \
            --force-new-deployment
```

---

## Estimated Costs (us-east-1, minimal setup)

| Service | Configuration | Monthly Estimate |
|---------|--------------|-----------------|
| ECS Fargate | 2 tasks × 0.5 vCPU / 1 GB | ~$30 |
| RDS PostgreSQL | db.t3.micro, 20 GB | ~$15 |
| ALB | 1 ALB + LCU hours | ~$20 |
| SNS | < 1M publishes | ~$0.50 |
| SQS | < 1M requests | ~$0.40 |
| CloudWatch Logs | 5 GB ingestion | ~$2.50 |
| ECR | < 1 GB storage | ~$0.10 |
| **Total** | | **~$70/month** |

> These are estimates for a development/staging environment. Production with higher availability (multi-AZ RDS, more Fargate tasks) would be higher.

---

## Local Development with LocalStack

For local development without an AWS account, use [LocalStack](https://localstack.cloud) to emulate SNS, SQS, and other services:

```yaml
# docker-compose.yml
services:
  app:
    build: ./app
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/m9monitoring
      - AWS_ENDPOINT_URL=http://localstack:4566
      - SNS_TOPIC_ARN=arn:aws:sns:us-east-1:000000000000:monitoring-events
      - SQS_TELEMETRY_QUEUE_URL=http://localstack:4566/000000000000/m9-telemetry-ingest
      - AWS_DEFAULT_REGION=us-east-1
      - AWS_ACCESS_KEY_ID=test
      - AWS_SECRET_ACCESS_KEY=test
    depends_on:
      db:
        condition: service_healthy
      localstack:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: m9monitoring
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    environment:
      - SERVICES=sns,sqs
      - DEFAULT_REGION=us-east-1
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:4566/_localstack/health"]
      interval: 5s
      timeout: 3s
      retries: 5
```

Initialize LocalStack resources with a startup script:

```bash
# scripts/init-localstack.sh
#!/bin/bash
awslocal sns create-topic --name monitoring-events
awslocal sqs create-queue --queue-name m9-telemetry-ingest
awslocal sqs create-queue --queue-name m6-monitoring-sub
awslocal sqs create-queue --queue-name m8-monitoring-sub
awslocal sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:000000000000:monitoring-events \
    --protocol sqs \
    --notification-endpoint arn:aws:sqs:us-east-1:000000000000:m6-monitoring-sub
awslocal sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:000000000000:monitoring-events \
    --protocol sqs \
    --notification-endpoint arn:aws:sqs:us-east-1:000000000000:m8-monitoring-sub
echo "LocalStack resources initialized."
```
