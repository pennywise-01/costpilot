"""Health check system for monitoring dependencies."""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio
import json
import logging
import time

from app.config import settings
from app.shared.utils.time import utc_now

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    response_time_ms: float
    message: str
    details: Optional[Dict] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = utc_now()


class HealthCheck:
    """Base class for health checks."""

    def __init__(self, name: str, timeout: float = 5.0):
        self.name = name
        self.timeout = timeout

    async def check(self) -> HealthCheckResult:
        """Execute health check."""
        raise NotImplementedError


class _CachedResult:
    """Thread-safe cached health check result."""

    def __init__(self, ttl_seconds: float = 60.0):
        self.ttl = ttl_seconds
        self._result: Optional[HealthCheckResult] = None
        self._timestamp: float = 0.0
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def is_valid(self) -> bool:
        return self._result is not None and (time.monotonic() - self._timestamp) < self.ttl

    async def get_or_compute(self, compute_fn) -> HealthCheckResult:
        if self.is_valid():
            return self._result
        async with self._get_lock():
            if self.is_valid():
                return self._result
            self._result = await compute_fn()
            self._timestamp = time.monotonic()
            return self._result


class DatabaseHealthCheck(HealthCheck):
    """Check PostgreSQL connectivity."""

    async def check(self) -> HealthCheckResult:
        start = utc_now()
        try:
            from app.database import async_session
            from sqlalchemy import text

            async with async_session() as session:
                result = await session.execute(text("SELECT 1"))
                await result.scalar()

            elapsed = (utc_now() - start).total_seconds() * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                response_time_ms=elapsed,
                message="PostgreSQL connection successful"
            )
        except Exception as e:
            elapsed = (utc_now() - start).total_seconds() * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=elapsed,
                message=f"PostgreSQL connection failed: {str(e)}"
            )


class MongoDBHealthCheck(HealthCheck):
    """Check MongoDB connectivity."""

    async def check(self) -> HealthCheckResult:
        start = utc_now()
        try:
            from app.database import get_mongo_db

            mongo_db = await get_mongo_db()
            await mongo_db.command("ping")

            elapsed = (utc_now() - start).total_seconds() * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                response_time_ms=elapsed,
                message="MongoDB connection successful"
            )
        except Exception as e:
            elapsed = (utc_now() - start).total_seconds() * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=elapsed,
                message=f"MongoDB connection failed: {str(e)}"
            )


class RedisHealthCheck(HealthCheck):
    """Check Redis connectivity."""

    async def check(self) -> HealthCheckResult:
        start = utc_now()
        try:
            from app.auth.service import _get_redis

            redis = await _get_redis()
            await redis.ping()

            # Check memory usage
            info = await redis.info("memory")
            used_memory = info.get("used_memory", 0)
            max_memory = info.get("maxmemory", 0)

            elapsed = (utc_now() - start).total_seconds() * 1000

            status = HealthStatus.HEALTHY
            message = "Redis connection successful"

            # Degraded if memory is high
            if max_memory > 0 and used_memory / max_memory > 0.9:
                status = HealthStatus.DEGRADED
                message = "Redis connection successful but memory usage is high (>90%)"

            return HealthCheckResult(
                name=self.name,
                status=status,
                response_time_ms=elapsed,
                message=message,
                details={"used_memory": used_memory, "max_memory": max_memory}
            )
        except Exception as e:
            elapsed = (utc_now() - start).total_seconds() * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=elapsed,
                message=f"Redis connection failed: {str(e)}"
            )


