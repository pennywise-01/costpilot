# Big Data Analytics Connector — Implementation Status

## ✅ Completed (Phase 1: Foundation)

### 1. CloudType Enum Values
**File:** `backend/app/shared/enums.py`

Added 4 new enum values:
- `BIGQUERY = "bigquery"` — GCP BigQuery
- `REDSHIFT = "redshift"` — AWS Redshift  
- `ATHENA = "athena"` — AWS Athena
- `SYNAPSE = "synapse"` — Azure Synapse Analytics

### 2. Database Migration
**File:** `backend/alembic/versions/023_add_analytics_connector_enums.py`

Migration 023 adds:
- Enum values: bigquery, redshift, athena, synapse (to cloudtype)
- Column: `data_source_config` JSON (for analytics-specific config)
- Column: `last_schema_sync` TIMESTAMP (for schema validation tracking)

### 3. AnalyticsAdapterBase Class
**File:** `backend/app/cloud_accounts/adapters/analytics_base.py`

Created comprehensive base class with:
- `AnalyticsConfig` — configuration wrapper with validation
- `AnalyticsAdapterBase` — abstract base with interface:
  - `validate_credentials()` — test connection
  - `get_cost_and_usage()` — query billing data
  - `get_monthly_cost_summary()` — aggregate costs
  - `get_daily_costs()` — daily breakdown
  - `discover_resources()` — list resources
  - `validate_table_schema()` — check expected columns
- Utility methods:
  - `sanitize_connection_error()` — credential leak prevention
  - `build_standard_query()` — parameterized SQL generation
  - `parse_cost_row()` — normalize row formats

---

## 📋 Remaining Work

### Phase 1: Foundation (Complete Infrastructure)

**Files to Modify:**

1. **`backend/app/shared/circuit_breaker.py`** — Add at bottom:
```python
# Analytics connector circuit breakers
bigquery_circuit_breaker = CircuitBreaker(
    name="bigquery-api",
    failure_threshold=5,
    recovery_timeout=120.0,
    expected_exceptions=(Exception,)
)

redshift_circuit_breaker = CircuitBreaker(
    name="redshift-api",
    failure_threshold=5,
    recovery_timeout=120.0,
    expected_exceptions=(Exception,)
)

athena_circuit_breaker = CircuitBreaker(
    name="athena-api",
    failure_threshold=5,
    recovery_timeout=120.0,
    expected_exceptions=(Exception,)
)

synapse_circuit_breaker = CircuitBreaker(
    name="synapse-api",
    failure_threshold=5,
    recovery_timeout=120.0,
    expected_exceptions=(Exception,)
)

CircuitBreakerRegistry.register("bigquery-api", bigquery_circuit_breaker)
CircuitBreakerRegistry.register("redshift-api", redshift_circuit_breaker)
CircuitBreakerRegistry.register("athena-api", athena_circuit_breaker)
CircuitBreakerRegistry.register("synapse-api", synapse_circuit_breaker)
```

2. **`backend/app/shared/retry.py`** — Add after existing retry configs:
```python
BIGQUERY_RETRY_CONFIG = {
    "max_attempts": 5,
    "base_delay": 2.0,
    "max_delay": 60.0,
    "backoff_factor": 2.0,
    "jitter": 0.25,
    "retryable_status_codes": [429, 500, 503],
    "retryable_errors": ["rateLimitExceeded", "jobRateLimitExceeded", "backendError"]
}

REDSHIFT_RETRY_CONFIG = {
    "max_attempts": 5,
    "base_delay": 3.0,
    "max_delay": 120.0,
    "backoff_factor": 2.0,
    "jitter": 0.25,
    "retryable_status_codes": [],
    "retryable_errors": ["InternalError", "CommunicationLinkFailure", "ClusterNotFound"]
}

ATHENA_RETRY_CONFIG = {
    "max_attempts": 5,
    "base_delay": 3.0,
    "max_delay": 120.0,
    "backoff_factor": 2.0,
    "jitter": 0.25,
    "retryable_status_codes": [429, 500, 503],
    "retryable_errors": ["TooManyRequestsException", "InternalServerError", "ThrottlingException"]
}

SYNAPSE_RETRY_CONFIG = {
    "max_attempts": 5,
    "base_delay": 3.0,
    "max_delay": 120.0,
    "backoff_factor": 2.0,
    "jitter": 0.25,
    "retryable_status_codes": [429, 500, 503],
    "retryable_errors": ["Throttled", "Timeout", "DatabaseUnavailable"]
}
```

