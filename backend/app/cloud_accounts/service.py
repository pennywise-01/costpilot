import json
import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cloud_accounts.models import CloudAccount
from app.cloud_accounts.schemas import CloudAccountCreate, CloudAccountUpdate
from app.cloud_accounts.adapters.aws import AWSAdapter
from app.cloud_accounts.adapters.azure import AzureAdapter
from app.cloud_accounts.adapters.gcp import GCPAdapter
from app.shared.exceptions import NotFoundError, BadRequestError
from app.shared.crypto import encrypt, decrypt
from app.shared.enums import CloudType
from app.shared.utils.time import utc_now


logger = logging.getLogger(__name__)


async def create_cloud_account(
    db: AsyncSession, org_id: str, data: CloudAccountCreate
) -> CloudAccount:
    if not data.name or not data.type:
        raise BadRequestError("Name and type are required")

    # Validate credentials before saving
    account_id = data.config.get("account_id", "")
    permission_warnings: list[str] = []

    if data.type == CloudType.AWS:
        try:
            adapter = AWSAdapter(data.config)
            result = await adapter.validate_credentials()
            account_id = adapter.account_id or account_id
            permission_warnings = result.get("permission_warnings", [])
        except BadRequestError:
            raise
        except Exception as e:
            raise BadRequestError(f"Failed to validate AWS credentials: {str(e)}")
    elif data.type == CloudType.AZURE:
        try:
            adapter = AzureAdapter(data.config)
            result = await adapter.validate_credentials()
            account_id = data.config.get("subscription_id", account_id)
            permission_warnings = result.get("permission_warnings", [])
        except BadRequestError:
            raise
        except Exception as e:
            raise BadRequestError(f"Failed to validate Azure credentials: {str(e)}")
    elif data.type == CloudType.GCP:
        # Handle both 'credentials_json' and 'service_account_key' field names from frontend
        config = dict(data.config)
        if 'service_account_key' in config and 'credentials_json' not in config:
            config['credentials_json'] = config.pop('service_account_key')

        try:
            adapter = GCPAdapter(config)
            result = await adapter.validate_credentials()
            # Use organization_id if available, otherwise project_id
            account_id = config.get("organization_id") or config.get("project_id", account_id)
            permission_warnings = result.get("permission_warnings", [])
        except BadRequestError as e:
            logger.warning("GCP credential validation failed")
            raise
        except Exception as e:
            logger.exception("Unexpected error during GCP credential validation")
            raise BadRequestError(f"Failed to validate GCP credentials: {str(e)}")

    # Use normalized config for storage (with credentials_json key)
    storage_config = config if data.type == CloudType.GCP else data.config

    cloud_account = CloudAccount(
        name=data.name,
        type=data.type,
        config=encrypt(json.dumps(storage_config)),
        organization_id=org_id,
        account_id=account_id,
    )
    db.add(cloud_account)
    await db.flush()
    return cloud_account


async def list_cloud_accounts(
    db: AsyncSession, org_id: str, offset: int = 0, limit: int = 50
) -> tuple[list[CloudAccount], int]:
    logger.info(f"[DEBUG] list_cloud_accounts called with org_id={org_id}")

    # Get total count
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count(CloudAccount.id)).where(
            CloudAccount.organization_id == org_id,
            CloudAccount.deleted_at.is_(None),
        )
    )
    total = count_result.scalar() or 0

    # Get paginated results
    result = await db.execute(
        select(CloudAccount)
        .where(
            CloudAccount.organization_id == org_id,
            CloudAccount.deleted_at.is_(None),
        )
        .offset(offset)
        .limit(limit)
    )
    accounts = list(result.scalars().all())
    logger.info(f"[DEBUG] Query returned {len(accounts)} accounts for org_id={org_id}")
    return accounts, total


async def get_cloud_account(db: AsyncSession, ca_id: str) -> CloudAccount:
    result = await db.execute(
        select(CloudAccount).where(
            CloudAccount.id == ca_id,
            CloudAccount.deleted_at.is_(None),
        )
    )
    cloud_account = result.scalar_one_or_none()
    if not cloud_account:
        raise NotFoundError("Cloud account not found")
    return cloud_account


