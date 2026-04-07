#!/usr/bin/env bash
# MongoDB backup Script for CostPilot
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups/mongodb}"
MONGO_URL="${MONGODB_URL:-mongodb://localhost:27017}"
MONGO_DB="${MONGODB_DB:-costpilot}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/costpilot_${TIMESTAMP}.gz"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting MongoDB backup..."
mongodump --uri="${MONGO_URL}" --db="${MONGO_DB}" --archive="${BACKUP_FILE}" --gzip

echo "[$(date)] Backup completed: ${BACKUP_FILE}"
echo "[$(date)] Size: $(du -h "${BACKUP_FILE}" | cut -f1)"

# Clean up old backups
echo "[$(date)] Cleaning up backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "costpilot_*.gz" -mtime +${RETENTION_DAYS} -delete

echo "[$(date)] Backup complete"
