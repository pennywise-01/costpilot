# Installation Guide

Deploy CostPilot using Docker Compose with this comprehensive installation guide.

---

## System Requirements

### Minimum Requirements
- **CPU**: 2 cores
- **RAM**: 4 GB
- **Disk**: 20 GB
- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher

### Recommended Requirements
- **CPU**: 4 cores
- **RAM**: 8 GB
- **Disk**: 50 GB SSD
- **Network**: Stable internet connection (for cloud provider APIs)

---

## Supported Platforms

- **Linux**: Ubuntu 20.04+, Debian 11+, CentOS 8+, Fedora 36+
- **macOS**: Monterey (12.0) or higher
- **Windows**: Windows 10/11 with WSL2
- **Cloud**: AWS EC2, Azure VMs, GCP Compute Engine

---

## Installation Steps

### Step 1: Install Docker

#### Ubuntu/Debian

```bash
# Update package index
sudo apt update

# Install prerequisites
sudo apt install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up the repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add your user to docker group (optional, to run without sudo)
sudo usermod -aG docker $USER
```

#### macOS

```bash
# Install Docker Desktop using Homebrew
brew install --cask docker

# Or download from: https://www.docker.com/products/docker-desktop/
```

#### Windows

1. Install WSL2:
```powershell
wsl --install
```

2. Install Docker Desktop for Windows from: https://www.docker.com/products/docker-desktop/

3. Enable WSL2 backend in Docker Desktop settings

---

### Step 2: Clone the Repository

```bash
git clone https://github.com/your-org/costpilot.git
cd costpilot
```

---

### Step 3: Configure Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

#### Required Environment Variables

```env
# ==========================================
# Database Configuration
# ==========================================

# PostgreSQL connection string
DATABASE_URL=postgresql+asyncpg://costpilot:costpilot@db:5432/costpilot

# ==========================================
# MongoDB Configuration
# ==========================================

# MongoDB connection string
MONGODB_URL=mongodb://mongo:27017

# MongoDB database name
MONGODB_DB_NAME=costpilot

# ==========================================
# Redis Configuration
# ==========================================

# Redis connection string
REDIS_URL=redis://redis:6379/0

# ==========================================
# Security Configuration
# ==========================================

# JWT Secret (generate with: python -c "import secrets; print(secrets.token_urlsafe(64))")
JWT_SECRET=your-super-secret-jwt-key-change-this-in-production

# Fernet Encryption Key (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ENCRYPTION_KEY=your-fernet-encryption-key-change-this

# ==========================================
# Frontend Configuration
# ==========================================

# Frontend URL (CORS)
FRONTEND_URL=http://localhost:5173

# ==========================================
# Email Configuration (Optional, for user invitations)
# ==========================================

# Email provider: smtp or ses
EMAIL_PROVIDER=smtp

# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@costpilot.io

# OR AWS SES Configuration
# AWS_REGION=us-east-1
# AWS_ACCESS_KEY_ID=your-aws-access-key
# AWS_SECRET_ACCESS_KEY=your-aws-secret-key
# SES_FROM_EMAIL=noreply@costpilot.io
```

#### Generate Secure Keys

**JWT Secret:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

**Encryption Key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

### Step 4: Start Services

```bash
# Start all services in detached mode
docker-compose up -d

# Wait for services to be ready (first run may take 1-2 minutes)
docker-compose ps
```

**Expected Output:**
```
NAME                STATUS          PORTS
costpilot-backend   Up (healthy)    0.0.0.0:8000->8000/tcp
costpilot-frontend  Up              0.0.0.0:5173->5173/tcp
costpilot-db        Up              5432/tcp
costpilot-mongo     Up              27017/tcp
costpilot-redis     Up              6379/tcp
```

---

### Step 5: Run Database Migrations

```bash
# Run Alembic migrations
docker-compose exec backend alembic upgrade head
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade -> <revision>, <description>
```

---

### Step 6: Verify Installation

**Check Health:**
```bash
curl http://localhost:8000/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-04-09T12:00:00.000Z"
}
```

**Check Detailed Health:**
```bash
curl http://localhost:8000/health/detailed
```

**Access Frontend:**
Open http://localhost:5173 in your browser

---

