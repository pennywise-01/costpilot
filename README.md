# CostPilot — Cloud Cost Optimization Platform

> A full-stack platform for monitoring, analyzing, and optimizing cloud infrastructure costs across AWS, Azure, and GCP.

---

## Table of Contents

1. [Overview](#overview)
2. [Tech Stack](#tech-stack)
3. [Project Structure](#project-structure)
4. [Architecture](#architecture)
5. [Data Flow](#data-flow)
6. [Backend Modules](#backend-modules)
7. [Frontend Application](#frontend-application)
8. [Infrastructure & Deployment](#infrastructure--deployment)
9. [Development Setup](#development-setup)
10. [Testing](#testing)
11. [Data Flow Cleanup (May 2026)](#data-flow-cleanup-may-2026)

---

## Overview

CostPilot connects to cloud provider accounts (AWS, Azure, GCP), ingests cost and resource data, and presents it through a unified dashboard with recommendations for cost savings. Key capabilities:

- **Multi-cloud cost aggregation** — pulls billing data from AWS Cost Explorer, Azure Cost Management, and GCP Billing
- **Resource discovery** — enumerates compute, storage, and database resources across all connected accounts
- **Recommendation engine** — combines CSP-native recommendations (AWS Compute Optimizer, Azure Advisor, GCP Recommender) with custom rules
- **Budget pools** — logical groupings with spending limits and owner assignments
- **Scheduled data collection** — APScheduler-based jobs that refresh cost caches, discover resources, and fetch recommendations
- **Role-based access control** — enterprise-grade RBAC with ABAC policies, SSO support, and audit logging
- **Graceful degradation** — fallback chains (live → cache → degraded) ensure the UI always renders, even when cloud APIs are down

---

## Tech Stack

### Backend

| Component | Technology |
|-----------|-----------|
| Framework | [FastAPI](https://fastapi.tiangolo.com/) (async) |
| ORM | SQLAlchemy 2.0 (async, `asyncpg` driver) |
| Primary DB | PostgreSQL 16 |
| Document DB | MongoDB 7 (Motor async driver) |
| Cache / Sessions | Redis 7 |
| Scheduler | APScheduler 3.x (`AsyncIOScheduler`) |
| Auth | JWT (python-jose) + httpOnly cookies + server-side session binding |
| Cloud SDKs | boto3, azure-identity/azure-mgmt-*, google-cloud-* |
| Observability | OpenTelemetry, Prometheus metrics, structured JSON logging |
| Migrations | Alembic |

### Frontend

| Component | Technology |
|-----------|-----------|
| Framework | React 18 (Vite + SWC) |
| Language | TypeScript 5.6 |
| UI Library | Ant Design 5 |
| State Management | Zustand 5 |
| Data Fetching | @tanstack/react-query 5 + Axios |
| Routing | React Router 6 |
| Charts | @ant-design/charts |

---

## Project Structure

```
costpilot/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, middleware, router registration
│   │   ├── config.py               # Pydantic Settings (env-based configuration)
│   │   ├── database.py             # SQLAlchemy engine, session factory, MongoDB client
│   │   ├── models_registry.py      # Central model import for Base.metadata discovery
│   │   ├── auth/                   # Authentication (login, JWT, sessions, password reset)
│   │   ├── organizations/          # Multi-tenant organization management
│   │   ├── cloud_accounts/         # Cloud account CRUD, credential management, adapters
│   │   │   └── adapters/           # AWS, Azure, GCP adapter implementations
│   │   ├── expenses/               # Cost data fetching and aggregation
│   │   ├── cost_cache/             # Cached cost summaries (background refresh)
│   │   ├── resources/              # Cloud resource discovery and listing
│   │   ├── recommendations/        # CSP-native + custom rule recommendations
│   │   ├── recommendation_rules/   # User-defined custom recommendation rules
│   │   ├── pools/                  # Budget pools and spending limits
│   │   ├── rules/                  # Alert/notification rules
│   │   ├── dashboards/             # Dashboard CRUD + batch widget data endpoint
│   │   ├── scheduler/              # APScheduler integration, job execution
│   │   ├── notifications/          # Email/notification preferences
│   │   ├── user_management/        # User invitations, activity logs, preferences
│   │   ├── enterprise/             # RBAC, export, SSO modules
│   │   │   └── modules/
│   │   │       ├── rbac/           # Roles, permissions, ABAC policies
│   │   │       └── export/         # Data export (CSV, scheduled exports)
│   │   ├── advisor_findings/       # Cloud advisor finding ingestion
│   │   ├── config_ingestors/       # Cloud config snapshot ingestion
│   │   ├── security/               # Audit logging, security alerts
│   │   ├── idempotency/            # Idempotency key middleware
│   │   ├── health/                 # Health check endpoints
│   │   ├── metrics/                # Prometheus metrics
│   │   ├── middleware/              # Rate limiting, input validation, timeout, exception handling
│   │   └── shared/                 # Cross-cutting utilities
│   │       ├── crypto.py           # Fernet encryption/decryption
│   │       ├── password.py         # Password hashing (PBKDF2)
│   │       ├── degradation.py      # Graceful degradation fallback chains
│   │       ├── field_encryption.py # Per-field encryption for PII
│   │       ├── tracing.py          # OpenTelemetry tracing
│   │       ├── sync_bounded_cache.py # Thread-safe LRU cache with TTL
│   │       ├── request_coalescing.py # Dedup concurrent identical requests
│   │       └── ...
│   ├── alembic/                    # Database migrations
│   ├── tests/                      # Pytest test suite
│   └── scripts/                    # Utility scripts (seed data, diagnostics)
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 # Route definitions, auth/org guards
│   │   ├── main.tsx                # React entry point, QueryClient provider
│   │   ├── api/                    # API client modules (one per domain)
│   │   │   ├── client.ts           # Axios instance with interceptors
│   │   │   ├── auth.ts
│   │   │   ├── cloudAccounts.ts
│   │   │   ├── expenses.ts
│   │   │   ├── recommendations.ts
│   │   │   ├── pools.ts
│   │   │   └── ...
│   │   ├── pages/                  # Route-level page components
│   │   ├── components/             # Reusable UI components
│   │   ├── store/                  # Zustand stores
│   │   │   ├── authStore.ts        # Authentication state
│   │   │   ├── orgStore.ts         # Organization selection state
│   │   │   ├── dashboardStore.ts   # Dashboard layout state
│   │   │   └── userStore.ts        # User preferences
│   │   ├── hooks/                  # Custom React hooks
│   │   ├── types/                  # TypeScript type definitions
│   │   └── utils/                  # Constants, formatters, route definitions
│   └── package.json
├── docker-compose.yml              # Full-stack Docker Compose
├── plans/                          # Architecture plans and audit reports
└── tests/                          # Browser-based E2E test cases
```

---

## Architecture

### Layered Architecture

CostPilot follows a **layered architecture** with clear separation of concerns:

**Text version:**

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│  Pages → API modules → Axios client → Backend           │
│  State: Zustand stores (auth, org, dashboard)           │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP (REST API)
┌────────────────────────▼────────────────────────────────┐
│                  FastAPI Routers                         │
│  Auth, CloudAccounts, Expenses, Resources,              │
│  Recommendations, Pools, Dashboards, Scheduler, ...     │
│  Middleware: RateLimit, InputValidation, Timeout,        │
│             Idempotency, Metrics, SessionBinding         │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                  Service Layer                           │
│  Domain logic, business rules, orchestration            │
│  Each module has its own service.py                     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              Data Access Layer                           │
│  SQLAlchemy (PostgreSQL) — relational data              │
│  Motor (MongoDB) — cost documents, recommendations      │
│  Redis — sessions, token blacklist, rate limits         │
│  Cloud Adapters — AWS/Azure/GCP API clients             │
└─────────────────────────────────────────────────────────┘
```

**Diagram version:**

```mermaid
flowchart TD
    subgraph FE["Frontend (React + TypeScript)"]
        Pages[Page Components] --> APIModules[API Modules]
        APIModules --> Axios[Axios Client + Interceptors]
        Stores[Zustand Stores<br/>authStore · orgStore · dashboardStore]
    end

    subgraph MW["Middleware Stack"]
        direction LR
        RL[Rate Limiting]
        IV[Input Validation]
        TO[Timeout]
        ID[Idempotency]
        MT[Metrics]
        SB[Session Binding]
    end

    subgraph Routers["FastAPI Routers"]
        direction LR
        AuthR[auth]
        CAR[cloud_accounts]
        ExpR[expenses]
        ResR[resources]
        RecR[recommendations]
        PoolR[pools]
        DashR[dashboards]
        SchedR[scheduler]
    end

    subgraph Services["Service Layer"]
        direction LR
        AuthS[auth/service]
        CAS[cloud_accounts/service]
        ExpS[expenses/service]
        ResS[resources/service]
        RecS[recommendations/service]
        PoolS[pools/service]
        DashB[dashboards/batch]
        SchedE[scheduler/executor]
    end

    subgraph DAL["Data Access Layer"]
        PG[(PostgreSQL<br/>SQLAlchemy + asyncpg)]
        Mongo[(MongoDB<br/>Motor)]
        Redis[(Redis<br/>sessions · cache · rate limits)]
        Cloud["Cloud Adapters<br/>AWS · Azure · GCP"]
    end

    Axios -->|HTTP REST| MW
    MW --> Routers
    Routers --> Services
    Services --> DAL

    style FE fill:#e3f2fd,stroke:#1976d2
    style MW fill:#fff8e1,stroke:#f9a825
    style Routers fill:#f3e5f5,stroke:#7b1fa2
    style Services fill:#e8f5e9,stroke:#388e3c
    style DAL fill:#fce4ec,stroke:#c62828
```

### Dependency Direction

**Text version:**

```
shared/  ←── (leaf dependency, no upward imports except documented exceptions)
  ↑
auth/  ←── user_management/ (imports shared/password.py, not auth internals)
  ↑
organizations/  ←── cloud_accounts/ ←── expenses/, resources/, cost_cache/
  ↑
pools/  (standalone, no cross-domain imports)
recommendations/  ←→ recommendation_rules/ (via public accessor functions)
dashboards/  ←── (reads from services, not direct ORM)
scheduler/  ←── (orchestrates services, uses public APIs)
```

**Diagram version:**

```mermaid
flowchart BT
    shared["shared/<br/>(leaf — no upward imports)"]
    auth["auth/"]
    um["user_management/"]
    org["organizations/"]
    ca["cloud_accounts/"]
    exp["expenses/"]
    cc["cost_cache/"]
    res["resources/"]
    rec["recommendations/"]
    rr["recommendation_rules/"]
    pools["pools/<br/>(standalone)"]
    dash["dashboards/"]
    sched["scheduler/"]

    um -->|shared/password| shared
    auth --> shared
    ca --> org
    exp --> ca
    cc --> ca
    res --> ca
    rec --> rr
    rr --> rec
    dash --> cc
    dash --> res
    dash --> rec
    dash --> ca
    dash --> pools
    dash --> org
    sched --> cc
    sched --> res
    sched --> rec

    style shared fill:#e8f5e9,stroke:#388e3c
    style pools fill:#e3f2fd,stroke:#1976d2
    style dash fill:#fce4ec,stroke:#c62828
    style sched fill:#fff3e0,stroke:#e65100

---

## Data Flow

### 1. Authentication Flow

**Text version:**

```
User → Login page → POST /api/v1/auth/login
  → auth/router.py → auth/service.py::authenticate_user()
    → verify_password() (shared/password.py)
    → create_session_binding() → Redis + PostgreSQL
    → create_access_token() → JWT (httpOnly cookie)
  → Frontend: authStore.setAuth() → orgStore subscribes to auth changes
  → Navigate to / (Dashboard)
```

**Diagram version:**

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant FE as Frontend
    participant API as FastAPI Router
    participant Auth as auth/service.py
    participant PW as shared/password.py
    participant Redis as Redis
    participant PG as PostgreSQL

    U->>FE: Submit login form
    FE->>API: POST /api/v1/auth/login
    API->>Auth: authenticate_user(email, password)
    Auth->>PW: verify_password(plain, hashed)
    PW-->>Auth: true
    Auth->>PG: Update last_login, reset failed_attempts
    Auth->>Redis: create_session_binding(user_id, session_id)
    Auth->>PG: Insert SessionBinding record
    Auth-->>API: User object
    API-->>FE: Set-Cookie: access_token (httpOnly, Secure)
    FE->>FE: authStore.setAuth(token, user)
    FE->>FE: orgStore subscribes → detects user change
    FE->>U: Navigate to / (Dashboard)
```

### 2. Cost Data Flow (Dashboard Batch Endpoint)

**Text version:**

```
Dashboard page loads
  → useQuery(['dashboard-batch', orgId])
    → POST /api/v1/dashboards/batch (batch widget data)
      → dashboards/batch.py::_group_by_data_source()
        Groups widgets by data source for deduplication
      → _fetch_expense_summary() → cost_cache/service.py::get_cached_summary()
        → Returns cached data if fresh, schedules background refresh if stale
      → _fetch_expense_breakdown() → cost_cache/service.py::get_cached_breakdown()
      → _fetch_resources() → resources/service.py::list_resources()
        → Checks in-memory cache → falls back to cloud API discovery
      → _fetch_recommendations_overview() → recommendations/service.py
      → _fetch_cloud_accounts() → cloud_accounts/service.py::list_cloud_accounts()
      → _fetch_pools() → pools/service.py::get_pool_tree()
      → _fetch_budget() → organizations/service.py + pools/service.py
  → Response includes X-Data-Source and X-Data-Freshness headers
```

**Diagram version:**

```mermaid
sequenceDiagram
    participant D as Dashboard Page
    participant RQ as react-query
    participant API as /api/v1/dashboards/batch
    participant B as batch.py
    participant CC as cost_cache/service
    participant RS as resources/service
    participant REC as recommendations/service
    participant CA as cloud_accounts/service
    participant PL as pools/service
    participant Cloud as AWS / Azure / GCP

    D->>RQ: useQuery(['dashboard-batch', orgId])
    RQ->>API: POST (widget requests)
    API->>B: _group_by_data_source(widgets)

    par Parallel data fetch
        B->>CC: get_cached_summary(org_id)
        CC-->>B: CachedExpenseSummary
    and
        B->>CC: get_cached_breakdown(org_id, group_by)
        CC-->>B: CachedExpenseBreakdown
    and
        B->>RS: list_resources(org_id)
        RS->>RS: Check SyncBoundedCache
        alt Cache hit
            RS-->>B: ResourceListResponse (cached)
        else Cache miss
            RS->>Cloud: discover_resources()
            Cloud-->>RS: Resource data
            RS->>RS: Cache results
            RS-->>B: ResourceListResponse (live)
        end
    and
        B->>REC: get_recommendations_overview(org_id)
        REC-->>B: RecommendationsOverview
    and
        B->>CA: list_cloud_accounts(org_id)
        CA-->>B: CloudAccount list
    and
        B->>PL: get_pool_tree(org_id)
        PL-->>B: PoolResponse tree
    end

    B-->>API: Mapped widget data
    API-->>D: Response + X-Data-Source + X-Data-Freshness headers
```

### 3. Scheduled Data Collection Flow

**Text version:**

```
APScheduler triggers job
  → scheduler/executor.py::execute_scheduler_job()
    → Phase 1: Expenses
      → cost_cache/service.py::refresh_cost_cache()
        → Fetches from AWS/Azure/GCP adapters
        → Stores in PostgreSQL cost_cache table
    → Phase 2: Resources
      → resources/service.py::discover_all_resources()
        → Enumerates resources from all connected cloud accounts
        → Caches results in-memory (SyncBoundedCache)
    → Phase 3: Recommendations
      → recommendations/csp_service.py::fetch_csp_recommendations()
      → advisor_findings/service.py::collect_advisor_findings_for_org()
      → config_ingestors/service.py::collect_config_snapshots_for_org()
    → Updates SchedulerRun record with final status
    → If max failures reached → DeadLetterJob
```

**Diagram version:**

```mermaid
sequenceDiagram
    participant APS as APScheduler
    participant EX as scheduler/executor.py
    participant CC as cost_cache/service
    participant RS as resources/service
    participant CSP as recommendations/csp_service
    participant ADV as advisor_findings/service
    participant CFG as config_ingestors/service
    participant PG as PostgreSQL
    participant Cloud as AWS / Azure / GCP

    APS->>EX: execute_scheduler_job(scheduler_id)
    EX->>PG: Create SchedulerRun (status=RUNNING)

    rect rgb(240, 248, 255)
        Note over EX,Cloud: Phase 1 — Expenses
        EX->>CC: refresh_cost_cache(session, org_id)
        CC->>Cloud: Fetch billing data (per account)
        Cloud-->>CC: Cost data
        CC->>PG: Upsert CostCache records
        CC-->>EX: CacheRefreshResult
        EX->>PG: Update SchedulerRun (expenses_status)
    end

    rect rgb(240, 255, 240)
        Note over EX,Cloud: Phase 2 — Resources
        EX->>RS: discover_all_resources(org_id)
        RS->>Cloud: Enumerate resources (per account)
        Cloud-->>RS: Resource list
        RS->>RS: Cache in SyncBoundedCache
        RS-->>EX: (resources, partial_failures)
        EX->>PG: Update SchedulerRun (resources_status)
    end

    rect rgb(255, 248, 240)
        Note over EX,Cloud: Phase 3 — Recommendations
        EX->>CSP: fetch_csp_recommendations(db, mongo, org_id)
        CSP->>Cloud: Fetch CSP recommendations
        Cloud-->>CSP: NormalizedRecommendation list
        EX->>ADV: collect_advisor_findings_for_org(db, org_id)
        EX->>CFG: collect_config_snapshots_for_org(db, org_id)
        EX->>PG: Update SchedulerRun (recommendations_status)
    end

    EX->>PG: Update SchedulerRun (status=COMPLETED|FAILED|PARTIAL)
    alt Max failures reached
        EX->>PG: Insert DeadLetterJob
        EX->>APS: Unschedule job
    end
```

### 4. Graceful Degradation Flow

**Text version:**

```
Request arrives → shared/degradation.py
  → Try live data from cloud API
    → Success: return (data, "live", 0)
    → Failure: log warning, try cache
  → Try cached data
    → Success: return (data, "cached"|"stale", freshness_seconds)
    → Failure: log warning, return degraded
  → Return degraded response
    → (empty_data, "unavailable", -1)
  → Response headers: X-Data-Source, X-Data-Freshness
```

**Diagram version:**

```mermaid
flowchart TD
    A[Incoming Request] --> B{Try live data<br/>from cloud API}
    B -->|Success| C[Return data<br/>source=live, freshness=0]
    B -->|Failure| D{Try cached data}
    D -->|Success| E{Is cache fresh?}
    E -->|Yes| F[Return data<br/>source=cached]
    E -->|No| G[Return data<br/>source=stale]
    D -->|Failure| H[Return degraded response<br/>source=unavailable]

    C --> I[Set response headers]
    F --> I
    G --> I
    H --> I

    I --> J["X-Data-Source: live | cached | stale | unavailable"]
    I --> K["X-Data-Freshness: seconds since last update"]

    style C fill:#d4edda,stroke:#28a745
    style F fill:#fff3cd,stroke:#ffc107
    style G fill:#fff3cd,stroke:#ffc107
    style H fill:#f8d7da,stroke:#dc3545
```

### 5. Frontend State Management Flow

**Text version:**

```
┌──────────────┐     subscribe()     ┌──────────────┐
│  authStore   │ ──────────────────→ │   orgStore   │
│              │                     │              │
│  user state  │  (clears org on     │  currentOrg  │
│  login/logout│   user change)      │  orgs list   │
└──────────────┘                     └──────────────┘
        │                                    │
        ▼                                    ▼
  ProtectedRoute                      OrgGuard
  (redirects to /login                (shows SelectOrganization
   if no user)                         if no org selected)
```

**Diagram version:**

```mermaid
flowchart LR
    subgraph authStore["authStore (Zustand)"]
        A1[user: User | null]
        A2[setAuth / setUser / logout]
    end

    subgraph orgStore["orgStore (Zustand)"]
        O1[currentOrg: OrgWithRole]
        O2[organizations: OrgWithRole[]]
        O3[clearOrg]
    end

    A2 -->|"subscribe() detects<br/>user change"| O3

    subgraph Guards["Route Guards"]
        G1[ProtectedRoute]
        G2[OrgGuard]
    end

    A1 --> G1
    G1 -->|"user === null"| R1["Redirect → /login"]
    G1 -->|"user exists"| G2
    O1 --> G2
    G2 -->|"currentOrg === null"| R2["Show SelectOrganization"]
    G2 -->|"org selected"| R3["Render page"]

    style authStore fill:#e3f2fd,stroke:#1976d2
    style orgStore fill:#f3e5f5,stroke:#7b1fa2
    style Guards fill:#fff8e1,stroke:#f9a825
```

### 6. Module Dependency Graph (Cleaned Up)

```mermaid
flowchart TD
    subgraph shared["shared/ (leaf — no upward imports)"]
        password[password.py]
        crypto[crypto.py]
        degradation[degradation.py]
        cache[sync_bounded_cache.py]
        coalescing[request_coalescing.py]
        tracing[tracing.py]
        encryption[field_encryption.py]
    end

    subgraph auth["auth/"]
        auth_svc[service.py]
        auth_router[router.py]
        token_mgr[token_manager.py]
    end

    subgraph um["user_management/"]
        um_svc[service.py]
        um_router[router.py]
    end

    subgraph org["organizations/"]
        org_svc[service.py]
    end

    subgraph ca["cloud_accounts/"]
        ca_svc[service.py]
        ca_adapters[adapters/ aws, azure, gcp]
    end

    subgraph exp["expenses/"]
        exp_svc[service.py]
    end

    subgraph cc["cost_cache/"]
        cc_svc[service.py]
    end

    subgraph res["resources/"]
        res_svc[service.py]
    end

    subgraph rec["recommendations/"]
        rec_svc[service.py]
        csp_svc[csp_service.py]
    end

    subgraph rr["recommendation_rules/"]
        rr_svc[service.py]
    end

    subgraph pools["pools/"]
        pools_svc[service.py]
    end

    subgraph dash["dashboards/"]
        dash_batch[batch.py]
    end

    subgraph sched["scheduler/"]
        sched_exec[executor.py]
    end

    %% Shared utilities
    password -.->|used by| auth_svc
    password -.->|used by| um_svc

    %% Auth dependencies
    um_svc -->|shared/password| password
    um_router -->|create_access_token| auth_svc

    %% Cloud account dependencies
    ca_svc --> ca_adapters
    exp_svc --> ca_adapters
    cc_svc --> ca_adapters
    res_svc --> ca_adapters

    %% Recommendations
    rec_svc -->|evaluate_custom_rules| rr_svc
    csp_svc -->|get_well_architected_rules| rec_svc

    %% Scheduler orchestrates services
    sched_exec --> cc_svc
    sched_exec --> res_svc
    sched_exec --> csp_svc

    %% Dashboards route through services
    dash_batch --> cc_svc
    dash_batch --> res_svc
    dash_batch --> rec_svc
    dash_batch --> ca_svc
    dash_batch --> pools_svc
    dash_batch --> org_svc

    %% Degradation uses deferred imports (documented)
    degradation -.->|deferred import| exp_svc
    degradation -.->|deferred import| res_svc
    degradation -.->|deferred import| cc_svc
    degradation -.->|deferred import| rec_svc

    %% Pools is standalone
    pools_svc -.->|no cross-domain imports| pools_svc

    style shared fill:#e8f5e9,stroke:#388e3c
    style auth fill:#e3f2fd,stroke:#1976d2
    style um fill:#e3f2fd,stroke:#1976d2
    style sched fill:#fff3e0,stroke:#e65100
    style dash fill:#fce4ec,stroke:#c62828
    style degradation fill:#fff8e1,stroke:#f9a825

---

## Backend Modules

### Core Modules

| Module | Purpose | Key Files |
|--------|---------|-----------|
| [`auth/`](backend/app/auth/) | Authentication, JWT, sessions, password reset | [`service.py`](backend/app/auth/service.py), [`router.py`](backend/app/auth/router.py), [`token_manager.py`](backend/app/auth/token_manager.py) |
| [`organizations/`](backend/app/organizations/) | Multi-tenant org management, employee records | [`service.py`](backend/app/organizations/service.py) |
| [`cloud_accounts/`](backend/app/cloud_accounts/) | Cloud account CRUD, credential vault, adapters | [`service.py`](backend/app/cloud_accounts/service.py), [`adapters/`](backend/app/cloud_accounts/adapters/) |
| [`expenses/`](backend/app/expenses/) | Cost data fetching from cloud providers | [`service.py`](backend/app/expenses/service.py) |
| [`cost_cache/`](backend/app/cost_cache/) | Background cost cache refresh, cached summaries | [`service.py`](backend/app/cost_cache/service.py) |
| [`resources/`](backend/app/resources/) | Cloud resource discovery and listing | [`service.py`](backend/app/resources/service.py) |
| [`recommendations/`](backend/app/recommendations/) | CSP-native + custom rule recommendations | [`service.py`](backend/app/recommendations/service.py), [`csp_service.py`](backend/app/recommendations/csp_service.py) |
| [`pools/`](backend/app/pools/) | Budget pools, spending limits, owner assignment | [`service.py`](backend/app/pools/service.py) |
| [`dashboards/`](backend/app/dashboards/) | Dashboard CRUD, batch widget data endpoint | [`batch.py`](backend/app/dashboards/batch.py) |
| [`scheduler/`](backend/app/scheduler/) | APScheduler integration, job execution | [`executor.py`](backend/app/scheduler/executor.py) |

### Cross-Cutting Modules

| Module | Purpose |
|--------|---------|
| [`shared/`](backend/app/shared/) | Crypto, password hashing, degradation, caching, tracing, enums |
| [`middleware/`](backend/app/middleware/) | Rate limiting, input validation, timeout, exception handling |
| [`security/`](backend/app/security/) | Audit logging, security alerts |
| [`metrics/`](backend/app/metrics/) | Prometheus metrics endpoint |
| [`health/`](backend/app/health/) | Health check endpoints |

### Shared Utilities

| File | Purpose |
|------|---------|
| [`shared/password.py`](backend/app/shared/password.py) | Password hashing (PBKDF2-HMAC-SHA256) — used by both `auth` and `user_management` |
| [`shared/crypto.py`](backend/app/shared/crypto.py) | Fernet encryption for cloud credentials |
| [`shared/degradation.py`](backend/app/shared/degradation.py) | Graceful degradation with live → cache → degraded fallback chains |
| [`shared/sync_bounded_cache.py`](backend/app/shared/sync_bounded_cache.py) | Thread-safe LRU cache with TTL (used by resources, recommendations) |
| [`shared/request_coalescing.py`](backend/app/shared/request_coalescing.py) | Deduplicates concurrent identical cloud API calls |
| [`shared/field_encryption.py`](backend/app/shared/field_encryption.py) | Per-field encryption for PII data |
| [`shared/tracing.py`](backend/app/shared/tracing.py) | OpenTelemetry distributed tracing |
| [`models_registry.py`](backend/app/models_registry.py) | Central model import for SQLAlchemy metadata discovery |

---

## Frontend Application

### Page Components

| Page | Route | Data Pattern |
|------|-------|-------------|
| [`Login`](frontend/src/pages/Login.tsx) | `/login` | Mutation (authApi.login) |
| [`Register`](frontend/src/pages/Register.tsx) | `/register` | Mutation (authApi.register) |
| [`Dashboard`](frontend/src/pages/Dashboard.tsx) | `/` | `useQuery` (batch widget data) |
| [`Expenses`](frontend/src/pages/Expenses.tsx) | `/expenses` | `useQuery` |
| [`Recommendations`](frontend/src/pages/Recommendations.tsx) | `/recommendations` | `useQuery` |
| [`CloudAccounts`](frontend/src/pages/CloudAccounts.tsx) | `/cloud-accounts` | `useQuery` |
| [`Resources`](frontend/src/pages/Resources.tsx) | `/resources` | `useQuery` |
| [`Pools`](frontend/src/pages/Pools.tsx) | `/pools` | `useQuery` |
| [`Users`](frontend/src/pages/Users.tsx) | `/users` | `useQuery` |
| [`Schedulers`](frontend/src/pages/Schedulers.tsx) | `/schedulers` | `useQuery` |
| [`Settings`](frontend/src/pages/Settings.tsx) | `/settings` | Mutation |
| [`RBAC`](frontend/src/pages/RBAC.tsx) | `/rbac` | `useQuery` |
| [`Exports`](frontend/src/pages/Exports.tsx) | `/exports` | `useQuery` |

### State Management

| Store | File | Purpose |
|-------|------|---------|
| `useAuthStore` | [`authStore.ts`](frontend/src/store/authStore.ts) | User authentication state (user, login/logout) |
| `useOrgStore` | [`orgStore.ts`](frontend/src/store/orgStore.ts) | Organization selection (subscribes to auth changes) |
| `useDashboardStore` | [`dashboardStore.ts`](frontend/src/store/dashboardStore.ts) | Dashboard layout persistence |
| `useUserStore` | [`userStore.ts`](frontend/src/store/userStore.ts) | User preferences |

### API Client

The [`api/client.ts`](frontend/src/api/client.ts) Axios instance includes:

- **Request interceptor** — attaches browser fingerprint header for session binding
- **Response interceptor** — handles 401 (logout + redirect to `/login`) and 403 org membership errors (clear org + redirect to `/`) with console logging for debugging

---

## Infrastructure & Deployment

### Docker Compose Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `backend` | Custom (Python 3.12) | 8000 | FastAPI application |
| `frontend` | Custom (Nginx) | 5173 | React SPA served via Nginx |
| `postgres` | postgres:16-alpine | 5432 | Primary relational database |
| `mongodb` | mongo:7 | 27017 | Document store for cost data |
| `redis` | redis:7-alpine | 6379 | Session cache, rate limiting |

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/costpilot
MONGODB_URL=mongodb://user:pass@host:27017/costpilot?authSource=admin
REDIS_URL=redis://:pass@host:6379/0

# Security
JWT_SECRET=<generate with: python -c "import secrets; print(secrets.token_urlsafe(64))">
ENCRYPTION_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# Optional
CORS_ORIGINS=["http://localhost:5173"]
DEBUG=false
```

---

## Development Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 16
- MongoDB 7
- Redis 7

### Backend

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Docker (Full Stack)

```bash
cp .env.example .env  # Edit with your values
docker compose up --build
```

---

## Testing

### Backend Tests

```bash
cd backend
python -m pytest tests/ -v
```

Test categories (via pytest markers):
- `@pytest.mark.unit` — Unit tests for individual components
- `@pytest.mark.integration` — Integration tests across modules
- `@pytest.mark.e2e` — End-to-end flow tests
- `@pytest.mark.security` — Security-related tests

### Frontend Type Checking

```bash
cd frontend
npx tsc --noEmit
```

---

## Data Flow Cleanup (May 2026)

The codebase underwent a comprehensive dataflow audit and cleanup. The following issues were identified and resolved:

### Critical Fixes

| # | Issue | Resolution |
|---|-------|-----------|
| 10 | **Bare `except:` clauses** catching `SystemExit`/`KeyboardInterrupt` in [`token_manager.py`](backend/app/auth/token_manager.py) | Changed to `except (ValueError, SyntaxError)` with `logger.warning()` |
| 10 | **Silent `except Exception: pass`** in 10+ locations across [`recommendations/service.py`](backend/app/recommendations/service.py), [`pools/service.py`](backend/app/pools/service.py), [`auth/router.py`](backend/app/auth/router.py) | Added specific exception types and `logger.warning()` calls |
| 2 | **Scheduler session explosion** — 15+ separate DB sessions per job run in [`executor.py`](backend/app/scheduler/executor.py) | Removed redundant config reload session |

### Structural Fixes

| # | Issue | Resolution |
|---|-------|-----------|
| 7 | **`user_management → auth` tight coupling** — importing `hash_password` from `auth.service` | Extracted to [`shared/password.py`](backend/app/shared/password.py); both modules now import from shared |
| 5 | **Dead coupling `pools → expenses`** — unused `get_expense_summary` import | Removed the import from [`pools/service.py`](backend/app/pools/service.py) |
| 15 | **Private function imports** — `_discover_all_resources`, `_get_cached_resources` used as public API | Renamed to [`discover_all_resources`](backend/app/resources/service.py:117) and [`get_cached_resources`](backend/app/resources/service.py:31); updated all consumers |
| 12 | **`main.py` model import fan-out** — 15 imports from 12 modules | Created [`models_registry.py`](backend/app/models_registry.py); `main.py` now imports one module |
| 6 | **Bidirectional `recommendations ↔ recommendation_rules`** — private `_WELL_ARCHITECTED_RULES` imported across modules | Added public [`get_well_architected_rules()`](backend/app/recommendations/service.py:838) accessor |
| 4 | **`dashboards/batch.py` bypassing service layers** — direct ORM queries for CloudAccount, Pool, Organization | Routed through [`cloud_accounts/service.py`](backend/app/cloud_accounts/service.py), [`pools/service.py`](backend/app/pools/service.py), [`organizations/service.py`](backend/app/organizations/service.py) |

### Observability Fixes

| # | Issue | Resolution |
|---|-------|-----------|
| 9 | **Global singletons without logging** — 8 singletons initialized silently | Added `logger.info()` to initialization in [`database.py`](backend/app/database.py), [`field_encryption.py`](backend/app/shared/field_encryption.py), [`audit_logger.py`](backend/app/security/audit_logger.py), [`credential_cache.py`](backend/app/cloud_accounts/credential_cache.py) |
| 8 | **Module-level mutable caches invisible to monitoring** | Added cache initialization logging in [`cloud_accounts/router.py`](backend/app/cloud_accounts/router.py) |
| 3 | **`shared/degradation.py` upward imports hidden from static analysis** | Added architecture documentation explaining the deferred import pattern and fallback chain semantics |

### Frontend Fixes

| # | Issue | Resolution |
|---|-------|-----------|
| 14 | **`authStore ↔ orgStore` cross-store side effects** — auth store directly called `orgStore.clearOrg()` | Removed direct calls from [`authStore.ts`](frontend/src/store/authStore.ts); added Zustand `subscribe()` in [`orgStore.ts`](frontend/src/store/orgStore.ts) to react to auth changes |
| 15 | **Silent navigation on 401/403 errors** — no logging in axios interceptor | Added `console.warn()` logging to [`api/client.ts`](frontend/src/api/client.ts) interceptor |

### Cleaned-Up Dependency Graph

**Text version:**

```
scheduler/executor ──→ expenses/service ──→ cloud_accounts/adapters
        │                    │
        ├──→ resources/service (public: discover_all_resources)
        ├──→ cost_cache/service
        ├──→ recommendations/csp_service ──→ recommendations/service
        │                                      ↑ (public: get_well_architected_rules)
        ├──→ advisor_findings/service          │
        └──→ config_ingestors/service    recommendation_rules/service

shared/degradation ──→ expenses/service   (documented upward import)
                   ──→ resources/service   (public: get_cached_resources)
                   ──→ cost_cache/service
                   ──→ recommendations/service

dashboards/batch ──→ cost_cache/service
               ──→ resources/service
               ──→ recommendations/service
               ──→ cloud_accounts/service  (via service layer, not direct ORM)
               ──→ pools/service           (via service layer, not direct ORM)
               ──→ organizations/service   (via service layer, not direct ORM)

pools/service ──→ (no cross-domain imports)
user_management/service ──→ shared/password (not auth/service)
```

**Diagram version:** See the [Module Dependency Graph](#6-module-dependency-graph-cleaned-up) in the Data Flow section above for the full Mermaid diagram.

Key changes:
- **`pools/service`** — no longer imports from `expenses/service` (dead coupling removed)
- **`user_management/service`** — imports from `shared/password` instead of `auth/service`
- **`dashboards/batch`** — routes through service layers instead of direct ORM queries
- **`resources/service`** — public functions `discover_all_resources()` and `get_cached_resources()` replace private `_` prefixed names
- **`recommendations/csp_service`** — uses public `get_well_architected_rules()` accessor instead of importing private `_WELL_ARCHITECTED_RULES`
- **`shared/degradation`** — documented upward imports with architecture notes explaining the deferred import pattern
- **`main.py`** — single `import app.models_registry` replaces 15 individual model imports
