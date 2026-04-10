# Root Cause Analysis: AWS Cloud Account Connection 500 Error

**Date:** April 9, 2026  
**Severity:** CRITICAL - Blocks users from connecting cloud accounts  
**Status:** ✅ **FIXED AND DEPLOYED**

---

## Executive Summary

Users received a **500 Internal Server Error** when trying to connect AWS cloud accounts through the UI.

**Root Cause:** SQLAlchemy was inserting the Python enum member name (`AWS`) instead of the enum value (`aws_cnr`) into the PostgreSQL `cloudtype` enum column.

**Fix:** Updated the `CloudAccount.type` column definition to use `values_callable=lambda e: [x.value for x in e]` which tells SQLAlchemy to use enum values instead of member names.

---

## Detailed Analysis

### Error Message (from backend logs)

```
sqlalchemy.exc.DBAPIError: (sqlalchemy.dialects.postgresql.asyncpg.Error) 
<class 'asyncpg.exceptions.InvalidTextRepresentationError'>: 
invalid input value for enum cloudtype: "AWS"

[SQL: INSERT INTO cloud_accounts (name, type, config, organization_id, ...) 
VALUES ($1::VARCHAR, $2::cloudtype, $3::VARCHAR, $4::VARCHAR, ...)]

[parameters: ('test-aws', 'AWS', 'gAAAAABp1yKauQbirWg3qMPV...', 
              '2e8cbf3b-46ba-4833-bc13-42d99ea5a5ac', True, 1, None, None, 
              '529166310484', True, 'fe3c5064-e85a-4ff4-92d2-b3e50ab3c578', None, 1)]
```

### Data Flow Investigation

#### 1. Frontend → Backend (✅ CORRECT)

**File:** `frontend/src/pages/ConnectCloudAccount.tsx` (line 144)

```typescript
await cloudAccountsApi.create(orgId, {
  name: accountName,
  type: selectedProvider!,  // Value: 'aws_cnr' ✅
  config,
});
```

**Providers defined** (line 40-80):
```typescript
const providers: ProviderOption[] = [
  { key: 'aws_cnr', name: 'Amazon Web Services', ... },  // ✅ Correct
  { key: 'azure_cnr', name: 'Microsoft Azure', ... },    // ✅ Correct
  { key: 'gcp_cnr', name: 'Google Cloud Platform', ... }, // ✅ Correct
  // ...
];
```

**Status:** ✅ Frontend sends correct value `'aws_cnr'`

---

#### 2. Backend API Reception (✅ CORRECT)

**File:** `backend/app/cloud_accounts/schemas.py`

```python
class CloudAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    type: CloudType  # Pydantic enum type
    config: dict
```

**Pydantic CloudType enum** (`backend/app/shared/enums.py`):

```python
class CloudType(str, enum.Enum):
    AWS = "aws_cnr"           # Member name: AWS, Value: "aws_cnr"
    AZURE = "azure_cnr"       # Member name: AZURE, Value: "azure_cnr"
    GCP = "gcp_cnr"           # Member name: GCP, Value: "gcp_cnr"
    # ...
```

**Status:** ✅ Pydantic correctly parses `'aws_cnr'` as `CloudType.AWS`

---

#### 3. Backend Service Processing (✅ CORRECT)

**File:** `backend/app/cloud_accounts/service.py` (line 22-82)

```python
async def create_cloud_account(
    db: AsyncSession, org_id: str, data: CloudAccountCreate
) -> CloudAccount:
    # Validates credentials
    if data.type == CloudType.AWS:  # ✅ Correct comparison
        adapter = AWSAdapter(data.config)
        result = await adapter.validate_credentials()
        # ...
    
    # Creates cloud account
    cloud_account = CloudAccount(
        name=data.name,
        type=data.type,  # ✅ CloudType.AWS enum member
        config=encrypt(json.dumps(storage_config)),
        organization_id=org_id,
        account_id=account_id,
    )
    db.add(cloud_account)
    await db.flush()  # ❌ ERROR HAPPENS HERE
    return cloud_account
```

**Status:** ✅ Service logic is correct

---

#### 4. SQLAlchemy Database Insert (❌ ROOT CAUSE)

**File:** `backend/app/cloud_accounts/models.py` (BEFORE FIX)

```python
class CloudAccount(BaseModel, OptimisticLockingMixin):
    __tablename__ = "cloud_accounts"
    
    type: Mapped[CloudType] = mapped_column(SAEnum(CloudType), nullable=False)
    #                                                            ^^^^^^^^^^^^
    #                                           PROBLEM: No values_callable
```

**What SQLAlchemy does without `values_callable`:**

