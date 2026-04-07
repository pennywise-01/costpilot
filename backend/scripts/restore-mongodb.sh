#!/usr/bin/env bash
# MongoDB restore Script for CostPilot
set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: $0 <backup-file.gz>"
    echo ""
    echo "Available backups:"
    ls -lt ./backups/mongodb/*.gz 2>/dev/null | head -10 || echo "  No backups found"
    exit 1
fi

BACKUP_FILE="$1"
MONGO_URL="${MONGODB_URL:-mongodb://localhost:27017}"
MONGO_DB="${MONGODB_DB:-costpilot}"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Error: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

echo "[$(date)] WARNING: This will overwrite the database '${MONGO_DB}'"
echo "[$(date)] Backup file: ${BACKUP_FILE}"
echo "[$(date)] Press Ctrl+C to cancel or wait 10 seconds..."
sleep 10

echo "[$(date)] Restoring MongoDB from backup..."
mongorestore --uri="${MONGO_URL}" --db="${MONGO_DB}" --archive="${BACKUP_FILE}" --gzip --drop

echo "[$(date)] Restore completed"
