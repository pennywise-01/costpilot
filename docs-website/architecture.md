# Architecture

System architecture, technology stack, and design decisions for CostPilot.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Client Browser                       │
│                      (React + TypeScript)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                    HTTPS / HTTP
                         │
┌────────────────────────▼────────────────────────────────────┐
│                      Frontend Server                         │
│                   (Vite + React 18 + Ant Design)             │
│                      Port: 5173                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                    REST API (JSON)
                         │
┌────────────────────────▼────────────────────────────────────┐
│                       Backend API                            │
│                   (FastAPI + Python 3.12+)                   │
│                      Port: 8000                              │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   Auth   │  │  Costs   │  │  Users   │  │Enterprise│   │
│  │  Module  │  │  Module  │  │  Module  │  │  Module  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Middleware Stack                            │  │
│  │  CORS → CSRF → Health → Metrics → Correlation ID    │  │
│  │  → Global Exception Handler → Idempotency           │  │
│  │  → Timeout → Rate Limit → Input Validation → GZip   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────┬──────────────────────────────┬───────────────┘
              │                              │
     ┌────────▼────────┐          ┌──────────▼──────────┐
     │   PostgreSQL    │          │      MongoDB        │
     │   (Primary DB)  │          │  (Expense Line Items)│
     │   Port: 5432    │          │   Port: 27017       │
     └─────────────────┘          └─────────────────────┘
              │
     ┌────────▼────────┐
     │     Redis       │
     │  (Cache/Sessions)│
     │   Port: 6379    │
     └─────────────────┘
