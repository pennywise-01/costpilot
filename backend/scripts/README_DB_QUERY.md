# CostPilot Database Query Script

A comprehensive CLI tool for querying and managing the CostPilot database.

## Prerequisites

Before using this script, ensure:

1. **Docker Compose is running** with PostgreSQL, MongoDB, and Redis services
2. **Python dependencies are installed** (run from `backend/` directory):
   ```bash
   pip install -r requirements.txt
   ```

## Starting the Database

If using Docker Compose, start the services first:

```bash
# From project root
docker-compose up -d postgres mongodb redis
```

## Usage

Navigate to the `backend/` directory and run:

```bash
cd backend
python scripts/db_query.py [OPTIONS]
```

### Available Commands

#### 1. List All Registered Users

```bash
python scripts/db_query.py --list-users
```

**Output:** Displays all active users (excluding soft-deleted) with:
- User ID, Email, Display Name, Role, Status, Verification Status, Creation Date

#### 2. List All Organizations

```bash
python scripts/db_query.py --list-orgs
```

**Output:** Displays all active organizations (excluding soft-deleted) with:
- Organization ID, Name, Currency, Pool ID, Demo Status, Disabled Status, Creation Date

#### 3. Create a New Organization

```bash
python scripts/db_query.py --create-org --name "Acme Corp" --currency USD
```

**Optional flags:**
- `--currency CURRENCY` - Currency code (default: USD)
- `--demo` - Mark as demo organization

**Example:**
```bash
python scripts/db_query.py --create-org --name "Demo Company" --currency EUR --demo
```

#### 4. Create a New User

```bash
python scripts/db_query.py --create-user --email "john@example.com" --name "John Doe" --password "SecurePass123!"
```

**Optional flags:**
- `--role {optscale_member,optscale_engineer,optscale_manager}` - User role (default: optscale_member)
- `--verified` - Mark user as verified

**Example:**
```bash
python scripts/db_query.py --create-user --email "admin@example.com" --name "Admin User" --password "Admin123!" --role optscale_manager --verified
```

#### 5. Add User to Organization

```bash
python scripts/db_query.py --add-to-org --user-id <USER_UUID> --org-id <ORG_UUID> --name "John Doe"
```

This creates an Employee record linking the user to the organization.

**Optional flags:**
- `--role {optscale_member,optscale_engineer,optscale_manager}` - Employee role (default: optscale_member)

## Examples

### Complete Workflow: Create Org, User, and Link Them

```bash
# Step 1: Create organization
python scripts/db_query.py --create-org --name "TechCorp" --currency USD
# Output: ID: abc123-def456-...

# Step 2: Create user
python scripts/db_query.py --create-user --email "alice@techcorp.com" --name "Alice Smith" --password "Password123!"
# Output: ID: xyz789-uvw012-...

# Step 3: Link user to organization
python scripts/db_query.py --add-to-org --user-id xyz789-uvw012-... --org-id abc123-def456-... --name "Alice Smith"
```

### List All Data

```bash
# View all users
python scripts/db_query.py --list-users

# View all organizations
python scripts/db_query.py --list-orgs
```

## Database Schema Reference

### Users Table
- **id**: UUID (String 36)
- **email**: String (256, unique)
- **display_name**: String (256)
- **hashed_password**: String (256, bcrypt hashed)
- **is_active**: Boolean (default: True)
- **verified**: Boolean (default: False)
- **role**: Enum (optscale_member, optscale_engineer, optscale_manager)
- **status**: String (32) - active, pending, suspended, deactivated, locked
- **created_at**: DateTime
- **updated_at**: DateTime
- **deleted_at**: DateTime (nullable, for soft deletes)

### Organizations Table
- **id**: UUID (String 36)
- **name**: String (256)
- **currency**: String (3, default: "USD")
- **pool_id**: String (36, foreign key to pools.id, nullable)
- **is_demo**: Boolean (default: False)
- **disabled**: Boolean (default: False)
- **created_at**: DateTime
- **updated_at**: DateTime
- **deleted_at**: DateTime (nullable, for soft deletes)

### Employees Table (User-Organization Link)
- **id**: UUID (String 36)
- **name**: String (256)
- **organization_id**: String (36, foreign key to organizations.id)
- **auth_user_id**: String (36, foreign key to users.id)
- **role**: Enum (optscale_member, optscale_engineer, optscale_manager)
- **joined_at**: DateTime
- **department**: String (128, nullable)
- **job_title**: String (128, nullable)

## Troubleshooting

### Connection Refused Error
```
ConnectionRefusedError: [WinError 1225] The remote computer refused the network connection
```
**Solution:** Ensure Docker Compose services are running:
```bash
docker-compose up -d postgres mongodb redis
```

### Module Import Errors
**Solution:** Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

### Password Hashing Error
**Solution:** Ensure `passlib` and `bcrypt` are installed:
```bash
pip install passlib[bcrypt] bcrypt
```

## Advanced Usage (Interactive Python)

For more complex queries, you can use Python interactively:

```bash
cd backend
python
```

```python
import asyncio
from sqlalchemy import select
from app.database import async_session
from app.auth.models import User
from app.organizations.models import Organization

async def custom_query():
    async with async_session() as session:
        # Example: Find user by email
        stmt = select(User).where(User.email == "test@example.com")
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        print(user)

asyncio.run(custom_query())
```

## Notes

- All queries exclude soft-deleted records (where `deleted_at IS NULL`)
- Passwords are automatically hashed using bcrypt
- UUIDs are generated automatically for new records
- Timestamps (`created_at`, `updated_at`) are set automatically
- The script uses async database sessions for optimal performance
