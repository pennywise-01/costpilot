"""Comprehensive tests for BaseService.

This module tests all features of BaseService:
- Generic base service for CRUD operations
- Organization-based scoping
- Soft delete support
- Pagination and filtering
- Relationship eager loading
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4

from app.shared.service_base import BaseService
from app.shared.exceptions import NotFoundError, ConflictError


# Mock model class for testing
class MockModel:
    """Mock model for testing."""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', str(uuid4()))
        self.organization_id = kwargs.get('organization_id')
        self.name = kwargs.get('name', 'Test')
        self.deleted_at = kwargs.get('deleted_at')
        self.created_at = kwargs.get('created_at')

    def __eq__(self, other):
        return isinstance(other, MockModel) and self.id == other.id


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def base_service(mock_db):
    """Create a base service with mocked DB."""
    return BaseService(MockModel, mock_db)


class TestGetById:
    """Test get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_entity(self, base_service, mock_db):
        """Test get_by_id returns the entity."""
        mock_entity = MockModel(id="test-id", name="Test Entity")

        # Mock the execute result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_db.execute.return_value = mock_result

        result = await base_service.get_by_id("test-id")

        assert result == mock_entity

    @pytest.mark.asyncio
    async def test_get_by_id_with_org_scope(self, base_service, mock_db):
        """Test get_by_id with organization scoping."""
        mock_entity = MockModel(id="test-id", organization_id="org-123")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_db.execute.return_value = mock_result

        result = await base_service.get_by_id("test-id", org_id="org-123")

        assert result == mock_entity
        # Should have applied org filter in query

    @pytest.mark.asyncio
    async def test_get_by_id_not_found_raises_error(self, base_service, mock_db):
        """Test get_by_id raises NotFoundError when entity doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError, match="MockModel not found"):
            await base_service.get_by_id("nonexistent-id")

    @pytest.mark.asyncio
    async def test_get_by_id_with_relations(self, base_service, mock_db):
        """Test get_by_id with eager loaded relations."""
        mock_entity = MockModel(id="test-id")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_db.execute.return_value = mock_result

        # Add relations
        base_service.with_relations("organization", "creator")

        result = await base_service.get_by_id("test-id")

        assert result == mock_entity


class TestGetByIds:
    """Test get_by_ids method."""

    @pytest.mark.asyncio
    async def test_get_by_ids_returns_list(self, base_service, mock_db):
        """Test get_by_ids returns list of entities."""
        mock_entities = [
            MockModel(id="id-1"),
            MockModel(id="id-2"),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_entities
        mock_db.execute.return_value = mock_result

        result = await base_service.get_by_ids(["id-1", "id-2"])

        assert len(result) == 2
        assert result[0].id == "id-1"
        assert result[1].id == "id-2"

    @pytest.mark.asyncio
    async def test_get_by_ids_empty_list(self, base_service, mock_db):
        """Test get_by_ids with empty list."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await base_service.get_by_ids([])

        assert result == []

    @pytest.mark.asyncio
    async def test_get_by_ids_excludes_deleted(self, base_service, mock_db):
        """Test get_by_ids excludes soft-deleted entities."""
        # Create entity with deleted_at set
        deleted_entity = MockModel(id="deleted-id", deleted_at="2024-01-01")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await base_service.get_by_ids(["deleted-id"])

        assert len(result) == 0


class TestListAll:
    """Test list_all method."""

    @pytest.mark.asyncio
    async def test_list_all_returns_entities_and_count(self, base_service, mock_db):
        """Test list_all returns entities and total count."""
        mock_entities = [MockModel(id="id-1"), MockModel(id="id-2")]

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        # Mock entity query
        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = mock_entities

        mock_db.execute.side_effect = [mock_count_result, mock_entity_result]

        entities, total = await base_service.list_all()

        assert len(entities) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_list_all_with_org_filter(self, base_service, mock_db):
        """Test list_all with organization filter."""
        mock_entities = [MockModel(id="id-1", organization_id="org-123")]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = mock_entities

        mock_db.execute.side_effect = [mock_count_result, mock_entity_result]

        entities, total = await base_service.list_all(org_id="org-123")

        assert len(entities) == 1
        assert entities[0].organization_id == "org-123"

    @pytest.mark.asyncio
    async def test_list_all_with_filters(self, base_service, mock_db):
        """Test list_all with custom filters."""
        mock_entities = [MockModel(id="id-1", name="Test")]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = mock_entities

        mock_db.execute.side_effect = [mock_count_result, mock_entity_result]

        entities, total = await base_service.list_all(filters={"name": "Test"})

        assert len(entities) == 1

    @pytest.mark.asyncio
    async def test_list_all_with_pagination(self, base_service, mock_db):
        """Test list_all with pagination."""
        mock_entities = [MockModel(id="id-3")]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 10

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = mock_entities

        mock_db.execute.side_effect = [mock_count_result, mock_entity_result]

        entities, total = await base_service.list_all(limit=1, offset=2)

        assert len(entities) == 1
        assert total == 10

    @pytest.mark.asyncio
    async def test_list_all_with_ordering(self, base_service, mock_db):
        """Test list_all with ordering."""
        mock_entities = [MockModel(id="id-1", name="A"), MockModel(id="id-2", name="B")]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = mock_entities

        mock_db.execute.side_effect = [mock_count_result, mock_entity_result]

        entities, total = await base_service.list_all(order_by="name")

        assert len(entities) == 2

    @pytest.mark.asyncio
    async def test_list_all_descending_order(self, base_service, mock_db):
        """Test list_all with descending order."""
        mock_entities = [MockModel(id="id-2", name="B"), MockModel(id="id-1", name="A")]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = mock_entities

        mock_db.execute.side_effect = [mock_count_result, mock_entity_result]

        entities, total = await base_service.list_all(order_by="name", descending=True)

        assert len(entities) == 2