3. **`backend/app/shared/request_coalescing.py`** — Add after existing coalescers:
```python
bigquery_costs_coalescer = RequestCoalescer(max_wait=60, name="bigquery_costs")
redshift_costs_coalescer = RequestCoalescer(max_wait=60, name="redshift_costs")
athena_costs_coalescer = RequestCoalescer(max_wait=60, name="athena_costs")
synapse_costs_coalescer = RequestCoalescer(max_wait=60, name="synapse_costs")
```

---

### Phase 2: BigQuery Adapter

**File to Create:** `backend/app/cloud_accounts/adapters/bigquery.py`

**Dependencies:** `google-cloud-bigquery` (add to `pyproject.toml`)

**Implementation Outline:**
```python
from google.cloud import bigquery
from google.oauth2 import service_account
from app.cloud_accounts.adapters.analytics_base import AnalyticsAdapterBase, AnalyticsConfig
from app.shared.retry import with_retry, BIGQUERY_RETRY_CONFIG
from app.shared.circuit_breaker import bigquery_circuit_breaker

class BigQueryConfig(AnalyticsConfig):
    def __init__(self, config: dict):
        super().__init__(config)
        self.project_id = config["project_id"]
        self.service_account_key = config.get("service_account_key")
        self.validate_required_fields(["project_id", "table_name"])
    
    def get_fully_qualified_table(self) -> str:
        return f"{self.project_id}.{self.dataset_id}.{self.table_name}"

class BigQueryAdapter(AnalyticsAdapterBase):
    platform_type = CloudType.BIGQUERY
    
    def __init__(self, config: dict):
        super().__init__(config)
        self._config = BigQueryConfig(config)
    
    async def validate_credentials(self) -> dict:
        # Create BigQuery client with service account
        # Run simple SELECT 1 query
        # Check if table exists
        # Return validation result
    
    @bigquery_circuit_breaker.call
    @with_retry(BIGQUERY_RETRY_CONFIG)
    async def get_cost_and_usage(self, ...):
        # Build SQL query
        # Execute with timeout
        # Parse results into standard format
    
    # ... implement all abstract methods
```

---

### Phase 3: Redshift Adapter

**File to Create:** `backend/app/cloud_accounts/adapters/redshift.py`

**Dependencies:** `boto3` (already installed for AWS adapter)

**Uses:** Redshift Data API (serverless, no persistent connection)

---

### Phase 4: Athena Adapter

**File to Create:** `backend/app/cloud_accounts/adapters/athena.py`

**Dependencies:** `boto3` (already installed)

**Uses:** Athena Query API (async: StartQueryExecution → poll → GetResults)

---

### Phase 5: Synapse Adapter

**File to Create:** `backend/app/cloud_accounts/adapters/synapse.py`

**Dependencies:** `aioodbc` or `pytds` (async SQL drivers)

**Uses:** TDS protocol with Azure AD authentication

---

### Phase 6: Integration

**Files to Modify:**
1. `backend/app/cloud_accounts/service.py` — Add analytics adapter routing
2. `backend/app/cost_cache/service.py` — Include analytics accounts in refresh
3. `backend/app/cloud_accounts/schemas.py` — Add analytics config schemas
4. Frontend: Add analytics connector forms
5. Documentation: Setup guides per platform

---

## Next Steps

The foundation is complete. To continue implementation:

1. **Run migration:** `docker exec costpilot-backend-1 alembic upgrade head`
2. **Add infrastructure code** to circuit_breaker.py, retry.py, request_coalescing.py (code provided above)
3. **Implement BigQuery adapter** (Phase 2) — I can complete this next if you'd like
4. **Test with real BigQuery data** (requires GCP project with billing export)

Would you like me to:
- **A)** Complete the infrastructure additions (circuit breakers, retry, coalescers)?
- **B)** Skip to implementing the BigQuery adapter?
- **C)** Something else?
