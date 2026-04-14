# CostPilot -- GCP-Native Deployment Plan (Dev/Testing)

## Overview

Deploy CostPilot on GCP-native services optimized for a dev/testing environment using:
- **Firebase Hosting** for frontend hosting, SSL, and API proxy rewrites
- **Cloud Run** for backend compute (serverless containers, scales to zero)
- **Cloud SQL** for managed PostgreSQL
- **External free-forever services** for MongoDB and Redis (no GCP free tier exists for these)
- **SendGrid** for transactional email (GCP has no native email service)

**Total monthly cost: $0** during $300 free credit period (90 days), then ~$8/mo for Cloud SQL only.

---

## Architecture Diagram

```
                        +------------------------------+
                        |   Firebase Hosting (FREE)     |
                        |  - DNS + SSL (auto)           |
                        |  - SPA: frontend hosting      |
                        |  - Rewrites: /api/** -> Run   |
                        +------+-----------+-----------+
                               |           |
                  +------------+--+    +---+----------------+
                  | Firebase        |    | Cloud Run            |
                  | Hosting         |    | (Backend Container)  |
                  | (React SPA)     |    | costpilot-xxxxx.     |
                  | costpilot.      |    | run.app              |
                  | web.app         |    | (scales to zero)     |
                  +-----------------+    +---+------------------+
                                                 |
                                     +------------+------------+
                                     | VPC: costpilot-vpc       |
                                     | 10.0.0.0/20              |
                                     |                          |
                                     |  +-- Serverless VPC      |
                                     |  |   Connector            |
                                     |  |   (10.4.0.0/28)        |
                                     |  |                       |
                                     |  +-- Private Subnet       |
                                     |  |   10.0.1.0/24          |
                                     |  |   Cloud SQL (private)  |
                                     |  |   No public IP         |
                                     +--+-----------------------+
                                                 |
                  +----------------------------+---------------------+
                  |  External (over internet)                         |
                  |  + MongoDB Atlas  + Upstash    + SendGrid         |
                  |  | M0 on GCP       | Redis      | (100 emails/day) |
                  |  | (512MB)         | (10K cmd/d)|                  |
                  |  |                 | (256MB)    |                  |
                  +--+----------------+------------+------------------+
```

---

## Component Breakdown

### VPC & Networking

### Recommended: Option A -- No VPC (Dev/Testing)

Cloud Run has a **built-in Cloud SQL Auth Proxy** that connects to Cloud SQL via the Cloud SQL Admin API over Google's internal network. No VPC, no VPC connector, no extra cost.

```
Cloud Run  --(Cloud SQL Admin API)-->  Cloud SQL
           Unix socket: /cloudsql/INSTANCE_CONNECTION_NAME
```

- Cloud SQL instance has **no public IP** (`--no-assign-ip`)
- Connection is authenticated via Cloud Run's service account (IAM)
- No VPC connector needed, no egress charges
- MongoDB Atlas and Upstash are accessed over the public internet (TLS-encrypted)

**This is the recommended approach for dev/testing.** Zero extra cost, zero extra infrastructure.

### Alternative: Option B -- Full VPC (Production-ready)

If you need private IP connectivity to Cloud SQL (e.g., for regulatory compliance or to avoid all public internet paths), use a VPC with a Serverless VPC Access connector.

```
Cloud Run  --(VPC Connector)-->  Private Subnet  -->  Cloud SQL (private IP only)
```

| Item | Detail |
|------|--------|
| **VPC** | costpilot-vpc (10.0.0.0/20) |
| **Private subnet** | costpilot-private (10.0.1.0/24, us-central1) |
| **Serverless VPC Connector** | costpilot-vpc-connector (10.4.0.0/28, min 3 / max 10 instances) |
| **Connector cost** | ~$7.67/mo (same as db-f1-micro!) |
| **Cloud SQL** | Private IP only, no public IP |

**Cost impact:** VPC connector adds ~$7.67/mo, doubling the post-credit cost to ~$15/mo. Not worth it for dev/testing.

