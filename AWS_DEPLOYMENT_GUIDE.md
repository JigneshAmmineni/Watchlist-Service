# AWS Deployment Guide for Movie Watchlist Microservices

## Current Architecture Summary

Your application consists of:
- **3 FastAPI microservices** (user, movie, watchlist)
- **3 PostgreSQL databases** (one per service)
- **1 Redis cache** (for movie service)
- **1 Nginx API Gateway** (routing + frontend serving)
- **1 Alpine.js/Tailwind frontend** (static files)

---

## Deployment Options (Easiest → Most Production-Ready)

### Option 1: EC2 with Docker Compose (Simplest - Good for Learning)
### Option 2: ECS with Fargate (Managed Containers - Recommended)
### Option 3: EKS with Kubernetes (Enterprise Scale - Complex)

---

## Option 1: EC2 with Docker Compose

**Best for**: Learning AWS, small projects, tight budgets

### Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                         AWS Cloud                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    VPC (10.0.0.0/16)                  │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │              Public Subnet                       │  │  │
│  │  │  ┌─────────────────────────────────────────┐    │  │  │
│  │  │  │           EC2 Instance (t3.medium)      │    │  │  │
│  │  │  │  ┌─────────────────────────────────┐    │    │  │  │
│  │  │  │  │      Docker Compose             │    │    │  │  │
│  │  │  │  │  ┌───────┐ ┌───────┐ ┌───────┐  │    │    │  │  │
│  │  │  │  │  │user-  │ │movie- │ │watch- │  │    │    │  │  │
│  │  │  │  │  │service│ │service│ │list   │  │    │    │  │  │
│  │  │  │  │  └───────┘ └───────┘ └───────┘  │    │    │  │  │
│  │  │  │  │  ┌───────┐ ┌───────┐ ┌───────┐  │    │    │  │  │
│  │  │  │  │  │user-db│ │movie- │ │watch- │  │    │    │  │  │
│  │  │  │  │  │       │ │db     │ │list-db│  │    │    │  │  │
│  │  │  │  │  └───────┘ └───────┘ └───────┘  │    │    │  │  │
│  │  │  │  │  ┌───────┐ ┌───────────────┐    │    │    │  │  │
│  │  │  │  │  │ Redis │ │ Nginx Gateway │    │    │    │  │  │
│  │  │  │  │  └───────┘ └───────────────┘    │    │    │  │  │
│  │  │  │  └─────────────────────────────────┘    │    │  │  │
│  │  │  └─────────────────────────────────────────┘    │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                              ↑                               │
│                    Elastic IP (static IP)                    │
└─────────────────────────────────────────────────────────────┘
```

### Steps to Deploy

1. **Create AWS Account & Set Up IAM**
   - Create an AWS account at aws.amazon.com
   - Create an IAM user with programmatic access
   - Install AWS CLI: `pip install awscli`
   - Configure: `aws configure`

2. **Launch EC2 Instance**
   ```bash
   # Create key pair
   aws ec2 create-key-pair --key-name movie-watchlist-key --query 'KeyMaterial' --output text > movie-watchlist-key.pem
   chmod 400 movie-watchlist-key.pem

   # Launch instance (Amazon Linux 2023)
   aws ec2 run-instances \
     --image-id ami-0c55b159cbfafe1f0 \
     --instance-type t3.medium \
     --key-name movie-watchlist-key \
     --security-group-ids sg-xxxxx \
     --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=movie-watchlist}]'
   ```

3. **Configure Security Group**
   - Inbound: SSH (22), HTTP (80), HTTPS (443), Custom (8080)
   - Outbound: All traffic

4. **SSH into Instance & Install Docker**
   ```bash
   ssh -i movie-watchlist-key.pem ec2-user@<public-ip>

   # Install Docker
   sudo yum update -y
   sudo yum install -y docker
   sudo systemctl start docker
   sudo usermod -aG docker ec2-user

   # Install Docker Compose
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

