#!/usr/bin/env bash
# PostgreSQL backup script for CostPilot
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups/postgresql}"
DB_NAME="${POSTGRES_DB:-costpilot}"
DB_USER="${POSTGRES_USER:-costpilot}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/costpilot_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting PostgreSQL backup..."
pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" --no-password | gzip > "${BACKUP_FILE}"

echo "[$(date)] Backup completed: ${BACKUP_FILE}"
echo "[$(date)] Size: $(du -h "${BACKUP_FILE}" | cut -f1)"

# Clean up old backups
echo "[$(date)] Cleaning up backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "costpilot_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

echo "[$(date)] Backup complete"