class CSPHealthCheck(HealthCheck):
    """Check Cloud Service Provider connectivity with actual API calls."""

    _cache: Optional[_CachedResult] = None

    def __init__(self, name: str, provider: str, cache_ttl: float = 60.0, timeout: float = 10.0):
        super().__init__(name, timeout=timeout)
        self.provider = provider
        self._cache = _CachedResult(ttl_seconds=cache_ttl)

    async def check(self) -> HealthCheckResult:
        return await self._cache.get_or_compute(self._do_check)

    async def _do_check(self) -> HealthCheckResult:
        start = utc_now()
        try:
            if self.provider == "AWS":
                account_info = await self._check_aws()
            elif self.provider == "AZURE":
                account_info = await self._check_azure()
            elif self.provider == "GCP":
                account_info = await self._check_gcp()
            else:
                raise Exception(f"Unknown provider: {self.provider}")

            elapsed = (utc_now() - start).total_seconds() * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                response_time_ms=elapsed,
                message=f"{self.provider} API accessible",
                details=account_info,
            )
        except Exception as e:
            elapsed = (utc_now() - start).total_seconds() * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.DEGRADED,
                response_time_ms=elapsed,
                message=f"{self.provider} API check failed: {str(e)}",
            )

    async def _check_aws(self) -> Dict:
        """Check AWS connectivity by calling STS GetCallerIdentity."""
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
        except ImportError:
            raise Exception("AWS SDK not installed")

        try:
            session = boto3.Session()
            sts = session.client("sts")
            response = sts.get_caller_identity()
            return {
                "account_id": response.get("Account"),
                "arn": response.get("Arn"),
                "user_id": response.get("UserId"),
            }
        except (NoCredentialsError, ClientError) as e:
            raise Exception(f"AWS credential error: {str(e)}")

    async def _check_azure(self) -> Dict:
        """Check Azure connectivity by calling a lightweight ARM API."""
        try:
            from azure.identity import ClientSecretCredential, AzureCliCredential
            from azure.core.exceptions import ClientAuthenticationError
        except ImportError:
            raise Exception("Azure SDK not installed")

        try:
            # Try CLI credential first (common for dev), then fall back to app credentials
            try:
                credential = AzureCliCredential()
            except Exception:
                credential = ClientSecretCredential.__new__(ClientSecretCredential)
                raise Exception("Azure credentials not configured")

            from azure.mgmt.resource import SubscriptionClient
            from azure.mgmt.resource.subscriptions.aio import SubscriptionClient as AsyncSubscriptionClient

            client = SubscriptionClient(credential)
            async with client:
                subs = [s async for s in client.subscriptions.list(top=1)]
                if subs:
                    return {
                        "subscription_id": subs[0].subscription_id,
                        "display_name": subs[0].display_name,
                        "state": subs[0].state,
                    }
                return {"status": "accessible"}
        except ClientAuthenticationError as e:
            raise Exception(f"Azure credential error: {str(e)}")

    async def _check_gcp(self) -> Dict:
        """Check GCP connectivity by calling a lightweight Resource Manager API."""
        try:
            from google.cloud import resourcemanager_v3
            from google.api_core.exceptions import GoogleAPIError
        except ImportError:
            raise Exception("GCP SDK not installed")

        try:
            client = resourcemanager_v3.ProjectsClient()
            # List projects with a very small page size (lightweight call)
            response = client.list_projects(page_size=1)
            projects = list(response)
            if projects:
                return {
                    "project_id": projects[0].name,
                    "state": projects[0].state,
                }
            return {"status": "accessible"}
        except GoogleAPIError as e:
            raise Exception(f"GCP API error: {str(e)}")


