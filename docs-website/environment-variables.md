# Environment Variables Reference

Complete configuration reference for CostPilot environment variables.

---

## Overview

CostPilot is configured via environment variables, typically set in a `.env` file when using Docker Compose.

---

## Required Variables

### Database

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://costpilot:costpilot@db:5432/costpilot` | Required |

---

### MongoDB

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `MONGODB_URL` | MongoDB connection string | `mongodb://mongo:27017` | Required |
| `MONGODB_DB_NAME` | MongoDB database name | `costpilot` | Required |

---

### Redis

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` | Required |

---

### Security

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `JWT_SECRET` | Secret key for JWT signing | `your-super-secret-key` | Required |
| `ENCRYPTION_KEY` | Fernet encryption key for credentials | `your-fernet-key` | Required |

**Generate JWT Secret:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

**Generate Encryption Key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

### Frontend

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `FRONTEND_URL` | Frontend URL for CORS | `http://localhost:5173` | Required |

---

## Optional Variables

### Email Configuration

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `EMAIL_PROVIDER` | Email provider (`smtp` or `ses`) | `smtp` | `smtp` |
| `SMTP_HOST` | SMTP server host | `smtp.gmail.com` | - |
| `SMTP_PORT` | SMTP server port | `587` | `587` |
| `SMTP_USER` | SMTP username | `your-email@gmail.com` | - |
| `SMTP_PASSWORD` | SMTP password | `your-app-password` | - |
| `SMTP_FROM_EMAIL` | From email address | `noreply@costpilot.io` | - |
| `AWS_REGION` | AWS region (for SES) | `us-east-1` | - |
| `AWS_ACCESS_KEY_ID` | AWS access key (for SES) | `AKIA...` | - |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key (for SES) | `wJalr...` | - |
| `SES_FROM_EMAIL` | SES verified email | `noreply@costpilot.io` | - |

---

### Cache Configuration

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `CLOUD_CACHE_TTL_SECONDS` | Cloud live data cache TTL | `300` (5 min) | `300` |
| `CACHE_TTL_EXPENSE_SUMMARY` | Expense summary cache TTL | `21600` (6 hrs) | `21600` |
| `CACHE_TTL_RECOMMENDATIONS` | Recommendations cache TTL | `600` (10 min) | `600` |
| `CACHE_TTL_RESOURCES` | Resources cache TTL | `300` (5 min) | `300` |
| `COST_CACHE_TTL_HOURS` | Cost cache TTL in hours | `6` | `6` |
| `COST_CACHE_STALE_HOURS` | Max stale cache duration | `24` | `24` |
| `COST_CACHE_AUTO_REFRESH` | Auto-refresh cost cache | `true` | `true` |
| `COST_CACHE_FALLBACK_TO_LIVE` | Fallback to live data | `true` | `true` |

---

### Security Configuration

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `INVITATION_EXPIRY_DAYS` | Invitation token expiry | `7` | `7` |
| `MAX_LOGIN_ATTEMPTS` | Max failed login attempts | `5` | `5` |
| `LOCKOUT_DURATION_MINUTES` | Account lockout duration | `30` | `30` |

---

### Timeout Configuration

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `CLOUD_ACCOUNT_LIVE_DATA_TIMEOUT` | Cloud API timeout (seconds) | `60` | `60` |
| `CREDENTIAL_CACHE_TTL_SECONDS` | Credential cache TTL | `300` | `300` |

---

### Database Connection Pool

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `DATABASE_POOL_SIZE` | Connection pool size | `20` | `20` |
| `DATABASE_MAX_OVERFLOW` | Max overflow connections | `40` | `40` |

---

## Complete .env Example

```env
# ==========================================
# Database Configuration
# ==========================================
DATABASE_URL=postgresql+asyncpg://costpilot:costpilot@db:5432/costpilot
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# ==========================================
# MongoDB Configuration
# ==========================================
MONGODB_URL=mongodb://mongo:27017
MONGODB_DB_NAME=costpilot

# ==========================================
# Redis Configuration
# ==========================================
REDIS_URL=redis://redis:6379/0

# ==========================================
# Security Configuration
# ==========================================
JWT_SECRET=your-super-secret-jwt-key-change-this-in-production
ENCRYPTION_KEY=your-fernet-encryption-key-change-this
INVITATION_EXPIRY_DAYS=7
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION_MINUTES=30

# ==========================================
# Frontend Configuration
# ==========================================
FRONTEND_URL=http://localhost:5173

# ==========================================
# Email Configuration (SMTP)
# ==========================================
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@costpilot.io

# ==========================================
# Cache Configuration
# ==========================================
CLOUD_CACHE_TTL_SECONDS=300
CACHE_TTL_EXPENSE_SUMMARY=21600
CACHE_TTL_RECOMMENDATIONS=600
CACHE_TTL_RESOURCES=300
COST_CACHE_TTL_HOURS=6
COST_CACHE_STALE_HOURS=24
COST_CACHE_AUTO_REFRESH=true
COST_CACHE_FALLBACK_TO_LIVE=true

# ==========================================
# Timeout Configuration
# ==========================================
CLOUD_ACCOUNT_LIVE_DATA_TIMEOUT=60
CREDENTIAL_CACHE_TTL_SECONDS=300
```

---

## Notes

1. **Required Variables**: Must be set for application to start
2. **Optional Variables**: Have sensible defaults
3. **Secrets**: Generate strong random values for production
4. **Email**: Configure either SMTP or SES for user invitations
5. **Cache**: Adjust TTLs based on your freshness vs. performance needs
