#!/bin/bash
# Faulkner-DB Backup Script
# Run daily via cron: 0 3 * * * /path/to/faulkner-db/scripts/backup-faulkner.sh

set -euo pipefail

# Auto-detect project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

BACKUP_DIR="${FAULKNER_BACKUP_DIR:-$PROJECT_ROOT/backups}"
LOG_FILE="/tmp/faulkner-backup.log"
RETENTION_COUNT=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "Starting Faulkner-DB backup..."

# 1. PostgreSQL backup using pg_dump
log "Backing up PostgreSQL..."
PG_BACKUP="$BACKUP_DIR/postgres-$TIMESTAMP.sql.gz"
if docker exec faulkner-db-postgres pg_dump -U graphiti graphiti 2>/dev/null | gzip > "$PG_BACKUP"; then
    log "PostgreSQL backup created: $PG_BACKUP ($(ls -lh "$PG_BACKUP" | awk '{print $5}'))"
else
    log "WARNING: PostgreSQL backup failed (database may be empty or not initialized)"
fi

# 2. FalkorDB backup - trigger BGSAVE and copy RDB
log "Backing up FalkorDB..."
FALKOR_BACKUP="$BACKUP_DIR/falkordb-$TIMESTAMP.rdb"

# Trigger background save (with password auth - security update 2026-02-01)
FALKORDB_PASSWORD="${FALKORDB_PASSWORD:-changeme}"
docker exec faulkner-db-falkordb redis-cli -a "$FALKORDB_PASSWORD" BGSAVE 2>/dev/null || true
sleep 3  # Wait for BGSAVE to complete

# Copy the RDB file from the data directory
if cp "$PROJECT_ROOT/docker/data/falkordb/dump.rdb" "$FALKOR_BACKUP" 2>/dev/null; then
    log "FalkorDB backup created: $FALKOR_BACKUP ($(ls -lh "$FALKOR_BACKUP" | awk '{print $5}'))"
else
    # Try copying from container if bind mount doesn't have it
    if docker cp faulkner-db-falkordb:/data/dump.rdb "$FALKOR_BACKUP" 2>/dev/null; then
        log "FalkorDB backup created from container: $FALKOR_BACKUP"
    else
        log "WARNING: FalkorDB backup failed (may have no data)"
    fi
fi

# 3. Local SQLite files backup
log "Backing up local SQLite files..."
SQLITE_BACKUP="$BACKUP_DIR/sqlite-$TIMESTAMP.tar.gz"
if tar czf "$SQLITE_BACKUP" -C "$PROJECT_ROOT/data" . 2>/dev/null; then
    log "SQLite backup created: $SQLITE_BACKUP ($(ls -lh "$SQLITE_BACKUP" | awk '{print $5}'))"
else
    log "WARNING: SQLite backup failed"
fi

# 4. Rotate old backups - keep only last N
log "Rotating old backups (keeping last $RETENTION_COUNT)..."
for pattern in "postgres-*.sql.gz" "falkordb-*.rdb" "sqlite-*.tar.gz"; do
    COUNT=$(ls -t "$BACKUP_DIR"/$pattern 2>/dev/null | wc -l)
    if [ "$COUNT" -gt "$RETENTION_COUNT" ]; then
        ls -t "$BACKUP_DIR"/$pattern | tail -n +$((RETENTION_COUNT + 1)) | xargs -r rm -v 2>&1 | tee -a "$LOG_FILE"
    fi
done

log "Faulkner-DB backup completed successfully!"