class CloudAccountHealthCheck(HealthCheck):
    """Check the health of individual cloud accounts by validating credentials."""

    _cache: Optional[_CachedResult] = None

    def __init__(self, name: str = "cloud-accounts", cache_ttl: float = 60.0, timeout: float = 10.0):
        super().__init__(name, timeout=timeout)
        self._cache = _CachedResult(ttl_seconds=cache_ttl)

    async def check(self) -> HealthCheckResult:
        return await self._cache.get_or_compute(self._do_check)

    async def _do_check(self) -> HealthCheckResult:
        from app.database import async_session
        from app.cloud_accounts.models import CloudAccount
        from app.shared.crypto import decrypt
        from sqlalchemy import select
        import json

        start = utc_now()
        account_results = []
        unhealthy_count = 0

        try:
            async with async_session() as session:
                result = await session.execute(select(CloudAccount))
                accounts = result.scalars().all()

            for account in accounts:
                account_health = await self._check_account(account, decrypt)
                account_results.append(account_health)
                if account_health["status"] != "healthy":
                    unhealthy_count += 1

            elapsed = (utc_now() - start).total_seconds() * 1000

            if unhealthy_count == 0:
                status = HealthStatus.HEALTHY
                message = "All cloud accounts healthy"
            elif unhealthy_count < len(accounts):
                status = HealthStatus.DEGRADED
                message = f"{unhealthy_count}/{len(accounts)} cloud accounts unhealthy"
            else:
                status = HealthStatus.UNHEALTHY if accounts else HealthStatus.UNKNOWN
                message = f"All {len(accounts)} cloud accounts unhealthy" if accounts else "No cloud accounts configured"

            return HealthCheckResult(
                name=self.name,
                status=status,
                response_time_ms=elapsed,
                message=message,
                details={"accounts": account_results},
            )
        except Exception as e:
            elapsed = (utc_now() - start).total_seconds() * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                response_time_ms=elapsed,
                message=f"Cloud account health check failed: {str(e)}",
            )

    async def _check_account(self, account, decrypt_fn) -> Dict:
        """Check a single cloud account's credential validity."""
        try:
            config = json.loads(decrypt_fn(account.config))
            if account.type.value == "AWS":
                return await self._check_aws_account(account, config)
            elif account.type.value == "AZURE":
                return await self._check_azure_account(account, config)
            elif account.type.value == "GCP":
                return await self._check_gcp_account(account, config)
            else:
                return {
                    "account_id": account.account_id,
                    "name": account.name,
                    "type": account.type.value,
                    "status": "unknown",
                    "message": f"Unknown cloud type: {account.type.value}",
                }
        except Exception as e:
            return {
                "account_id": account.account_id,
                "name": account.name,
                "type": account.type.value,
                "status": "unhealthy",
                "message": str(e),
            }

    async def _check_aws_account(self, account, config: Dict) -> Dict:
        """Validate AWS account credentials by calling STS."""
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError:
            return {"account_id": account.account_id, "name": account.name, "type": "AWS", "status": "unhealthy", "message": "AWS SDK not installed"}

        try:
            session = boto3.Session(
                aws_access_key_id=config.get("aws_access_key_id"),
                aws_secret_access_key=config.get("aws_secret_access_key"),
                aws_session_token=config.get("aws_session_token"),
                region_name=config.get("region_name", "us-east-1"),
            )
            sts = session.client("sts")
            response = sts.get_caller_identity()
            return {
                "account_id": account.account_id,
                "name": account.name,
                "type": "AWS",
                "status": "healthy",
                "message": f"Connected to AWS account {response.get('Account')}",
            }
        except (ClientError, Exception) as e:
            return {
                "account_id": account.account_id,
                "name": account.name,
                "type": "AWS",
                "status": "unhealthy",
                "message": f"AWS credential error: {str(e)}",
            }

    async def _check_azure_account(self, account, config: Dict) -> Dict:
        """Validate Azure account credentials by calling a lightweight API."""
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.resource.subscriptions.aio import SubscriptionClient
            from azure.core.exceptions import ClientAuthenticationError
        except ImportError:
            return {"account_id": account.account_id, "name": account.name, "type": "AZURE", "status": "unhealthy", "message": "Azure SDK not installed"}

        try:
            credential = ClientSecretCredential(
                tenant_id=config.get("tenant_id"),
                client_id=config.get("client_id"),
                client_secret=config.get("client_secret"),
            )
            client = SubscriptionClient(credential)
            async with client:
                subs = [s async for s in client.subscriptions.list(top=1)]
                if subs:
                    return {
                        "account_id": account.account_id,
                        "name": account.name,
                        "type": "AZURE",
                        "status": "healthy",
                        "message": f"Connected to Azure subscription {subs[0].display_name}",
                    }
                return {
                    "account_id": account.account_id,
                    "name": account.name,
                    "type": "AZURE",
                    "status": "healthy",
                    "message": "Azure credentials valid",
                }
        except (ClientAuthenticationError, Exception) as e:
            return {
                "account_id": account.account_id,
                "name": account.name,
                "type": "AZURE",
                "status": "unhealthy",
                "message": f"Azure credential error: {str(e)}",
            }

    async def _check_gcp_account(self, account, config: Dict) -> Dict:
        """Validate GCP account credentials by calling a lightweight API."""
        try:
            from google.oauth2 import service_account
            from google.cloud import resourcemanager_v3
            from google.api_core.exceptions import GoogleAPIError
        except ImportError:
            return {"account_id": account.account_id, "name": account.name, "type": "GCP", "status": "unhealthy", "message": "GCP SDK not installed"}

        try:
            credentials = service_account.Credentials.from_service_account_info(config)
            client = resourcemanager_v3.ProjectsClient(credentials=credentials)
            response = client.list_projects(page_size=1)
            projects = list(response)
            return {
                "account_id": account.account_id,
                "name": account.name,
                "type": "GCP",
                "status": "healthy",
                "message": "GCP credentials valid",
            }
        except (GoogleAPIError, Exception) as e:
            return {
                "account_id": account.account_id,
                "name": account.name,
                "type": "GCP",
                "status": "unhealthy",
                "message": f"GCP API error: {str(e)}",
            }


