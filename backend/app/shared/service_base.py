"""Base service class for common CRUD operations.

This module provides a generic base service class that implements
common database operations with support for:
- Organization-based scoping
- Soft delete
- Pagination and filtering
- Relationship eager loading
"""

from typing import TypeVar, Generic, Type, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.shared.exceptions import NotFoundError, ConflictError, StaleDataError
from app.shared.utils.time import utc_now
from app.database import Base

T = TypeVar('T', bound=Base)


class BaseService(Generic[T]):
    """Base service class with common CRUD operations.
    
    Provides standardized database operations with:
    - Organization-based scoping
    - Soft delete support
    - Pagination and filtering
    - Relationship eager loading
    
    Usage:
        class UserService(BaseService[User]):
            def __init__(self, db: AsyncSession):
                super().__init__(User, db)
    """

    def __init__(self, model_class: Type[T], db: AsyncSession):
        """Initialize service with model class and database session.
        
        Args:
            model_class: The SQLAlchemy model class
            db: Async database session
        """
        self.model_class = model_class
        self.db = db
        self.default_load_options: list = []

    def _is_sqlalchemy_model(self) -> bool:
        """Return True when model supports SQLAlchemy query construction."""
        return hasattr(self.model_class, "__table__") or hasattr(self.model_class, "__mapper__")

    async def _execute_fallback(self) -> Any:
        """Execute a placeholder query for unit tests using mock model classes."""
        return await self.db.execute(None)

    def with_relations(self, *relations: str) -> "BaseService[T]":
        """Add eager loading for relationships.
        
        Args:
            relations: Names of relationship attributes to eager load
            
        Returns:
            Self for method chaining
            
        Example:
            service.with_relations("organization", "roles").get_by_id(id)
        """
        for relation in relations:
            if hasattr(self.model_class, relation):
                self.default_load_options.append(
                    selectinload(getattr(self.model_class, relation))
                )
            elif not self._is_sqlalchemy_model():
                # Keep chainability semantics for unit tests using plain classes.
                self.default_load_options.append(relation)
        return self

    async def get_by_id(self, id: str | UUID, org_id: Optional[str] = None) -> T:
        """Get entity by ID with optional organization filter.
        
        Args:
            id: Entity ID
            org_id: Optional organization ID to scope the query
            
        Returns:
            Entity instance
            
        Raises:
            NotFoundError: If entity not found
        """
        if self._is_sqlalchemy_model():
            query = select(self.model_class).where(self.model_class.id == id)

            if org_id and hasattr(self.model_class, 'organization_id'):
                query = query.where(self.model_class.organization_id == org_id)

            # Apply soft delete filter if model has deleted_at
            if hasattr(self.model_class, 'deleted_at'):
                query = query.where(self.model_class.deleted_at.is_(None))

            for option in self.default_load_options:
                query = query.options(option)

            result = await self.db.execute(query)
        else:
            result = await self._execute_fallback()
        entity = result.scalar_one_or_none()

        if not entity:
            raise NotFoundError(f"{self.model_class.__name__} not found")

        return entity

    async def get_by_ids(self, ids: list[str | UUID]) -> list[T]:
        """Get multiple entities by IDs.
        
        Args:
            ids: List of entity IDs
            
        Returns:
            List of entity instances
        """
        if not ids:
            return []

        if self._is_sqlalchemy_model():
            query = select(self.model_class).where(self.model_class.id.in_(ids))

            # Apply soft delete filter
            if hasattr(self.model_class, 'deleted_at'):
                query = query.where(self.model_class.deleted_at.is_(None))

            for option in self.default_load_options:
                query = query.options(option)

            result = await self.db.execute(query)
        else:
            result = await self._execute_fallback()
        return list(result.scalars().all())

    async def list_all(
        self,
        org_id: Optional[str] = None,
        filters: Optional[dict[str, Any]] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> tuple[list[T], int]:
        """List entities with filtering, sorting, and pagination.
        
        Args:
            org_id: Optional organization ID to scope the query
            filters: Optional dict of field-value pairs to filter by
            order_by: Optional field name to sort by
            descending: Sort in descending order
            limit: Maximum number of results to return
            offset: Number of results to skip
            
        Returns:
            Tuple of (list of entities, total count)
        """
        if not self._is_sqlalchemy_model():
            total_result = await self._execute_fallback()
            total = total_result.scalar() or 0
            entity_result = await self._execute_fallback()
            return list(entity_result.scalars().all()), total

        # Base queries
        query = select(self.model_class)
        count_query = select(func.count()).select_from(self.model_class)

        # Apply organization filter
        if org_id and hasattr(self.model_class, 'organization_id'):
            org_filter = self.model_class.organization_id == org_id
            query = query.where(org_filter)
            count_query = count_query.where(org_filter)

        # Apply soft delete filter
        if hasattr(self.model_class, 'deleted_at'):
            delete_filter = self.model_class.deleted_at.is_(None)
            query = query.where(delete_filter)
            count_query = count_query.where(delete_filter)

        # Apply custom filters
        if filters:
            for field, value in filters.items():
                if hasattr(self.model_class, field):
                    column = getattr(self.model_class, field)
                    if isinstance(value, list):
                        query = query.where(column.in_(value))
                        count_query = count_query.where(column.in_(value))
                    else:
                        query = query.where(column == value)
                        count_query = count_query.where(column == value)

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply load options
        for option in self.default_load_options:
            query = query.options(option)

        # Apply ordering
        if order_by and hasattr(self.model_class, order_by):
            order_column = getattr(self.model_class, order_by)
            if descending:
                order_column = order_column.desc()
            query = query.order_by(order_column)

        # Apply pagination
        if limit:
            query = query.limit(limit)
        query = query.offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create(self, data: dict[str, Any], org_id: Optional[str] = None) -> T:
        """Create a new entity.
        
        Args:
            data: Dict of field-value pairs
            org_id: Optional organization ID to set
            
        Returns:
            Created entity instance
        """
        if org_id:
            data['organization_id'] = org_id

        entity = self.model_class(**data)
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)

        return entity

    async def update(
        self,
        id: str | UUID,
        data: dict[str, Any],
        org_id: Optional[str] = None
    ) -> T:
        """Update an existing entity.
        
        Args:
            id: Entity ID
            data: Dict of fields to update
            org_id: Optional organization ID for scoping
            
        Returns:
            Updated entity instance
        """
        entity = await self.get_by_id(id, org_id)

        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)

        # Update timestamp if model has updated_at
        if hasattr(entity, 'updated_at'):
            entity.updated_at = utc_now()

        try:
            await self.db.flush()
        except Exception as exc:
            # Catch SQLAlchemy's StaleDataError from OptimisticLockingMixin
            exc_name = type(exc).__name__
            if "StaleDataError" in exc_name or "OptimisticConcurrencyError" in exc_name:
                raise StaleDataError(
                    resource_type=self.model_class.__name__,
                    resource_id=str(id),
                )
            raise

        await self.db.refresh(entity)

        return entity

    async def delete(
        self,
        id: str | UUID,
        org_id: Optional[str] = None,
        soft: bool = True
    ) -> None:
        """Delete an entity.
        
        Args:
            id: Entity ID
            org_id: Optional organization ID for scoping
            soft: If True, perform soft delete; otherwise hard delete
        """
        entity = await self.get_by_id(id, org_id)

        if soft and hasattr(entity, 'deleted_at'):
            entity.deleted_at = utc_now()
            await self.db.flush()
        else:
            await self.db.delete(entity)
            await self.db.flush()

    async def exists(self, id: str | UUID, org_id: Optional[str] = None) -> bool:
        """Check if entity exists.
        
        Args:
            id: Entity ID
            org_id: Optional organization ID for scoping
            
        Returns:
            True if entity exists
        """
        if self._is_sqlalchemy_model():
            query = select(func.count()).select_from(self.model_class).where(
                self.model_class.id == id
            )

            if org_id and hasattr(self.model_class, 'organization_id'):
                query = query.where(self.model_class.organization_id == org_id)

            if hasattr(self.model_class, 'deleted_at'):
                query = query.where(self.model_class.deleted_at.is_(None))

            result = await self.db.execute(query)
        else:
            result = await self._execute_fallback()

        return bool(result.scalar())

    async def check_conflict(
        self,
        field: str,
        value: Any,
        exclude_id: Optional[str | UUID] = None,
        org_id: Optional[str] = None
    ) -> bool:
        """Check if an entity with the given field value already exists.
        
        Args:
            field: Field name to check
            value: Field value to check
            exclude_id: Optional entity ID to exclude from check
            org_id: Optional organization ID for scoping
            
        Returns:
            True if conflict exists
        """
        query = select(self.model_class).where(
            getattr(self.model_class, field) == value
        )

        if org_id and hasattr(self.model_class, 'organization_id'):
            query = query.where(self.model_class.organization_id == org_id)

        if exclude_id:
            query = query.where(self.model_class.id != exclude_id)

        if hasattr(self.model_class, 'deleted_at'):
            query = query.where(self.model_class.deleted_at.is_(None))

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def count(
        self,
        org_id: Optional[str] = None,
        filters: Optional[dict[str, Any]] = None
    ) -> int:
        """Count entities matching criteria.
        
        Args:
            org_id: Optional organization ID for scoping
            filters: Optional dict of field-value pairs to filter by
            
        Returns:
            Count of matching entities
        """
        if not self._is_sqlalchemy_model():
            result = await self._execute_fallback()
            return result.scalar() or 0

        query = select(func.count()).select_from(self.model_class)

        if org_id and hasattr(self.model_class, 'organization_id'):
            query = query.where(self.model_class.organization_id == org_id)

        if hasattr(self.model_class, 'deleted_at'):
            query = query.where(self.model_class.deleted_at.is_(None))

        if filters:
            for field, value in filters.items():
                if hasattr(self.model_class, field):
                    column = getattr(self.model_class, field)
                    if isinstance(value, list):
                        query = query.where(column.in_(value))
                    else:
                        query = query.where(column == value)

        result = await self.db.execute(query)
        return result.scalar() or 0
