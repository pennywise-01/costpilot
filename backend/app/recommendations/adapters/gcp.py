import asyncio
import logging

from app.recommendations.adapters.base import NormalizedRecommendation, RecommenderAdapter

logger = logging.getLogger(__name__)

# GCP recommender IDs to query
_RECOMMENDER_IDS = [
    "google.compute.instance.MachineTypeRecommender",
    "google.compute.instance.IdleResourceRecommender",
    "google.compute.disk.IdleResourceRecommender",
]


class GcpRecommenderAdapter(RecommenderAdapter):
    """Fetch recommendations from GCP Recommender API."""

    async def fetch_recommendations(self, config: dict) -> list[NormalizedRecommendation]:
        try:
            return await asyncio.to_thread(self._fetch_sync, config)
        except Exception:
            logger.exception("Failed to fetch GCP recommendations")
            return []

    def _fetch_sync(self, config: dict) -> list[NormalizedRecommendation]:
        from google.cloud import recommender_v1

        project_id = config.get("project_id", "")
        zones = config.get("zones", ["us-central1-a"])

        client = recommender_v1.RecommenderClient()
        results: list[NormalizedRecommendation] = []

        for zone in zones:
            for recommender_id in _RECOMMENDER_IDS:
                parent = f"projects/{project_id}/locations/{zone}/recommenders/{recommender_id}"
                try:
                    for rec in client.list_recommendations(parent=parent):
                        saving = 0.0
                        if rec.primary_impact and rec.primary_impact.cost_projection:
                            cost = rec.primary_impact.cost_projection.cost
                            saving = abs(float(cost.units or 0) + float(cost.nanos or 0) / 1e9)
                            # Convert to monthly if duration is provided
                            duration = rec.primary_impact.cost_projection.duration
                            if duration and duration.seconds:
                                days = duration.seconds / 86400
                                if days > 0:
                                    saving = saving / days * 30

                        resource_name = ""
                        if rec.content and rec.content.operation_groups:
                            for op_group in rec.content.operation_groups:
                                for op in op_group.operations:
                                    if op.resource:
                                        resource_name = op.resource.split("/")[-1]
                                        break

                        rec_type = "idle_resource"
                        if "MachineType" in recommender_id:
                            rec_type = "rightsizing"
                        elif "Disk" in recommender_id:
                            rec_type = "idle_disk"

                        results.append(NormalizedRecommendation(
                            rec_type=rec_type,
                            name=rec.description or "GCP Recommendation",
                            description=rec.description or "",
                            category="cost",
                            resource_id=rec.name,
                            resource_name=resource_name,
                            cloud_type="gcp_cnr",
                            region=zone,
                            source_service="GCP Recommender",
                            saving=round(saving, 2),
                        ))
                except Exception:
                    logger.debug(
                        "GCP Recommender API call failed for %s/%s",
                        zone, recommender_id, exc_info=True,
                    )

        return results
