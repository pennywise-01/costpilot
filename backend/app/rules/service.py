from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.rules.models import Rule, Condition
from app.rules.schemas import RuleCreate, RuleUpdate
from app.shared.exceptions import NotFoundError


async def create_rule(
    db: AsyncSession, org_id: str, creator_id: str, owner_id: str, data: RuleCreate
) -> Rule:
    """Create a new rule with conditions. Auto-assigns next priority."""
    result = await db.execute(
        select(func.coalesce(func.max(Rule.priority), 0)).where(
            Rule.organization_id == org_id,
            Rule.deleted_at.is_(None),
        )
    )
    max_priority = result.scalar_one()
    next_priority = max_priority + 1

    rule = Rule(
        name=data.name,
        priority=next_priority,
        organization_id=org_id,
        pool_id=data.pool_id,
        owner_id=owner_id,
        creator_id=creator_id,
        active=data.active,
    )
    db.add(rule)
    await db.flush()

    for condition_data in data.conditions:
        condition = Condition(
            type=condition_data.type,
            rule_id=rule.id,
            meta_info=condition_data.meta_info,
        )
        db.add(condition)

    await db.flush()
    await db.refresh(rule)
    return rule


async def list_rules(db: AsyncSession, org_id: str, offset: int = 0, limit: int = 50) -> tuple[list[Rule], int]:
    """List all rules for an organization, ordered by priority."""
    # Get total count
    count_result = await db.execute(
        select(func.count(Rule.id)).where(
            Rule.organization_id == org_id,
            Rule.deleted_at.is_(None),
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Rule)
        .where(Rule.organization_id == org_id, Rule.deleted_at.is_(None))
        .options(selectinload(Rule.conditions))
        .order_by(Rule.priority)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def get_rule(db: AsyncSession, rule_id: str) -> Rule:
    """Get a single rule by ID."""
    result = await db.execute(
        select(Rule)
        .where(Rule.id == rule_id, Rule.deleted_at.is_(None))
        .options(selectinload(Rule.conditions))
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundError("Rule not found")
    return rule


async def update_rule(
    db: AsyncSession, rule_id: str, data: RuleUpdate, owner_id: str | None = None
) -> Rule:
    """Update a rule and optionally replace its conditions."""
    rule = await get_rule(db, rule_id)

    if data.name is not None:
        rule.name = data.name
    if data.pool_id is not None:
        rule.pool_id = data.pool_id
    # SEC-20: owner_id can only be changed via explicit server-side parameter
    if owner_id is not None:
        rule.owner_id = owner_id
    if data.active is not None:
        rule.active = data.active

    if data.conditions is not None:
        # Remove existing conditions (soft delete)
        for condition in rule.conditions:
            condition.deleted_at = datetime.now(timezone.utc)

        # Create new conditions
        new_conditions = []
        for condition_data in data.conditions:
            condition = Condition(
                type=condition_data.type,
                rule_id=rule.id,
                meta_info=condition_data.meta_info,
            )
            db.add(condition)
            new_conditions.append(condition)

    await db.flush()
    await db.refresh(rule)
    return rule


async def delete_rule(db: AsyncSession, rule_id: str) -> Rule:
    """Soft delete a rule and its conditions."""
    rule = await get_rule(db, rule_id)
    now = datetime.now(timezone.utc)
    rule.deleted_at = now
    for condition in rule.conditions:
        condition.deleted_at = now
    await db.flush()
    return rule