5. **Deploy Your Application**
   ```bash
   # Clone your repo
   git clone <your-repo-url>
   cd ClaudeCodeDemo

   # Start services
   docker-compose up -d --build
   ```

6. **Allocate Elastic IP** (optional but recommended)
   ```bash
   aws ec2 allocate-address --domain vpc
   aws ec2 associate-address --instance-id i-xxxxx --allocation-id eipalloc-xxxxx
   ```

**Estimated Monthly Cost**: ~$30-50/month (t3.medium)

---

## Option 2: ECS with Fargate (Recommended)

**Best for**: Production workloads, auto-scaling, managed infrastructure

### Architecture
```
┌────────────────────────────────────────────────────────────────────────────┐
│                              AWS Cloud                                      │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        VPC (10.0.0.0/16)                            │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                 Application Load Balancer                    │    │   │
│  │  │              (Routes /api/users, /api/movies, etc.)          │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                              │                                       │   │
│  │  ┌───────────────────────────┼───────────────────────────────────┐  │   │
│  │  │                   ECS Cluster (Fargate)                       │  │   │
│  │  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐   │  │   │
│  │  │  │ user-service │ │ movie-service│ │ watchlist-service    │   │  │   │
│  │  │  │ (2 tasks)    │ │ (2 tasks)    │ │ (2 tasks)            │   │  │   │
│  │  │  └──────────────┘ └──────────────┘ └──────────────────────┘   │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  │                              │                                       │   │
│  │  ┌───────────────────────────┼───────────────────────────────────┐  │   │
│  │  │                    Private Subnets                            │  │   │
│  │  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐   │  │   │
│  │  │  │   RDS        │ │    RDS       │ │       RDS            │   │  │   │
│  │  │  │  (user-db)   │ │  (movie-db)  │ │   (watchlist-db)     │   │  │   │
│  │  │  │  PostgreSQL  │ │  PostgreSQL  │ │   PostgreSQL         │   │  │   │
│  │  │  └──────────────┘ └──────────────┘ └──────────────────────┘   │  │   │
│  │  │                                                                │  │   │
│  │  │  ┌──────────────────────────────────────────────────────────┐  │  │   │
│  │  │  │                    ElastiCache (Redis)                   │  │  │   │
│  │  │  └──────────────────────────────────────────────────────────┘  │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    S3 + CloudFront (Frontend)                       │   │
│  │              Static website hosting with CDN                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         ECR (Container Registry)                    │   │
│  │        Stores Docker images for all 3 microservices                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

### AWS Services You'll Use

| Service | Purpose | Replaces |
|---------|---------|----------|
| **ECR** | Container image registry | Docker Hub |
| **ECS Fargate** | Serverless container orchestration | Docker Compose |
| **RDS PostgreSQL** | Managed databases | PostgreSQL containers |
| **ElastiCache** | Managed Redis | Redis container |
| **ALB** | Load balancer + routing | Nginx (routing) |
| **S3 + CloudFront** | Static frontend hosting | Nginx (static files) |
| **Route 53** | DNS management | - |
| **ACM** | SSL/TLS certificates | - |
| **Secrets Manager** | Database credentials | Environment variables |
| **CloudWatch** | Logging & monitoring | docker logs |

### Deployment Steps

#### Step 1: Set Up ECR Repositories
```bash
# Create repositories for each service
aws ecr create-repository --repository-name movie-watchlist/user-service
aws ecr create-repository --repository-name movie-watchlist/movie-service
aws ecr create-repository --repository-name movie-watchlist/watchlist-service

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push images
docker build -t movie-watchlist/user-service ./user-service
docker tag movie-watchlist/user-service:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/movie-watchlist/user-service:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/movie-watchlist/user-service:latest
# Repeat for other services...
```

#### Step 2: Create VPC & Networking
```bash
# Create VPC with public/private subnets
aws ec2 create-vpc --cidr-block 10.0.0.0/16
# Create subnets, internet gateway, NAT gateway, route tables...
# (Or use AWS Console VPC Wizard - much easier)
```

#### Step 3: Create RDS Databases
```bash
# Create PostgreSQL instances (one per service)
aws rds create-db-instance \
  --db-instance-identifier user-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username user \
  --master-user-password <secure-password> \
  --allocated-storage 20
