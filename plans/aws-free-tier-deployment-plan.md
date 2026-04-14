# CostPilot -- AWS Free Tier Deployment Plan

## Overview

Deploy CostPilot entirely within free-tier services using:
- **Cloudflare** for frontend hosting, DNS, SSL, and tunneling
- **AWS** for backend compute (ECS on EC2), managed PostgreSQL (RDS), and email (SES)
- **External free-forever services** for MongoDB and Redis (no AWS free tier exists for these)

**Total monthly cost: $0** (or ~$0.75/mo with a custom domain)

---

## Architecture Diagram

`
                          +------------------------------+
                          |     Cloudflare (FREE)        |
                          |  - DNS + SSL (auto)          |
                          |  - Pages: frontend hosting   |
                          |  - Tunnel: backend proxy     |
                          +------+-----------+-----------+
                                 |           |
                    +------------+--+    +---+----------------+
                    | Cloudflare      |    | Cloudflare          |
                    | Pages           |    | Tunnel              |
                    | (React SPA)     |    | (cloudflared)       |
                    | costpilot.      |    |                     |
                    | pages.dev       |    |                     |
                    +-----------------+    +---+-----------------+
                                             |
                    +----------------------------+---------------------+
                    |  AWS EC2 t3.micro (ECS on EC2 launch type)           |
                    |  - ECS Agent + Backend Container                     |
                    |  - cloudflared tunnel client                          |
                    |  - Port 8000 (internal only, no inbound)             |
                    +--+--------------+----------------+------------------+
                       |              |                |
              +--------+-----+  +----+----------+  +--+--------------+
              | RDS           |  | MongoDB      |  | Upstash         |
              | db.t4g.micro  |  | Atlas M0     |  | Redis           |
              | PostgreSQL   |  | (512MB)      |  | (10K cmd/day)   |
              | (20GB)       |  |              |  | (256MB)         |
              +--------------+  +--------------+  +-----------------+
                       |
              +--------+---------------------------+
              |  Amazon SES (3K emails/mo)        |
              |  + Cost Explorer APIs (boto3)      |
              |  + Azure/GCP SDKs                  |
              +------------------------------------+
`

---

## Component Breakdown

### 1. Frontend -- Cloudflare Pages

| Item | Detail |
|------|--------|
| **Service** | Cloudflare Pages |
| **Cost** | Free forever |
| **Domain** | costpilot.pages.dev (free) or custom domain |
| **Build** | pnpm build -> outputs to dist/ |
| **Auto-deploy** | Connect GitHub repo, auto-build on push |
| **Limits** | 500 builds/mo, 100K requests/day, 25MB per asset |
| **SSL** | Automatic (Cloudflare-managed) |

**Setup steps:**
1. Push frontend to GitHub
2. In Cloudflare dashboard -> Pages -> Create project -> Connect GitHub repo
3. Build settings: pnpm build, output directory dist
4. Add env var VITE_API_BASE = /api/v1 (relative, proxied by Worker)

