from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.recommendation_rules.models import RecommendationRule, RecommendationRuleCondition
from app.recommendation_rules.schemas import RecRuleCreate, RecRuleUpdate
from app.recommendations.schemas import RecommendationType
from app.shared.exceptions import NotFoundError


async def create_rec_rule(
    db: AsyncSession, org_id: str, creator_id: str, data: RecRuleCreate
) -> RecommendationRule:
    """Create a new recommendation rule with conditions. Auto-assigns next priority."""
    result = await db.execute(
        select(func.coalesce(func.max(RecommendationRule.priority), 0)).where(
            RecommendationRule.organization_id == org_id,
            RecommendationRule.deleted_at.is_(None),
        )
    )
    max_priority = result.scalar_one()
    next_priority = max_priority + 1

    rule = RecommendationRule(
        name=data.name,
        description=data.description,
        priority=next_priority,
        organization_id=org_id,
        creator_id=creator_id,
        active=data.active,
        category=data.category,
        severity=data.severity,
        action_description=data.action_description,
        saving_type=data.saving_type,
        saving_value=data.saving_value,
    )
    db.add(rule)
    await db.flush()

    for condition_data in data.conditions:
        condition = RecommendationRuleCondition(
            type=condition_data.type,
            rule_id=rule.id,
            meta_info=condition_data.meta_info,
        )
        db.add(condition)

    await db.flush()
    await db.refresh(rule)
    return rule


async def list_rec_rules(db: AsyncSession, org_id: str) -> list[RecommendationRule]:
    """List all recommendation rules for an organization, ordered by priority."""
    result = await db.execute(
        select(RecommendationRule)
        .where(
            RecommendationRule.organization_id == org_id,
            RecommendationRule.deleted_at.is_(None),
        )
        .order_by(RecommendationRule.priority)
    )
    return list(result.scalars().all())


async def get_rec_rule(db: AsyncSession, rule_id: str) -> RecommendationRule:
    """Get a single recommendation rule by ID."""
    result = await db.execute(
        select(RecommendationRule).where(
            RecommendationRule.id == rule_id,
            RecommendationRule.deleted_at.is_(None),
        ).limit(1)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundError("Recommendation rule not found")
    return rule


async def update_rec_rule(
    db: AsyncSession, rule_id: str, data: RecRuleUpdate
) -> RecommendationRule:
    """Update a recommendation rule and optionally replace its conditions."""
    rule = await get_rec_rule(db, rule_id)

    if data.name is not None:
        rule.name = data.name
    if data.description is not None:
        rule.description = data.description
    if data.category is not None:
        rule.category = data.category
    if data.severity is not None:
        rule.severity = data.severity
    if data.action_description is not None:
        rule.action_description = data.action_description
    if data.saving_type is not None:
        rule.saving_type = data.saving_type
    if data.saving_value is not None:
        rule.saving_value = data.saving_value
    if data.active is not None:
        rule.active = data.active

    if data.conditions is not None:
        # Soft delete existing conditions
        for condition in rule.conditions:
            condition.deleted_at = datetime.now(timezone.utc)

        # Create new conditions
        for condition_data in data.conditions:
            condition = RecommendationRuleCondition(
                type=condition_data.type,
                rule_id=rule.id,
                meta_info=condition_data.meta_info,
            )
            db.add(condition)

    await db.flush()
    await db.refresh(rule)
    return rule


async def delete_rec_rule(db: AsyncSession, rule_id: str) -> RecommendationRule:
    """Soft delete a recommendation rule and its conditions."""
    rule = await get_rec_rule(db, rule_id)
    now = datetime.now(timezone.utc)
    rule.deleted_at = now
    for condition in rule.conditions:
        condition.deleted_at = now
    await db.flush()
    return rule


async def evaluate_custom_rules(
    db: AsyncSession, org_id: str
) -> list[RecommendationType]:
    """Convert active recommendation rules into RecommendationType objects."""
    rules = await list_rec_rules(db, org_id)
    results: list[RecommendationType] = []

    for rule in rules:
        if not rule.active:
            continue

        # Generate a unique type key from the rule id
        rec_type = f"custom_rule_{rule.id}"

        results.append(
            RecommendationType(
                type=rec_type,
                name=rule.name,
                description=rule.description or rule.action_description,
                category=rule.category,
                cloud_types=[],
                count=0,
                saving=rule.saving_value if rule.saving_type.value == "fixed" else 0,
                items=[],
                rules=[],
                source="custom_rule",
            )
        )

    return results
