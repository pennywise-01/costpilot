import sys
from pathlib import Path

# Add the backend directory to Python path so 'app' module can be found
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.config import settings
from app.database import Base

# Import all models so they are registered with Base.metadata
from app.auth.models import User  # noqa: F401
from app.organizations.models import Organization, Employee  # noqa: F401
from app.cloud_accounts.models import CloudAccount  # noqa: F401
from app.pools.models import Pool, PoolPolicy  # noqa: F401
from app.rules.models import Rule, Condition  # noqa: F401
from app.notifications.models import NotificationPreference, NotificationLog  # noqa: F401
from app.recommendation_rules.models import RecommendationRule, RecommendationRuleCondition  # noqa: F401
from app.enterprise.modules.rbac.models import Role, RolePermission, UserRoleAssignment, ABACPolicy, AccessReview, SSOConfig  # noqa: F401
from app.dashboards.models import Dashboard  # noqa: F401
from app.advisor_findings.models import AdvisorFinding  # noqa: F401
from app.config_ingestors.models import ResourceConfigSnapshot  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