# Repeat for movie-db and watchlist-db
```

#### Step 4: Create ElastiCache Redis
```bash
aws elasticache create-cache-cluster \
  --cache-cluster-id movie-cache \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --num-cache-nodes 1
```

#### Step 5: Create ECS Cluster & Task Definitions
```bash
# Create cluster
aws ecs create-cluster --cluster-name movie-watchlist

# Register task definitions (JSON files needed)
aws ecs register-task-definition --cli-input-json file://user-service-task.json
```

#### Step 6: Create Application Load Balancer
```bash
# Create ALB with path-based routing rules:
# /api/users/* → user-service target group
# /api/movies/* → movie-service target group
# /api/watchlist/* → watchlist-service target group
```

#### Step 7: Deploy Frontend to S3 + CloudFront
```bash
# Create S3 bucket
aws s3 mb s3://movie-watchlist-frontend

# Upload frontend files
aws s3 sync ./frontend s3://movie-watchlist-frontend

# Create CloudFront distribution pointing to S3
```

**Estimated Monthly Cost**: ~$100-200/month

---

## Option 3: EKS with Kubernetes (Enterprise)

**Best for**: Large teams, complex scaling requirements, multi-cloud strategy

This option uses Kubernetes for orchestration. Only recommended if you already know Kubernetes or plan to learn it for career purposes.

**Additional complexity**:
- Helm charts for deployment
- Ingress controllers
- Kubernetes secrets management
- Pod autoscaling

**Estimated Monthly Cost**: ~$200-500/month (EKS cluster + nodes)

---

## Technologies You Need to Learn

### Essential (All Options)
| Technology | What to Learn | Resources |
|------------|---------------|-----------|
| **AWS IAM** | Users, roles, policies | AWS IAM Documentation |
| **AWS VPC** | Subnets, security groups, routing | AWS VPC Workshop |
| **AWS CLI** | Command-line management | `aws help` |

### For Option 1 (EC2)
| Technology | What to Learn | Resources |
|------------|---------------|-----------|
| **EC2** | Instance types, AMIs, key pairs | AWS EC2 Documentation |
| **Elastic IP** | Static IP allocation | - |
| **SSH** | Remote server access | - |

### For Option 2 (ECS - Recommended)
| Technology | What to Learn | Resources |
|------------|---------------|-----------|
| **ECR** | Container registry, image pushing | AWS ECR Documentation |
| **ECS** | Task definitions, services, Fargate | AWS ECS Workshop |
| **RDS** | PostgreSQL setup, backups, security | AWS RDS Documentation |
| **ElastiCache** | Redis cluster configuration | AWS ElastiCache Docs |
| **ALB** | Target groups, path-based routing | - |
| **S3** | Static website hosting | AWS S3 Documentation |
| **CloudFront** | CDN configuration | - |
| **Route 53** | DNS and domain management | - |
| **ACM** | SSL certificate provisioning | - |
| **Secrets Manager** | Secure credential storage | - |
| **CloudWatch** | Logs, metrics, alarms | - |

### For Option 3 (EKS)
All of the above, plus:
| Technology | What to Learn | Resources |
|------------|---------------|-----------|
| **Kubernetes** | Pods, deployments, services | kubernetes.io |
| **Helm** | Package management | helm.sh |
| **kubectl** | Kubernetes CLI | - |

---

## Required Code Changes for Production

### 1. Externalize Configuration
Create environment-specific configs:
```python
# config.py
import os

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL")
MOVIE_SERVICE_URL = os.getenv("MOVIE_SERVICE_URL")
```

### 2. Update Frontend API Base URL
```javascript
// api.js - Change from localhost
const API_BASE = window.location.hostname === 'localhost'
  ? 'http://localhost:8080/api'
  : '/api';  // Same origin in production