class CircuitBreakerHealthCheck(HealthCheck):
    """Check circuit breaker status."""

    def __init__(self, name: str = "circuit_breakers"):
        super().__init__(name)

    async def check(self) -> HealthCheckResult:
        from app.shared.circuit_breaker import CircuitBreakerRegistry

        status = CircuitBreakerRegistry.get_status()

        open_circuits = [
            name for name, data in status.items()
            if data.get("state") == "open"
        ]

        if open_circuits:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.DEGRADED,
                response_time_ms=0,
                message=f"Open circuit breakers: {', '.join(open_circuits)}",
                details={"open_circuits": open_circuits, "all_status": status}
            )

        return HealthCheckResult(
            name=self.name,
            status=HealthStatus.HEALTHY,
            response_time_ms=0,
            message="All circuit breakers closed",
            details=status
        )


class HealthCheckRegistry:
    """Registry for all health checks."""

    def __init__(self):
        self.checks: List[HealthCheck] = []

    def register(self, check: HealthCheck):
        self.checks.append(check)

    def unregister(self, name: str):
        self.checks = [c for c in self.checks if c.name != name]

    async def run_all(self) -> Dict:
        """Run all health checks concurrently."""
        results = await asyncio.gather(
            *[self._run_check(check) for check in self.checks],
            return_exceptions=True
        )

        check_results = []
        for check, result in zip(self.checks, results):
            if isinstance(result, Exception):
                check_results.append(HealthCheckResult(
                    name=check.name,
                    status=HealthStatus.UNKNOWN,
                    response_time_ms=0,
                    message=f"Check failed to execute: {str(result)}"
                ))
            else:
                check_results.append(result)

        # Determine overall status
        statuses = [r.status for r in check_results]
        if HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        return {
            "status": overall.value,
            "timestamp": utc_now().isoformat(),
            "checks": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "response_time_ms": round(r.response_time_ms, 2),
                    "message": r.message,
                    "details": r.details
                }
                for r in check_results
            ]
        }

    async def _run_check(self, check: HealthCheck) -> HealthCheckResult:
        try:
            return await asyncio.wait_for(check.check(), timeout=check.timeout)
        except asyncio.TimeoutError:
            return HealthCheckResult(
                name=check.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=check.timeout * 1000,
                message="Health check timed out"
            )

    def get_check(self, name: str) -> Optional[HealthCheck]:
        """Get a specific health check by name."""
        for check in self.checks:
            if check.name == name:
                return check
        return None


# Initialize global registry
health_registry = HealthCheckRegistry()
health_registry.register(DatabaseHealthCheck("postgresql", timeout=5.0))
health_registry.register(MongoDBHealthCheck("mongodb", timeout=5.0))
health_registry.register(RedisHealthCheck("redis", timeout=3.0))
health_registry.register(CSPHealthCheck("aws-api", "AWS", cache_ttl=60.0, timeout=10.0))
health_registry.register(CSPHealthCheck("azure-api", "AZURE", cache_ttl=60.0, timeout=10.0))
health_registry.register(CSPHealthCheck("gcp-api", "GCP", cache_ttl=60.0, timeout=10.0))
health_registry.register(CloudAccountHealthCheck("cloud-accounts", cache_ttl=60.0, timeout=10.0))
health_registry.register(CircuitBreakerHealthCheck())