```

---

## Technology Stack

### Backend

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Framework** | FastAPI | Latest | REST API framework |
| **Language** | Python | 3.12+ | Backend logic |
| **ORM** | SQLAlchemy | 2.x | Database ORM |
| **Async Driver** | asyncpg | Latest | Async PostgreSQL |
| **Migrations** | Alembic | Latest | Database migrations |
| **Scheduler** | APScheduler | 3.x | Task scheduling |
| **MongoDB Driver** | Motor | Latest | Async MongoDB |
| **Redis Client** | redis-py | Latest | Redis client |
| **JWT** | PyJWT | Latest | JWT token handling |
| **Encryption** | Cryptography (Fernet) | Latest | Credential encryption |

---

### Frontend

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Framework** | React | 18.x | UI framework |
| **Language** | TypeScript | 5.x | Type safety |
| **Build Tool** | Vite | 4.x | Fast builds |
| **UI Library** | Ant Design | 5.x | UI components |
| **State** | Zustand | Latest | State management |
| **Data Fetching** | React Query | Latest | Server state |
| **Routing** | React Router | 6.x | Client routing |
| **Charts** | Ant Design Charts | Latest | Data visualization |
| **HTTP Client** | Axios | Latest | HTTP requests |

---

### Infrastructure

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Database** | PostgreSQL | 15 | Primary data store |
| **Document DB** | MongoDB | 6 | Expense line items |
| **Cache** | Redis | 7 | Caching & sessions |
| **Containerization** | Docker Compose | 2.x | Infrastructure orchestration |

---

## Database Architecture

### PostgreSQL Schema

**Core Tables:**
- `users` - User accounts
- `organizations` - Multi-tenant organizations
- `cloud_accounts` - Connected cloud provider accounts (encrypted credentials)
- `pools` - Budget pool hierarchy
- `roles` - RBAC roles
- `role_assignments` - User-role mappings
- `abac_policies` - Attribute-based access policies
- `rules` - Resource-to-pool assignment rules
- `conditions` - Rule conditions
- `recommendation_rules` - Custom recommendation rules
- `schedulers` - Scheduled tasks
- `scheduler_runs` - Run history
- `scheduler_logs` - Run logs
- `notifications` - Notification preferences
- `audit_logs` - Security audit trail
- `export_templates` - Export configurations
- `export_jobs` - Export job tracking
- `invitations` - User invitation tokens
- `feature_flags` - Runtime feature toggles

**Connection Pooling:**
- Pool size: 20 connections
- Max overflow: 40 connections
- Total max: 60 concurrent connections

---

### MongoDB Schema

**Collections:**
- `expenses` - Raw expense line items from cloud providers
- `resources` - Discovered cloud resources
- `recommendations` - Generated recommendations

**Document Structure (Expense):**
```json
{
  "cloud_account_id": "uuid",
  "date": "2026-04-09",
  "service": "EC2",
  "resource_id": "i-123abc",
  "resource_name": "prod-web-server",
  "cost": 12.50,
  "currency": "USD",
  "region": "us-east-1",
  "tags": {"environment": "production", "team": "backend"},
  "metadata": {...}
}
```

---

### Redis Usage

**Purposes:**
1. **Session Management**: JWT session storage with IP/fingerprint binding
2. **Rate Limiting**: Token bucket algorithm for API rate limits
3. **Caching**: 
   - Cloud live data (5 min TTL)
   - Expense summary (6 hour TTL)
   - Recommendations (10 min TTL)
   - Resources (5 min TTL)
4. **Token Blacklisting**: Immediate logout support
5. **Correlation IDs**: Request tracing

**Key Patterns:**
```
session:{session_id}        → Session data
ratelimit:{ip}:{endpoint}   → Rate limit counters
cache:{type}:{key}          → Cached data
blacklist:{token_jti}       → Blacklisted tokens
correlation:{request_id}    → Request correlation
```

---

## Middleware Stack

Applied in order for each request:

1. **CORS**: Cross-origin resource sharing
2. **CSRF**: Double-submit cookie pattern (exempts API endpoints)
3. **Health**: Restricts `/health/detailed` to localhost
4. **Metrics**: Prometheus metrics collection
5. **Correlation ID**: Request tracing ID generation
6. **Global Exception Handler**: Centralized error handling
7. **Idempotency**: Write operation deduplication
8. **Timeout**: Per-endpoint timeout enforcement
9. **Rate Limit**: Tiered rate limiting
10. **Input Validation**: Request size and content type checks
11. **GZip**: Response compression (>1000 bytes)

---

## Security Architecture

### Authentication Flow

```
1. User logs in (POST /auth/login)
2. Backend validates credentials
3. JWT access token generated (15-min expiry)
4. Token set as httpOnly cookie
5. Session stored in Redis with IP/fingerprint binding
6. Max 5 concurrent sessions per user (oldest evicted)
```

### Credential Encryption

```
Cloud Credentials → Fernet Encrypt → Store in PostgreSQL
                                              ↓
Decrypt when needed → Call Cloud API → Discard from memory
```

### Session Binding

```
Session = {
  user_id: "...",
  ip_hash: "...",
  user_agent_hash: "...",
  fingerprint: "...",
  created_at: "..."
}

On each request:
  - Validate IP matches
  - Validate User-Agent matches
  - Reject if mismatch (possible session hijacking)
```

---

## Caching Strategy

### Multi-Layer Caching

**Layer 1: Live Data Cache (5 min TTL)**
- Cloud provider API responses
- Per cloud account
- Stale-cache fallback (24 hours max)

**Layer 2: Expense Cache (6 hours TTL)**
- Aggregated expense summaries
- Auto-refresh enabled
- Fallback to live data

**Layer 3: Recommendations Cache (10 min TTL)**
- Generated recommendations
- Clearable via API
- Re-generated by scheduler

**Layer 4: Resources Cache (5 min TTL)**
- Resource inventory
- Auto-refresh on discovery

### Cache Keys

```
cloud:{account_id}:live_data
expense:{org_id}:summary:{start}:{end}
recommendations:{org_id}:{cloud_account_id}
resources:{org_id}:{filters}
```

### Graceful Degradation

```
Try: Fetch live data from cloud API
Catch: Return stale cache (if < 24 hours old)
Catch: Return error with helpful message
```

---

## Scheduler Architecture

### APScheduler Integration

**Job Stores:**
- In-memory (development)
- SQLAlchemy (production, persisted)

**Executors:**
- ThreadPoolExecutor (default)
- ProcessPoolExecutor (for CPU-intensive tasks)

**Job Types:**
1. **Expense Collection**: Fetch costs from cloud providers
2. **Resource Discovery**: Discover resources from cloud providers
3. **Recommendation Generation**: Analyze resources for optimization
4. **Custom Jobs**: User-defined scheduled tasks

### Failure Handling

```
Job Fails → Retry with exponential backoff (3 attempts)
         → Move to Dead Letter Queue
         → Manual retry or abandon
