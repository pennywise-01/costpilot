# CostPilot Overview

## What is CostPilot?

CostPilot is an enterprise-grade cloud cost optimization platform that helps organizations track, analyze, and optimize their cloud spending across multiple cloud providers including AWS, Azure, and Google Cloud Platform (GCP).

Built with modern technologies including FastAPI (Python 3.12+), React 18 with TypeScript, PostgreSQL, MongoDB, and Redis, CostPilot provides a comprehensive solution for FinOps teams to manage cloud costs effectively.

---

## Key Capabilities

### 💰 Multi-Cloud Cost Tracking
- **Unified Dashboard**: View costs across AWS, Azure, and GCP in a single pane of glass
- **Real-time Data**: Live cost data with 5-minute caching and stale-cache fallback
- **Cost Breakdown**: Analyze costs by cloud provider, service, region, pool, or owner
- **Trend Analysis**: 30-day cost trends with period-over-period comparisons
- **Forecasting**: Predict future costs based on historical data

### 🔍 Resource Discovery
- **Automatic Discovery**: Automatically discover cloud resources across all connected accounts
- **Resource Tracking**: Track EC2 instances, RDS databases, Lambda functions, S3 buckets, Azure VMs, GCP Compute instances, and more
- **Cost Attribution**: Associate costs with individual resources
- **Filtering & Search**: Filter by cloud type, region, pool, and owner
- **Tag Analysis**: Leverage tags for cost allocation and reporting

### 🎯 Cost Optimization Recommendations
- **AI-Powered Insights**: Receive intelligent recommendations to reduce costs
- **Multiple Categories**: Recommendations categorized by Cost, Security, Reliability, Performance, and Operational Excellence
- **Custom Rules**: Create custom recommendation rules based on resource attributes
- **Savings Tracking**: Track potential savings by category and cloud provider
- **Built-in & Custom**: Combine built-in recommendations with custom rules engine

### 📊 Budget Management
- **Pool-Based Hierarchy**: Organize costs using hierarchical budget pools
- **Budget Limits**: Set budget limits with utilization tracking
- **Purpose Types**: Categorize pools by Budget, Business Unit, Team, Project, CI/CD, ML/AI, or Asset Pool
- **Parent-Child Relationships**: Create nested pool structures for complex organizations
- **Real-time Tracking**: Monitor spent vs. budget with progress bars

### 👥 Team Collaboration
- **Multi-Tenant**: Support for multiple organizations with users belonging to multiple orgs
- **User Invitations**: Invite team members via email with secure token-based acceptance
- **Bulk Operations**: Bulk invite multiple users at once
- **User Lifecycle Management**: Suspend, activate, update, and remove users
- **Activity Tracking**: Track user activity and organization-wide audit logs

### 🔐 Advanced Access Control
- **Role-Based Access Control (RBAC)**: Create custom roles with granular permissions
- **Attribute-Based Access Control (ABAC)**: Define policies based on resource attributes
- **Pre-built Roles**: 6 system roles auto-created (Organization Admin, Admin View Only, Engineer, Viewer, Billing Admin, Security Auditor)
- **SSO Integration**: Configure SAML or OIDC identity providers
- **Access Reviews**: Certification workflows to review and approve/revoke user access
- **Session Security**: JWT auth with httpOnly cookies, session binding to IP/fingerprint

### ⚙️ Automation & Scheduling
- **Data Collection Schedulers**: Automated expense, resource, and recommendation data collection
- **Flexible Scheduling**: Support for interval-based and cron-based scheduling
- **Run History**: Track scheduler execution with status and logs
- **Dead Letter Queue**: Automatic retry and failure handling
- **Manual Triggers**: Manually trigger schedulers with optional overrides

### 📧 Notifications
- **Email Alerts**: Configurable email notifications for important events
- **Multiple Types**: Budget Alerts, Recommendation Updates, Daily Cost Summary, Weekly Report, Anomaly Alerts, New User Joined
- **User Preferences**: Per-user, per-organization notification preferences
- **Multiple Providers**: Support for SMTP and AWS SES email delivery

### 📤 Data Export
- **Multiple Formats**: Export to CSV, JSON, Parquet, PDF, and Excel
- **Export Templates**: Create reusable export configurations
- **Scheduled Exports**: Recurring exports with cron expressions
- **Streaming Export**: Direct streaming export without loading everything into memory
- **Secure Downloads**: HMAC-signed download tokens with 15-minute expiry
- **Multiple Delivery Methods**: Direct download, S3, GCS, Azure Blob, Email, SFTP

