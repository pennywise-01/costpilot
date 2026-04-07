"""GCP Cloud Adapter - Fetches real cost and resource data from Google Cloud Platform."""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from app.cloud_accounts.adapters.base import CloudAdapter
from app.shared.circuit_breaker import gcp_circuit_breaker
from app.shared.exceptions import BadRequestError
from app.shared.retry import GCP_RETRY_CONFIG, with_retry
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

# Try to import GCP libraries - handle gracefully if not installed
try:
    from google.oauth2 import service_account
    from google.auth import default as google_auth_default
    from google.api_core.exceptions import PermissionDenied, NotFound
    from google.api_core.exceptions import Forbidden as GCForbidden
    # Try to import Unauthorized, some versions don't have it
    try:
        from google.api_core.exceptions import Unauthorized
    except ImportError:
        Unauthorized = None
    
    # Import GCP service libraries (some may not be installed)
    try:
        from google.cloud import compute_v1
    except ImportError:
        compute_v1 = None
    try:
        from google.cloud import storage
    except ImportError:
        storage = None
    try:
        from google.cloud import resourcemanager_v3
    except ImportError:
        resourcemanager_v3 = None
    try:
        from google.cloud import bigquery
    except ImportError:
        bigquery = None
    
    GCP_LIBS_AVAILABLE = True
except ImportError as e:
    GCP_LIBS_AVAILABLE = False
    logger.warning(f"GCP libraries not installed: {e}. GCP adapter will not function.")

# GCP regions list (commonly used)
GCP_REGIONS = [
    "us-central1", "us-east1", "us-east4", "us-west1", "us-west2", "us-west3", "us-west4",
    "us-south1", "northamerica-northeast1", "northamerica-northeast2",
    "europe-west1", "europe-west2", "europe-west3", "europe-west4", "europe-west6",
    "europe-west8", "europe-west9", "europe-west12", "europe-north1", "europe-central2",
    "europe-southwest1", "asia-east1", "asia-east2", "asia-northeast1", "asia-northeast2",
    "asia-northeast3", "asia-southeast1", "asia-southeast2", "asia-south1", "asia-south2",
    "australia-southeast1", "australia-southeast2", "southamerica-east1", "southamerica-west1",
    "africa-south1", "me-west1", "me-central1", "me-central2",
]