```

### 3. Add Health Check Improvements
```python
# Add database connectivity check
@app.get("/health")
async def health():
    try:
        # Check database connection
        conn = get_db_connection()
        conn.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )
```

### 4. Production Dockerfile Improvements
```dockerfile
FROM python:3.11-slim

# Add non-root user for security
RUN useradd --create-home appuser
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

# Use gunicorn for production
CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

---

## Recommended Learning Path

### Week 1-2: AWS Fundamentals
1. Create AWS Free Tier account
2. Complete AWS Cloud Practitioner Essentials (free)
3. Learn IAM, VPC basics
4. Deploy Option 1 (EC2 + Docker Compose)

### Week 3-4: Container Services
1. Learn ECR (push your first image)
2. Understand ECS concepts (tasks, services, clusters)
3. Learn RDS PostgreSQL setup
4. Learn ElastiCache Redis setup

### Week 5-6: Production Deployment
1. Set up full ECS Fargate deployment
2. Configure ALB with path-based routing
3. Deploy frontend to S3 + CloudFront
4. Set up custom domain with Route 53
5. Add SSL with ACM

### Week 7-8: Operations
1. Set up CloudWatch logging and alarms
2. Learn Secrets Manager for credentials
3. Implement CI/CD with GitHub Actions + ECR/ECS
4. Learn cost optimization strategies

---

## CI/CD Pipeline (GitHub Actions - Complete Guide)

### Pipeline Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   GitHub    │───▶│   Build &   │───▶│   Push to   │───▶│  Deploy to  │
│   Push      │    │   Test      │    │   ECR       │    │  ECS        │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
    Trigger          Run tests          Tag images        Rolling update
    on main          Lint code          Push to ECR       Zero downtime
```

### Complete Workflow File

```yaml
# .github/workflows/deploy.yml
name: Build, Test, and Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  AWS_REGION: us-east-1
  ECR_REGISTRY: ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com
  ECS_CLUSTER: movie-watchlist

jobs:
  # ═══════════════════════════════════════════════════════════════
  # JOB 1: Test all services
  # ═══════════════════════════════════════════════════════════════
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [user-service, movie-service, watchlist-service]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        working-directory: ${{ matrix.service }}
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov flake8 bandit safety

      - name: Lint with flake8
        working-directory: ${{ matrix.service }}
        run: flake8 . --max-line-length=120

      - name: Security scan with bandit
        working-directory: ${{ matrix.service }}
        run: bandit -r . -ll  # Low severity and above

      - name: Check dependencies for vulnerabilities
        working-directory: ${{ matrix.service }}
        run: safety check -r requirements.txt

      - name: Run tests
        working-directory: ${{ matrix.service }}
        run: pytest --cov=. --cov-report=xml
        env:
          DATABASE_URL: sqlite:///test.db  # Use SQLite for tests

  # ═══════════════════════════════════════════════════════════════
  # JOB 2: Build and push Docker images
  # ═══════════════════════════════════════════════════════════════
  build:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [user-service, movie-service, watchlist-service]

    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        uses: aws-actions/amazon-ecr-login@v2

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.ECR_REGISTRY }}/movie-watchlist/${{ matrix.service }}
          tags: |
            type=sha,prefix=
            type=raw,value=latest

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: ./${{ matrix.service }}
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Scan image for vulnerabilities
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.ECR_REGISTRY }}/movie-watchlist/${{ matrix.service }}:latest
          format: 'table'
          exit-code: '1'
          severity: 'CRITICAL,HIGH'

  # ═══════════════════════════════════════════════════════════════
  # JOB 3: Deploy to ECS
  # ═══════════════════════════════════════════════════════════════
  deploy:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production  # Requires approval if configured

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Deploy user-service
        run: |
          aws ecs update-service \
            --cluster ${{ env.ECS_CLUSTER }} \
            --service user-service \
            --force-new-deployment

      - name: Deploy movie-service
        run: |
          aws ecs update-service \
            --cluster ${{ env.ECS_CLUSTER }} \
            --service movie-service \
            --force-new-deployment

      - name: Deploy watchlist-service
        run: |
          aws ecs update-service \
            --cluster ${{ env.ECS_CLUSTER }} \
            --service watchlist-service \
            --force-new-deployment

      - name: Wait for deployment stability
        run: |
          aws ecs wait services-stable \
            --cluster ${{ env.ECS_CLUSTER }} \
            --services user-service movie-service watchlist-service

      - name: Verify deployment
        run: |
          # Hit health endpoints to verify
          curl -f https://your-domain.com/api/health/users || exit 1
          curl -f https://your-domain.com/api/health/movies || exit 1
          curl -f https://your-domain.com/api/health/watchlist || exit 1

  # ═══════════════════════════════════════════════════════════════
  # JOB 4: Deploy Frontend
  # ═══════════════════════════════════════════════════════════════
  deploy-frontend:
    needs: deploy
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Sync to S3
        run: |
          aws s3 sync ./frontend s3://movie-watchlist-frontend \
            --delete \
            --cache-control "max-age=31536000" \
            --exclude "index.html"

          # index.html should not be cached long-term
          aws s3 cp ./frontend/index.html s3://movie-watchlist-frontend/index.html \
            --cache-control "max-age=0, no-cache, no-store, must-revalidate"

      - name: Invalidate CloudFront cache
        run: |
          aws cloudfront create-invalidation \
            --distribution-id ${{ secrets.CLOUDFRONT_DISTRIBUTION_ID }} \
            --paths "/*"
