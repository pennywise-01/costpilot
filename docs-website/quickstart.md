# Quick Start Guide

Get CostPilot up and running in 5 minutes with this quick start guide.

---

## Prerequisites

- **Docker**: Docker Desktop installed and running
- **Docker Compose**: Version 2.0 or higher
- **Git**: For cloning the repository
- **Browser**: Modern browser (Chrome, Firefox, Edge, Safari)

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/costpilot.git
cd costpilot
```

---

## Step 2: Configure Environment Variables

Copy the example environment file and customize it:

```bash
cp .env.example .env
```

**Minimum Required Configuration:**

```env
# Database
DATABASE_URL=postgresql+asyncpg://costpilot:costpilot@db:5432/costpilot

# Redis
REDIS_URL=redis://redis:6379/0

# MongoDB
MONGODB_URL=mongodb://mongo:27017
MONGODB_DB_NAME=costpilot

# JWT Secret (generate a strong random string)
JWT_SECRET=your-super-secret-jwt-key-change-this

# Encryption Key (32-byte Fernet key)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-fernet-encryption-key

# Frontend URL (adjust if using different port)
FRONTEND_URL=http://localhost:5173
```

---

## Step 3: Start with Docker Compose

```bash
docker-compose up -d
```

This will start:
- **PostgreSQL**: Primary database
- **MongoDB**: Expense line items storage
- **Redis**: Caching and session management
- **Backend API**: FastAPI server (port 8000)
- **Frontend**: React app (port 5173)

**Check Status:**

```bash
docker-compose ps
```

All services should show "Up" status.

---

## Step 4: Access the Application

Open your browser and navigate to:

```
http://localhost:5173
```

**Note**: If using WSL2, you may need to access via the WSL2 IP address instead:
```
http://<WSL2-IP>:5173
```

---

## Step 5: Create Your First Account

1. Click **"Register"** on the login page
2. Fill in your details:
   - Email address
   - Display name
   - Password (minimum 8 characters, include uppercase, lowercase, number, special character)
3. Click **"Register"**
4. You'll be automatically logged in and a new organization will be created for you

**Default Roles Created:**
- You'll be assigned the **Organization Admin** role automatically
- System creates 6 default roles: Organization Admin, Admin View Only, Engineer, Viewer, Billing Admin, Security Auditor

---

## Step 6: Connect Your First Cloud Account

1. Navigate to **Cloud Accounts** from the left sidebar
2. Click **"Connect Cloud Account"**
3. Select your cloud provider (AWS, Azure, or GCP)
4. Enter your credentials:

**For AWS:**
- Access Key ID
- Secret Access Key
- Region (optional, defaults to us-east-1)

**For Azure:**
- Subscription ID
- Client ID
- Client Secret
- Tenant ID

**For GCP:**
- Service Account Credentials JSON
- Organization ID or Project ID

5. Click **"Validate & Connect"**
6. Wait for credential validation (takes a few seconds)
7. Account will be created and data collection will begin

---

## Step 7: Explore the Dashboard

Once connected, the dashboard will show:

- **Monthly Spend**: Current month's total cost
- **Forecast**: Predicted end-of-month cost
- **Last Month Cost**: Previous month's total
- **Potential Savings**: From optimization recommendations
- **Cost Trend Chart**: 30-day cost history
- **Cloud Account Cards**: Per-account costs with trends
- **Top Resources**: Most expensive resources
- **Recommendations by Category**: Savings opportunities

**Note**: Initial data collection may take a few minutes. The dashboard uses caching with 5-minute TTL for live data.

---

## Step 8: Invite Team Members

1. Navigate to **Users** from the left sidebar
2. Click **"Invite User"**
3. Enter the team member's email
4. Select their role (e.g., Engineer, Viewer, Billing Admin)
5. Click **"Send Invitation"**
6. The invitee will receive an email with an acceptance link

**Bulk Invite:**
- Click **"Bulk Invite"**
- Enter multiple emails (one per line)
- Select a default role
- All invitations will be sent

---

## Step 9: Set Up Budget Pools

1. Navigate to **Pools** from the left sidebar
2. Click **"Create Pool"**
3. Fill in:
   - Pool name
   - Budget limit (optional)
   - Purpose type (Budget, Business Unit, Team, Project, CI/CD, ML/AI, Asset Pool)
   - Parent pool (optional, for nesting)
4. Click **"Create"**

**Example Structure:**
```
Root Pool
├── Engineering
│   ├── Backend Team
│   └── Frontend Team
├── Data Science
│   └── ML Training
└── Infrastructure
    └── Production
```

---

## Step 10: Configure Recommendations

1. Navigate to **Recommendation Rules** from the left sidebar
2. Click **"Create Rule"**
3. Define your rule:
   - Rule name and description
   - Category (Cost, Security, Reliability, Performance, Operational Excellence)
   - Severity (Critical, High, Medium, Low)
   - Savings type (Fixed amount or Percentage)
   - Conditions (e.g., resource type, tags, name patterns)
4. Click **"Create"**

**Example Rule:**
```
Name: "Identify idle development instances"
Category: Cost
Severity: Medium
Savings: 30% of cost
Conditions:
  - tag_is: environment=development
  - resource_type_is: EC2 Instance
```

---

## Next Steps

Now that you have CostPilot running, explore these features:

- **[Dashboard](dashboard.md)** - Understand your cost overview
- **[Cloud Accounts](cloud-accounts.md)** - Learn about connecting cloud providers
- **[Expense Tracking](expenses.md)** - Deep dive into cost analysis
- **[Resource Discovery](resources.md)** - Track your cloud resources
- **[User Management](users.md)** - Manage your team
- **[Schedulers](schedulers.md)** - Automate data collection

---

## Troubleshooting

### Can't Access the Application

**Check Container Status:**
```bash
docker-compose ps
```

**View Logs:**
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Database Connection Issues

**Run Migrations:**
```bash
docker-compose exec backend alembic upgrade head
```

### Redis Not Available

**Check Redis:**
```bash
docker-compose exec redis redis-cli ping
```

Should return: `PONG`

### Frontend Shows Blank Page

**Clear Browser Cache:**
- Hard refresh: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
- Clear cache and reload

### Backend API Errors

**Check Backend Logs:**
```bash
docker-compose logs --tail=100 backend
```

Look for error messages and stack traces.

---

## Default Ports

| Service | Port | URL |
|---------|------|-----|
| Frontend | 5173 | http://localhost:5173 |
| Backend API | 8000 | http://localhost:8000 |
| API Docs | 8000 | http://localhost:8000/docs |
| PostgreSQL | 5432 | localhost:5432 |
| MongoDB | 27017 | localhost:27017 |
| Redis | 6379 | localhost:6379 |

---

## Health Checks

**Simple Health Check:**
```
http://localhost:8000/health
```

**Detailed Health Check (localhost only):**
```
http://localhost:8000/health/detailed
```

**API Health:**
```
http://localhost:8000/api/v1/health
```

---

## Need Help?

- **[Overview](overview.md)** - Learn about CostPilot's capabilities
- **[Installation Guide](installation.md)** - Detailed deployment instructions
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions
- **[API Reference](api-reference.md)** - Complete REST API documentation

---

**Ready to explore?** Start with the [Dashboard Documentation](dashboard.md)