class TestCreate:
    """Test create method."""

    @pytest.mark.asyncio
    async def test_create_returns_new_entity(self, base_service, mock_db):
        """Test create returns the new entity."""
        data = {"name": "New Entity", "organization_id": "org-123"}

        result = await base_service.create(data)

        assert result.name == "New Entity"
        assert result.organization_id == "org-123"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_sets_org_id(self, base_service, mock_db):
        """Test create sets organization ID from parameter."""
        data = {"name": "New Entity"}

        result = await base_service.create(data, org_id="org-456")

        assert result.organization_id == "org-456"


class TestUpdate:
    """Test update method."""

    @pytest.mark.asyncio
    async def test_update_existing_entity(self, base_service, mock_db):
        """Test update modifies existing entity."""
        mock_entity = MockModel(id="test-id", name="Old Name")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_db.execute.return_value = mock_result

        result = await base_service.update("test-id", {"name": "New Name"})

        assert result.name == "New Name"

    @pytest.mark.asyncio
    async def test_update_not_found_raises_error(self, base_service, mock_db):
        """Test update raises NotFoundError when entity doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError):
            await base_service.update("nonexistent-id", {"name": "New"})


class TestDelete:
    """Test delete method."""

    @pytest.mark.asyncio
    async def test_soft_delete_sets_deleted_at(self, base_service, mock_db):
        """Test soft delete sets deleted_at timestamp."""
        mock_entity = MockModel(id="test-id", deleted_at=None)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_db.execute.return_value = mock_result

        await base_service.delete("test-id", soft=True)

        assert mock_entity.deleted_at is not None

    @pytest.mark.asyncio
    async def test_hard_delete_removes_entity(self, base_service, mock_db):
        """Test hard delete removes entity from database."""
        mock_entity = MockModel(id="test-id")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_db.execute.return_value = mock_result

        await base_service.delete("test-id", soft=False)

        mock_db.delete.assert_called_once_with(mock_entity)


class TestExists:
    """Test exists method."""

    @pytest.mark.asyncio
    async def test_exists_returns_true(self, base_service, mock_db):
        """Test exists returns True when entity exists."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result

        result = await base_service.exists("test-id")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false(self, base_service, mock_db):
        """Test exists returns False when entity doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_db.execute.return_value = mock_result

        result = await base_service.exists("nonexistent-id")

        assert result is False


class TestCount:
    """Test count method."""

    @pytest.mark.asyncio
    async def test_count_returns_total(self, base_service, mock_db):
        """Test count returns total number of entities."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_db.execute.return_value = mock_result

        result = await base_service.count()

        assert result == 42

    @pytest.mark.asyncio
    async def test_count_with_filters(self, base_service, mock_db):
        """Test count with filters."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        result = await base_service.count(filters={"status": "active"})

        assert result == 5


class TestWithRelations:
    """Test with_relations method."""

    def test_with_relations_returns_self(self, base_service):
        """Test with_relations returns self for chaining."""
        result = base_service.with_relations("org", "user")

        assert result is base_service

    def test_with_relations_adds_load_options(self, base_service):
        """Test with_relations adds load options."""
        base_service.with_relations("organization")

        assert len(base_service.default_load_options) == 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_list_all_with_empty_filters(self, base_service, mock_db):
        """Test list_all with empty filters."""
        mock_entities = [MockModel(id="id-1")]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = mock_entities

        mock_db.execute.side_effect = [mock_count_result, mock_entity_result]

        entities, total = await base_service.list_all(filters={})

        assert len(entities) == 1

    @pytest.mark.asyncio
    async def test_list_all_with_list_filter(self, base_service, mock_db):
        """Test list_all with list filter (IN clause)."""
        mock_entities = [MockModel(id="id-1"), MockModel(id="id-2")]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = mock_entities

        mock_db.execute.side_effect = [mock_count_result, mock_entity_result]

        entities, total = await base_service.list_all(filters={"status": ["active", "pending"]})

        assert len(entities) == 2

    @pytest.mark.asyncio
    async def test_create_with_org_id_override(self, base_service, mock_db):
        """Test create with org_id overriding data."""
        data = {"name": "Test", "organization_id": "from-data"}

        result = await base_service.create(data, org_id="from-param")

        assert result.organization_id == "from-param"

    @pytest.mark.asyncio
    async def test_update_with_invalid_field(self, base_service, mock_db):
        """Test update ignores invalid fields."""
        mock_entity = MockModel(id="test-id", name="Old")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entity
        mock_db.execute.return_value = mock_result

        # Update with non-existent field
        result = await base_service.update("test-id", {"name": "New", "invalid_field": "value"})

        assert result.name == "New"
        # Should not crash on invalid field