### 🔒 Security & Compliance
- **Encrypted Credentials**: Cloud credentials encrypted using Fernet symmetric encryption
- **Rate Limiting**: Tiered rate limiting (public: 30/min, auth: 100/min, expensive: 10/min, export: 5/5min)
- **Input Validation**: Request size and content type validation
- **Timeout Middleware**: Configurable per-endpoint timeout
- **Audit Logging**: Tamper-resistant logs tracking all security events with 90-day retention
- **CSRF Protection**: Double-submit cookie pattern
- **Security Headers**: HSTS, X-Content-Type-Options, X-Frame-Options, CSP
- **Account Lockout**: Automatic lockout after 5 failed login attempts
- **Token Blacklisting**: Immediate logout via Redis token blacklisting

---

## Architecture Overview

### Tech Stack

**Backend:**
- **Framework**: FastAPI (Python 3.12+)
- **ORM**: SQLAlchemy with async support
- **Database**: PostgreSQL (primary), MongoDB (expense line items)
- **Cache**: Redis (caching, session management, rate limiting)
- **Scheduler**: APScheduler
- **Migrations**: Alembic

**Frontend:**
- **Framework**: React 18 with TypeScript
- **UI Library**: Ant Design
- **State Management**: Zustand
- **Data Fetching**: React Query
- **Routing**: React Router

**Infrastructure:**
- **Containerization**: Docker Compose
- **Database Connection Pooling**: PostgreSQL (pool_size=20, max_overflow=40)
- **Caching**: Redis with connection pooling

### Security Features

- **Authentication**: JWT with httpOnly cookies (15-min expiry)
- **Session Binding**: IP address, User-Agent, browser fingerprint
- **Concurrent Sessions**: Maximum 5 concurrent sessions (oldest evicted)
- **Credential Encryption**: Fernet symmetric encryption for cloud credentials
- **Circuit Breakers**: Per cloud provider circuit breakers
- **Retry Logic**: Exponential backoff with request coalescing
- **Graceful Degradation**: Stale-cache fallback when providers unavailable

---

## Supported Cloud Providers

### Amazon Web Services (AWS)
- **Services**: EC2, RDS, Lambda, S3, and more
- **Cost Data**: Cost Explorer API integration
- **Required Permissions**: `ce:GetCostAndUsage`, `ce:GetCostForecast`, `ec2:DescribeInstances`, `ec2:DescribeRegions`, `rds:DescribeDBInstances`, `lambda:ListFunctions`, `s3:ListAllMyBuckets`

### Microsoft Azure
- **Services**: Virtual Machines, App Services, SQL Database, Storage, and more
- **Cost Data**: Cost Management API integration
- **Required Permissions**: Cost Management read, Resource read

### Google Cloud Platform (GCP)
- **Services**: Compute Engine, Cloud SQL, Cloud Functions, Cloud Storage, and more
- **Cost Data**: Billing API integration
- **Required IAM Roles**: Billing Account Viewer, Compute Viewer

---

## Feature Status

### ✅ Implemented Features
- Multi-cloud cost tracking (AWS, Azure, GCP)
- Dashboard with cost overview
- Expense tracking with breakdowns
- Resource discovery
- Recommendations engine
- Custom recommendation rules
- Pool-based budget hierarchy
- User management and invitations
- Advanced RBAC with ABAC
- SSO integration (SAML/OIDC)
- Notifications system
- Data collection schedulers
- Data export (CSV, JSON, Parquet, PDF, Excel)
- Audit logging
- Session security and token blacklisting
- Rate limiting and input validation
- Feature flags

### 🚧 Enterprise Stubs (Planned)
- E01: Chargeback/Showback
- E02: Allocation Engine
- E03: Audit Logging / Regulatory Reports (SOC 2, ISO 27001)
- E04: Approval Workflow
- E05: Spend Forecasting
- E06: Commitment Tracker (RI/Savings Plan utilization)
- E08: FX/Tax Conversion
- E09: Anomaly Detection
- E10: FinOps Maturity Assessment
- E11: Collaboration Notes
- E12: Enterprise Connectors (ServiceNow, Jira, Slack, webhooks)
- E14: Platform Health Dashboard

---

## Getting Started

Ready to get started with CostPilot? Check out the following guides:

- **[Quick Start Guide](quickstart.md)** - Get up and running in 5 minutes
- **[Installation Guide](installation.md)** - Deploy CostPilot with Docker Compose
- **[How to Add Cloud Accounts](guides/add-cloud-account.md)** - Connect your cloud providers
- **[How to Invite Users](guides/invite-users.md)** - Add team members

---

## Next Steps

- Explore the **[Dashboard Documentation](dashboard.md)** to understand the main overview page
- Learn about **[Cloud Account Management](cloud-accounts.md)** to connect your providers
- Set up **[Budget Pools](pools.md)** for organizational cost tracking
- Configure **[User Management](users.md)** to invite your team

---

**Need Help?** Check the [Troubleshooting Guide](troubleshooting.md) or review the [Security Audit Report](AUDIT.md)