**VPC setup (Option B only):**
```bash
# Create VPC
 gcloud compute networks create costpilot-vpc --subnet-mode=custom

# Create private subnet
 gcloud compute networks subnets create costpilot-private \
  --network=costpilot-vpc --region=us-central1 --range=10.0.1.0/24

# Create Serverless VPC Access connector
 gcloud compute networks vpc-access connectors create costpilot-vpc-connector \
  --network=costpilot-vpc \
  --region=us-central1 \
  --range=10.4.0.0/28 \
  --min-instances=3 \
  --max-instances=10

# Create Cloud SQL with private IP only
 gcloud sql instances create costpilot-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --storage-type=SSD \
  --storage-size=10 \
  --no-assign-ip \
  --network=costpilot-vpc \
  --database=costpilot

# Deploy Cloud Run with VPC connector
 gcloud run deploy costpilot-backend \
  --vpc-connector=costpilot-vpc-connector \
  --vpc-egress=private-ranges-only \
  --add-cloudsql-instances=PROJECT_ID:us-central1:costpilot-db \
  ... (other flags same as before)

# Allocate IP range for Cloud SQL private services access
 gcloud compute addresses create google-managed-services-costpilot-vpc \
  --global --purpose=VPC_PEERING --prefix-length=16 --network=costpilot-vpc

# Create private services connection (required for Cloud SQL private IP)
 gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=google-managed-services-costpilot-vpc \
  --network=costpilot-vpc
```

**Key differences from Option A:**
- DATABASE_URL uses Cloud SQL private IP instead of Unix socket
- Cloud Run deployed with `--vpc-connector` and `--vpc-egress=private-ranges-only`
- Cloud SQL created with `--network=costpilot-vpc` instead of just `--no-assign-ip`
- Requires private services access peering for Cloud SQL

---

### 1. Frontend -- Firebase Hosting

| Item | Detail |
|------|--------|
| **Service** | Firebase Hosting |
| **Cost** | Free forever (10 GB storage, 360 MB/day transfer) |
| **Domain** | costpilot.web.app (free) or custom domain |
| **Build** | pnpm build -> outputs to dist/ |
| **Deploy** | firebase deploy --only hosting |
| **SSL** | Automatic (Google-managed) |

**Setup steps:**
1. `npm install -g firebase-tools && firebase login`
2. `firebase init hosting` -- set dist/ as public directory, SPA rewrite
3. `firebase deploy --only hosting`

**API proxy -- Firebase Hosting rewrites:**
Configure `firebase.json` to proxy `/api/**` to Cloud Run.

```json
{
  "hosting": {
    "public": "dist",
    "rewrites": [
      {
        "source": "/api/**",
        "run": { "serviceId": "costpilot-backend", "region": "us-central1" }
      }
    ],
    "cleanUrls": true
  }
}
```

Firebase Hosting automatically authenticates proxied requests to Cloud Run using the project's default service account -- no Cloudflare Tunnel needed.

---

### 2. Backend -- Cloud Run

| Item | Detail |
|------|--------|
| **Service** | Google Cloud Run |
| **Cost** | Free -- 2M requests/mo, 360K GB-seconds, 180K vCPU-seconds (always-free) |
| **Region** | us-central1 |
| **CPU** | 1 vCPU (allocated per request) |
| **Memory** | 512 MiB |
| **Concurrency** | 80 requests per instance |
| **Min instances** | 0 (scales to zero, no idle cost) |
| **Max instances** | 3 |
| **Container** | CostPilot backend Docker image (Artifact Registry) |

**Why Cloud Run (not GCE or GKE):**
- Scales to zero -- no cost when idle (perfect for dev/testing)
- No VM management or SSH hardening
- Built-in Cloud Logging and Cloud Monitoring
- Artifact Registry free tier: 500 MB storage (enough for one image)
- Firebase Hosting rewrites integrate natively with Cloud Run

**Memory constraints (512 MiB):**
- Single uvicorn worker (no --workers N)
- Reduce DB_POOL_SIZE to 5 (from 20)
- Reduce DB_MAX_OVERFLOW to 10 (from 40)
- Reduce MONGODB_MAX_POOL_SIZE to 10 (from 50)
- Reduce REDIS_MAX_CONNECTIONS to 20 (from 100)

**Deploy:**
```bash
# Build and push to Artifact Registry
gcloud builds submit --tag us-central1-docker.pkg.dev/PROJECT_ID/costpilot/backend

# Deploy to Cloud Run
gcloud run deploy costpilot-backend \
  --image us-central1-docker.pkg.dev/PROJECT_ID/costpilot/backend \
  --region us-central1 \
  --platform managed \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --allow-unauthenticated \
  --set-env-vars "DATABASE_URL=postgresql+asyncpg://costpilot:PW@/costpilot?host=/cloudsql/PROJECT_ID:us-central1:costpilot-db" \
  --set-env-vars "MONGODB_URL=mongodb+srv://costpilot:PW@cluster0.xxxxx.mongodb.net/costpilot" \
  --set-env-vars "REDIS_URL=redis://default:PW@us1-xxx-12345.upstash.io:6379" \
  --set-env-vars "JWT_SECRET=SECRET,ENCRYPTION_KEY=FERNET_KEY" \
  --set-env-vars "EMAIL_PROVIDER=sendgrid,SENDGRID_API_KEY=SG_KEY" \
  --add-cloudsql-instances PROJECT_ID:us-central1:costpilot-db
```

