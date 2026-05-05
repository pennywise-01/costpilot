# Spaghetti Dataflow Audit — CostPilot

> **Date:** 2026-05-05  
> **Scope:** Full codebase (backend + frontend)  
> **Purpose:** Identify tangled dataflow patterns that will make future debugging significantly harder.

---

## Table of Contents

1. [Backend: Cross-Module Service Dependencies](#1-backend-cross-module-service-dependencies)
2. [Backend: `scheduler/executor.py` — God Module](#2-backendschedulerexecutorpy--god-module)
3. [Backend: `shared/degradation.py` — Upward Imports from Shared](#3-backendshareddegradationpy--upward-imports-from-shared)
4. [Backend: `dashboards/batch.py` — Fan-Out Aggregator Bypassing Service Layers](#4-backenddashboardsbatchpy--fan-out-aggregator-bypassing-service-layers)
5. [Backend: `pools/service.py` → `expenses/service.py` — Cross-Domain Coupling](#5-backendpoolsservicepy--expensesservicepy--cross-domain-coupling)
6. [Backend: `recommendations` ↔ `recommendation_rules` — Bidirectional Dependency](#6-backendrecommendations--recommendation_rules--bidirectional-dependency)
7. [Backend: `user_management` → `auth` — Tight Coupling on Internal Implementation](#7-backenduser_management--auth--tight-coupling-on-internal-implementation)
8. [Backend: Module-Level Mutable Caches in Routers/Services](#8-backend-module-level-mutable-caches-in-routersservices)
9. [Backend: Global Singletons via `global` Keyword](#9-backend-global-singletons-via-global-keyword)
10. [Backend: Bare `except` Clauses and Silent Exception Swallowing](#10-backend-bare-except-clauses-and-silent-exception-swallowing)
11. [Backend: Services Creating Their Own DB Sessions](#11-backend-services-creating-their-own-db-sessions)
12. [Backend: `main.py` Model Import Fan-Out](#12-backendmainpy-model-import-fan-out)
13. [Frontend: Three Different Data Fetching Paradigms](#13-frontend-three-different-data-fetching-paradigms)
14. [Frontend: `authStore` ↔ `orgStore` Cross-Store Side Effects](#14-frontend-authstore--orgstore-cross-store-side-effects)
15. [Frontend: `api/client.ts` — Silent Navigation on Errors](#15-frontend-apiclientts--silent-navigation-on-errors)
16. [Dependency Graph Summary](#16-dependency-graph-summary)
17. [Risk Ranking](#17-risk-ranking)

---

## 1. Backend: Cross-Module Service Dependencies

The codebase has **48 cross-module service imports** and **76 cross-module model imports**. The following modules are the worst offenders:

| Importing Module | Imports From | Count |
|---|---|---|
| `scheduler/executor.py` | `expenses`, `resources`, `recommendations`, `cost_cache`, `advisor_findings`, `config_ingestors` | 6 |
| `shared/degradation.py` | `expenses`, `resources`, `cost_cache`, `recommendations` | 4 |
| `dashboards/batch.py` | `cost_cache`, `resources`, `recommendations`, `cloud_accounts`, `pools`, `organizations` | 6 |
| `enterprise/modules/export/service.py` | `expenses`, `resources`, `recommendations` | 3 |
| `enterprise/modules/export/router.py` | `expenses`, `resources`, `recommendations` | 3 |
| `pools/service.py` | `expenses`, `organizations` | 2 |
| `recommendations/service.py` | `recommendation_rules`, `cloud_accounts` | 2 |
| `recommendations/csp_service.py` | `recommendations/service` (back-reference) | 1 |
| `user_management/service.py` | `auth` | 1 |
| `user_management/router.py` | `auth` | 1 |

**Why this matters:** Each arrow above is a debugging liability. When `scheduler/executor.py` fails, the root cause could be in any of 6 different service modules, each with their own error handling, session management, and caching logic.

---

## 2. Backend: `scheduler/executor.py` — God Module

**File:** [`backend/app/scheduler/executor.py`](backend/app/scheduler/executor.py) (634 lines)

This single file directly imports and calls into **6 different service modules**:

- [`get_expense_summary`, `get_expense_breakdown`](backend/app/expenses/service.py:18) from `expenses.service`
- [`fetch_csp_recommendations`](backend/app/recommendations/csp_service.py:19) from `recommendations.csp_service`
- [`_discover_all_resources`](backend/app/resources/service.py:20) from `resources.service` (private function!)
- [`refresh_cost_cache`](backend/app/cost_cache/service.py:213) from `cost_cache.service`
- [`collect_advisor_findings_for_org`](backend/app/advisor_findings/service.py:323) from `advisor_findings.service`
- [`collect_config_snapshots_for_org`](backend/app/config_ingestors/service.py:395) from `config_ingestors.service`

### Session Explosion

The executor opens **~15 separate `async_session_factory()` sessions** across a single job run:

| Line | Purpose |
|------|---------|
| 60 | Load schedulers from DB |
| 154 | Get scheduler config |
| 190 | Reload config after session close |
| 214 | Refresh cost cache |
| 222 | Update run record (expenses success) |
| 261 | Update run record (expenses failure) |
| 285 | Update run record (resources success) |
| 302 | Update run record (resources failure) |
| 327 | Fetch CSP recommendations |
| 336 | Collect advisor findings |
| 351 | Update run record (recommendations success) |
| 376 | Update run record (recommendations failure) |
| 398 | Collect config snapshots |
| 412 | Update run record (config snapshots) |
| 429 | Calculate final status |
| 486 | Dead letter job handling |
| 534 | Config check for dead letter |
| 551 | Log event helper |
| 601 | Create run record |

**Debugging impact:** If a scheduler run partially succeeds (expenses OK, resources fail, recommendations OK), the state is scattered across 5+ separate database sessions. There is no transaction boundary coordination. Tracing requires reading `SchedulerLog` entries and correlating them across sessions.

### Private Function Import

[`_discover_all_resources`](backend/app/resources/service.py:20) is a **private function** (prefixed with `_`) being imported from another module. This breaks encapsulation — the resources module never intended this to be a public API.

---

## 3. Backend: `shared/degradation.py` — Upward Imports from Shared

**File:** [`backend/app/shared/degradation.py`](backend/app/shared/degradation.py) (383 lines)

The `shared` package is architecturally positioned as a **leaf dependency** — it should have no upward imports into domain modules. However, `degradation.py` uses **deferred imports inside function bodies** to reach into 5 service modules:

- [`get_expense_breakdown`, `get_expense_summary`](backend/app/shared/degradation.py:241) from `expenses.service`
- [`get_cached_summary`, `get_cached_breakdown`](backend/app/shared/degradation.py:255) from `cost_cache.service`
- [`list_resources`](backend/app/shared/degradation.py:298) from `resources.service`
- [`_get_cached_resources`](backend/app/shared/degradation.py:309) from `resources.service` (private function!)
- [`get_recommendations_overview`](backend/app/shared/degradation.py:352) from `recommendations.service`

### The Fallback Chain Problem

Each `get_*_with_fallback()` function has a **3-layer fallback chain**:

```
try live → try cache → return degraded
```

Each layer has its own `try/except` block. When a request returns degraded data, the caller has no visibility into which layer failed or why. The `data_source` return value (`"live"`, `"cached"`, `"stale"`, `"unavailable"`) is the only signal.

**Debugging impact:** A call to `get_expenses_with_fallback()` can silently return stale cached data from 24 hours ago, and the only way to know is to inspect the `data_source` and `freshness_seconds` tuple values. The deferred imports also hide the dependency from static analysis tools — no linter will catch a circular import until runtime.

---

## 4. Backend: `dashboards/batch.py` — Fan-Out Aggregator Bypassing Service Layers

**File:** [`backend/app/dashboards/batch.py`](backend/app/dashboards/batch.py) (383 lines)

This file imports and calls into 4 service modules via deferred imports:

- [`get_cached_summary`](backend/app/dashboards/batch.py:78) from `cost_cache.service`
- [`get_cached_breakdown`](backend/app/dashboards/batch.py:84) from `cost_cache.service`
- [`list_resources`](backend/app/dashboards/batch.py:93) from `resources.service`
- [`get_recommendations_overview`](backend/app/dashboards/batch.py:101) from `recommendations.service`

### Direct ORM Model Queries (Bypassing Service Layers)

The batch module also **directly queries ORM models** from other modules:

- [`CloudAccount`](backend/app/dashboards/batch.py:109) — queries cloud_accounts model directly
- [`Pool`](backend/app/dashboards/batch.py:133) — queries pools model directly
- [`Organization`](backend/app/dashboards/batch.py:158) — queries organizations model directly

**Why this matters:** The batch endpoint is a "god function" that knows the internal data model of every domain. If `CloudAccount` adds a required field or `Pool` changes its schema, the dashboard silently breaks. These queries should go through their respective service layers.

---

## 5. Backend: `pools/service.py` → `expenses/service.py` — Cross-Domain Coupling

**File:** [`backend/app/pools/service.py`](backend/app/pools/service.py:12)

```python
from app.expenses.service import get_expense_summary
```

**Dependency chain:** `pools` → `expenses` → `cloud_accounts.adapters` → cloud SDKs

A pool is a logical grouping/budgeting concept. Its service should not need to know how expenses are fetched from cloud providers. The [`enrich_pool_with_spent_and_owner()`](backend/app/pools/service.py:15) function even has a comment admitting it can't calculate spending properly:

```python
# We need a mongo_db reference - skip expense calculation for now
# and return 0 for spent. The frontend can handle this gracefully.
spent = 0.0
```

This means the import exists but the function always returns `0.0` — dead coupling.

---

## 6. Backend: `recommendations` ↔ `recommendation_rules` — Bidirectional Dependency

**Forward:** [`recommendations/service.py`](backend/app/recommendations/service.py:948) imports [`evaluate_custom_rules`](backend/app/recommendation_rules/service.py:948) from `recommendation_rules.service`

**Backward:** [`recommendations/csp_service.py`](backend/app/recommendations/csp_service.py:234) imports [`_WELL_ARCHITECTED_RULES`](backend/app/recommendations/service.py:250) from `recommendations.service`

This creates a **bidirectional dependency** between `recommendations` and `recommendation_rules`, hidden by deferred imports. Python's module system tolerates this at runtime (because the imports are deferred), but it makes the dependency graph cyclic and any refactoring risky.

---

## 7. Backend: `user_management` → `auth` — Tight Coupling on Internal Implementation

**File:** [`backend/app/user_management/service.py`](backend/app/user_management/service.py:12)

```python
from app.auth.service import hash_password
```

**File:** [`backend/app/user_management/router.py`](backend/app/user_management/router.py:322)

```python
from app.auth.service import create_access_token
```

User management and auth are separate modules but share internal implementation details. If `hash_password` changes its algorithm or `create_access_token` changes its signature, user management breaks. These should be exposed via a public API or extracted into a shared utility.

---

## 8. Backend: Module-Level Mutable Caches in Routers/Services

### [`cloud_accounts/router.py`](backend/app/cloud_accounts/router.py:45-46)

```python
_live_data_cache: TTLCache = TTLCache(maxsize=500, ttl=300)  # 5 minutes
_permission_cache: TTLCache = TTLCache(maxsize=500, ttl=3600)  # 1 hour
```

### [`resources/service.py`](backend/app/resources/service.py:27-28)

```python
_resource_cache = SyncBoundedCache(max_size=500, ttl_seconds=300, name="resources")
_resource_detail_cache = SyncBoundedCache(max_size=500, ttl_seconds=300, name="resource_details")
```

**Why this matters:** These are **module-level mutable state** that lives in the process memory. In a multi-worker deployment (e.g., gunicorn with multiple workers), each worker has its own cache, leading to inconsistent data. The caches are also invisible to monitoring — there's no way to see cache hit rates, sizes, or stale entries without reading the source code and adding instrumentation manually.

**Debugging impact:** "Why is the user seeing stale resource data?" could be caused by the TTL cache in `resources/service.py`, the TTL cache in `cloud_accounts/router.py`, the Redis cache in `cloud_accounts/cloud_cache.py`, or the MongoDB cache in `cost_cache/service.py`. Four different caching layers with different TTLs and invalidation strategies.

---

## 9. Backend: Global Singletons via `global` Keyword

The codebase has **8 global singletons** managed via the `global` keyword:

| Module | Singleton | Purpose |
|--------|-----------|---------|
| [`database.py`](backend/app/database.py:31) | `_mongo_client` | MongoDB connection |
| [`auth/service.py`](backend/app/auth/service.py:25) | `_redis_client` | Redis connection |
| [`scheduler/executor.py`](backend/app/scheduler/executor.py:32) | `_scheduler` | APScheduler instance |
| [`cloud_accounts/credential_cache.py`](backend/app/cloud_accounts/credential_cache.py:281) | `_credential_cache` | Credential cache |
| [`cloud_accounts/cloud_cache.py`](backend/app/cloud_accounts/cloud_cache.py:226) | `_cloud_cache` | Cloud data cache |
| [`shared/field_encryption.py`](backend/app/shared/field_encryption.py:130) | `_field_encryption` | Encryption instance |
| [`security/audit_logger.py`](backend/app/security/audit_logger.py:337) | `_audit_logger` | Audit logger |
| [`shared/tracing.py`](backend/app/shared/tracing.py:23) | `_tracer` | OpenTelemetry tracer |

**Why this matters:** Global singletons make testing harder (you can't inject mocks without patching the module), create hidden initialization order dependencies, and make it impossible to run multiple configurations in the same process. The `get_scheduler()` / `init_scheduler()` / `shutdown_scheduler()` trio in `scheduler/executor.py` is particularly fragile — calling them in the wrong order causes `NoneType` errors.

---

## 10. Backend: Bare `except` Clauses and Silent Exception Swallowing

### Bare `except:` (catches everything including `SystemExit`, `KeyboardInterrupt`)

**File:** [`backend/app/auth/token_manager.py`](backend/app/auth/token_manager.py)

- Line 122: `except:` — catches corrupted token data
- Line 177: `except: pass` — silently ignores token revocation failures
- Line 209: `except: pass` — silently ignores token validation failures

### Silent `except Exception: pass` Patterns

**File:** [`backend/app/recommendations/service.py`](backend/app/recommendations/service.py)

- Line 917: `except Exception: pass` — silently ignores cloud account count failure
- Line 957: `except Exception: pass` — silently ignores custom rule evaluation failure
- Line 993: `except Exception: pass` — silently ignores cloud account count failure (duplicate)
- Line 1009: `except Exception: pass` — silently ignores CSP recommendation fetch failure

**File:** [`backend/app/pools/service.py`](backend/app/pools/service.py)

- Lines 29-30: `except Exception: spent = 0.0` — silently returns 0 on any error
- Lines 76-78: `except Exception: pass` — silently ignores enrichment errors

**File:** [`backend/app/auth/router.py`](backend/app/auth/router.py)

- Line 195: `except Exception: pass` — silently ignores email sending failure

**Why this matters:** When a user reports "recommendations aren't showing," the root cause could be silently swallowed in any of these `except` blocks. There is no log output, no metric, no alert. The only way to debug is to add breakpoints or temporarily remove the `except` blocks.

---

## 11. Backend: Services Creating Their Own DB Sessions

Several service functions create their own `async_session_factory()` sessions instead of receiving them via dependency injection:

### [`expenses/service.py`](backend/app/expenses/service.py)

- Line 65-69: `_get_cloud_adapters()` creates its own session
- Line 204-206: `get_expense_summary()` creates its own session
- Line 247-249: `get_expense_breakdown()` creates its own session
- Line 397-399: `get_clean_expenses()` creates its own session

### [`resources/service.py`](backend/app/resources/service.py)

- Line 63-65: `_discover_all_resources()` creates its own session
- Line 279-281: `get_resource_detail()` creates its own session

### [`auth/service.py`](backend/app/auth/service.py)

- Line 322-325: `create_password_reset_token()` creates its own session
- Line 350-360: `reset_password_with_token()` creates its own session

### [`cost_cache/service.py`](backend/app/cost_cache/service.py)

- Line 44-46: `refresh_cost_cache()` creates its own session (for background tasks)

**Why this matters:** When `scheduler/executor.py` calls `refresh_cost_cache()`, the cache service creates its own session. If the executor then tries to read the cached data in a different session, it may not see the committed data (depending on isolation level). This is the root cause of the "session explosion" problem in the scheduler.

---

## 12. Backend: `main.py` Model Import Fan-Out

**File:** [`backend/app/main.py`](backend/app/main.py:57-78)

```python
from app.auth.models import User  # noqa: F401
from app.organizations.models import Organization, Employee  # noqa: F401
from app.cloud_accounts.models import CloudAccount  # noqa: F401
from app.pools.models import Pool, PoolPolicy  # noqa: F401
from app.rules.models import Rule, Condition  # noqa: F401
from app.recommendation_rules.models import RecommendationRule, RecommendationRuleCondition  # noqa: F401
from app.notifications.models import NotificationPreference, NotificationLog  # noqa: F401
from app.enterprise.modules.rbac.models import Role, RolePermission, UserRoleAssignment, ABACPolicy, AccessReview, SSOConfig  # noqa: F401
from app.scheduler.models import SchedulerConfig, SchedulerRun, SchedulerLog  # noqa: F401
from app.user_management.models import UserInvitation, UserActivityLog, UserPreferences  # noqa: F401
from app.enterprise.modules.export.models import ExportTemplate, ExportJob, ScheduledExport  # noqa: F401
from app.dashboards.models import Dashboard  # noqa: F401
from app.security.models import AuditLog, SecurityAlert  # noqa: F401
from app.idempotency.models import IdempotencyKey  # noqa: F401
from app.advisor_findings.models import AdvisorFinding  # noqa: F401
```

This is **15 model imports from 12 modules** — all marked `# noqa: F401` (unused import). This is a symptom of SQLAlchemy's `Base.metadata` registration pattern, but it means `main.py` has compile-time dependencies on every single module. Adding a new model requires modifying `main.py`.

---

## 13. Frontend: Three Different Data Fetching Paradigms

The frontend uses **three different data fetching approaches** simultaneously:

### Pattern A: `@tanstack/react-query` `useQuery` (modern, cached, deduped)

Used in: `CloudAccounts`, `Recommendations`, `RecommendationRules`, `RecommendationDetail`, `Dashboard`, `SelectOrganization`, `CloudAccountDetails`

```tsx
const { data, isLoading } = useQuery({
  queryKey: ['cloud-accounts', orgId],
  queryFn: () => cloudAccountsApi.list(orgId),
});
```

### Pattern B: Manual `useState` + `useEffect` + `try/catch` (legacy, no caching)

Used in: `Pools`, `Resources`, `ResourceDetail`, `RBAC`, `Exports`, `Schedulers`, `Users`, `Settings`, `AcceptInvitation`

```tsx
const [data, setData] = useState([]);
const [loading, setLoading] = useState(false);
useEffect(() => {
  const fetchData = async () => {
    setLoading(true);
    try {
      const result = await api.list(orgId);
      setData(result);
    } catch (e) {
      message.error('Failed to load');
    } finally {
      setLoading(false);
    }
  };
  fetchData();
}, [orgId]);
```

### Pattern C: Mixed (both in the same file)

Used in: `Dashboard` — uses `useQuery` for dashboard list/detail but `useEffect` for some side effects.

**Why this matters:**

| Concern | Pattern A (react-query) | Pattern B (manual) |
|---------|------------------------|-------------------|
| Caching | ✅ Automatic | ❌ None |
| Deduplication | ✅ Same queryKey = 1 request | ❌ Each component fetches independently |
| Retry on failure | ✅ Configurable | ❌ None |
| Stale-while-revalidate | ✅ Built-in | ❌ None |
| Background refetch | ✅ On window focus | ❌ None |
| Loading state | ✅ Automatic | ⚠️ Manual `useState` |
| Error state | ✅ Automatic | ⚠️ Manual `try/catch` |

Debugging "why is data stale?" requires knowing which pattern the page uses. A developer working on `Pools.tsx` (Pattern B) will have a completely different debugging experience than one working on `CloudAccounts.tsx` (Pattern A).

---

## 14. Frontend: `authStore` ↔ `orgStore` Cross-Store Side Effects

**File:** [`frontend/src/store/authStore.ts`](frontend/src/store/authStore.ts:23)

```typescript
setAuth: (_token, user) => {
  const previousUserId = get().user?.id ?? null;
  if (previousUserId !== user.id) {
    useOrgStore.getState().clearOrg();  // ← Side effect!
  }
  set({ token: null, user });
},
```

The `authStore` directly calls `useOrgStore.getState().clearOrg()` inside `setAuth`, `setUser`, and `logout`. This creates a **hidden dependency** where auth state changes silently mutate org state.

**Debugging impact:** If org data disappears unexpectedly, the cause could be in auth store — not org store. The coupling is invisible unless you read the auth store source. There is no event system, no middleware, no explicit contract between the stores.

---

## 15. Frontend: `api/client.ts` — Silent Navigation on Errors

**File:** [`frontend/src/api/client.ts`](frontend/src/api/client.ts:26-55)

```typescript
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // ... not an auth endpoint?
      useAuthStore.getState().logout();
      window.location.href = '/login';  // ← Hard navigation!
    }
    if (error.response?.status === 403 && ...) {
      useOrgStore.getState().clearOrg();
      window.location.href = '/';  // ← Hard navigation!
    }
    return Promise.reject(error);
  }
);
```

**Why this matters:**

1. **Any 401 from any API call** triggers a full app state reset and hard navigation to `/login`. This includes transient network issues, proxy errors, or backend restarts.
2. **Specific 403 errors** trigger org state clearing and navigation to `/`. The condition checks for the string `"not a member of this organization"` — a brittle string match.
3. **Hard navigation** (`window.location.href`) destroys all React state, query cache, and component tree. This is the nuclear option.
4. The side effects happen in an **axios interceptor** — a global middleware that every API call passes through. There is no way for individual components to opt out or handle these errors differently.

**Debugging impact:** "Why did I get logged out?" requires tracing through every API call in the app to find which one returned a 401. The interceptor has no logging, no metrics, no way to distinguish between "token expired" and "backend restarted."

---

## 16. Dependency Graph Summary

```
scheduler/executor ──→ expenses/service ──→ cloud_accounts/adapters
        │                    │
        ├──→ resources/service ──→ cloud_accounts/models
        ├──→ cost_cache/service ──→ cloud_accounts/adapters
        ├──→ recommendations/csp_service ──→ recommendations/service ←→ recommendation_rules/service
        ├──→ advisor_findings/service ──→ cloud_accounts/models
        └──→ config_ingestors/service ──→ cloud_accounts/models

shared/degradation ──→ expenses/service (UPWARD import from shared!)
                   ──→ resources/service
                   ──→ cost_cache/service
                   ──→ recommendations/service

dashboards/batch ──→ cost_cache/service
               ──→ resources/service
               ──→ recommendations/service
               ──→ cloud_accounts/models (direct ORM query)
               ──→ pools/models (direct ORM query)
               ──→ organizations/models (direct ORM query)

pools/service ──→ expenses/service
user_management/service ──→ auth/service
user_management/router ──→ auth/service

enterprise/export/service ──→ expenses/service
                        ──→ resources/service
                        ──→ recommendations/service

enterprise/export/router ──→ expenses/service
                       ──→ resources/service
                       ──→ recommendations/service
```

---

## 17. Risk Ranking

| # | Finding | Severity | Debugging Impact |
|---|---------|----------|-----------------|
| 1 | `scheduler/executor.py` god module (6 modules, 15+ sessions) | 🔴 Critical | Failures require tracing through 6 modules with no transaction coordination |
| 2 | `shared/degradation.py` upward imports + 3-layer fallback chains | 🔴 Critical | Shared package depends on domain services; degraded responses are invisible |
| 3 | Silent exception swallowing (`except Exception: pass`) | 🔴 Critical | Root causes are silently discarded in 10+ locations |
| 4 | Services creating own DB sessions | 🟠 High | Session isolation causes stale reads; no transaction boundary coordination |
| 5 | `dashboards/batch.py` bypassing service layers | 🟠 High | Schema changes in any module silently break dashboard |
| 6 | Frontend: 3 different data fetching paradigms | 🟠 High | Inconsistent caching, retry, and error handling across pages |
| 7 | `recommendations` ↔ `recommendation_rules` bidirectional dependency | 🟠 High | Cyclic dependency hidden by deferred imports; refactoring is risky |
| 8 | Module-level mutable caches (4 different caching layers) | 🟡 Medium | "Why is data stale?" has 4 possible answers |
| 8 global singletons via `global` keyword | 🟡 Medium | Testing requires module patching; initialization order bugs |
| 10 | `authStore` ↔ `orgStore` cross-store side effects | 🟡 Medium | Org data disappears when auth state changes; no explicit contract |
| 11 | `api/client.ts` silent navigation on errors | 🟡 Medium | Any 401 triggers full app reset; no logging or metrics |
| 12 | `pools/service.py` → `expenses/service.py` dead coupling | 🟢 Low | Import exists but function always returns 0.0 |
| 13 | `main.py` model import fan-out (15 imports, 12 modules) | 🟢 Low | Adding a model requires modifying main.py |
| 14 | Bare `except:` clauses in `auth/token_manager.py` | 🟡 Medium | Catches `SystemExit`/`KeyboardInterrupt`; hides corruption |
| 15 | Private function imports (`_discover_all_resources`, `_get_cached_resources`) | 🟢 Low | Breaks encapsulation; private API used as public contract |
