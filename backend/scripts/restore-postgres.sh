#!/usr/bin/env bash
# PostgreSQL restore Script for CostPilot
set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: $0 <backup-file.sql.gz>"
    echo ""
    echo "Available backups:"
    ls -lt ./backups/postgresql/*.sql.gz 2>/dev/null | head -10 || echo "  No backups found"
    exit 1
fi

BACKUP_FILE="$1"
DB_NAME="${POSTGRES_DB:-costpilot}"
DB_USER="${POSTGRES_USER:-costpilot}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Error: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

echo "[$(date)] WARNING: This will overwrite the database '${DB_NAME}'"
echo "[$(date)] Backup file: ${BACKUP_FILE}"
echo "[$(date)] Press Ctrl+C to cancel or wait 10 seconds..."
sleep 10

echo "[$(date)] Restoring PostgreSQL from backup..."
gunzip -c "${BACKUP_FILE}" | psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}"

echo "[$(date)] Restore completed"
