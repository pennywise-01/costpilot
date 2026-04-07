import logging
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

# Database engine with connection pooling for high concurrency
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # Connection pool settings for supporting >5 concurrent users
    pool_size=settings.DB_POOL_SIZE,  # Base pool size
    max_overflow=settings.DB_MAX_OVERFLOW,  # Additional connections for spikes
    pool_timeout=settings.DB_POOL_TIMEOUT,  # Wait time for available connection
    pool_recycle=settings.DB_POOL_RECYCLE,  # Recycle connections periodically
    pool_pre_ping=settings.DB_POOL_PRE_PING,  # Verify connections before use
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
async_session_factory = async_session  # Alias for use in services

# Lazy-loaded MongoDB client (only created when needed)
_mongo_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    """Get MongoDB client with properly URL-encoded credentials and connection pooling."""
    global _mongo_client
    if _mongo_client is not None:
        return _mongo_client
    
    # Parse the MongoDB URL and encode username/password if present
    mongo_url = settings.MONGODB_URL
    if "://" in mongo_url:
        scheme, rest = mongo_url.split("://", 1)
        if "@" in rest:
            credentials, host_part = rest.rsplit("@", 1)
            if ":" in credentials:
                username, password = credentials.split(":", 1)
                encoded_username = quote_plus(username)
                encoded_password = quote_plus(password)
                mongo_url = f"{scheme}://{encoded_username}:{encoded_password}@{host_part}"
    
    # Create client with connection pooling settings
    _mongo_client = AsyncIOMotorClient(
        mongo_url,
        # Connection pool settings for high concurrency
        maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
        minPoolSize=settings.MONGODB_MIN_POOL_SIZE,
        maxIdleTimeMS=settings.MONGODB_MAX_IDLE_TIME_MS,
        waitQueueTimeoutMS=settings.MONGODB_WAIT_QUEUE_TIMEOUT_MS,
        # Server selection and retry settings
        serverSelectionTimeoutMS=5000,
        retryWrites=True,
    )
    return _mongo_client


def get_mongo_db():
    """Get MongoDB database instance."""
    return get_mongo_client()[settings.MONGODB_DB]


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_mongo():
    return get_mongo_db()


# Backward compatibility - lazy property-like access
class _MongoAccessor:
    """Lazy accessor for MongoDB client that doesn't connect until used."""
    
    @property
    def client(self) -> AsyncIOMotorClient:
        return get_mongo_client()
    
    @property
    def db(self):
        return get_mongo_db()
    
    def __getattr__(self, name):
        # Delegate to the actual client for any other attributes
        return getattr(get_mongo_client(), name)


# Module-level accessor that doesn't connect until accessed
mongo_client = _MongoAccessor()


async def check_db_health() -> dict:
    """Check database connection health.
    
    Returns:
        Dict with health status and connection pool stats
    """
    health = {
        "postgresql": {"status": "unknown", "pool": {}},
        "mongodb": {"status": "unknown"},
    }
    
    # Check PostgreSQL
    try:
        async with engine.connect() as conn:
            result = await conn.execute("SELECT 1")
            await result.scalar()
        health["postgresql"]["status"] = "healthy"
        health["postgresql"]["pool"] = {
            "size": engine.pool.size(),
            "checked_in": engine.pool.checkedin(),
            "checked_out": engine.pool.checkedout(),
            "overflow": engine.pool.overflow(),
        }
    except Exception as e:
        health["postgresql"]["status"] = "unhealthy"
        health["postgresql"]["error"] = str(e)
    
    # Check MongoDB
    try:
        client = get_mongo_client()
        await client.admin.command("ping")
        health["mongodb"]["status"] = "healthy"
    except Exception as e:
        health["mongodb"]["status"] = "unhealthy"
        health["mongodb"]["error"] = str(e)
    
    return health


async def close_mongo_client() -> None:
    """Close MongoDB client and release connections."""
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
        logging.info("MongoDB client closed")
