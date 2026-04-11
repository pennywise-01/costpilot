"""Azure Cloud Adapter - Fetches real cost and resource data from Azure."""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from app.cloud_accounts.adapters.base import CloudAdapter
from app.shared.circuit_breaker import azure_circuit_breaker
from app.shared.exceptions import BadRequestError, RateLimitException
from app.shared.retry import AZURE_RETRY_CONFIG, with_retry
from app.shared.utils.time import utc_now

logger = logging.getLogger(__name__)


def _sanitize_csp_error(error: Exception) -> str:
    """Sanitize cloud provider error messages to prevent information leakage."""
    error_str = str(error)
    # Remove AWS account IDs
    error_str = re.sub(r'\b\d{12}\b', '***REDACTED***', error_str)
    # Remove ARNs
    error_str = re.sub(r'arn:aws:[^:\s]+:[^:\s]+:\d{12}:[^/\s]+', '***REDACTED***', error_str)
    # Remove Azure subscription IDs (GUIDs in certain contexts)
    error_str = re.sub(r'subscription[^:]*:?[\s"]*([0-9a-fA-F-]{36})', 'subscription_id: ***REDACTED***', error_str)
    # Remove GCP project IDs/numbers
    error_str = re.sub(r'project[-_]?[nN]umbers?[/\s]+(\d{6,})', 'project_number: ***REDACTED***', error_str)
    # Remove full error details, return generic message
    return "Cloud provider API error. Check server logs for details."

# Azure regions list (commonly used)
AZURE_REGIONS = [
    "eastus", "eastus2", "westus", "westus2", "westus3",
    "centralus", "northcentralus", "southcentralus", "westcentralus",
    "canadacentral", "canadaeast",
    "brazilsouth",
    "northeurope", "westeurope", "uksouth", "ukwest",
    "francecentral", "germanywestcentral", "swedencentral", "norwayeast",
    "switzerlandnorth",
    "uaenorth", "southafricanorth",
    "australiaeast", "australiasoutheast", "australiacentral",
    "eastasia", "southeastasia",
    "japaneast", "japanwest",
    "koreacentral", "koreasouth",
    "centralindia", "southindia", "westindia",
]