**Cloud SQL connection:**
Cloud Run connects to Cloud SQL via the built-in Cloud SQL Auth Proxy (no need to install or configure separately). Just add `--add-cloudsql-instances` flag. The PostgreSQL connection uses Unix socket path `/cloudsql/INSTANCE_CONNECTION_NAME`.

---

### 3. PostgreSQL -- Cloud SQL (db-f1-micro)

| Item | Detail |
|------|--------|
| **Service** | Cloud SQL for PostgreSQL |
| **Instance** | db-f1-micro (shared-core, 0.6 GB RAM) |
| **Cost** | ~$7.67/mo (no always-free tier; covered by $300 free credit for 90 days) |
| **Storage** | 10 GB SSD (included) |
| **Backup** | 7-day automatic backups (included) |
| **AZ** | Single-zone |
| **Engine** | PostgreSQL 16 |

**Why Cloud SQL (not AlloyDB or Bare Metal):**
- AlloyDB has no small instance tier; cheapest is ~$200/mo
- Cloud SQL db-f1-micro is the smallest managed PostgreSQL on GCP
- Built-in Cloud SQL Auth Proxy for secure, passwordless connections from Cloud Run
- No public IP needed -- private connectivity via VPC connector or Unix socket

**Setup:**
```bash
gcloud sql instances create costpilot-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --storage-type=SSD \
  --storage-size=10 \
  --no-assign-ip \
  --database=costpilot

gcloud sql users create costpilot \
  --instance=costpilot-db \
  --password=<secure-password>
```

**Connection from Cloud Run:**
```
postgresql+asyncpg://costpilot:<pw>@/costpilot?host=/cloudsql/PROJECT_ID:us-central1:costpilot-db
```

**Post-free-credit cost:** ~$7.67/mo (db-f1-micro)

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
| **Network** | Atlas allows GCP VPC peering on M0 (shared) |

**Why not Firestore or MongoDB on GCE:**
- Firestore is a document DB but not MongoDB-compatible -- would require code rewrite
- Self-hosted MongoDB on GCE costs at least ~$7/mo for the VM
- Atlas M0 is free forever and compatible with the Motor async driver already used

**Setup:**
1. Create account at cloud.mongodb.com
2. Build a cluster -> M0 Free -> GCP -> us-central1
3. Create database user
4. Whitelist Cloud Run egress IPs (or use 0.0.0.0/0 for dev)
5. Get connection string -> set as MONGODB_URL

**Connection string format:**
```
mongodb+srv://costpilot:<password>@cluster0.xxxxx.mongodb.net/costpilot?retryWrites=true&w=majority
```

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

**Why not Memorystore or Redis on GCE:**
- Memorystore has no free tier; cheapest M1 is ~$35/mo
- Self-hosted Redis on GCE costs ~$7/mo for the VM
- Upstash is serverless, pay-per-request, with a generous free tier

**Setup:**
1. Create account at upstash.com
2. Create Redis database -> GCP us-central1
3. Get endpoint: redis://default:<password>@us1-xxx-12345.upstash.io:6379
4. Set as REDIS_URL

**Compatibility notes:**
- Upstash supports standard Redis protocol -- redis-py and aioredis work natively
- The codebase uses Redis for: sessions, rate limiting, idempotency, request coalescing
- 10K commands/day is sufficient for dev/testing; each API request uses ~2-5 Redis commands

---

### 6. Email -- SendGrid (Free Tier)

| Item | Detail |
|------|--------|
| **Service** | SendGrid |
| **Cost** | Free -- 100 emails/day forever |
| **Already integrated** | Yes -- `send_email_sendgrid()` added to `email_service.py` |

**Why not GCP-native email:**
- GCP has no native transactional email service
- SendGrid has a GCP Marketplace integration and a generous free tier
- 100 emails/day is plenty for dev/testing