```

### Required GitHub Secrets

Configure these in your repository settings (Settings → Secrets → Actions):

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `AWS_ACCESS_KEY_ID` | IAM user access key | IAM Console → Users → Security Credentials |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret key | Generated with access key |
| `AWS_ACCOUNT_ID` | Your 12-digit AWS account ID | Top-right corner of AWS Console |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution ID | CloudFront Console |

### IAM Policy for CI/CD User

Create a dedicated IAM user with minimal permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecs:DescribeClusters"
      ],
      "Resource": [
        "arn:aws:ecs:us-east-1:*:cluster/movie-watchlist",
        "arn:aws:ecs:us-east-1:*:service/movie-watchlist/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::movie-watchlist-frontend",
        "arn:aws:s3:::movie-watchlist-frontend/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "cloudfront:CreateInvalidation",
      "Resource": "*"
    }
  ]
}
```

### Deployment Strategies

| Strategy | Description | Use When |
|----------|-------------|----------|
| **Rolling** (default) | Replace tasks gradually | Most deployments |
| **Blue-Green** | Run new version alongside old, then switch | Critical services |
| **Canary** | Route small % of traffic to new version first | High-risk changes |

---

## Security Vulnerabilities & Best Practices

### Current Vulnerabilities in Your Codebase

#### 1. Hardcoded Credentials (CRITICAL)
**Location**: `docker-compose.yml`
```yaml
# Current (INSECURE)
environment:
  - DATABASE_URL=postgresql://user:password@user-db:5432/userdb
```

**Risk**: Credentials in version control, visible to anyone with repo access

**Fix**: Use AWS Secrets Manager
```python
# config.py
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Usage
secrets = get_secret('movie-watchlist/user-db')
DATABASE_URL = f"postgresql://{secrets['username']}:{secrets['password']}@{secrets['host']}:5432/{secrets['dbname']}"
```

#### 2. SQL Injection Potential
**Location**: Any raw SQL queries

**Risk**: Attackers can manipulate database queries

**Current Code to Audit**:
```python
# Check for patterns like:
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")  # VULNERABLE
```

**Fix**: Always use parameterized queries
```python
# Safe
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

#### 3. No Input Validation on IDs
**Risk**: Path traversal, unexpected behavior

**Fix**: Add Pydantic validation
```python
from pydantic import BaseModel, Field, validator