async def update_cloud_account(
    db: AsyncSession, ca_id: str, data: CloudAccountUpdate
) -> CloudAccount:
    cloud_account = await get_cloud_account(db, ca_id)

    if data.name is not None:
        cloud_account.name = data.name
    if data.config is not None:
        cloud_account.config = encrypt(json.dumps(data.config))
    if data.auto_import is not None:
        cloud_account.auto_import = data.auto_import
    if data.process_recommendations is not None:
        cloud_account.process_recommendations = data.process_recommendations

    await db.flush()
    return cloud_account


async def delete_cloud_account(db: AsyncSession, ca_id: str) -> None:
    cloud_account = await get_cloud_account(db, ca_id)
    cloud_account.deleted_at = utc_now()
    await db.flush()


async def get_cloud_account_resources(cloud_account: CloudAccount, limit: int = 50) -> list[dict]:
    """Get resources for a specific cloud account from the cloud provider.
    
    This is called for the cloud account details page, so we include costs.
    """
    from app.cloud_accounts.adapters.aws import AWSAdapter
    from app.cloud_accounts.adapters.azure import AzureAdapter
    from app.cloud_accounts.adapters.gcp import GCPAdapter
    from app.shared.crypto import decrypt
    from app.shared.enums import CloudType
    import logging
    
    logger = logging.getLogger(__name__)
    
    if cloud_account.type not in (CloudType.AWS, CloudType.AZURE, CloudType.GCP):
        return []
    
    try:
        config = json.loads(decrypt(cloud_account.config))
        
        if cloud_account.type == CloudType.AWS:
            adapter = AWSAdapter(config)
            resources = await adapter.discover_resources()
        elif cloud_account.type == CloudType.AZURE:
            adapter = AzureAdapter(config)
            # Include costs for cloud account details page
            resources = await adapter.discover_resources(include_costs=True)
        else:  # GCP
            adapter = GCPAdapter(config)
            # Include costs for cloud account details page
            resources = await adapter.discover_resources(include_costs=True)
        
        # Format resources for the response
        result = []
        for res in resources[:limit]:
            daily_cost = res.get("daily_cost", 0) or 0
            result.append({
                "id": f"{cloud_account.id}:{res['cloud_resource_id']}",
                "name": res.get("name", res["cloud_resource_id"]),
                "resource_type": res.get("resource_type", "Unknown"),
                "region": res.get("region", "unknown"),
                "state": res.get("state", "unknown"),
                "daily_cost": daily_cost,
                "tags": res.get("tags", {}),
            })
        
        return result
    except Exception as e:
        logger.warning("Failed to get resources for cloud account %s: %s", cloud_account.id, e)
        return []