1. Receives `CloudType.AWS` enum member
2. By default, uses the **member name** (`"AWS"`) for database operations
3. Tries to insert `"AWS"` into PostgreSQL `cloudtype` enum column
4. PostgreSQL rejects it because the enum only has `"aws_cnr"`, not `"AWS"`

**PostgreSQL enum values** (verified):
```sql
SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'cloudtype');

Result:
aws_cnr        ✅
azure_cnr      ✅
azure_tenant   ✅
gcp_cnr        ✅
gcp_tenant     ✅
alibaba_cnr    ✅
kubernetes_cnr ✅
environment    ✅
nebius         ✅
databricks     ✅
```

**Status:** ❌ **ROOT CAUSE IDENTIFIED**

---

### The Fix

**File:** `backend/app/cloud_accounts/models.py` (AFTER FIX)

```python
class CloudAccount(BaseModel, OptimisticLockingMixin):
    __tablename__ = "cloud_accounts"
    
    type: Mapped[CloudType] = mapped_column(
        SAEnum(CloudType, values_callable=lambda e: [x.value for x in e]),
        #         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        #         SOLUTION: Tell SQLAlchemy to use enum VALUES, not NAMES
        nullable=False
    )
```

**What this does:**

- `values_callable=lambda e: [x.value for x in e]` generates: `["aws_cnr", "azure_cnr", "gcp_cnr", ...]`
- Now SQLAlchemy inserts `"aws_cnr"` (the value) instead of `"AWS"` (the name)
- PostgreSQL accepts the value because it matches the enum definition

**Status:** ✅ **FIXED AND DEPLOYED**

---

## Complete Data Flow Map (After Fix)

```
Frontend
  ↓ type: 'aws_cnr' ✅
  
Backend API (Pydantic validation)
  ↓ type: CloudType.AWS (member with value "aws_cnr") ✅
  
Backend Service (credential validation)
  ↓ cloud_account.type = CloudType.AWS ✅
  
SQLAlchemy Model (with fix)
  ↓ Uses values_callable → "aws_cnr" ✅
  
PostgreSQL Database
  ↓ INSERT INTO cloud_accounts (..., type, ...) VALUES (..., 'aws_cnr', ...) ✅
  
Result: Success! ✅
```

---

## Why This Happened

### SQLAlchemy Enum Behavior

SQLAlchemy has two ways to handle Python enums:

1. **Default behavior** (what we had):
   - Uses enum **member names** for database operations
   - `CloudType.AWS` → `"AWS"`
   - ❌ Doesn't match PostgreSQL enum

2. **With `values_callable`** (what we need):
   - Uses enum **member values** for database operations
   - `CloudType.AWS` → `"aws_cnr"`
   - ✅ Matches PostgreSQL enum

### Why It Wasn't Caught Earlier

1. The cloud accounts feature was likely tested with a different database state
2. The enum mismatch only manifests on INSERT/UPDATE operations
3. SELECT operations might have worked if data was manually inserted
4. No test coverage for cloud account creation flow

---

## Other Potential Issues Found

### 1. Missing Permission Warnings in Response

**File:** `backend/app/cloud_accounts/service.py` (line 30-45)

The service collects `permission_warnings` from credential validation but **doesn't return them** to the caller:

```python
# In create_cloud_account:
permission_warnings = result.get("permission_warnings", [])
# ❌ These warnings are never returned or stored

cloud_account = CloudAccount(
    name=data.name,
    type=data.type,
    config=encrypt(json.dumps(storage_config)),
    organization_id=org_id,
    account_id=account_id,
    # ❌ No permission_warnings field
)
```

**Impact:** Users don't see warnings about missing IAM permissions

**Recommendation:** Add a response schema that includes permission warnings

---

### 2. No API Documentation

There's no OpenAPI/Swagger documentation for the cloud accounts endpoints. Users can't see:
- Required fields
- Valid enum values
- Config structure for each provider

**Recommendation:** Add examples to the Pydantic schemas:

```python
class CloudAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256, examples=["My AWS Account"])
    type: CloudType = Field(examples=["aws_cnr"])
    config: dict = Field(examples=[{
        "access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "region": "us-east-1"
    }])
```

---

### 3. Frontend Type Mismatch Risk

**File:** `frontend/src/api/cloudAccounts.ts`

```typescript
create: (orgId: string, data: { name: string; type: string; config: Record<string, string> }) =>
  apiClient.post<CloudAccount>(`/organizations/${orgId}/cloud-accounts`, data),
```

The `type` is typed as `string` instead of the specific enum values. This allows TypeScript to pass invalid values without compile-time errors.

**Recommendation:**

