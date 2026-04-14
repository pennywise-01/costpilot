from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "CostPilot"
    DEBUG: bool = False

    # Database
    # Required — must be set in .env, e.g. postgresql+asyncpg://user:pass@host:5432/dbname
    DATABASE_URL: str
    # Required — must be set in .env, e.g. mongodb://user:pass@host:27017/dbname
    MONGODB_URL: str
    MONGODB_DB: str = "costpilot"
    # Required — must be set in .env, e.g. redis://user:pass@host:6379/0
    REDIS_URL: str
    
    # Database Connection Pooling
    DB_POOL_SIZE: int = 20  # Main pool size for concurrent connections
    DB_MAX_OVERFLOW: int = 40  # Additional connections allowed beyond pool_size
    DB_POOL_TIMEOUT: int = 30  # Seconds to wait for available connection
    DB_POOL_RECYCLE: int = 1800  # Recycle connections after 30 minutes
    DB_POOL_PRE_PING: bool = True  # Verify connections before use
    
    # MongoDB Connection Pooling
    MONGODB_MAX_POOL_SIZE: int = 50  # Max connections in MongoDB pool
    MONGODB_MIN_POOL_SIZE: int = 10  # Min connections to maintain
    MONGODB_MAX_IDLE_TIME_MS: int = 60000  # Close idle connections after 60s
    MONGODB_WAIT_QUEUE_TIMEOUT_MS: int = 5000  # Wait timeout for connection
    
    # Redis Connection Pooling
    REDIS_MAX_CONNECTIONS: int = 100  # Max connections to Redis
    REDIS_CONNECTION_TIMEOUT: int = 5  # Connection timeout in seconds
    REDIS_SOCKET_TIMEOUT: int = 5  # Socket operation timeout
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5  # Socket connect timeout

    # Encryption
    # Required — generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str

    # Auth
    # Required — generate with: python -c "import secrets; print(secrets.token_urlsafe(64))"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # 15 minutes (reduced for security)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7 days

    # Email / SMTP
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_TLS: bool = False
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@costpilot.io"

    # Email Provider Selection
    EMAIL_PROVIDER: str = "smtp"  # "smtp", "ses", or "sendgrid"

    # AWS SES Configuration
    AWS_REGION: str = "us-east-1"  # AWS region for SES (must match where identity is verified)
    AWS_ACCESS_KEY_ID: str = ""  # IAM user access key for SES
    AWS_SECRET_ACCESS_KEY: str = ""  # IAM user secret access key for SES
    SES_FROM_EMAIL: str = "noreply@costpilot.io"  # Verified SES sender email

    # SendGrid Configuration
    SENDGRID_API_KEY: str = ""  # SendGrid API key
    SENDGRID_FROM_EMAIL: str = "noreply@costpilot.io"  # Verified SendGrid sender email

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    # Security Settings
    # Request Validation
    MAX_REQUEST_SIZE_BYTES: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_CONTENT_TYPES: list[str] = [
        "application/json",
        "multipart/form-data",
        "text/plain",
        "application/x-www-form-urlencoded",
    ]

    # Rate Limiting
    RATE_LIMITING_ENABLED: bool = True
    RATE_LIMIT_PUBLIC_REQUESTS: int = 30  # per minute
    RATE_LIMIT_AUTH_REQUESTS: int = 100  # per minute
    RATE_LIMIT_EXPENSIVE_REQUESTS: int = 10  # per minute
    RATE_LIMIT_EXPORT_REQUESTS: int = 5  # per 5 minutes
    RATE_LIMIT_WEBHOOK_REQUESTS: int = 1000  # per minute

    # Request Timeouts
    TIMEOUT_MIDDLEWARE_ENABLED: bool = True
    DEFAULT_REQUEST_TIMEOUT: float = 30.0  # seconds
    ENDPOINT_TIMEOUTS: dict[str, float] = {
        "/api/v1/auth": 10.0,
        "/api/v1/organizations": 10.0,
        "/api/v1/pools": 15.0,
        "/api/v1/expenses": 90.0,  # Expenses fetches costs from all cloud providers - needs extra time
        "/api/v1/resources": 90.0,  # Resources discovers across all regions - needs more time
        "/api/v1/recommendations": 90.0,
        "/api/v1/export": 300.0,
        "/api/v1/cloud-accounts": 90.0,  # Cloud account live data needs extra time for multi-region discovery
    }
    
    # Cloud Provider API Timeouts
    CLOUD_ACCOUNT_LIVE_DATA_TIMEOUT: float = 60.0  # Timeout for fetching live data from cloud providers

    # Session Security
    MAX_SESSION_AGE_HOURS: int = 24
    REQUIRE_IP_BINDING: bool = True
    REQUIRE_FINGERPRINT_BINDING: bool = True

    # RBAC Rollout
    RBAC_LEGACY_MEMBER_FALLBACK_ENABLED: bool = False

    # Credential Cache
    CREDENTIAL_CACHE_TTL_SECONDS: int = 300  # 5 minutes
    CREDENTIAL_CACHE_ENABLED: bool = True
    
    # Cloud Data Cache Settings
    CLOUD_CACHE_ENABLED: bool = True
    CLOUD_CACHE_TTL_SECONDS: int = 300  # 5 minutes default TTL for cloud API calls
    CLOUD_CACHE_MAX_SIZE_MB: int = 100  # Max memory cache size
    
    # Cache TTLs for specific operations (in seconds)
    CACHE_TTL_EXPENSE_SUMMARY: int = 300  # 5 minutes
    CACHE_TTL_EXPENSE_BREAKDOWN: int = 300  # 5 minutes
    CACHE_TTL_RESOURCES: int = 300  # 5 minutes
    CACHE_TTL_RECOMMENDATIONS: int = 600  # 10 minutes
    CACHE_TTL_CLOUD_COSTS: int = 300  # 5 minutes
    CACHE_TTL_RESOURCE_DISCOVERY: int = 600  # 10 minutes

    # Request Coalescing
    REQUEST_COALESCING_ENABLED: bool = True
    REQUEST_COALESCING_MAX_WAIT_SECONDS: float = 180.0  # Max wait for coalesced requests (must be >= longest endpoint timeout)
    
    # Audit Logging
    AUDIT_LOG_ENABLED: bool = True
    AUDIT_LOG_RETENTION_DAYS: int = 90

    # Reliability Settings
    # Circuit Breaker
    CIRCUIT_BREAKER_ENABLED: bool = True
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: float = 60.0
    CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS: int = 3
    CIRCUIT_BREAKER_SUCCESS_THRESHOLD: int = 2

    # Retry Configuration
    RETRY_ENABLED: bool = True
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_BASE_DELAY: float = 1.0
    RETRY_MAX_DELAY: float = 60.0
    RETRY_JITTER: bool = True

    # Graceful Degradation
    DEGRADATION_ENABLED: bool = True
    DEGRADATION_AUTO_RECOVERY_MINUTES: int = 5
    DEGRADATION_MAX_STALENESS_HOURS: int = 24

    # Health Checks
    HEALTH_CHECK_ENABLED: bool = True
    HEALTH_CHECK_TIMEOUT_SECONDS: float = 5.0

    # Cost Cache Settings (for persisted dashboard data)
    COST_CACHE_ENABLED: bool = True
    COST_CACHE_TTL_HOURS: int = 6  # How long cached data is considered fresh
    COST_CACHE_STALE_HOURS: int = 24  # When to show staleness warnings
    COST_CACHE_AUTO_REFRESH: bool = True  # Auto-refresh via scheduler
    COST_CACHE_FALLBACK_TO_LIVE: bool = True  # Call CSP APIs on cache miss
    COST_CACHE_REFRESH_TIMEOUT_SECONDS: float = 300.0  # Max time for cache refresh

    # Dashboard Settings
    DASHBOARD_MAX_PER_ORG: int = 20
    DASHBOARD_MAX_WIDGETS: int = 30
    DASHBOARD_LAYOUT_MAX_SIZE_KB: int = 64
    DASHBOARD_WIDGET_CONFIG_MAX_SIZE_KB: int = 128
    DASHBOARD_BATCH_MAX_WIDGETS: int = 30
    DASHBOARD_BATCH_RATE_LIMIT: int = 20
    DASHBOARD_BATCH_CACHE_TTL: int = 300

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