```

### Run History

```
Scheduler Run {
  status: pending | running | completed | failed | cancelled | partial
  started_at: timestamp
  ended_at: timestamp
  duration: seconds
  logs: [log entries]
}
```

---

## API Design

### RESTful Conventions

```
GET    /api/v1/resource           → List
GET    /api/v1/resource/{id}      → Get single
POST   /api/v1/resource           → Create
PATCH  /api/v1/resource/{id}      → Update
DELETE /api/v1/resource/{id}      → Delete
```

### Response Format

**Success:**
```json
{
  "data": {...},
  "meta": {
    "page": 1,
    "total": 100
  }
}
```

**Error:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": {...}
  }
}
```

### Rate Limits

| Tier | Limit | Use Case |
|------|-------|----------|
| Public | 30/min | Unauthenticated endpoints |
| Authenticated | 100/min | General authenticated |
| Expensive | 10/min | Costly operations |
| Export | 5/5min | Export creation |

---

## Deployment Architecture

### Docker Compose (Development/Small Scale)

```
docker-compose.yml
├── backend (FastAPI)
├── frontend (React)
├── db (PostgreSQL)
├── mongo (MongoDB)
└── redis (Redis)
```

### Production (Recommended)

```
Load Balancer (Nginx/ALB)
├── Backend (3+ instances)
│   └── FastAPI on multiple nodes
├── Frontend (CDN)
│   └── Static React build
├── PostgreSQL (RDS/Cloud SQL)
│   └── Multi-AZ, read replicas
├── MongoDB (Atlas)
│   └── Replica set
├── Redis (ElastiCache/Memorystore)
│   └── Cluster mode
└── Object Storage (S3/GCS)
    └── Export files
```

---

## Performance Characteristics

### Expected Load

- **Users**: 10-500 concurrent users
- **Cloud Accounts**: 1-50 accounts
- **Resources**: 100-100,000 resources
- **Expenses**: 1M-100M line items per month

### Response Times

| Endpoint Type | Target P95 |
|---------------|------------|
| Dashboard | < 500ms (cached) |
| Expense List | < 1s |
| Resource List | < 500ms |
| Cloud Live Data | < 5s (API call) |
| Export Creation | < 30s |
| Login | < 200ms |

---

## Monitoring

### Prometheus Metrics

**Available at:** `/metrics`

**Metrics:**
- Request count by endpoint
- Request duration histogram
- Active connections
- Cache hit/miss rates
- Scheduler run success/failure rates
- Database query duration

### Health Checks

**Simple:** `GET /health`
**Detailed:** `GET /health/detailed` (localhost only)

**Checks:**
- PostgreSQL connection
- MongoDB connection
- Redis connection
- Backend API status

---

## Future Architecture

### Planned Enhancements

- **Microservices**: Split into cost, user, notification services
- **Message Queue**: RabbitMQ/Kafka for async processing
- **Object Storage**: S3/GCS for export file storage
- **CDN**: CloudFront/Cloud CDN for frontend static assets
- **Observability**: OpenTelemetry tracing, Grafana dashboards
- **Kubernetes**: Helm chart for production deployment

---

## Next Steps

- **[Overview](overview.md)** - Feature capabilities
- **[Installation](installation.md)** - Deploy CostPilot
- **[Environment Variables](environment-variables.md)** - Configuration reference
- **[Troubleshooting](troubleshooting.md)** - Common issues

---

**Related Documentation:**
- [Security Best Practices](security-best-practices.md)
- [API Reference](api-reference.md)