**Network connectivity:**
- Cloud Run -> SendGrid is **outbound HTTPS over the public internet**
- Cloud Run has full outbound internet access by default (both Option A and Option B)
- Connection: `POST https://api.sendgrid.com/v3/mail/send` (TLS-encrypted)
- Auth: `Authorization: Bearer <SENDGRID_API_KEY>` header
- No VPC, NAT gateway, or special networking needed
- **Option B caveat:** If using `--vpc-egress=all`, internet still works. If using `--vpc-egress=private-ranges-only`, you need a Cloud NAT gateway (~$7/mo) for outbound internet -- another reason to prefer Option A for dev

**Setup:**
1. Create account at sendgrid.com
2. Verify sender identity (single sender email is fine for dev)
3. Generate API key -> set SENDGRID_API_KEY
4. Set EMAIL_PROVIDER=sendgrid, SENDGRID_FROM_EMAIL=noreply@costpilot.dev

**Code integration (already done):**
```python
# backend/app/notifications/email_service.py
async def send_email_sendgrid(to: str, subject: str, html_body: str) -> None:
    """Send an email via SendGrid REST API. Raises on failure."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": settings.SENDGRID_FROM_EMAIL},
                "subject": subject,
                "content": [{"type": "text/html", "value": html_body}],
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(f"SendGrid API error: {response.status_code} - {response.text}")
```

**Config (already added to `backend/app/config.py`):**
```python
SENDGRID_API_KEY: str = ""       # SendGrid API key
SENDGRID_FROM_EMAIL: str = "noreply@costpilot.io"  # Verified sender email
```

**Alternative:** Use SMTP via Gmail for dev (free, 500 emails/day with a Google account).

---

### 7. Domain & DNS -- Firebase Hosting

| Item | Detail |
|------|--------|
| **Free domain** | costpilot.web.app (Firebase default) |
| **Custom domain** | ~$10-12/yr from Google Domains or Cloudflare Registrar |
| **DNS** | Firebase-managed (free) |
| **SSL** | Google-managed SSL certificate (free, auto-provisioned) |

**Why not Cloud DNS:**
- Cloud DNS charges $0.20/mo per zone + per-query fees
- Firebase Hosting includes DNS and SSL at no cost for custom domains
- Simpler setup -- just add domain in Firebase console

**Custom domain setup (optional):**
1. Buy domain at Google Domains or Cloudflare Registrar
2. In Firebase console -> Hosting -> Add custom domain
3. Add TXT/A records at registrar as instructed
4. Firebase auto-provisions SSL certificate within 24 hours

---

## Cost Summary

| Component | Service | Monthly Cost | Free Tier Duration |
|-----------|---------|-------------|-------------------|
| Frontend | Firebase Hosting | **$0** | Forever (10 GB storage) |
| Backend | Cloud Run | **$0** | Forever (2M req/mo always-free) |
| PostgreSQL | Cloud SQL db-f1-micro | **~$7.67** | 90-day free credit |
| VPC Connector | Serverless VPC Access | **~$7.67** | 90-day free credit (Option B only) |
| MongoDB | Atlas M0 | **$0** | Forever |
| Redis | Upstash | **$0** | Forever |
| Email | SendGrid | **$0** | Forever (100/day) |
| DNS + SSL | Firebase | **$0** | Forever |
| Container Registry | Artifact Registry | **$0** | 500 MB free (forever) |
| Monitoring | Cloud Monitoring | **$0** | Basic metrics (free) |
| Logging | Cloud Logging | **$0** | 50 GB/month (free) |
| Domain (optional) | Google Domains | **~$1/mo** | N/A (annual ~$12) |
| **TOTAL (Option A)** | | **$0/mo** (90 days) | then ~$8/mo |
| **TOTAL (Option B)** | | **$0/mo** (90 days) | then ~$15/mo |

**Post-free-credit costs (after 90 days):**
- Cloud SQL db-f1-micro: ~$7.67/mo
- Cloud Run: likely still free (always-free tier covers dev traffic)
- VPC Connector (Option B only): ~$7.67/mo
- Everything else: still free

---

## Deployment Sequence

### Phase 1: GCP Infrastructure (Day 1)

1. Create GCP account (get $300 free credit for 90 days)
2. Create project: `costpilot-dev`
3. Enable APIs: Cloud Run, Cloud SQL Admin, Artifact Registry, Cloud Build, Firebase, Serverless VPC Access (if Option B)
4. **(Option B only)** Create VPC, private subnet, VPC connector, and private services access peering
5. Create Cloud SQL PostgreSQL db-f1-micro instance (with `--network` if Option B, with `--no-assign-ip` if Option A)
6. Create database and user
7. Create Artifact Registry repo, push backend Docker image