async def get_cloud_account_cost_history(cloud_account: CloudAccount, days: int = 30) -> list[dict]:
    """Get daily cost history for a specific cloud account from the cloud provider."""
    from app.cloud_accounts.adapters.aws import AWSAdapter
    from app.cloud_accounts.adapters.azure import AzureAdapter
    from app.cloud_accounts.adapters.gcp import GCPAdapter
    from app.shared.crypto import decrypt
    from app.shared.enums import CloudType
    import logging
    
    logger = logging.getLogger(__name__)
    
    if cloud_account.type not in (CloudType.AWS, CloudType.AZURE, CloudType.GCP):
        return []
    
    try:
        config = json.loads(decrypt(cloud_account.config))
        
        if cloud_account.type == CloudType.AWS:
            adapter = AWSAdapter(config)
        elif cloud_account.type == CloudType.AZURE:
            adapter = AzureAdapter(config)
        else:  # GCP
            adapter = GCPAdapter(config)
        
        # Calculate date range
        end_date = utc_now().date()
        start_date = end_date - timedelta(days=days)
        
        daily_costs = await adapter.get_daily_costs(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        return daily_costs
    except Exception as e:
        logger.warning("Failed to get cost history for cloud account %s: %s", cloud_account.id, e)
        return []


async def get_cloud_account_summary(cloud_account: CloudAccount) -> dict:
    """Get summary info (resource count, monthly cost) for a cloud account."""
    from app.cloud_accounts.adapters.aws import AWSAdapter
    from app.cloud_accounts.adapters.azure import AzureAdapter
    from app.shared.crypto import decrypt
    from app.shared.enums import CloudType
    import logging

    logger = logging.getLogger(__name__)

    logger.info(f"[DEBUG] get_cloud_account_summary called for account {cloud_account.id} ({cloud_account.name}, type: {cloud_account.type})")

    result = {
        "resources_count": 0,
        "monthly_cost": 0.0,
        "forecast": 0.0,
        "last_month_cost": 0.0,
        "resources_data_available": False,
        "cost_data_available": False,
    }

    if cloud_account.type not in (CloudType.AWS, CloudType.AZURE, CloudType.GCP):
        logger.warning(f"[DEBUG] Unsupported cloud type: {cloud_account.type}")
        return result

    try:
        config = json.loads(decrypt(cloud_account.config))
        logger.info(f"[DEBUG] Config loaded for account {cloud_account.id}, has keys: {list(config.keys())}")

        if cloud_account.type == CloudType.AWS:
            adapter = AWSAdapter(config)
        elif cloud_account.type == CloudType.AZURE:
            adapter = AzureAdapter(config)
        else:  # GCP
            adapter = GCPAdapter(config)

        # Get resource count
        try:
            logger.info(f"[DEBUG] Discovering resources for account {cloud_account.id} ({cloud_account.type})")
            resources = await adapter.discover_resources()
            result["resources_count"] = len(resources)
            result["resources_data_available"] = True
            logger.info(f"[DEBUG] Found {len(resources)} resources for account {cloud_account.id}")
        except Exception as e:
            logger.error(f"[DEBUG] Failed to get resources for {cloud_account.id}: {type(e).__name__}: {e}", exc_info=True)

        # Get cost summary
        try:
            logger.info(f"[DEBUG] Getting cost summary for account {cloud_account.id}")
            cost_summary = await adapter.get_monthly_cost_summary()
            result["monthly_cost"] = cost_summary.get("this_month", 0)
            result["forecast"] = cost_summary.get("forecast", 0)
            result["last_month_cost"] = cost_summary.get("last_month", 0)
            result["cost_data_available"] = True
            logger.info(f"[DEBUG] Cost summary for {cloud_account.id}: monthly={result['monthly_cost']}, forecast={result['forecast']}")
        except Exception as e:
            logger.error(f"[DEBUG] Failed to get costs for {cloud_account.id}: {type(e).__name__}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"[DEBUG] Failed to get summary for cloud account {cloud_account.id}: {type(e).__name__}: {e}", exc_info=True)

    logger.info(f"[DEBUG] get_cloud_account_summary result for {cloud_account.id}: {result}")
    return result


async def validate_cloud_account_credentials(cloud_account: CloudAccount) -> list[str]:
    """Validate credentials for an existing cloud account and return permission warnings.

    Returns:
        List of permission warnings (empty if credentials have all required permissions)
    """
    from app.cloud_accounts.adapters.aws import AWSAdapter
    from app.cloud_accounts.adapters.azure import AzureAdapter
    from app.shared.crypto import decrypt
    from app.shared.enums import CloudType

    if cloud_account.type not in (CloudType.AWS, CloudType.AZURE, CloudType.GCP):
        return ["Unsupported cloud provider"]

    config = json.loads(decrypt(cloud_account.config))

    if cloud_account.type == CloudType.AWS:
        adapter = AWSAdapter(config)
    elif cloud_account.type == CloudType.AZURE:
        adapter = AzureAdapter(config)
    else:  # GCP
        adapter = GCPAdapter(config)

    result = await adapter.validate_credentials()
    return result.get("permission_warnings", [])