class GCPAdapter(CloudAdapter):
    """Adapter for GCP cloud accounts using Google Cloud SDK.

    Supports both project-level and organization-level access.
    When organization_id is provided, all accessible projects are discovered automatically.
    """

    MINIMUM_PERMISSIONS = [
        "cloudbilling.resourceCommitments.get",
        "compute.instances.list",
        "compute.zones.list",
        "sql.instances.list",
        "storage.buckets.list",
        "bigquery.jobs.list",
    ]

    def __init__(self, config: dict):
        """Initialize with decrypted config containing GCP credentials.

        Expected config keys:
        - project_id: GCP project ID (for single project access)
        - organization_id: GCP organization ID (for multi-project access, e.g., "123456789")
        - credentials_json: Service account JSON key content (optional if using ADC)
        - region: Default region (optional, defaults to us-central1)
        - auto_discover_projects: If True and organization_id provided, discover all projects (default: True)
        - project_filter: Optional filter for project discovery (e.g., "labels.env:production")
        """
        self.project_id = config.get("project_id", "")
        self.organization_id = config.get("organization_id", "")
        self.credentials_json = config.get("credentials_json", "")
        self.region = config.get("region", "us-central1")
        self.auto_discover_projects = config.get("auto_discover_projects", True)
        self.project_filter = config.get("project_filter", "")
        self._credentials = None
        self._cached_projects: list[dict] | None = None
        self._permission_warnings: list[str] = []

        if not self.project_id and not self.organization_id:
            raise BadRequestError("Either GCP project_id or organization_id is required")

    def _get_credentials(self):
        """Create GCP credentials object."""
        if not GCP_LIBS_AVAILABLE:
            raise BadRequestError("GCP libraries not installed. Please install google-cloud libraries.")

        if self._credentials is None:
            if self.credentials_json:
                # Parse service account JSON
                try:
                    info = json.loads(self.credentials_json)
                    self._credentials = service_account.Credentials.from_service_account_info(
                        info,
                        scopes=["https://www.googleapis.com/auth/cloud-platform"],
                    )
                except json.JSONDecodeError as e:
                    raise BadRequestError(f"Invalid GCP credentials JSON: {str(e)}")
            else:
                # Try Application Default Credentials
                creds, _ = google_auth_default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                self._credentials = creds

        return self._credentials

    async def validate_credentials(self) -> dict[str, Any]:
        """Validate GCP credentials by listing projects.

        Returns:
            dict with 'valid' (bool) and 'permission_warnings' (list[str])
        """
        try:
            async def _api_call():
                return await asyncio.to_thread(self._validate_credentials_sync)

            await with_retry(
                lambda: gcp_circuit_breaker.call(_api_call),
                config=GCP_RETRY_CONFIG,
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
        if not resourcemanager_v3:
            raise BadRequestError(
                "GCP Resource Manager library not installed. "
                "Please install google-cloud-resource-manager."
            )
        
        try:
            credentials = self._get_credentials()
            client = resourcemanager_v3.ProjectsClient(credentials=credentials)

            # If organization_id is provided, validate org-level access
            if self.organization_id:
                try:
                    # Try to list projects in the organization to validate access
                    org_name = f"organizations/{self.organization_id}"
                    # Just try to access the organization
                    list(client.list_projects(parent=org_name, page_size=1))
                    return True
                except BadRequestError:
                    raise
                except Exception as e:
                    raise BadRequestError(
                        f"Cannot access organization {self.organization_id}. "
                        f"Ensure the Service Account has 'Browser' or 'Viewer' role at the organization level. "
                        f"Details: {_sanitize_csp_error(e)}"
                    )

            # Otherwise validate project-level access
            project_name = f"projects/{self.project_id}"
            project = client.get_project(name=project_name)

            if project and project.project_id == self.project_id:
                return True
            raise BadRequestError(f"Project {self.project_id} not found or access denied")

        except BadRequestError:
            raise
        except PermissionDenied as e:
            raise BadRequestError(
                f"GCP access denied. The Service Account needs 'Viewer' or 'Browser' role on the project. "
                f"Go to GCP Console → IAM & Admin → IAM → Add principal. "
                f"Details: {_sanitize_csp_error(e)}"
            )
        except NotFound:
            raise BadRequestError(
                f"GCP project '{self.project_id}' not found. "
                f"Please verify the project ID is correct."
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "invalid_grant" in error_msg:
                raise BadRequestError(
                    "GCP authentication failed. The Service Account key may be expired or revoked."
                )
            raise BadRequestError(_sanitize_csp_error(e))

    async def _validate_permissions(self) -> list[str]:
        """Check minimum required permissions."""
        missing = []
        credentials = self._get_credentials()

        for perm in self.MINIMUM_PERMISSIONS:
            try:
                if perm == "cloudbilling.resourceCommitments.get":
                    from google.cloud import billing_v1
                    client = billing_v1.CloudBillingClient(credentials=credentials)
                    # Try to get billing info
                    name = f"projects/{self.project_id}"
                    client.get_project_billing_info(name=name)
                elif perm == "compute.instances.list":
                    if compute_v1:
                        client = compute_v1.InstancesClient(credentials=credentials)
                        request = compute_v1.AggregatedListInstancesRequest(project=self.project_id)
                        list(client.aggregated_list(request=request, max_results=1))
                elif perm == "compute.zones.list":
                    if compute_v1:
                        client = compute_v1.ZonesClient(credentials=credentials)
                        request = compute_v1.ListZonesRequest(project=self.project_id)
                        list(client.list(request=request, max_results=1))
                elif perm == "sql.instances.list":
                    from googleapiclient.discovery import build
                    service = build('sqladmin', 'v1', credentials=credentials)
                    service.instances().list(project=self.project_id, maxResults=1).execute()
                elif perm == "storage.buckets.list":
                    if storage:
                        client = storage.Client(credentials=credentials, project=self.project_id)
                        list(client.list_buckets(project=self.project_id, max_results=1))
                elif perm == "bigquery.jobs.list":
                    if bigquery:
                        client = bigquery.Client(credentials=credentials, project=self.project_id)
                        list(client.list_jobs(max_results=1))
            except GCForbidden:
                missing.append(perm)
            except PermissionDenied:
                missing.append(perm)
            except Exception:
                # Other errors don't necessarily mean missing permissions
                pass
        return missing

    def get_permission_warnings(self) -> list[str]:
        """Return permission warnings from last credential validation."""
        return self._permission_warnings

    async def get_regions(self) -> list[str]:
        """Get list of GCP regions."""
        # Return static list - GCP regions don't change often
        return GCP_REGIONS

    def _get_all_projects(self) -> list[dict]:
        """Get list of all projects accessible with the credentials.

        If organization_id is provided and auto_discover_projects is True,
        discovers all projects in the organization.
        Otherwise returns just the single project_id.
        """
        if self._cached_projects is not None:
            return self._cached_projects

        projects = []

        # If organization-level access with auto-discovery enabled
        if self.organization_id and self.auto_discover_projects:
            try:
                credentials = self._get_credentials()
                client = resourcemanager_v3.ProjectsClient(credentials=credentials)

                parent = f"organizations/{self.organization_id}"

                # Build filter if provided
                filter_str = None
                if self.project_filter:
                    filter_str = self.project_filter

                request = resourcemanager_v3.ListProjectsRequest(
                    parent=parent,
                    filter=filter_str,
                    show_deleted=False,
                )

                for project in client.list_projects(request=request):
                    if project.state.name == "ACTIVE":
                        projects.append({
                            "project_id": project.project_id,
                            "name": project.display_name,
                            "project_number": str(project.name).split("/")[-1],
                            "labels": dict(project.labels) if project.labels else {},
                        })

                logger.info(f"Discovered {len(projects)} projects in organization {self.organization_id}")
            except Exception as e:
                logger.warning(f"Failed to discover projects in organization: {_sanitize_csp_error(e)}. Falling back to single project.")
                # Fall back to single project
                if self.project_id:
                    projects = [{"project_id": self.project_id, "name": self.project_id, "labels": {}, "project_number": ""}]
        else:
            # Single project mode
            projects = [{"project_id": self.project_id, "name": self.project_id, "labels": {}, "project_number": ""}]

        self._cached_projects = projects
        return projects

    async def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "DAILY",
        group_by: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch cost data from GCP Cloud Billing API.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            granularity: DAILY or MONTHLY
            group_by: List of dimensions to group by (service, sku, etc.)

        Returns:
            Cost data with rows and columns
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
                lambda: gcp_circuit_breaker.call(_api_call),
                config=GCP_RETRY_CONFIG,
            )
        except asyncio.TimeoutError:
            logger.warning(f"[DEBUG] GCP Billing API call timed out after 25s for project {self.project_id or 'unknown'}")
            raise BadRequestError("GCP Billing API call timed out. The GCP API may be experiencing delays.")
        except BadRequestError:
            raise
        except Exception as e:
            logger.warning(f"GCP Cloud Billing API error: {_sanitize_csp_error(e)}")
            raise BadRequestError(_sanitize_csp_error(e))

    def _get_cost_and_usage_sync(
        self,
        start_date: str,
        end_date: str,
        granularity: str,
        group_by: list[str] | None,
    ) -> dict[str, Any]:
        """Synchronous cost data retrieval using BigQuery billing export or Cloud Billing API."""
        from google.cloud import bigquery
        from google.api_core.exceptions import Forbidden, NotFound as BQNotFound

        credentials = self._get_credentials()

        # Try to query BigQuery billing export first (most accurate)
        try:
            return self._query_billing_export(
                credentials, start_date, end_date, granularity, group_by
            )
        except (BQNotFound, Forbidden) as e:
            logger.warning(f"BigQuery billing export not available: {e}")
            # Fall back to simplified cost estimation
            return self._get_estimated_costs(start_date, end_date, granularity, group_by)

    def _query_billing_export(
        self,
        credentials,
        start_date: str,
        end_date: str,
        granularity: str,
        group_by: list[str] | None,
    ) -> dict[str, Any]:
        """Query BigQuery billing export table."""
        from google.cloud import bigquery
        from google.api_core.exceptions import Forbidden, NotFound as BQNotFound

        # Common billing dataset names
        dataset_names = ["billing", "billing_export", "cloud_billing"]
        table_names = ["gcp_billing_export_v1", "gcp_billing_export_resource_v1"]

        client = bigquery.Client(credentials=credentials, project=self.project_id)

        # Build the query
        date_format = "%Y-%m-%d"
        if granularity.upper() == "MONTHLY":
            date_select = "FORMAT_DATE('%Y-%m-01', DATE(usage_start_time)) as date"
        else:
            date_select = "DATE(usage_start_time) as date"

        # Build group by clause
        group_cols = [date_select]
        if group_by:
            for dim in group_by:
                if dim.lower() == "service":
                    group_cols.append("service.description as service")
                elif dim.lower() == "sku":
                    group_cols.append("sku.description as sku")
                elif dim.lower() == "resource":
                    group_cols.append("resource.name as resource_name")
                elif dim.lower() == "region" or dim.lower() == "location":
                    group_cols.append("location.location as region")

        select_clause = ", ".join(group_cols) + ", SUM(cost) as cost"
        group_clause = ", ".join([f"{i+1}" for i in range(len(group_cols))])

        # Try to find the billing table
        for dataset_name in dataset_names:
            for table_name in table_names:
                table_id = f"{self.project_id}.{dataset_name}.{table_name}"
                query = f"""
                    SELECT {select_clause}
                    FROM `{table_id}`
                    WHERE DATE(usage_start_time) >= '{start_date}'
                      AND DATE(usage_start_time) < '{end_date}'
                      AND project.id = '{self.project_id}'
                    GROUP BY {group_clause}
                    ORDER BY date
                """

                try:
                    job = client.query(query)
                    rows = list(job.result())

                    # Convert to dict format matching AWS/Azure
                    columns = ["date", "cost"]
                    if group_by:
                        columns.extend([dim.lower() for dim in group_by])

                    return {
                        "columns": columns,
                        "rows": [list(row.values()) for row in rows],
                        "cost_index": 1,
                        "date_index": 0,
                    }
                except (BQNotFound, Forbidden):
                    continue

        raise BQNotFound("No billing export table found")

    def _get_estimated_costs(
        self,
        start_date: str,
        end_date: str,
        granularity: str,
        group_by: list[str] | None,
    ) -> dict[str, Any]:
        """Get estimated costs when BigQuery billing export is not available."""
        # This is a placeholder - in production, you might use Cloud Billing API
        # or Pricing API to estimate costs
        logger.warning("Using estimated costs - BigQuery billing export not configured")

        return {
            "columns": ["date", "cost"],
            "rows": [],
            "cost_index": 1,
            "date_index": 0,
            "estimated": True,
        }

    async def get_monthly_cost_summary(self) -> dict[str, float]:
        """Get this month and last month cost totals."""
        today = utc_now().date()
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        logger.info(f"[DEBUG] GCPAdapter.get_monthly_cost_summary called for project {self.project_id or 'unknown'}")
        logger.info(f"[DEBUG] Date range: this_month={first_of_month.isoformat()} to {(today + timedelta(days=1)).isoformat()}, last_month={last_month_start.isoformat()} to {first_of_month.isoformat()}")

        try:
            # This month (up to today)
            logger.info("[DEBUG] Fetching this month data from GCP Billing")
            this_month_data = await self.get_cost_and_usage(
                start_date=first_of_month.isoformat(),
                end_date=(today + timedelta(days=1)).isoformat(),
                granularity="MONTHLY",
            )
            logger.info(f"[DEBUG] This month data: columns={this_month_data.get('columns')}, rows_count={len(this_month_data.get('rows', []))}, cost_index={this_month_data.get('cost_index')}")

            # Last month
            logger.info("[DEBUG] Fetching last month data from GCP Billing")
            last_month_data = await self.get_cost_and_usage(
                start_date=last_month_start.isoformat(),
                end_date=first_of_month.isoformat(),
                granularity="MONTHLY",
            )
            logger.info(f"[DEBUG] Last month data: columns={last_month_data.get('columns')}, rows_count={len(last_month_data.get('rows', []))}, cost_index={last_month_data.get('cost_index')}")

            this_month_cost = self._sum_costs(this_month_data)
            last_month_cost = self._sum_costs(last_month_data)

            logger.info(f"[DEBUG] GCP calculated costs: this_month_cost={this_month_cost}, last_month_cost={last_month_cost}")

            # Forecast: extrapolate this month
            days_elapsed = max((today - first_of_month).days + 1, 1)
            days_in_month = ((first_of_month + timedelta(days=32)).replace(day=1) - first_of_month).days
            forecast = this_month_cost / days_elapsed * days_in_month

            result = {
                "this_month": round(this_month_cost, 2),
                "last_month": round(last_month_cost, 2),
                "forecast": round(forecast, 2),
            }
            logger.info(f"[DEBUG] GCP returning result: {result}")
            return result
        except Exception as e:
            logger.error(f"[DEBUG] Failed to get GCP cost summary: {e}", exc_info=True)
            return {
                "this_month": 0.0,
                "last_month": 0.0,
                "forecast": 0.0,
            }

    def _sum_costs(self, data: dict) -> float:
        """Sum costs from parsed cost data."""
        cost_idx = data.get("cost_index", 1)
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
                granularity="DAILY",
                group_by=group_dims,
            )

            return self._parse_daily_costs(data, group_by is not None)
        except Exception as e:
            logger.warning(f"Failed to get GCP daily costs: {e}")
            return []

    def _map_group_dimension(self, group_by: str) -> str:
        """Map generic group_by values to GCP dimension names."""
        mapping = {
            "SERVICE": "service",
            "SKU": "sku",
            "REGION": "location",
            "LOCATION": "location",
            "RESOURCE": "resource",
        }
        return mapping.get(group_by.upper(), group_by) if group_by else "service"

    def _parse_daily_costs(self, data: dict, has_group: bool) -> list[dict]:
        """Parse daily costs from GCP billing response."""
        columns = data.get("columns", [])
        rows = data.get("rows", [])

        cost_idx = data.get("cost_index", 1)
        date_idx = data.get("date_index", 0)

        # Find group column
        group_idx = None
        if has_group:
            for i, col in enumerate(columns):
                if i != cost_idx and i != date_idx and col.lower() not in ("date", "cost"):
                    group_idx = i
                    break

        results = []
        for row in rows:
            try:
                cost = float(row[cost_idx]) if cost_idx is not None and len(row) > cost_idx else 0.0

                # Parse date
                date_val = row[date_idx] if date_idx is not None and len(row) > date_idx else None
                if isinstance(date_val, str):
                    date = date_val[:10]  # Take YYYY-MM-DD part
                elif isinstance(date_val, datetime):
                    date = date_val.strftime("%Y-%m-%d")
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
        """Discover GCP resources in the project.

        Args:
            include_costs: If True, fetch and include cost data for each resource.
                          Defaults to False for faster loading.
        """
        logger.info(f"[DEBUG] GCP discover_resources starting for project {self.project_id}, org: {self.organization_id}")
        try:
            async def _api_call():
                return await asyncio.to_thread(self._discover_resources_sync)

            resources = await with_retry(
                lambda: gcp_circuit_breaker.call(_api_call),
                config=GCP_RETRY_CONFIG,
            )
            logger.info(f"[DEBUG] GCP discovered {len(resources)} resources for project {self.project_id}")

            # Only fetch costs if explicitly requested
            if include_costs:
                await self._enrich_resources_with_costs(resources)
            else:
                for resource in resources:
                    resource["daily_cost"] = 0
                    resource["total_cost_7d"] = 0

            return resources
        except Exception as e:
            logger.warning(f"Failed to discover GCP resources: {_sanitize_csp_error(e)}", exc_info=True)
            return []

    def _discover_resources_sync(self) -> list[dict]:
        """Synchronous resource discovery across all accessible projects."""
        resources = []

        # Get all projects to scan
        projects = self._get_all_projects()
        logger.info(f"Scanning {len(projects)} project(s) for resources")

        for project_info in projects:
            project_id = project_info["project_id"]
            project_name = project_info.get("name", project_id)
            project_labels = project_info.get("labels", {})

            logger.debug(f"Scanning project: {project_name} ({project_id})")

            # Temporarily set the current project for discovery methods
            original_project_id = self.project_id
            self.project_id = project_id

            try:
                # Discover Compute Engine VMs
                resources.extend(self._discover_compute_instances(project_id, project_name, project_labels))

                # Discover Cloud SQL instances
                resources.extend(self._discover_cloud_sql(project_id, project_name, project_labels))

                # Discover Cloud Storage buckets
                resources.extend(self._discover_storage_buckets(project_id, project_name, project_labels))

                # Discover Cloud Functions
                resources.extend(self._discover_cloud_functions(project_id, project_name, project_labels))

                # Discover AI Platform / Vertex AI resources
                resources.extend(self._discover_vertex_ai_models(project_id, project_name, project_labels))
                resources.extend(self._discover_vertex_ai_endpoints(project_id, project_name, project_labels))
                resources.extend(self._discover_vertex_ai_datasets(project_id, project_name, project_labels))
                resources.extend(self._discover_vertex_ai_notebooks(project_id, project_name, project_labels))

                # Discover Discovery Engine resources
                resources.extend(self._discover_discovery_engine_datastores(project_id, project_name, project_labels))
                resources.extend(self._discover_discovery_engine_engines(project_id, project_name, project_labels))

                # Discover additional AI services
                resources.extend(self._discover_dialogflow_agents(project_id, project_name, project_labels))
                resources.extend(self._discover_vision_datasets(project_id, project_name, project_labels))
                resources.extend(self._discover_automl_models(project_id, project_name, project_labels))

            except Exception as e:
                logger.warning(f"Failed to scan project {project_id}: {e}")
            finally:
                # Restore original project_id
                self.project_id = original_project_id

        logger.info(f"Discovered {len(resources)} total resources across {len(projects)} project(s)")
        return resources

    def _discover_compute_instances(self, project_id: str | None = None, project_name: str = "", project_labels: dict | None = None) -> list[dict]:
        """Discover Compute Engine instances."""
        resources = []
        pid = project_id or self.project_id
        plabels = project_labels or {}

        try:
            credentials = self._get_credentials()
            client = compute_v1.InstancesClient(credentials=credentials)

            # List instances across all zones
            request = compute_v1.AggregatedListInstancesRequest(project=pid)
            agg_list = client.aggregated_list(request=request)

            for zone, instances_scoped_list in agg_list:
                if instances_scoped_list.instances:
                    for instance in instances_scoped_list.instances:
                        # Merge instance labels with project labels
                        instance_tags = dict(instance.labels) if instance.labels else {}
                        tags = {**plabels, **instance_tags, "gcp_project": pid, "gcp_project_name": project_name}

                        # Determine state
                        status_map = {
                            "RUNNING": "running",
                            "TERMINATED": "stopped",
                            "STOPPED": "stopped",
                            "STAGING": "pending",
                            "PROVISIONING": "pending",
                            "SUSPENDED": "suspended",
                        }
                        state = status_map.get(instance.status, instance.status.lower())

                        # Extract zone from self_link
                        zone_name = zone.replace("zones/", "") if zone else "unknown"

                        resources.append({
                            "cloud_resource_id": f"{pid}/{zone_name}/{instance.name}",
                            "name": instance.name,
                            "resource_type": "Compute Engine VM",
                            "region": zone_name,
                            "state": state,
                            "tags": tags,
                            "meta": {
                                "machine_type": instance.machine_type.split("/")[-1] if instance.machine_type else "",
                                "cpu_platform": instance.cpu_platform,
                                "creation_timestamp": instance.creation_timestamp,
                                "self_link": instance.self_link,
                                "project_id": pid,
                                "project_name": project_name,
                            },
                        })
        except PermissionDenied:
            logger.warning(f"Permission denied when listing Compute Engine instances in {pid}")
        except NotFound:
            logger.warning(f"Compute Engine API not enabled or project {pid} not found")
        except Exception as e:
            logger.warning(f"Failed to discover Compute Engine instances in {pid}: {_sanitize_csp_error(e)}")

        return resources

    def _discover_cloud_sql(self, project_id: str | None = None, project_name: str = "", project_labels: dict | None = None) -> list[dict]:
        """Discover Cloud SQL instances using REST API."""
        resources = []
        pid = project_id or self.project_id
        plabels = project_labels or {}

        try:
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError

            credentials = self._get_credentials()
            service = build('sqladmin', 'v1', credentials=credentials)

            request = service.instances().list(project=pid)
            response = request.execute()

            for instance in response.get('items', []):
                # Merge labels with project labels
                labels = instance.get('settings', {}).get('userLabels', {})
                tags = {**plabels, **labels, "gcp_project": pid, "gcp_project_name": project_name}

                # Determine state
                state_map = {
                    "RUNNABLE": "running",
                    "SUSPENDED": "suspended",
                    "PENDING_CREATE": "pending",
                    "MAINTENANCE": "maintenance",
                    "FAILED": "failed",
                }
                state = state_map.get(instance.get('state'), instance.get('state', 'unknown').lower())

                # Extract region from region field
                region = instance.get('region', 'unknown')

                settings = instance.get('settings', {})
                resources.append({
                    "cloud_resource_id": instance.get('selfLink') or f"{pid}/{instance.get('name')}",
                    "name": instance.get('name'),
                    "resource_type": "Cloud SQL Instance",
                    "region": region,
                    "state": state,
                    "tags": tags,
                    "meta": {
                        "database_version": instance.get('databaseVersion'),
                        "tier": settings.get('tier'),
                        "data_disk_size_gb": settings.get('dataDiskSizeGb'),
                        "availability_type": settings.get('availabilityType'),
                        "connection_name": instance.get('connectionName'),
                        "project_id": pid,
                        "project_name": project_name,
                    },
                })
        except PermissionDenied:
            logger.warning(f"Permission denied when listing Cloud SQL instances in {pid}")
        except NotFound:
            logger.warning(f"Cloud SQL API not enabled or project {pid} not found")
        except Exception as e:
            logger.warning(f"Failed to discover Cloud SQL instances in {pid}: {_sanitize_csp_error(e)}")

        return resources

    def _discover_storage_buckets(self, project_id: str | None = None, project_name: str = "", project_labels: dict | None = None) -> list[dict]:
        """Discover Cloud Storage buckets."""
        resources = []
        pid = project_id or self.project_id
        plabels = project_labels or {}

        try:
            credentials = self._get_credentials()
            client = storage.Client(credentials=credentials, project=pid)

            for bucket in client.list_buckets(project=pid):
                # Merge labels with project labels
                labels = bucket.labels or {}
                tags = {**plabels, **labels, "gcp_project": pid, "gcp_project_name": project_name}

                # Determine region/location
                location = bucket.location or "unknown"

                resources.append({
                    "cloud_resource_id": f"gs://{bucket.name}",
                    "name": bucket.name,
                    "resource_type": "Cloud Storage Bucket",
                    "region": location,
                    "state": "active",
                    "tags": tags,
                    "meta": {
                        "storage_class": bucket.storage_class,
                        "time_created": bucket.time_created.isoformat() if bucket.time_created else None,
                        "location_type": bucket.location_type,
                        "public_access_prevention": bucket.iam_configuration.public_access_prevention if bucket.iam_configuration else None,
                        "project_id": pid,
                        "project_name": project_name,
                    },
                })
        except PermissionDenied:
            logger.warning(f"Permission denied when listing Cloud Storage buckets in {pid}")
        except NotFound:
            logger.warning(f"Cloud Storage API not enabled or project {pid} not found")
        except Exception as e:
            logger.warning(f"Failed to discover Cloud Storage buckets in {pid}: {_sanitize_csp_error(e)}")

        return resources

    def _discover_cloud_functions(self, project_id: str | None = None, project_name: str = "", project_labels: dict | None = None) -> list[dict]:
        """Discover Cloud Functions."""
        from google.cloud import functions_v2
        from google.api_core.exceptions import PermissionDenied, NotFound

        resources = []
        pid = project_id or self.project_id
        plabels = project_labels or {}
        try:
            credentials = self._get_credentials()
            client = functions_v2.FunctionServiceClient(credentials=credentials)

            parent = f"projects/{pid}/locations/-"
            request = functions_v2.ListFunctionsRequest(parent=parent)
            page_result = client.list_functions(request=request)

            for function in page_result:
                # Get labels as tags, merge with project labels
                labels = function.labels or {}
                tags = {**plabels, **dict(labels), "gcp_project": pid, "gcp_project_name": project_name}

                # Extract region from name
                # Format: projects/{project}/locations/{location}/functions/{function}
                parts = function.name.split("/")
                region = parts[3] if len(parts) > 3 else "unknown"

                # Determine state
                state_map = {
                    "ACTIVE": "active",
                    "FAILED": "failed",
                    "DEPLOYING": "deploying",
                    "DELETING": "deleting",
                    "UNKNOWN": "unknown",
                }
                state = state_map.get(function.state.name, function.state.name.lower())

                resources.append({
                    "cloud_resource_id": function.name,
                    "name": function.name.split("/")[-1],
                    "resource_type": "Cloud Function",
                    "region": region,
                    "state": state,
                    "tags": tags,
                    "meta": {
                        "runtime": function.build_config.runtime if function.build_config else "",
                        "entry_point": function.build_config.entry_point if function.build_config else "",
                        "memory": function.service_config.available_memory if function.service_config else "",
                        "timeout": str(function.service_config.timeout) if function.service_config and function.service_config.timeout else "",
                        "ingress_settings": function.service_config.ingress_settings.name if function.service_config and function.service_config.ingress_settings else "",
                    },
                })
        except PermissionDenied:
            logger.warning("Permission denied when listing Cloud Functions")
        except NotFound:
            logger.warning("Cloud Functions API not enabled or project not found")
        except Exception as e:
            logger.warning(f"Failed to discover Cloud Functions: {_sanitize_csp_error(e)}")

        return resources

    async def _enrich_resources_with_costs(self, resources: list[dict]) -> None:
        """Fetch costs from GCP and add daily_cost to each resource."""
        if not resources:
            return

        try:
            # Get last 7 days of costs grouped by resource
            end_date = utc_now().date()
            start_date = end_date - timedelta(days=7)

            cost_data = await self.get_cost_and_usage(
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                granularity="Daily",
                group_by=["resource"],
            )

            # Map resource names to costs (resource ID format varies)
            resource_costs = self._map_costs_by_resource_name(cost_data)

            # Calculate average daily cost for each resource
            days = 7
            for resource in resources:
                resource_name = resource.get("name", "")
                total_cost = resource_costs.get(resource_name.lower(), 0)
                daily_cost = round(total_cost / days, 4) if days > 0 else 0
                resource["daily_cost"] = daily_cost
                resource["total_cost_7d"] = round(total_cost, 4)

        except Exception as e:
            logger.warning(f"Failed to enrich resources with costs: {e}")
            for resource in resources:
                resource["daily_cost"] = 0
                resource["total_cost_7d"] = 0

    def _map_costs_by_resource_name(self, cost_data: dict) -> dict[str, float]:
        """Parse cost data and map resource names to total costs."""
        columns = cost_data.get("columns", [])
        rows = cost_data.get("rows", [])

        cost_idx = cost_data.get("cost_index", 1)

        # Find resource column index
        resource_idx = None
        for i, col in enumerate(columns):
            if col.lower() in ("resource", "resource_name", "name"):
                resource_idx = i
                break

        if cost_idx is None or resource_idx is None:
            return {}

        resource_costs = {}
        for row in rows:
            try:
                resource_name = str(row[resource_idx]).lower()
                cost = float(row[cost_idx])
                resource_costs[resource_name] = resource_costs.get(resource_name, 0) + cost
            except (IndexError, ValueError, TypeError):
                continue

        return resource_costs

    def _discover_vertex_ai_models(self, project_id: str | None = None, project_name: str = "", project_labels: dict | None = None) -> list[dict]:
        """Discover Vertex AI Models."""
        resources = []
        pid = project_id or self.project_id
        plabels = project_labels or {}
        try:
            from google.cloud import aiplatform

            credentials = self._get_credentials()
            aiplatform.init(project=pid, credentials=credentials)

            # List models across all locations
            for location in ["us-central1", "europe-west4", "asia-southeast1"]:
                try:
                    models = aiplatform.Model.list(project=pid, location=location)
                    for model in models:
                        labels = dict(model.gca_resource.labels) if hasattr(model.gca_resource, 'labels') and model.gca_resource.labels else {}
                        tags = {**plabels, **labels, "gcp_project": pid, "gcp_project_name": project_name}
                        resources.append({
                            "cloud_resource_id": model.resource_name,
                            "name": model.display_name,
                            "resource_type": "Vertex AI Model",
                            "region": location,
                            "state": "active" if model.gca_resource else "unknown",
                            "tags": tags,
                            "meta": {
                                "model_type": model.gca_resource.model_source_info.source_type.name if hasattr(model.gca_resource, 'model_source_info') else "custom",
                                "training_job": model.gca_resource.training_pipeline if hasattr(model.gca_resource, 'training_pipeline') else None,
                                "version_id": model.version_id,
                            },
                        })
                except Exception as e:
                    logger.debug(f"Failed to list Vertex AI models in {location}: {_sanitize_csp_error(e)}")
                    continue
        except Exception as e:
            logger.warning(f"Failed to discover Vertex AI models: {_sanitize_csp_error(e)}")
        return resources

    def _discover_vertex_ai_endpoints(self, project_id: str | None = None, project_name: str = "", project_labels: dict | None = None) -> list[dict]:
        """Discover Vertex AI Endpoints."""
        resources = []
        pid = project_id or self.project_id
        plabels = project_labels or {}
        try:
            from google.cloud import aiplatform

            credentials = self._get_credentials()
            aiplatform.init(project=pid, credentials=credentials)

            for location in ["us-central1", "europe-west4", "asia-southeast1"]:
                try:
                    endpoints = aiplatform.Endpoint.list(project=pid, location=location)
                    for endpoint in endpoints:
                        labels = dict(endpoint.gca_resource.labels) if hasattr(endpoint.gca_resource, 'labels') and endpoint.gca_resource.labels else {}
                        tags = {**plabels, **labels, "gcp_project": pid, "gcp_project_name": project_name}
                        resources.append({
                            "cloud_resource_id": endpoint.resource_name,
                            "name": endpoint.display_name,
                            "resource_type": "Vertex AI Endpoint",
                            "region": location,
                            "state": "active" if endpoint.gca_resource.deployed_models else "empty",
                            "tags": tags,
                            "meta": {
                                "deployed_models_count": len(endpoint.gca_resource.deployed_models) if hasattr(endpoint.gca_resource, 'deployed_models') else 0,
                                "private_endpoints": hasattr(endpoint.gca_resource, 'private_endpoints'),
                            },
                        })
                except Exception as e:
                    logger.debug(f"Failed to list Vertex AI endpoints in {location}: {_sanitize_csp_error(e)}")
                    continue
        except Exception as e:
            logger.warning(f"Failed to discover Vertex AI endpoints: {_sanitize_csp_error(e)}")
        return resources

    def _discover_vertex_ai_datasets(self, project_id: str | None = None, project_name: str = "", project_labels: dict | None = None) -> list[dict]:
        """Discover Vertex AI Datasets."""
        resources = []
        pid = project_id or self.project_id
        plabels = project_labels or {}
        try:
            from google.cloud import aiplatform

            credentials = self._get_credentials()
            aiplatform.init(project=pid, credentials=credentials)

            for location in ["us-central1", "europe-west4", "asia-southeast1"]:
                try:
                    datasets = aiplatform.TabularDataset.list(project=pid, location=location)
                    for dataset in datasets:
                        labels = dict(dataset.gca_resource.labels) if hasattr(dataset.gca_resource, 'labels') and dataset.gca_resource.labels else {}
                        tags = {**plabels, **labels, "gcp_project": pid, "gcp_project_name": project_name}
                        resources.append({
                            "cloud_resource_id": dataset.resource_name,
                            "name": dataset.display_name,
                            "resource_type": "Vertex AI Dataset",
                            "region": location,
                            "state": "active",
                            "tags": tags,
                            "meta": {
                                "dataset_type": "tabular",
                                "create_time": dataset.gca_resource.create_time.isoformat() if hasattr(dataset.gca_resource, 'create_time') else None,
                            },
                        })
                except Exception as e:
                    logger.debug(f"Failed to list Vertex AI datasets in {location}: {_sanitize_csp_error(e)}")
                    continue
        except Exception as e:
            logger.warning(f"Failed to discover Vertex AI datasets: {_sanitize_csp_error(e)}")
        return resources

    def _discover_vertex_ai_notebooks(self, project_id: str | None = None, project_name: str = "", project_labels: dict | None = None) -> list[dict]:
        """Discover Vertex AI Workbench Notebooks using REST API."""
        resources = []
        pid = project_id or self.project_id
        plabels = project_labels or {}
        try:
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError

            credentials = self._get_credentials()
            service = build('notebooks', 'v1', credentials=credentials)

            for location in ["us-central1", "europe-west4", "asia-southeast1"]:
                try:
                    parent = f"projects/{pid}/locations/{location}"
                    response = service.projects().locations().instances().list(parent=parent).execute()

                    for instance in response.get('instances', []):
                        labels = instance.get('labels', {})
                        tags = {**plabels, **labels, "gcp_project": pid, "gcp_project_name": project_name}
                        resources.append({
                            "cloud_resource_id": instance.get('name'),
                            "name": instance.get('name', '').split("/")[-1],
                            "resource_type": "Vertex AI Workbench",
                            "region": location,
                            "state": instance.get('state', 'unknown').lower(),
                            "tags": tags,
                            "meta": {
                                "machine_type": instance.get('machineType'),
                                "proxy_uri": instance.get('proxyUri'),
                                "create_time": instance.get('createTime'),
                            },
                        })
                except HttpError as e:
                    logger.debug(f"Failed to list Vertex AI notebooks in {location}: {_sanitize_csp_error(e)}")
                    continue
        except Exception as e:
            logger.warning(f"Failed to discover Vertex AI notebooks: {_sanitize_csp_error(e)}")
        return resources

    def _discover_discovery_engine_datastores(self, project_id: str | None = None, project_name: str = "", project_labels: dict | None = None) -> list[dict]:
        """Discover Discovery Engine (Vertex AI Search) Data Stores."""
        resources = []
        pid = project_id or self.project_id
        plabels = project_labels or {}
        try:
            from google.cloud import discoveryengine_v1

            credentials = self._get_credentials()
            client = discoveryengine_v1.DataStoreServiceClient(credentials=credentials)

            for location in ["global", "us", "eu"]:
                try:
                    parent = f"projects/{pid}/locations/{location}"
                    request = discoveryengine_v1.ListDataStoresRequest(parent=parent)
                    response = client.list_data_stores(request=request)

                    for datastore in response:
                        tags = {**plabels, "gcp_project": pid, "gcp_project_name": project_name}
                        resources.append({
                            "cloud_resource_id": datastore.name,
                            "name": datastore.display_name,
                            "resource_type": "Discovery Engine Data Store",
                            "region": location,
                            "state": "active",
                            "tags": tags,
                            "meta": {
                                "industry_vertical": datastore.industry_vertical.name,
                                "solution_types": [st.name for st in datastore.solution_types],
                                "content_config": datastore.content_config.name,
                                "create_time": datastore.create_time.isoformat() if datastore.create_time else None,
                            },
                        })
                except Exception as e:
                    logger.debug(f"Failed to list Discovery Engine datastores in {location}: {_sanitize_csp_error(e)}")
                    continue
        except Exception as e:
            logger.warning(f"Failed to discover Discovery Engine datastores: {_sanitize_csp_error(e)}")
        return resources

    def _discover_discovery_engine_engines(self, project_id: str | None = None, project_name: str = "", project_labels: dict | None = None) -> list[dict]:
        """Discover Discovery Engine (Vertex AI Search) Search Engines."""
        resources = []
        pid = project_id or self.project_id
        plabels = project_labels or {}
        try:
            from google.cloud import discoveryengine_v1

            credentials = self._get_credentials()
            client = discoveryengine_v1.EngineServiceClient(credentials=credentials)

            for location in ["global", "us", "eu"]:
                try:
                    parent = f"projects/{pid}/locations/{location}/collections/default_collection"
                    request = discoveryengine_v1.ListEnginesRequest(parent=parent)
                    response = client.list_engines(request=request)

                    for engine in response:
                        tags = {**plabels, "gcp_project": pid, "gcp_project_name": project_name}
                        resources.append({
                            "cloud_resource_id": engine.name,
                            "name": engine.display_name,
                            "resource_type": "Discovery Engine Search",
                            "region": location,
                            "state": "active",
                            "tags": tags,
                            "meta": {
                                "search_engine_type": engine.search_engine_config.search_engine_type.name if hasattr(engine, 'search_engine_config') else "unknown",
                                "data_stores": [ds.split("/")[-1] for ds in engine.data_store_ids],
                                "create_time": engine.create_time.isoformat() if engine.create_time else None,
                            },
                        })
                except Exception as e:
                    logger.debug(f"Failed to list Discovery Engine engines in {location}: {_sanitize_csp_error(e)}")
                    continue
        except Exception as e:
            logger.warning(f"Failed to discover Discovery Engine engines: {_sanitize_csp_error(e)}")
        return resources

    def _discover_dialogflow_agents(self, project_id: str | None = None, project_name: str = "", project_labels: dict | None = None) -> list[dict]:
        """Discover Dialogflow CX Agents using REST API."""
        resources = []
        pid = project_id or self.project_id
        plabels = project_labels or {}
        try:
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError

            credentials = self._get_credentials()
            service = build('dialogflow', 'v3', credentials=credentials)

            for location in ["global", "us-central1", "europe-west1"]:
                try:
                    parent = f"projects/{pid}/locations/{location}"
                    response = service.projects().locations().agents().list(parent=parent).execute()

                    for agent in response.get('agents', []):
                        labels = agent.get('labels', {})
                        tags = {**plabels, **labels, "gcp_project": pid, "gcp_project_name": project_name}
                        resources.append({
                            "cloud_resource_id": agent.get('name'),
                            "name": agent.get('displayName'),
                            "resource_type": "Dialogflow CX Agent",
                            "region": location,
                            "state": "active",
                            "tags": tags,
                            "meta": {
                                "default_language_code": agent.get('defaultLanguageCode'),
                                "time_zone": agent.get('timeZone'),
                                "enable_stackdriver_logging": agent.get('enableStackdriverLogging'),
                                "enable_spell_correction": agent.get('enableSpellCorrection'),
                            },
                        })
                except HttpError as e:
                    logger.debug(f"Failed to list Dialogflow agents in {location}: {_sanitize_csp_error(e)}")
                    continue
        except Exception as e:
            logger.warning(f"Failed to discover Dialogflow agents: {_sanitize_csp_error(e)}")
        return resources

    def _discover_vision_datasets(self, project_id: str | None = None, project_name: str = "", project_labels: dict | None = None) -> list[dict]:
        """Discover Vision AI Product Sets using REST API."""
        resources = []
        pid = project_id or self.project_id
        plabels = project_labels or {}
        try:
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError

            credentials = self._get_credentials()
            service = build('vision', 'v1', credentials=credentials)

            for location in ["us-central1", "europe-west1", "asia-east1"]:
                try:
                    parent = f"projects/{pid}/locations/{location}"
                    response = service.projects().locations().productSets().list(parent=parent).execute()

                    for product_set in response.get('productSets', []):
                        labels = product_set.get('labels', {})
                        tags = {**plabels, **labels, "gcp_project": pid, "gcp_project_name": project_name}
                        resources.append({
                            "cloud_resource_id": product_set.get('name'),
                            "name": product_set.get('displayName'),
                            "resource_type": "Vision AI Product Set",
                            "region": location,
                            "state": "active",
                            "tags": tags,
                            "meta": {
                                "index_time": product_set.get('indexTime'),
                            },
                        })
                except HttpError as e:
                    logger.debug(f"Failed to list Vision AI product sets in {location}: {_sanitize_csp_error(e)}")
                    continue
        except Exception as e:
            logger.warning(f"Failed to discover Vision AI datasets: {_sanitize_csp_error(e)}")
        return resources

    def _discover_automl_models(self, project_id: str | None = None, project_name: str = "", project_labels: dict | None = None) -> list[dict]:
        """Discover AutoML Models."""
        resources = []
        pid = project_id or self.project_id
        plabels = project_labels or {}
        try:
            from google.cloud import automl_v1

            credentials = self._get_credentials()
            client = automl_v1.AutoMlClient(credentials=credentials)

            for location in ["us-central1", "europe-west4", "asia-east1"]:
                try:
                    parent = f"projects/{pid}/locations/{location}"
                    request = automl_v1.ListModelsRequest(parent=parent)
                    response = client.list_models(request=request)

                    for model in response:
                        tags = {**plabels, "gcp_project": pid, "gcp_project_name": project_name}
                        resources.append({
                            "cloud_resource_id": model.name,
                            "name": model.display_name,
                            "resource_type": "AutoML Model",
                            "region": location,
                            "state": model.deployment_state.name.lower(),
                            "tags": tags,
                            "meta": {
                                "model_type": model.model_type,
                                "dataset_id": model.dataset_id,
                                "create_time": model.create_time.isoformat() if model.create_time else None,
                                "training_cost_milli_node_hours": model.training_cost_milli_node_hours if hasattr(model, 'training_cost_milli_node_hours') else None,
                            },
                        })
                except Exception as e:
                    logger.debug(f"Failed to list AutoML models in {location}: {_sanitize_csp_error(e)}")
                    continue
        except Exception as e:
            logger.warning(f"Failed to discover AutoML models: {_sanitize_csp_error(e)}")
        return resources