### Phase 2: External Services (Day 1)

7. Create MongoDB Atlas M0 cluster (GCP us-central1)
8. Whitelist Cloud Run egress IPs in Atlas
9. Create Upstash Redis database
10. Create SendGrid account, verify sender, generate API key

### Phase 3: Cloud Run & Firebase (Day 1-2)

11. Deploy backend to Cloud Run with Cloud SQL connection (add `--vpc-connector` if Option B)
12. Initialize Firebase in frontend project
13. Configure firebase.json with Cloud Run rewrite
14. Deploy frontend to Firebase Hosting
15. Test end-to-end: Firebase -> Cloud Run -> Cloud SQL / Atlas / Upstash

### Phase 4: Configuration & Testing (Day 2)

16. Set all environment variables in Cloud Run
17. Update CORS_ORIGINS to include Firebase Hosting origin
18. Reduce pool sizes for 512 MiB memory constraint
19. Run Alembic migrations against Cloud SQL
20. Verify API proxy rewrite works through Firebase Hosting

### Phase 5: Domain (Optional, Day 2+)

21. Buy domain on Google Domains or Cloudflare Registrar
22. Add custom domain in Firebase console
23. Configure DNS records as instructed by Firebase

---

## Security Notes

- **Cloud Run has no inbound ports** -- only accessible via Firebase Hosting rewrite or HTTPS endpoint
- **Cloud SQL has no public IP** -- connected via Unix socket (Cloud SQL Auth Proxy built into Cloud Run, Option A) or private IP via VPC connector (Option B)
- **VPC Connector (Option B)** -- egress restricted to private ranges only (`--vpc-egress=private-ranges-only`), Cloud Run cannot reach internet through VPC
- **MongoDB Atlas** -- IP whitelist or VPC peering restricted
- **Upstash** -- TLS required, password-protected
- **SendGrid** -- API key with minimal permissions (Mail Send only)
- **All credentials** -- stored in Cloud Run environment variables (consider Secret Manager later)
- **HTTPS everywhere** -- Firebase Hosting handles SSL termination; Cloud Run enforces HTTPS

---

## RAM Budget (Cloud Run -- 512 MiB)

| Process | Estimated RAM |
|---------|--------------|
| FastAPI (uvicorn) | ~200 MB |
| Cloud SQL Auth Proxy (built-in) | ~30 MB |
| boto3 / Azure SDK / GCP SDK | ~100 MB (lazy-loaded) |
| SQLAlchemy + asyncpg | ~50 MB |
| Motor (MongoDB) | ~30 MB |
| Redis client | ~10 MB |
| Python runtime overhead | ~50 MB |
| **Total** | ~470 MB |
| **Available headroom** | ~42 MB |

**Critical:** Run single uvicorn worker. Reduce all pool sizes. Cloud Run auto-scales horizontally under load.

---

## Files to Create/Modify

### New files:
- `frontend/firebase.json` -- Firebase Hosting config with Cloud Run rewrite
- `frontend/.firebaserc` -- Firebase project association
- `infrastructure/cloud-run-service.yaml` -- Cloud Run service definition (optional, for declarative deploy)
- `infrastructure/vpc-setup.sh` -- VPC + connector setup script (Option B only)

### Modified files:
- `backend/app/config.py` -- Added `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL` config fields; updated `EMAIL_PROVIDER` docstring to include "sendgrid"
- `backend/app/notifications/email_service.py` -- Added `send_email_sendgrid()` using `httpx.AsyncClient`; updated `send_email()` dispatcher to route `"sendgrid"` provider; added `import httpx`
- `.env.example` -- Added SendGrid configuration section with `SENDGRID_API_KEY` and `SENDGRID_FROM_EMAIL` examples
- `docker-compose.yml` -- No changes needed (local dev stays the same)

---

## Monitoring & Alerts

| Metric | Service | Free Tier Limit |
|--------|---------|----------------|
| Cloud Run requests/latency | Cloud Monitoring | Basic metrics (free) |
| Cloud SQL connections | Cloud Monitoring | Included with Cloud SQL |
| Cloud Run logs | Cloud Logging | 50 GB/month (free) |
| SendGrid sends | SendGrid dashboard | Built-in |
| Upstash usage | Upstash dashboard | Built-in |
| Atlas metrics | Atlas dashboard | Built-in |

**Set up GCP Budget alert at $1 to catch any unexpected charges early.**