**API proxy -- Cloudflare Pages Functions:**
Create frontend/functions/api/v1/[[path]].ts to proxy /api/v1/* to the backend via Cloudflare Tunnel.

``ts
// frontend/functions/api/v1/[[path]].ts
const BACKEND_ORIGIN = "https://api.costpilot.pages.dev"; // Tunnel hostname

export const onRequest: PagesFunction = async (context) => {
  const url = new URL(context.request.url);
  const backendUrl = ${BACKEND_ORIGIN}/api/v1;

  // Forward the request, preserving method/headers/body
  const headers = new Headers(context.request.headers);
  headers.set("Host", new URL(BACKEND_ORIGIN).host);

  const response = await fetch(backendUrl, {
    method: context.request.method,
    headers,
    body: ["GET", "HEAD"].includes(context.request.method) ? undefined : context.request.body,
    redirect: "manual",
  });

  // Copy response, adding CORS headers for same-origin compatibility
  const newHeaders = new Headers(response.headers);
  newHeaders.set("Access-Control-Allow-Origin", new URL(context.request.url).origin);
  newHeaders.set("Access-Control-Allow-Credentials", "true");

  return new Response(response.body, {
    status: response.status,
    headers: newHeaders,
  });
};
``

---

### 2. Backend -- ECS on EC2 (t3.micro)

| Item | Detail |
|------|--------|
| **Service** | Amazon ECS on EC2 launch type |
| **EC2 instance** | t3.micro (2 vCPU, 1GB RAM) |
| **Cost** | Free -- 750 hrs/mo (Free Plan credits or 12-mo free tier) |
| **ECS fee** | $0 (no additional charge for EC2 launch type) |
| **EBS** | 30 GB free (gp3) |
| **Container** | CostPilot backend Docker image |

**Why ECS on EC2 (not plain Docker on EC2):**
- ECS provides automatic container restart, health checks, and task definition management
- No additional cost over plain EC2
- ECR (container registry) is free for 500MB (enough for one image)

**Memory constraints (1GB RAM):**
- Single uvicorn worker (no --workers N)
- Reduce DB_POOL_SIZE to 5 (from 20)
- Reduce DB_MAX_OVERFLOW to 10 (from 40)
- Reduce MONGODB_MAX_POOL_SIZE to 10 (from 50)
- Reduce REDIS_MAX_CONNECTIONS to 20 (from 100)

**ECS Task Definition (key settings):**
`json
{
  "family": "costpilot-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["EC2"],
  "cpu": "512",
  "memory": "768",
  "containerDefinitions": [{
    "name": "backend",
    "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/costpilot-backend:latest",
    "essential": true,
    "portMappings": [{ "containerPort": 8000, "protocol": "tcp" }],
    "environment": [
      { "name": "DATABASE_URL", "value": "postgresql+asyncpg://costpilot:<pw>@<rds-endpoint>:5432/costpilot" },
      { "name": "MONGODB_URL", "value": "mongodb+srv://costpilot:<pw>@cluster0.xxxxx.mongodb.net/costpilot" },
      { "name": "REDIS_URL", "value": "redis://default:<pw>@us1-xxx-12345.upstash.io:6379" },
      { "name": "JWT_SECRET", "value": "<generated-secret>" },
      { "name": "ENCRYPTION_KEY", "value": "<fernet-key>" },
      { "name": "EMAIL_PROVIDER", "value": "ses" },
      { "name": "AWS_REGION", "value": "us-east-1" }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/costpilot-backend",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }]
}
`

**cloudflared on EC2 (sidecar):**
Run cloudflared as a systemd service on the EC2 instance alongside the ECS agent. The tunnel connects outbound to Cloudflare -- no inbound security group rules needed.

`ash
# Install cloudflared
sudo curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared

# Authenticate
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create costpilot

# Configure: ~/.cloudflared/config.yml
# tunnel: <tunnel-id>
# credentials-file: ~/.cloudflared/<tunnel-id>.json
# ingress:
#   - hostname: api.costpilot.pages.dev
#     service: http://localhost:8000
#   - service: http_status:404

# Route DNS (in Cloudflare dashboard):
#   api.costpilot.pages.dev -> CNAME -> <tunnel-id>.cfargotunnel.com

# Run as service
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
`

---

### 3. PostgreSQL -- Amazon RDS (db.t4g.micro)

| Item | Detail |
|------|--------|
| **Service** | Amazon RDS for PostgreSQL |
| **Instance** | db.t4g.micro (2 vCPU, 1GB RAM) |
| **Cost** | Free -- 750 hrs/mo (Free Plan credits or 12-mo free tier) |
| **Storage** | 20 GB gp3 (free) |
| **Backup** | 20 GB backup storage (free) |
| **AZ** | Single-AZ only (free tier) |
| **Engine** | PostgreSQL 16 |

**Setup:**
`ash
aws rds create-db-instance \
  --db-instance-identifier costpilot-db \
  --db-instance-class db.t4g.micro \
  --engine postgres \
  --engine-version 16.4 \
  --master-username costpilot \
  --master-user-password <secure-password> \
  --allocated-storage 20 \
  --storage-type gp3 \
  --db-name costpilot \
  --no-multi-az \
  --publicly-accessible no \
  --vpc-security-group-ids <backend-sg>
`

**Post-free-tier cost:** ~$12/mo (db.t4g.micro on-demand)

---

### 4. MongoDB -- MongoDB Atlas M0 (Free Forever)

| Item | Detail |
|------|--------|
| **Service** | MongoDB Atlas |
| **Tier** | M0 (Shared Cluster) |
| **Cost** | Free forever |
| **Storage** | 512 MB |
| **Ops/sec** | 100 |
| **Connection** | mongodb+srv:// (SRV connection string) |
| **Network** | Atlas allows AWS VPC peering on M0 (shared) |

**Why not AWS DocumentDB:**
- DocumentDB has no free tier
- Cheapest DocumentDB is ~$50/mo
- Atlas M0 is free forever and compatible with the Motor async driver already used in the codebase

**Setup:**
1. Create account at cloud.mongodb.com
2. Build a cluster -> M0 Free -> AWS -> us-east-1
3. Create database user
4. Whitelist EC2 security group or IP
5. Get connection string -> set as MONGODB_URL

**Connection string format:**
`
mongodb+srv://costpilot:<password>@cluster0.xxxxx.mongodb.net/costpilot?retryWrites=true&w=majority
`

---

### 5. Redis -- Upstash Redis (Free Forever)

| Item | Detail |
|------|--------|
| **Service** | Upstash Redis |
| **Cost** | Free forever |
| **Commands/day** | 10,000 |
| **Storage** | 256 MB |
| **Connections** | Up to 256 concurrent |
| **Protocol** | Redis-compatible (also has REST API) |

**Why not AWS ElastiCache:**
- ElastiCache has no free tier
- Smallest ElastiCache node (cache.t4g.micro) is ~$12/mo
- Upstash is serverless, pay-per-request, with a generous free tier

**Setup:**
1. Create account at upstash.com
2. Create Redis database -> AWS us-east-1
3. Get endpoint: redis://default:<password>@us1-xxx-12345.upstash.io:6379
4. Set as REDIS_URL

**Compatibility notes:**
- Upstash supports standard Redis protocol -- redis-py and aioredis work natively
- The codebase uses Redis for: sessions, rate limiting, idempotency, request coalescing
- 10K commands/day is sufficient for personal/dev use; each API request uses ~2-5 Redis commands

---

### 6. Email -- Amazon SES

| Item | Detail |
|------|--------|
| **Service** | Amazon SES |
| **Cost** | Free -- 3,000 messages/mo (12-mo free) or via Free Plan credits |
| **Post-free cost** | ~$0.10 per 1,000 messages |
| **Already integrated** | Yes -- EMAIL_PROVIDER=ses in config |

**Setup:**
1. Verify sender identity in SES console (email or domain)
2. Create IAM user with ses:SendEmail + ses:SendRawEmail permissions
3. Generate access keys -> set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
4. Set EMAIL_PROVIDER=ses, SES_FROM_EMAIL=noreply@costpilot.io
5. While in sandbox: can only send to verified email addresses
6. Request production access to send to any address

---

### 7. Domain & DNS -- Cloudflare

| Item | Detail |
|------|--------|
| **Free domain** | costpilot.pages.dev (Cloudflare Pages default) |
| **Custom domain** | ~$8-12/yr from Cloudflare Registrar, Namecheap, or Porkbun |
| **DNS** | Cloudflare DNS (free) |
| **SSL** | Cloudflare Universal SSL (free, auto-managed) |
| **Email** | Cloudflare Email Routing (free) -- forward noreply@ to your inbox |

**Why not AWS Route 53:**
- Route 53 charges $0.50/mo per hosted zone + $0.40/mo per million queries
- Cloudflare DNS is free with unlimited queries
- Cloudflare provides free SSL, proxy, and email routing

**Custom domain setup (optional):**
1. Buy domain at Cloudflare Registrar (~$9.15/yr for .com, at-cost pricing)
2. Domain auto-added to Cloudflare DNS
3. Add CNAME: costpilot.yourdomain.com -> costpilot.pages.dev
4. Add CNAME: api.yourdomain.com -> <tunnel-id>.cfargotunnel.com
5. Cloudflare auto-provisions SSL certificates

---

## Cost Summary

| Component | Service | Monthly Cost | Free Tier Duration |
|-----------|---------|-------------|-------------------|
| Frontend | Cloudflare Pages | **$0** | Forever |
| Backend | ECS on EC2 t3.micro | **$0** | 6-mo credits / 12-mo free |
| PostgreSQL | RDS db.t4g.micro | **$0** | 6-mo credits / 12-mo free |
| MongoDB | Atlas M0 | **$0** | Forever |
| Redis | Upstash | **$0** | Forever |
| Email | SES | **$0** | 12-mo free |
| DNS + SSL | Cloudflare | **$0** | Forever |
| Tunnel | Cloudflare Tunnel | **$0** | Forever |
| Container Registry | ECR | **$0** | 500 MB free (forever) |
| Monitoring | CloudWatch | **$0** | 10 metrics + 10 alarms (forever) |
| Domain (optional) | Cloudflare Registrar | **~$0.75/mo** | N/A (annual $9.15) |
| **TOTAL** | | **$0/mo** | |

**Post-free-tier costs (after 12 months):**
- EC2 t3.micro: ~$7.50/mo
- RDS db.t4g.micro: ~$12/mo
- SES: ~$0.10/1K emails
- Everything else: still free

---

## Deployment Sequence

### Phase 1: AWS Infrastructure (Day 1)

1. Create AWS account (select Free Plan for $200 credits)
2. Create VPC with public + private subnets in us-east-1
3. Create RDS PostgreSQL db.t4g.micro in private subnet
4. Create EC2 t3.micro in public subnet (for ECS)
5. Create ECR repository, push backend Docker image
6. Create ECS cluster, task definition, and service
7. Create IAM user for SES with minimal permissions
8. Verify SES sender identity

### Phase 2: External Services (Day 1)

9. Create MongoDB Atlas M0 cluster (AWS us-east-1)
10. Whitelist EC2 IP in Atlas
11. Create Upstash Redis database
12. Create Cloudflare account

### Phase 3: Cloudflare & Networking (Day 1-2)

13. Deploy frontend to Cloudflare Pages (connect GitHub)
14. Create Cloudflare Pages Functions proxy (functions/api/v1/[[path]].ts)
15. Install cloudflared on EC2, create tunnel
16. Configure tunnel: api.costpilot.pages.dev -> http://localhost:8000
17. Route DNS in Cloudflare dashboard

### Phase 4: Configuration & Testing (Day 2)

18. Set all environment variables in ECS task definition
19. Update CORS_ORIGINS to include Cloudflare Pages origin
20. Reduce pool sizes for 1GB RAM constraint
21. Run Alembic migrations against RDS
22. Test end-to-end: frontend -> Cloudflare -> tunnel -> backend -> RDS/Atlas/Upstash

### Phase 5: Domain (Optional, Day 2+)

23. Buy domain on Cloudflare Registrar
24. Add CNAME records for frontend and API
25. Configure Cloudflare Email Routing for noreply@

---

## Security Notes

- **EC2 has no inbound ports** -- all traffic goes through Cloudflare Tunnel
- **RDS is in private subnet** -- only accessible from EC2 within VPC
- **MongoDB Atlas** -- IP whitelist restricted to EC2's IP
- **Upstash** -- TLS required, password-protected
- **SES** -- IAM user with minimal permissions (only ses:SendEmail, ses:SendRawEmail)
- **All credentials** -- stored in ECS task definition environment variables (consider AWS Secrets Manager later)
- **HTTPS everywhere** -- Cloudflare handles SSL termination; tunnel provides encrypted transport

---

## RAM Budget (EC2 t3.micro -- 1GB)

| Process | Estimated RAM |
|---------|--------------|
| OS + ECS Agent | ~200 MB |
| cloudflared | ~20 MB |
| FastAPI (uvicorn) | ~400 MB |
| boto3 / Azure SDK / GCP SDK | ~150 MB (lazy-loaded) |
| SQLAlchemy + asyncpg | ~50 MB |
| Motor (MongoDB) | ~30 MB |
| Redis client | ~10 MB |
| **Total** | ~860 MB |
| **Available headroom** | ~140 MB |

**Critical**: Run single uvicorn worker. Reduce all pool sizes. Monitor with CloudWatch.

---

## Files to Create/Modify

### New files:
- frontend/functions/api/v1/[[path]].ts -- Cloudflare Pages proxy function
- infrastructure/ec2-user-data.sh -- EC2 bootstrap script (install ECS agent + cloudflared)
- infrastructure/ecs-task-definition.json -- ECS task definition
- infrastructure/cloudflared-config.yml -- Tunnel configuration

### Modified files:
- backend/app/config.py -- Add VITE_API_BASE or adjust CORS for Cloudflare origin
- docker-compose.yml -- Add cloudflared service (for local dev parity)
- .env.example -- Add Upstash/Atlas connection string examples

---

## Monitoring & Alerts

| Metric | Service | Free Tier Limit |
|--------|---------|----------------|
| EC2 CPU | CloudWatch | 10 custom metrics (always free) |
| RDS connections | CloudWatch | Included with RDS |
| ECS task health | CloudWatch | Basic 1-min resolution (free) |
| API errors | CloudWatch Logs | 5 GB ingestion (free tier) |
| SES sends | SES dashboard | Built-in |
| Upstash usage | Upstash dashboard | Built-in |
| Atlas metrics | Atlas dashboard | Built-in |

**Set up AWS Budget alert at $1 to catch any unexpected charges early.**