## Docker Compose Configuration

### Full docker-compose.yml

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: costpilot
      POSTGRES_PASSWORD: costpilot
      POSTGRES_DB: costpilot
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U costpilot"]
      interval: 10s
      timeout: 5s
      retries: 5

  # MongoDB
  mongo:
    image: mongo:6
    environment:
      MONGO_INITDB_DATABASE: costpilot
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Backend API
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      mongo:
        condition: service_started
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: npm run dev

volumes:
  postgres_data:
  mongo_data:
  redis_data:
```

---

## Production Deployment

### Security Hardening

1. **Use Strong Secrets:**
```env
JWT_SECRET=<generate-with-secrets-token_urlsafe-64>
ENCRYPTION_KEY=<generate-with-fernet>
DATABASE_PASSWORD=<strong-database-password>
```

2. **Enable HTTPS:**
- Use a reverse proxy (Nginx, Traefik) with Let's Encrypt
- Update `FRONTEND_URL` to use HTTPS

3. **Restrict Ports:**
- Only expose ports 80 (HTTP) and 443 (HTTPS)
- Use internal Docker networking for inter-service communication

4. **Use Docker Secrets:**
```yaml
secrets:
  jwt_secret:
    file: ./secrets/jwt_secret.txt
  encryption_key:
    file: ./secrets/encryption_key.txt
```

5. **Enable Database Authentication:**
```env
DATABASE_URL=postgresql+asyncpg://costpilot:<strong-password>@db:5432/costpilot
```

### Scaling

**Horizontal Scaling:**
- Backend can be scaled horizontally behind a load balancer
- Use external database (RDS, Cloud SQL) for production
- Use managed Redis (ElastiCache, Memorystore)
- Use MongoDB Atlas or self-managed replica sets

**Example:**
```bash
docker-compose up -d --scale backend=3
```

### Monitoring

**Prometheus Metrics:**
```
http://localhost:8000/metrics
```

**Health Checks:**
```bash
# Simple health
curl http://localhost:8000/health

# Detailed health (localhost only)
curl http://localhost:8000/health/detailed

# API health
curl http://localhost:8000/api/v1/health
```

---

## Backup and Restore

### Database Backup

**PostgreSQL:**
```bash
docker-compose exec db pg_dump -U costpilot costpilot > backup_$(date +%Y%m%d).sql
```

**MongoDB:**
```bash
docker-compose exec mongo mongodump --db costpilot --out /data/backup
```

**Redis:**
```bash
docker-compose exec redis redis-cli SAVE
docker cp costpilot-redis:/data/dump.rdb ./redis_dump.rdb
```

### Database Restore

**PostgreSQL:**
```bash
docker-compose exec -T db psql -U costpilot costpilot < backup_20260409.sql
```

**MongoDB:**
```bash
docker-compose exec mongo mongorestore --db costpilot /data/backup/costpilot
```

---

## Troubleshooting

### Services Won't Start

**Check Logs:**
```bash
docker-compose logs -f
```

**Common Issues:**

1. **Port Already in Use:**
```bash
# Find process using port
netstat -tulpn | grep :8000

# Kill process
kill -9 <PID>
```

2. **Database Migration Failed:**
```bash
docker-compose exec backend alembic downgrade base
docker-compose exec backend alembic upgrade head
```

3. **Permission Denied:**
```bash
sudo chown -R $USER:$USER .
```

### Performance Issues

**Increase Connection Pool:**
```env
# In .env or config.py
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
```

**Increase Cache TTL:**
```env
CACHE_TTL_EXPENSE_SUMMARY=1800  # 30 minutes
CACHE_TTL_RESOURCES=600         # 10 minutes
```

---

## Uninstall

**Stop Services:**
```bash
docker-compose down
```

**Remove Volumes (deletes all data):**
```bash
docker-compose down -v
```

**Remove Images:**
```bash
docker-compose down --rmi all
```

---

## Next Steps

- **[Quick Start Guide](quickstart.md)** - Get up and running
- **[Overview](overview.md)** - Learn about CostPilot's features
- **[Environment Variables](environment-variables.md)** - Complete configuration reference

---

**Need Help?** Check the [Troubleshooting Guide](troubleshooting.md)