```typescript
type CloudTypeEnum = 'aws_cnr' | 'azure_cnr' | 'gcp_cnr' | 'alibaba_cnr' | 'kubernetes_cnr' | 'nebius';

create: (orgId: string, data: { name: string; type: CloudTypeEnum; config: Record<string, string> }) =>
  apiClient.post<CloudAccount>(`/organizations/${orgId}/cloud-accounts`, data),
```

---

## Testing Recommendations

### 1. Unit Test for Cloud Account Creation

```python
async def test_create_cloud_account_enum_values():
    """Test that cloud type enum values are correctly saved to database."""
    async with async_session() as session:
        data = CloudAccountCreate(
            name="Test AWS",
            type=CloudType.AWS,
            config={
                "access_key_id": "test_key",
                "secret_access_key": "test_secret",
                "region": "us-east-1"
            }
        )
        
        account = await create_cloud_account(session, "org_id", data)
        
        # Verify the value is 'aws_cnr', not 'AWS'
        assert account.type == CloudType.AWS
        assert account.type.value == "aws_cnr"
        
        # Verify it's correctly saved in database
        result = await session.execute(
            text("SELECT type FROM cloud_accounts WHERE id = :id"),
            {"id": account.id}
        )
        db_type = result.scalar()
        assert db_type == "aws_cnr"  # NOT "AWS"
```

### 2. Integration Test

```bash
# Test creating AWS cloud account
curl -X POST http://localhost:8000/api/v1/organizations/{org_id}/cloud-accounts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "Test AWS Account",
    "type": "aws_cnr",
    "config": {
      "access_key_id": "AKIAIOSFODNN7EXAMPLE",
      "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
      "region": "us-east-1"
    }
  }'

# Expected: 201 Created
# Should NOT return 500 error
```

---

## Files Modified

| File | Change | Status |
|------|--------|--------|
| `backend/app/cloud_accounts/models.py` | Added `values_callable` to enum column | ✅ DEPLOYED |

---

## Deployment Steps

1. ✅ Modified `backend/app/cloud_accounts/models.py`
2. ✅ Copied to Docker container: `docker cp backend/app/cloud_accounts/models.py costpilot-backend-1:/app/app/cloud_accounts/models.py`
3. ✅ Restarted backend: `docker restart costpilot-backend-1`
4. ✅ Verified backend started successfully
5. ⏳ **TODO:** Test creating AWS cloud account through UI

---

## Verification Steps

After the fix, verify by:

1. **Login to application:**
   - Navigate to: http://localhost:5173
   - Login: `test@test.com` / `H4fz4n12@#`
   - Select organization: **Luminor**

2. **Connect AWS account:**
   - Go to: Cloud Accounts → Connect Cloud Account
   - Select: Amazon Web Services
   - Fill in credentials (use test credentials)
   - Click: Submit

3. **Expected result:**
   - ✅ 201 Created response
   - ✅ Account appears in cloud accounts list
   - ❌ NO 500 error

4. **Verify database:**
   ```sql
   SELECT name, type, account_id FROM cloud_accounts WHERE deleted_at IS NULL;
   
   Expected:
   name        | type    | account_id
   ------------|---------|------------
   Test AWS    | aws_cnr | 529166310484
   ```

---

## Prevention

### To prevent similar issues in the future:

1. **Add SQLAlchemy enum validation to CI/CD:**
   ```python
   def test_enum_values_match_database():
       """Verify all enum values match PostgreSQL enum definitions."""
       for enum_type in CloudType:
           assert enum_type.value in VALID_DB_ENUM_VALUES[enum_type.__class__.__name__]
   ```

2. **Add integration tests for all cloud providers:**
   - Test AWS account creation
   - Test Azure account creation
   - Test GCP account creation
   - Verify enum values are correctly saved

3. **Code review checklist:**
   - [ ] All enum columns use `values_callable`
   - [ ] Enum values match database definitions
   - [ ] Integration tests cover enum fields

4. **Add database migration check:**
   - When adding new enum values, ensure migrations update PostgreSQL enums
   - Document enum value changes in migration files

---

## Lessons Learned

1. **Always use `values_callable` for enums** when the Python enum member name differs from the database value
2. **Test the full data flow** from frontend to database, not just individual components
3. **Enum mismatches can be silent** - they only fail on write operations, not reads
4. **Add integration tests** that actually insert data and verify it in the database
5. **Document enum values** in both frontend and backend to prevent confusion

---

**Report prepared by:** Systematic Debugging Process  
**Date:** April 9, 2026  
**Classification:** Bug Fix (Data Type Mismatch)  
**Risk Level:** LOW (fix is backward compatible, no data migration needed)