class UserID(BaseModel):
    id: int = Field(..., gt=0)  # Must be positive integer

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid user ID")
```

#### 4. Missing Rate Limiting
**Risk**: DoS attacks, brute force attempts

**Fix**: Add rate limiting middleware
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/users")
@limiter.limit("100/minute")
async def get_users(request: Request):
    ...
```

#### 5. No HTTPS Enforcement
**Risk**: Man-in-the-middle attacks, credential theft

**Fix**: Configure ALB to redirect HTTP → HTTPS
```yaml
# ALB Listener Rule
ListenerArn: !Ref HTTPListener
Actions:
  - Type: redirect
    RedirectConfig:
      Protocol: HTTPS
      Port: '443'
      StatusCode: HTTP_301
```

#### 6. Missing Security Headers
**Risk**: XSS, clickjacking, MIME sniffing attacks

**Fix**: Add security headers middleware
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

#### 7. CORS Too Permissive
**Risk**: Unauthorized cross-origin requests

**Fix**: Restrict CORS origins
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # Not "*"
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

#### 8. No Request Size Limits
**Risk**: Memory exhaustion, DoS

**Fix**: Limit request body size
```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class LimitRequestSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.headers.get("content-length"):
            if int(request.headers["content-length"]) > 1_000_000:  # 1MB
                return JSONResponse(status_code=413, content={"detail": "Request too large"})
        return await call_next(request)
```

---

### AWS Security Best Practices

#### Network Security

```
┌─────────────────────────────────────────────────────────────────┐
│                          VPC                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Public Subnets                         │    │
│  │  ┌─────────────┐                                        │    │
│  │  │     ALB     │ ← Only component with public access    │    │
│  │  └─────────────┘                                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                    Security Group: Allow 443 only                │
│                              │                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Private Subnets                        │    │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────────────┐    │    │
│  │  │  ECS      │  │   RDS     │  │   ElastiCache     │    │    │
│  │  │  Tasks    │  │ Databases │  │   Redis           │    │    │
│  │  └───────────┘  └───────────┘  └───────────────────┘    │    │
│  │       ↑              ↑                 ↑                │    │
│  │       └──────────────┴─────────────────┘                │    │
│  │         Security Group: Internal traffic only           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  NO INTERNET ACCESS for databases/cache                          │
└─────────────────────────────────────────────────────────────────┘
```

#### Security Group Rules

```yaml
# ALB Security Group
ALBSecurityGroup:
  Inbound:
    - Port: 443, Source: 0.0.0.0/0  # HTTPS from internet
    - Port: 80, Source: 0.0.0.0/0   # Redirect to HTTPS
  Outbound:
    - Port: 8000, Destination: ECSSecurityGroup

# ECS Security Group
ECSSecurityGroup:
  Inbound:
    - Port: 8000, Source: ALBSecurityGroup  # Only from ALB
  Outbound:
    - Port: 5432, Destination: RDSSecurityGroup
    - Port: 6379, Destination: RedisSecurityGroup
    - Port: 443, Destination: 0.0.0.0/0  # For Secrets Manager API

# RDS Security Group
RDSSecurityGroup:
  Inbound:
    - Port: 5432, Source: ECSSecurityGroup  # Only from ECS
  Outbound: None

# Redis Security Group
RedisSecurityGroup:
  Inbound:
    - Port: 6379, Source: ECSSecurityGroup  # Only from ECS
  Outbound: None
```

#### Secrets Management

```python
# secrets.py - Centralized secrets retrieval
import boto3
from functools import lru_cache
import json

@lru_cache(maxsize=10)
def get_secret(secret_name: str) -> dict:
    """
    Retrieve secret from AWS Secrets Manager.
    Cached to avoid repeated API calls.
    """
    client = boto3.client('secretsmanager', region_name='us-east-1')
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except client.exceptions.ResourceNotFoundException:
        raise ValueError(f"Secret {secret_name} not found")

# Usage in service
db_secrets = get_secret("movie-watchlist/user-db")
DATABASE_URL = f"postgresql://{db_secrets['username']}:{db_secrets['password']}@{db_secrets['host']}:{db_secrets['port']}/{db_secrets['dbname']}"
```

