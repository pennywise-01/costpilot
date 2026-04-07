"""Feature flag system."""
import logging
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class FeatureFlag:
    """Simple in-memory feature flag store."""
    
    _flags: dict[str, dict] = {}
    
    @classmethod
    def register(cls, name: str, enabled: bool = False, rollout_percentage: float = 100.0, description: str = ""):
        """Register a feature flag."""
        cls._flags[name] = {
            "name": name,
            "enabled": enabled,
            "rollout_percentage": rollout_percentage,
            "description": description,
        }
        logger.info(f"Feature flag registered: {name} (enabled={enabled})")
    
    @classmethod
    def is_enabled(cls, name: str, user_id: Optional[str] = None) -> bool:
        """Check if a feature is enabled for a user."""
        flag = cls._flags.get(name)
        if not flag or not flag["enabled"]:
            return False
        
        # Use user_id for consistent rollout
        if user_id and flag["rollout_percentage"] < 100.0:
            user_hash = hash(user_id) % 100
            return user_hash < flag["rollout_percentage"]
        
        return True
    
    @classmethod
    def get_flag(cls, name: str) -> Optional[dict]:
        """Get flag details."""
        return cls._flags.get(name)
    
    @classmethod
    def list_flags(cls) -> list[dict]:
        """List all flags."""
        return list(cls._flags.values())
    
    @classmethod
    def set_flag(cls, name: str, enabled: bool, rollout_percentage: float = 100.0):
        """Update a flag."""
        if name not in cls._flags:
            raise KeyError(f"Feature flag '{name}' not found")
        cls._flags[name]["enabled"] = enabled
        cls._flags[name]["rollout_percentage"] = rollout_percentage
        logger.info(f"Feature flag updated: {name} (enabled={enabled})")


# Register existing feature flags from config
def init_feature_flags():
    """Initialize feature flags from config settings."""
    from app.config import settings
    
    FeatureFlag.register(
        "structured_logging",
        enabled=True,
        description="JSON structured logging"
    )
    
    FeatureFlag.register(
        "correlation_ids",
        enabled=True,
        description="X-Correlation-ID header propagation"
    )
    
    FeatureFlag.register(
        "gzip_compression",
        enabled=True,
        description="Response gzip compression"
    )
    
    FeatureFlag.register(
        "csrf_protection",
        enabled=True,
        description="CSRF double-submit cookie"
    )
    
    FeatureFlag.register(
        "idempotency",
        enabled=True,
        description="Idempotency key support"
    )
    
    FeatureFlag.register(
        "mfa",
        enabled=True,
        description="Multi-factor authentication"
    )
    
    FeatureFlag.register(
        "brute_force_protection",
        enabled=True,
        description="Login brute force protection"
    )
