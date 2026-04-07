# CostPilot Test Suite

Comprehensive test suite covering all security implementations and clean code patterns.

## Test Structure

### Unit Tests

Individual component tests ensuring each module works correctly in isolation:

| File | Component | Coverage |
|------|-----------|----------|
| [`test_middleware_validation.py`](test_middleware_validation.py) | Input Validation Middleware | Request size, Content-Type, path traversal, headers |
| [`test_security_validators.py`](test_security_validators.py) | Security Validators | HTML injection, filename safety, UUID, email, sanitization |
| [`test_token_manager.py`](test_token_manager.py) | Secure Token Manager | Token generation, rotation, reuse detection, revocation |
| [`test_session_security.py`](test_session_security.py) | Session Security Validator | Fingerprint generation, IP binding, validation |
| [`test_field_encryption.py`](test_field_encryption.py) | Field-Level Encryption | Per-field encryption, batch operations, key derivation |
| [`test_credential_cache.py`](test_credential_cache.py) | Secure Credential Cache | Two-tier caching, TTL, invalidation, thread safety |
| [`test_audit_logger.py`](test_audit_logger.py) | Audit Logger | Event types, PII redaction, severity levels, hashing |
| [`test_rate_limiter.py`](test_rate_limiter.py) | Rate Limiting Middleware | Tiers, sliding window, headers, Redis/memory backends |
| [`test_base_service.py`](test_base_service.py) | Base Service | CRUD operations, pagination, soft delete, relations |
| [`test_error_handling.py`](test_error_handling.py) | Error Handling | Provider mapping, decorator, aggregator |
| [`test_dependencies.py`](test_dependencies.py) | Dependency Injection | Container, providers, mock implementations |

### E2E Tests

Integration tests covering complete workflows:

| File | Coverage |
|------|----------|
| [`test_e2e_security_flows.py`](test_e2e_security_flows.py) | Complete authentication, session binding, credential lifecycle |
| [`test_e2e_clean_code.py`](test_e2e_clean_code.py) | Type safety, service patterns, real-world scenarios |

## Running Tests

### Run All Tests

```bash
cd backend
pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest -m unit

# Security tests
pytest -m security

# Integration tests
pytest -m integration

# E2E tests
pytest -m e2e

# Exclude slow tests
pytest -m "not slow"
```

### Run Specific Test Files

```bash
pytest tests/test_token_manager.py
pytest tests/test_field_encryption.py -v
```

### Run With Coverage

```bash
pytest --cov=app --cov-report=html
pytest --cov=app --cov-report=term-missing
```

## Test Categories

### Security Tests

All security-related functionality is comprehensively tested:

- **Authentication**: Token generation, rotation, reuse detection
- **Authorization**: Session binding, IP validation, fingerprinting
- **Input Validation**: HTML injection prevention, path traversal blocking
- **Data Protection**: Field-level encryption, credential caching
- **API Security**: Rate limiting, request timeouts
- **Audit**: Event logging, PII redaction, privacy hashing

### Clean Code Tests

Validates clean code implementations:

- **Type Safety**: NewType usage, Result pattern, TypedDict
- **Service Pattern**: BaseService CRUD, pagination, soft delete
- **Error Handling**: Provider mapping, decorators, aggregation
- **Dependency Injection**: Container, providers, mocking

## Key Test Scenarios

### Token Manager

- ✅ Token pair generation (access + refresh)
- ✅ Token rotation on use
- ✅ Token reuse detection and revocation
- ✅ Session binding (sid_hash)
- ✅ Token revocation by user/session
- ✅ JWT expiration handling

### Session Security

- ✅ Fingerprint generation (IP + UA + headers)
- ✅ IP binding validation (/24 subnet matching)
- ✅ Strict vs lenient binding modes
- ✅ Fingerprint mismatch detection
- ✅ Timing-safe HMAC comparison

### Field Encryption

- ✅ Per-field key derivation (PBKDF2HMAC)
- ✅ Cryptographic isolation
- ✅ Batch encrypt/decrypt operations
- ✅ PII and sensitive field handling
- ✅ Unicode and large data support

### Rate Limiting

- ✅ Tier-based limits (PUBLIC, AUTHENTICATED, EXPENSIVE, EXPORT, WEBHOOK)
- ✅ Sliding window algorithm
- ✅ Redis and in-memory backends
- ✅ Rate limit headers
- ✅ Burst allowance

### Audit Logging

- ✅ 40+ event types
- ✅ 5 severity levels
- ✅ PII redaction (passwords, tokens, keys)
- ✅ IP/UA hashing for privacy
- ✅ Nested structure sanitization

## Mocking Strategy

The test suite uses extensive mocking to:

1. **Isolate components**: Mock external dependencies (Redis, DB, etc.)
2. **Control behavior**: Simulate errors, timeouts, edge cases
3. **Improve speed**: Avoid actual network/database calls
4. **Ensure repeatability**: Consistent test conditions

### Common Mocks

```python
# Mock Redis
mock_redis = AsyncMock()
mock_redis.get = AsyncMock(return_value=None)
mock_redis.setex = AsyncMock()

# Mock Database
mock_db = AsyncMock()
mock_db.execute = AsyncMock(return_value=mock_result)

# Mock Settings
with patch('app.config.settings') as mock_settings:
    mock_settings.JWT_SECRET = "test-secret"
```

## Fixtures

Reusable test fixtures are defined in:

- [`fixtures.py`](fixtures.py): Mock adapters, providers, test data
- [`factories.py`](factories.py): Test data factories

## Configuration

Test configuration is in [`pytest.ini`](../pytest.ini):

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow tests
    security: Security tests
```

## Adding New Tests

When adding new tests:

1. **Follow naming**: `test_<component>_<scenario>.py`
2. **Use markers**: `@pytest.mark.unit`, `@pytest.mark.security`
3. **Add docstrings**: Describe what's being tested
4. **Mock external**: Don't call real services
5. **Test edge cases**: Empty inputs, errors, boundaries
6. **Keep focused**: One concept per test function

Example:

```python
import pytest

@pytest.mark.unit
@pytest.mark.security
class TestNewFeature:
    """Test new security feature."""

    def test_happy_path(self):
        """Test normal operation."""
        # Arrange
        # Act
        # Assert

    def test_edge_case(self):
        """Test boundary condition."""
        # Test empty input, maximum value, etc.

    def test_error_handling(self):
        """Test error scenarios."""
        # Test exceptions, invalid input
```

## Coverage Goals

- **Unit Tests**: >90% code coverage
- **Integration Tests**: Key workflows covered
- **E2E Tests**: Critical user paths covered

## Continuous Integration

Tests should be run in CI with:

1. All tests passing
2. Coverage report generated
3. No warnings or errors
4. Security scan passed

## Troubleshooting

### Common Issues

1. **Async test failures**: Ensure `@pytest.mark.asyncio` is used
2. **Import errors**: Check PYTHONPATH includes backend directory
3. **Mock not working**: Verify patch target path is correct
4. **Flaky tests**: Check for time-dependent or stateful tests

### Debug Mode

```bash
# Run with verbose output
pytest -vvs

# Run with PDB on failure
pytest --pdb

# Run specific test with debugging
pytest tests/test_token_manager.py::TestTokenRotation::test_rotate_token_returns_new_pair -vvs
```

## Test Data

Test data is:

- **Deterministic**: Same input produces same output
- **Isolated**: No shared state between tests
- **Realistic**: Mirrors production data patterns
- **Safe**: No real credentials or PII

## Maintenance

- Update tests when code changes
- Remove obsolete tests
- Add tests for new features
- Refactor tests for clarity
- Review and update regularly
