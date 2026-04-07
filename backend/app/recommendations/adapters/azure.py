import asyncio
import logging

from app.recommendations.adapters.base import NormalizedRecommendation, RecommenderAdapter

logger = logging.getLogger(__name__)

_CATEGORY_MAP = {
    "Cost": "cost",
    "Security": "security",
    "HighAvailability": "reliability",
    "Performance": "performance",
    "OperationalExcellence": "operational_excellence",
}


class AzureRecommenderAdapter(RecommenderAdapter):
    """Fetch recommendations from Azure Advisor API."""

    async def fetch_recommendations(self, config: dict) -> list[NormalizedRecommendation]:
        try:
            return await asyncio.to_thread(self._fetch_sync, config)
        except Exception:
            logger.exception("Failed to fetch Azure recommendations")
            return []

    def _fetch_sync(self, config: dict) -> list[NormalizedRecommendation]:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.advisor import AdvisorManagementClient

        subscription_id = config.get("subscription_id", "")
        tenant_id = config.get("tenant_id", "")
        client_id = config.get("client_id", "")
        logger.debug("Starting Azure Advisor recommendation fetch")

        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=config.get("client_secret", ""),
        )
        client = AdvisorManagementClient(credential, subscription_id)

        results: list[NormalizedRecommendation] = []
        api_call_count = 0

        try:
            for rec in client.recommendations.list():
                api_call_count += 1
                
                # Skip suppressed/dismissed recommendations
                # When a recommendation is suppressed in Azure Portal, it has suppression_ids
                if rec.suppression_ids and len(rec.suppression_ids) > 0:
                    logger.debug("Skipping suppressed recommendation: %s", rec.short_description.problem if rec.short_description else "Unknown")
                    continue
                
                category = _CATEGORY_MAP.get(rec.category, "cost")
                saving = 0.0
                if rec.extended_properties:
                    saving_str = rec.extended_properties.get("annualSavingsAmount", "0")
                    try:
                        saving = float(saving_str) / 12  # Convert annual to monthly
                    except (ValueError, TypeError):
                        pass

                resource_id = rec.resource_metadata.resource_id if rec.resource_metadata else ""
                normalized_rec = NormalizedRecommendation(
                    rec_type=f"azure_{rec.category.lower()}" if rec.category else "azure_general",
                    name=rec.short_description.problem if rec.short_description else "Azure Recommendation",
                    description=rec.short_description.solution if rec.short_description else "",
                    category=category,
                    resource_id=resource_id,
                    resource_name=resource_id.split("/")[-1] if resource_id else "",
                    cloud_type="azure_cnr",
                    region=rec.resource_metadata.source if rec.resource_metadata else "",
                    source_service="Azure Advisor",
                    saving=saving,
                )
                results.append(normalized_rec)
                logger.debug("Azure API returned recommendation #%d: type=%s, name=%s, resource_id=%s, saving=%.2f",
                           api_call_count, normalized_rec.rec_type, normalized_rec.name, normalized_rec.resource_id, normalized_rec.saving)
            
            logger.debug("Azure Advisor API call completed - total recommendations fetched: %d", len(results))
        except Exception as e:
            logger.error("Azure Advisor API call failed: %s", str(e), exc_info=True)

        return results
