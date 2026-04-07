"""Model factories for testing.

This module provides factory classes for creating test data
using the factory_boy library.
"""

import factory
from factory import Faker, SubFactory, LazyAttribute, Sequence

# Note: These factories assume the models exist in the app
# Uncomment and adjust based on your actual model imports

# from app.auth.models import User
# from app.organizations.models import Organization, Employee
# from app.cloud_accounts.models import CloudAccount
# from app.shared.crypto import encrypt


class UserFactory(factory.Factory):
    """Factory for creating test users."""

    class Meta:
        # model = User
        pass  # Remove this line when model is imported

    id = Sequence(lambda n: f"user-{n:03d}")
    email = LazyAttribute(lambda obj: f"{obj.id}@test.com")
    hashed_password = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/IJG"  # 'testpassword'
    is_active = True
    is_superuser = False


class OrganizationFactory(factory.Factory):
    """Factory for creating test organizations."""

    class Meta:
        # model = Organization
        pass  # Remove this line when model is imported

    id = Sequence(lambda n: f"org-{n:03d}")
    name = Faker("company")
    slug = LazyAttribute(lambda obj: obj.name.lower().replace(" ", "-"))


class EmployeeFactory(factory.Factory):
    """Factory for creating test employees."""

    class Meta:
        # model = Employee
        pass  # Remove this line when model is imported

    id = Sequence(lambda n: f"emp-{n:03d}")
    user = SubFactory(UserFactory)
    organization = SubFactory(OrganizationFactory)
    role = "member"


class CloudAccountFactory(factory.Factory):
    """Factory for creating test cloud accounts."""

    class Meta:
        # model = CloudAccount
        pass  # Remove this line when model is imported

    id = Sequence(lambda n: f"account-{n:03d}")
    name = Faker("word")
    organization = SubFactory(OrganizationFactory)
    type = "aws"
    # config = LazyAttribute(lambda _: encrypt('{"access_key_id": "test"}'))
    is_active = True


class ResourceFactory(factory.Factory):
    """Factory for creating test resources."""

    class Meta:
        pass

    id = Sequence(lambda n: f"resource-{n:03d}")
    name = Faker("word")
    resource_type = "ec2"
    region = "us-east-1"
    status = "running"
    cost_per_month = 100.0
    tags = factory.Dict({"Name": Faker("word"), "Environment": "test"})


class PoolFactory(factory.Factory):
    """Factory for creating test pools."""

    class Meta:
        pass

    id = Sequence(lambda n: f"pool-{n:03d}")
    name = Faker("word")
    budget = 1000.0
    organization = SubFactory(OrganizationFactory)


# Factory registry for easy access
FACTORIES = {
    "user": UserFactory,
    "organization": OrganizationFactory,
    "employee": EmployeeFactory,
    "cloud_account": CloudAccountFactory,
    "resource": ResourceFactory,
    "pool": PoolFactory,
}


def get_factory(name: str):
    """Get a factory by name.

    Args:
        name: Factory name

    Returns:
        Factory class

    Raises:
        KeyError: If factory not found
    """
    if name not in FACTORIES:
        raise KeyError(f"Factory '{name}' not found. Available: {list(FACTORIES.keys())}")
    return FACTORIES[name]