#### IAM Roles for ECS Tasks

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:*:secret:movie-watchlist/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:*:log-group:/ecs/movie-watchlist/*"
    }
  ]
}
```

#### RDS Security Settings

```yaml
RDSInstance:
  # Encryption at rest
  StorageEncrypted: true
  KmsKeyId: alias/aws/rds

  # No public access
  PubliclyAccessible: false

  # Deletion protection
  DeletionProtection: true

  # Automated backups
  BackupRetentionPeriod: 7

  # Enhanced monitoring
  MonitoringInterval: 60

  # Enable audit logging
  EnableCloudwatchLogsExports:
    - postgresql
```

---

### Security Checklist for Production

#### Before Deployment
- [ ] Remove all hardcoded credentials from code
- [ ] Set up AWS Secrets Manager for database passwords
- [ ] Enable RDS encryption at rest
- [ ] Configure VPC with private subnets for databases
- [ ] Create separate IAM roles for each service (least privilege)
- [ ] Enable CloudTrail for API auditing
- [ ] Set up WAF rules on ALB

#### Application Level
- [ ] Add rate limiting to all endpoints
- [ ] Implement input validation on all user inputs
- [ ] Add security headers middleware
- [ ] Configure restrictive CORS policy
- [ ] Enable request size limits
- [ ] Use parameterized queries everywhere
- [ ] Add authentication (JWT, OAuth) for protected endpoints

#### Monitoring & Detection
- [ ] Enable GuardDuty for threat detection
- [ ] Set up CloudWatch alarms for:
  - [ ] 5xx error rate spikes
  - [ ] Unusual API call patterns
  - [ ] Failed authentication attempts
  - [ ] Database connection failures
- [ ] Enable VPC Flow Logs
- [ ] Configure SNS notifications for security events

#### Ongoing
- [ ] Regularly rotate secrets (automated with Secrets Manager)
- [ ] Keep dependencies updated (`safety check`, `pip-audit`)
- [ ] Run container vulnerability scans (Trivy, ECR scanning)
- [ ] Review IAM policies quarterly
- [ ] Conduct periodic penetration testing

---

## Cost Comparison

| Component | Option 1 (EC2) | Option 2 (ECS) | Option 3 (EKS) |
|-----------|---------------|----------------|----------------|
| Compute | ~$30 (t3.medium) | ~$50 (Fargate) | ~$150 (EKS + EC2) |
| Database | Included | ~$45 (3x RDS t3.micro) | ~$45 |
| Cache | Included | ~$15 (ElastiCache) | ~$15 |
| Load Balancer | - | ~$20 (ALB) | ~$20 |
| Storage/CDN | - | ~$5 (S3 + CloudFront) | ~$5 |
| **Total** | **~$30-50/mo** | **~$135-200/mo** | **~$235-400/mo** |

---

## Recommendation

**Start with Option 1 (EC2)** to learn AWS basics, then **migrate to Option 2 (ECS Fargate)** once you're comfortable. Here's why:

1. **EC2 first**: Your docker-compose.yml works unchanged, minimal learning curve
2. **ECS later**: Managed infrastructure, auto-scaling, production-ready
3. **Skip EKS**: Unless you specifically need Kubernetes for other projects

The ECS architecture separates concerns properly (managed databases, CDN for frontend, container orchestration) and scales well from small to medium-sized applications.

---

## Verification Steps

After deployment, verify:
1. [ ] Frontend loads at your domain
2. [ ] Health endpoints respond: `/api/health/users`, `/api/health/movies`, `/api/health/watchlist`
3. [ ] CRUD operations work for all three services
4. [ ] Watchlist can add movies (validates inter-service communication)
5. [ ] Redis caching works (check movie service logs for cache hits)
6. [ ] CloudWatch logs capture application output