class AzureAdapter(CloudAdapter):
    """Adapter for Azure cloud accounts using Azure SDK."""

    MINIMUM_PERMISSIONS = [
        "Microsoft.CostManagement/query/action",
        "Microsoft.Resources/subscriptions/resourceGroups/read",
        "Microsoft.Compute/virtualMachines/read",
        "Microsoft.Storage/storageAccounts/read",
        "Microsoft.Sql/servers/read",
    ]

    def __init__(self, config: dict):
        """Initialize with decrypted config containing Azure credentials.

        Expected config keys:
        - tenant_id: Azure AD tenant ID
        - client_id: Application (client) ID
        - client_secret: Client secret value
        - subscription_id: Azure subscription ID
        """
        self.tenant_id = config.get("tenant_id", "")
        self.client_id = config.get("client_id", "")
        self.client_secret = config.get("client_secret", "")
        self.subscription_id = config.get("subscription_id", "")
        self._permission_warnings: list[str] = []

        if not all([self.tenant_id, self.client_id, self.client_secret, self.subscription_id]):
            raise BadRequestError(
                "Azure credentials (tenant_id, client_id, client_secret, subscription_id) are required"
            )

    def _get_credential(self):
        """Create Azure credential object."""
        from azure.identity import ClientSecretCredential
        return ClientSecretCredential(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )

    async def validate_credentials(self) -> dict[str, Any]:
        """Validate Azure credentials by listing resource groups.

        Returns:
            dict with 'valid' (bool) and 'permission_warnings' (list[str])
        """
        try:
            async def _api_call():
                return await asyncio.to_thread(self._validate_credentials_sync)

            await with_retry(
                lambda: azure_circuit_breaker.call(_api_call),
                config=AZURE_RETRY_CONFIG,
            )
            # After identity validation, check permissions
            missing = await self._validate_permissions()
            if missing:
                logger.warning(f"Credentials missing permissions: {missing}")
                self._permission_warnings = missing
            return {"valid": True, "permission_warnings": self._permission_warnings}
        except BadRequestError:
            raise
        except Exception as e:
            raise BadRequestError(_sanitize_csp_error(e))

    def _validate_credentials_sync(self) -> bool:
        """Synchronous credential validation."""
        from azure.mgmt.resource import ResourceManagementClient
        from azure.core.exceptions import ClientAuthenticationError, HttpResponseError

        try:
            credential = self._get_credential()
            client = ResourceManagementClient(credential, self.subscription_id)
            # Try to list resource groups (limit to 1) to validate access
            list(client.resource_groups.list())
            return True
        except ClientAuthenticationError as e:
            raise BadRequestError(
                f"Invalid Azure credentials. Please verify your Tenant ID, Client ID, and Client Secret. "
                f"Details: {_sanitize_csp_error(e)}"
            )
        except HttpResponseError as e:
            if e.status_code == 401:
                raise BadRequestError(
                    "Azure authentication failed. Please check your Client Secret is correct "
                    "and hasn't expired."
                )
            elif e.status_code == 403:
                raise BadRequestError(
                    "Azure access denied. The Service Principal needs 'Reader' role on the subscription. "
                    "Go to Azure Portal → Subscriptions → Access control (IAM) → Add role assignment."
                )
            raise BadRequestError(_sanitize_csp_error(e))

    async def _validate_permissions(self) -> list[str]:
        """Check minimum required permissions."""
        from azure.core.exceptions import HttpResponseError

        missing = []
        credential = self._get_credential()

        for perm in self.MINIMUM_PERMISSIONS:
            try:
                if perm == "Microsoft.CostManagement/query/action":
                    from azure.mgmt.costmanagement import CostManagementClient
                    client = CostManagementClient(credential)
                    scope = f"/subscriptions/{self.subscription_id}"
                    # Try a minimal query
                    list(client.query.usage(scope=scope, parameters={}))
                elif perm == "Microsoft.Resources/subscriptions/resourceGroups/read":
                    from azure.mgmt.resource import ResourceManagementClient
                    client = ResourceManagementClient(credential, self.subscription_id)
                    list(client.resource_groups.list())
                elif perm == "Microsoft.Compute/virtualMachines/read":
                    from azure.mgmt.compute import ComputeManagementClient
                    client = ComputeManagementClient(credential, self.subscription_id)
                    list(client.virtual_machines.list_all())
                elif perm == "Microsoft.Storage/storageAccounts/read":
                    from azure.mgmt.storage import StorageManagementClient
                    client = StorageManagementClient(credential, self.subscription_id)
                    list(client.storage_accounts.list())
                elif perm == "Microsoft.Sql/servers/read":
                    from azure.mgmt.sql import SqlManagementClient
                    client = SqlManagementClient(credential, self.subscription_id)
                    list(client.servers.list())
            except HttpResponseError as e:
                if e.status_code == 403:
                    missing.append(perm)
            except Exception:
                # Other errors don't necessarily mean missing permissions
                pass
        return missing

    def get_permission_warnings(self) -> list[str]:
        """Return permission warnings from last credential validation."""
        return self._permission_warnings

    async def get_regions(self) -> list[str]:
        """Get list of Azure regions."""
        # Return static list - Azure regions don't change often
        return AZURE_REGIONS

    async def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "Daily",
        group_by: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch cost data from Azure Cost Management API.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            granularity: Daily or Monthly
            group_by: List of dimensions to group by (ServiceName, ResourceGroup, etc.)

        Returns:
            Cost Management query result
        """
        try:
            async def _api_call():
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        self._get_cost_and_usage_sync, start_date, end_date, granularity, group_by
                    ),
                    timeout=25.0
                )

            return await with_retry(
                lambda: azure_circuit_breaker.call(_api_call),
                config=AZURE_RETRY_CONFIG,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Azure Cost Management API call timed out after 25s for subscription {self.subscription_id}"
            )
            raise BadRequestError(
                "Azure Cost Management API call timed out. The Azure API may be experiencing delays."
            )
        except BadRequestError:
            raise
        except Exception as e:
            logger.warning(f"Azure Cost Management API error: {_sanitize_csp_error(e)}")
            raise BadRequestError(_sanitize_csp_error(e))

    def _get_cost_and_usage_sync(
        self,
        start_date: str,
        end_date: str,
        granularity: str,
        group_by: list[str] | None,
    ) -> dict[str, Any]:
        """Synchronous cost data retrieval."""
        from azure.mgmt.costmanagement import CostManagementClient
        from azure.mgmt.costmanagement.models import (
            QueryDefinition,
            QueryTimePeriod,
            QueryDataset,
            QueryAggregation,
            QueryGrouping,
            ExportType,
        )
        from azure.core.exceptions import HttpResponseError
        
        credential = self._get_credential()
        client = CostManagementClient(credential)
        
        scope = f"/subscriptions/{self.subscription_id}"
        
        # Build aggregation
        aggregation = {
            "totalCost": QueryAggregation(name="Cost", function="Sum"),
        }
        
        # Build grouping
        grouping = None
        if group_by:
            grouping = [
                QueryGrouping(type="Dimension", name=dim) for dim in group_by
            ]
        
        # Build dataset - use string values for granularity
        dataset = QueryDataset(
            granularity=granularity,  # "Daily" or "Monthly" as string
            aggregation=aggregation,
            grouping=grouping,
        )
        
        # Build query definition
        query = QueryDefinition(
            type=ExportType.ACTUAL_COST,
            timeframe="Custom",
            time_period=QueryTimePeriod(
                from_property=datetime.fromisoformat(start_date),
                to=datetime.fromisoformat(end_date),
            ),
            dataset=dataset,
        )
        
        try:
            result = client.query.usage(scope=scope, parameters=query)
            return self._parse_cost_result(result)
        except HttpResponseError as e:
            if e.status_code == 429:
                # Extract Retry-After header if present
                retry_after = 10  # Default 10 seconds
                if hasattr(e, 'response') and e.response:
                    retry_after = int(e.response.headers.get('Retry-After', 10))
                
                logger.warning(
                    f"Azure rate limited (429). Retry-After: {retry_after}s"
                )
                # Raise RateLimitException so the async retry logic handles backoff
                raise RateLimitException(
                    f"Azure Cost Management API rate limited. Retry after {retry_after}s",
                    retry_after=retry_after,
                )
            
            if e.status_code == 401 or e.status_code == 403:
                raise BadRequestError(
                    "Azure credentials lack Cost Management permissions. "
                    "Ensure the Service Principal has Cost Management Reader role."
                )
            raise BadRequestError(_sanitize_csp_error(e))

    def _parse_cost_result(self, result) -> dict[str, Any]:
        """Parse Azure Cost Management query result into a standardized format."""
        columns = [col.name for col in result.columns] if result.columns else []
        rows = result.rows if result.rows else []
        
        logger.debug("Parsed Azure Cost Management response with %d rows", len(rows))
        
        # Find column indices - look for "Cost" or "PreTaxCost" (Azure uses different names)
        cost_idx = None
        for i, c in enumerate(columns):
            c_lower = c.lower()
            if c_lower in ("cost", "pretaxcost", "totalcost"):
                cost_idx = i
                break
        
        date_idx = None
        for i, c in enumerate(columns):
            c_lower = c.lower()
            if "date" in c_lower or "billingperiod" in c_lower or "usagedate" in c_lower:
                date_idx = i
                break
        
        logger.debug("Azure cost parser indices resolved")
        
        return {
            "columns": columns,
            "rows": rows,
            "cost_index": cost_idx,
            "date_index": date_idx,
        }

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if an error looks like an Azure rate-limit response (429)."""
        message = str(error).lower()
        return "429" in message or "too many requests" in message

    async def get_monthly_cost_summary(self) -> dict[str, float]:
        """Get this month and last month cost totals."""
        today = utc_now().date()
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        
        logger.debug(f"AzureAdapter.get_monthly_cost_summary called for subscription {self.subscription_id}")
        logger.debug(f"Date range: this_month={first_of_month.isoformat()} to {today.isoformat()}, last_month={last_month_start.isoformat()} to {first_of_month.isoformat()}")
        
        this_month_cost = 0.0
        last_month_cost = 0.0

        # This month should be resilient: keep trying to return this value even if other calls fail.
        try:
            logger.debug("Fetching this month data from Azure Cost Management")
            this_month_data = await self.get_cost_and_usage(
                start_date=first_of_month.isoformat(),
                end_date=today.isoformat(),
                granularity="Monthly",
            )
            logger.debug(
                f"This month data: columns={this_month_data.get('columns')}, rows_count={len(this_month_data.get('rows', []))}, cost_index={this_month_data.get('cost_index')}"
            )
            this_month_cost = self._sum_costs(this_month_data)
        except Exception as monthly_error:
            logger.warning(
                "Failed to get Azure this month monthly summary, falling back to daily costs: %s",
                monthly_error,
            )

            try:
                this_month_daily_data = await self.get_cost_and_usage(
                    start_date=first_of_month.isoformat(),
                    end_date=today.isoformat(),
                    granularity="Daily",
                )
                this_month_cost = self._sum_costs(this_month_daily_data)
                logger.debug("Azure this month daily fallback cost: %s", this_month_cost)
            except Exception as daily_fallback_error:
                logger.error("Failed to get Azure cost summary: %s", daily_fallback_error, exc_info=True)
                raise

        # Last month is best-effort. Do not discard a successful this-month value if this call fails.
        try:
            logger.debug("Fetching last month data from Azure Cost Management")
            last_month_data = await self.get_cost_and_usage(
                start_date=last_month_start.isoformat(),
                end_date=first_of_month.isoformat(),
                granularity="Monthly",
            )
            logger.debug(
                f"Last month data: columns={last_month_data.get('columns')}, rows_count={len(last_month_data.get('rows', []))}, cost_index={last_month_data.get('cost_index')}"
            )
            last_month_cost = self._sum_costs(last_month_data)
        except Exception as e:
            logger.warning("Failed to get Azure last month costs, defaulting to 0: %s", e)

        logger.debug(
            f"Azure calculated costs: this_month_cost={this_month_cost}, last_month_cost={last_month_cost}"
        )

        # Forecast: extrapolate this month
        days_elapsed = max((today - first_of_month).days + 1, 1)
        days_in_month = ((first_of_month + timedelta(days=32)).replace(day=1) - first_of_month).days
        forecast = this_month_cost / days_elapsed * days_in_month

        result = {
            "this_month": round(this_month_cost, 2),
            "last_month": round(last_month_cost, 2),
            "forecast": round(forecast, 2),
        }
        logger.debug(f"Azure returning result: {result}")
        return result

    def _sum_costs(self, data: dict) -> float:
        """Sum costs from parsed cost data."""
        cost_idx = data.get("cost_index")
        if cost_idx is None:
            return 0.0
        
        total = 0.0
        for row in data.get("rows", []):
            try:
                total += float(row[cost_idx])
            except (IndexError, ValueError, TypeError):
                continue
        return total

    async def get_daily_costs(
        self,
        start_date: str,
        end_date: str,
        group_by: str | None = None,
    ) -> list[dict]:
        """Get daily cost breakdown.
        
        Returns list of {date, cost, [group_key]} dicts.
        """
        group_dims = [self._map_group_dimension(group_by)] if group_by else None
        
        try:
            data = await self.get_cost_and_usage(
                start_date=start_date,
                end_date=end_date,
                granularity="Daily",
                group_by=group_dims,
            )
            
            return self._parse_daily_costs(data, group_by is not None)
        except Exception as e:
            logger.warning(f"Failed to get Azure daily costs: {e}")
            return []

    def _map_group_dimension(self, group_by: str) -> str:
        """Map generic group_by values to Azure dimension names."""
        mapping = {
            "SERVICE": "ServiceName",
            "REGION": "ResourceLocation",
            "RESOURCE_GROUP": "ResourceGroup",
        }
        return mapping.get(group_by.upper(), group_by) if group_by else "ServiceName"

    def _parse_daily_costs(self, data: dict, has_group: bool) -> list[dict]:
        """Parse daily costs from Azure Cost Management response."""
        columns = data.get("columns", [])
        rows = data.get("rows", [])
        
        # Find column indices
        cost_idx = data.get("cost_index", 0)
        date_idx = data.get("date_index")
        
        # Find group column (first non-cost, non-date column)
        group_idx = None
        if has_group:
            for i, col in enumerate(columns):
                col_lower = col.lower()
                if i != cost_idx and i != date_idx and "cost" not in col_lower and "date" not in col_lower:
                    group_idx = i
                    break
        
        results = []
        for row in rows:
            try:
                cost = float(row[cost_idx]) if cost_idx is not None else 0.0
                
                # Parse date - Azure returns as integer YYYYMMDD or datetime
                date_val = row[date_idx] if date_idx is not None else None
                if isinstance(date_val, int):
                    date_str = str(date_val)
                    date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                elif isinstance(date_val, datetime):
                    date = date_val.strftime("%Y-%m-%d")
                elif isinstance(date_val, str):
                    date = date_val[:10]  # Take YYYY-MM-DD part
                else:
                    date = utc_now().strftime("%Y-%m-%d")
                
                entry = {
                    "date": date,
                    "cost": round(cost, 2),
                }
                
                if group_idx is not None and len(row) > group_idx:
                    entry["group_key"] = str(row[group_idx]) if row[group_idx] else "Unknown"
                
                results.append(entry)
            except (IndexError, ValueError, TypeError) as e:
                logger.debug(f"Error parsing cost row: {e}")
                continue
        
        return results

    async def discover_resources(self, include_costs: bool = False) -> list[dict]:
        """Discover Azure resources in the subscription.

        Args:
            include_costs: If True, fetch and include cost data for each resource.
                          Defaults to False for faster loading.
        """
        logger.debug(f"Azure discover_resources starting for subscription {self.subscription_id}")
        try:
            async def _api_call():
                return await asyncio.to_thread(self._discover_resources_sync)

            resources = await with_retry(
                lambda: azure_circuit_breaker.call(_api_call),
                config=AZURE_RETRY_CONFIG,
            )
            logger.debug(f"Azure discovered {len(resources)} resources for subscription {self.subscription_id}")

            # Only fetch costs if explicitly requested (e.g., for cloud account details page)
            if include_costs:
                await self._enrich_resources_with_costs(resources)
            else:
                # Set default cost values without API call
                for resource in resources:
                    resource["daily_cost"] = 0
                    resource["total_cost_7d"] = 0

            return resources
        except Exception as e:
            logger.warning("Failed to discover Azure resources: %s", _sanitize_csp_error(e), exc_info=True)
            return []

    def _discover_resources_sync(self) -> list[dict]:
        """Synchronous resource discovery."""
        resources = []
        
        # Discover VMs
        resources.extend(self._discover_virtual_machines())
        
        # Discover Storage Accounts
        resources.extend(self._discover_storage_accounts())
        
        # Discover SQL Databases
        resources.extend(self._discover_sql_databases())
        
        return resources

    async def _enrich_resources_with_costs(self, resources: list[dict]) -> None:
        """Fetch costs from Azure and add daily_cost to each resource."""
        if not resources:
            return
        
        try:
            # Get last 7 days of costs grouped by ResourceId
            end_date = utc_now().date()
            start_date = end_date - timedelta(days=7)
            
            cost_data = await self.get_cost_and_usage(
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                granularity="Daily",
                group_by=["ResourceId"],
            )
            
            # Map resource IDs to costs
            resource_costs = self._map_costs_by_resource_id(cost_data)
            logger.debug("Mapped Azure costs for %d resources", len(resource_costs))
            
            # Calculate average daily cost for each resource
            days = 7
            for resource in resources:
                resource_id = resource.get("cloud_resource_id", "")
                total_cost = resource_costs.get(resource_id.lower(), 0)
                # Average daily cost over the period
                daily_cost = round(total_cost / days, 4) if days > 0 else 0
                resource["daily_cost"] = daily_cost
                resource["total_cost_7d"] = round(total_cost, 4)
            
        except Exception as e:
            logger.warning("Failed to enrich resources with costs: %s", e)
            # Set default 0 costs
            for resource in resources:
                resource["daily_cost"] = 0
                resource["total_cost_7d"] = 0

    def _map_costs_by_resource_id(self, cost_data: dict) -> dict[str, float]:
        """Parse cost data and map resource IDs to total costs."""
        columns = cost_data.get("columns", [])
        rows = cost_data.get("rows", [])
        
        # Find column indices
        cost_idx = cost_data.get("cost_index")
        
        # Find ResourceId column index
        resource_id_idx = None
        for i, col in enumerate(columns):
            if col.lower() in ("resourceid", "resource_id", "resourceid"):
                resource_id_idx = i
                break
        
        if cost_idx is None:
            logger.warning("Could not find cost column in Azure cost data")
            return {}
        
        resource_costs = {}
        for row in rows:
            try:
                cost = float(row[cost_idx]) if cost_idx is not None else 0.0
                
                # Get resource ID if available
                resource_id = None
                if resource_id_idx is not None and len(row) > resource_id_idx:
                    resource_id = str(row[resource_id_idx]).lower() if row[resource_id_idx] else None
                
                if resource_id:
                    resource_costs[resource_id] = resource_costs.get(resource_id, 0) + cost

            except (IndexError, ValueError, TypeError) as e:
                continue
        
        return resource_costs

    def _discover_virtual_machines(self) -> list[dict]:
        """Discover Azure Virtual Machines."""
        from azure.mgmt.compute import ComputeManagementClient
        from azure.core.exceptions import HttpResponseError

        resources = []
        try:
            credential = self._get_credential()
            client = ComputeManagementClient(credential, self.subscription_id)

            for vm in client.virtual_machines.list_all():
                # Parse resource group and location from ID
                parts = vm.id.split("/")
                resource_group = ""
                for i, part in enumerate(parts):
                    if part.lower() == "resourcegroups" and i + 1 < len(parts):
                        resource_group = parts[i + 1]
                        break

                # Get VM state
                state = "unknown"
                try:
                    instance_view = client.virtual_machines.instance_view(
                        resource_group, vm.name
                    )
                    for status in instance_view.statuses or []:
                        if status.code and status.code.startswith("PowerState/"):
                            state = status.code.replace("PowerState/", "")
                            break
                except Exception:
                    pass

                resources.append({
                    "cloud_resource_id": vm.id,
                    "name": vm.name,
                    "resource_type": "Virtual Machine",
                    "region": vm.location,
                    "state": state,
                    "tags": vm.tags or {},
                    "meta": {
                        "vm_size": vm.hardware_profile.vm_size if vm.hardware_profile else "",
                        "resource_group": resource_group,
                        "os_type": vm.storage_profile.os_disk.os_type if vm.storage_profile and vm.storage_profile.os_disk else "",
                    },
                })
        except HttpResponseError as e:
            logger.debug(f"Error discovering VMs: {_sanitize_csp_error(e)}")

        return resources

    def _discover_storage_accounts(self) -> list[dict]:
        """Discover Azure Storage Accounts."""
        from azure.mgmt.storage import StorageManagementClient
        from azure.core.exceptions import HttpResponseError

        resources = []
        try:
            credential = self._get_credential()
            client = StorageManagementClient(credential, self.subscription_id)

            for account in client.storage_accounts.list():
                # Parse resource group from ID
                parts = account.id.split("/")
                resource_group = ""
                for i, part in enumerate(parts):
                    if part.lower() == "resourcegroups" and i + 1 < len(parts):
                        resource_group = parts[i + 1]
                        break

                resources.append({
                    "cloud_resource_id": account.id,
                    "name": account.name,
                    "resource_type": "Storage Account",
                    "region": account.location,
                    "state": account.provisioning_state or "unknown",
                    "tags": account.tags or {},
                    "meta": {
                        "kind": account.kind,
                        "sku": account.sku.name if account.sku else "",
                        "resource_group": resource_group,
                        "access_tier": account.access_tier,
                        "creation_time": account.creation_time.isoformat() if account.creation_time else None,
                    },
                })
        except HttpResponseError as e:
            logger.debug(f"Error discovering Storage Accounts: {_sanitize_csp_error(e)}")

        return resources

    def _discover_sql_databases(self) -> list[dict]:
        """Discover Azure SQL Databases."""
        from azure.mgmt.sql import SqlManagementClient
        from azure.core.exceptions import HttpResponseError

        resources = []
        try:
            credential = self._get_credential()
            client = SqlManagementClient(credential, self.subscription_id)

            # First list SQL servers
            for server in client.servers.list():
                # Parse resource group from server ID
                parts = server.id.split("/")
                resource_group = ""
                for i, part in enumerate(parts):
                    if part.lower() == "resourcegroups" and i + 1 < len(parts):
                        resource_group = parts[i + 1]
                        break

                # Then list databases in each server
                try:
                    for db in client.databases.list_by_server(resource_group, server.name):
                        # Skip system databases
                        if db.name.lower() == "master":
                            continue

                        resources.append({
                            "cloud_resource_id": db.id,
                            "name": db.name,
                            "resource_type": "SQL Database",
                            "region": db.location,
                            "state": db.status or "unknown",
                            "tags": db.tags or {},
                            "meta": {
                                "server_name": server.name,
                                "resource_group": resource_group,
                                "sku": db.sku.name if db.sku else "",
                                "tier": db.sku.tier if db.sku else "",
                                "max_size_bytes": db.max_size_bytes,
                                "creation_date": db.creation_date.isoformat() if db.creation_date else None,
                            },
                        })
                except HttpResponseError as e:
                    logger.debug(f"Error listing databases for server {server.name}: {_sanitize_csp_error(e)}")
                    continue
        except HttpResponseError as e:
            logger.debug(f"Error discovering SQL databases: {_sanitize_csp_error(e)}")

        return resources

    async def get_resource_cost(self, resource_id: str, days: int = 30) -> dict:
        """Get cost for a specific resource over the past N days."""
        end_date = utc_now().date()
        start_date = end_date - timedelta(days=days)

        try:
            data = await self.get_cost_and_usage(
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                granularity="Daily",
                group_by=["ResourceId"],
            )

            # Filter for the specific resource
            total_cost = 0.0
            daily_costs = []

            # This would require filtering the response by resource_id
            # For now, return placeholder similar to AWS
            return {
                "resource_id": resource_id,
                "total_cost": total_cost,
                "daily_costs": daily_costs,
                "note": "Per-resource costs require Cost Management Reader role and may have delay",
            }
        except Exception as e:
            logger.warning(f"Failed to get resource cost: {_sanitize_csp_error(e)}")
            return {
                "resource_id": resource_id,
                "total_cost": 0.0,
                "daily_costs": [],
                "note": "Failed to retrieve resource cost. Check server logs for details.",
            }
