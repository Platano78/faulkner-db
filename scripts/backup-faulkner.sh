#!/bin/bash
# Faulkner-DB Backup Script (remote-first: live data lives on ai-utility, not locally)
# Run daily via cron: 0 3 * * * /path/to/faulkner-db/scripts/backup-faulkner.sh

set -uo pipefail  # no -e: lanes handle their own failures explicitly

# Auto-detect project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

BACKUP_DIR="${FAULKNER_BACKUP_DIR:-$PROJECT_ROOT/backups}"
LOG_FILE="/tmp/faulkner-backup.log"
RETENTION_COUNT=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

ENV_FILE="${FAULKNER_HEALTH_ENV_FILE:-$HOME/.config/faulkner-health/env}"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

if [ ! -f "$ENV_FILE" ]; then
    log "ERROR: $ENV_FILE not found. See scripts/run-health-check.sh header for setup."
    exit 64
fi
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

REMOTE_HOST="${FALKORDB_HOST:-192.168.1.79}"

: "${FALKORDB_PASSWORD:?FALKORDB_PASSWORD not set in $ENV_FILE}"

# cron has no ssh-agent, so use a dedicated deploy key rather than riding
# an interactive agent's SSH_AUTH_SOCK.
SSH_KEY="${FAULKNER_SSH_KEY:-$HOME/.config/faulkner-health/ssh_key}"
if [ ! -f "$SSH_KEY" ]; then
    log "ERROR: $SSH_KEY not found. See INSTALL.md for setup."
    exit 64
fi
SSH_CMD=(ssh -i "$SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=5)

# ssh flattens args into one remote shell string, so quote the password
# locally before it crosses ssh (word-splitting risk if it were sent raw).
PW_Q=$(printf '%q' "$FALKORDB_PASSWORD")

log "Starting Faulkner-DB backup (remote host: $REMOTE_HOST)..."

OVERALL_STATUS=0

# 1. FalkorDB backup - trigger BGSAVE remotely, wait for it, stream the RDB
log "Backing up FalkorDB..."
FALKOR_BACKUP="$BACKUP_DIR/falkordb-$TIMESTAMP.rdb"

LASTSAVE_BEFORE=$("${SSH_CMD[@]}" "$REMOTE_HOST" "docker exec faulkner-db-falkordb redis-cli -a $PW_Q --no-auth-warning LASTSAVE" 2>/dev/null)
if [ -z "$LASTSAVE_BEFORE" ]; then
    log "ERROR: FalkorDB backup failed (could not reach $REMOTE_HOST or read LASTSAVE)"
    exit 1
fi

if ! "${SSH_CMD[@]}" "$REMOTE_HOST" "docker exec faulkner-db-falkordb redis-cli -a $PW_Q --no-auth-warning BGSAVE" >/dev/null 2>&1; then
    log "ERROR: FalkorDB backup failed (BGSAVE command failed)"
    exit 1
fi

# Poll LASTSAVE until it advances (max ~30s)
SAVE_DONE=0
for _ in $(seq 1 15); do
    sleep 2
    LASTSAVE_AFTER=$("${SSH_CMD[@]}" "$REMOTE_HOST" "docker exec faulkner-db-falkordb redis-cli -a $PW_Q --no-auth-warning LASTSAVE" 2>/dev/null)
    if [ -n "$LASTSAVE_AFTER" ] && [ "$LASTSAVE_AFTER" != "$LASTSAVE_BEFORE" ]; then
        SAVE_DONE=1
        break
    fi
done

if [ "$SAVE_DONE" -ne 1 ]; then
    log "ERROR: FalkorDB backup failed (BGSAVE did not complete within 30s)"
    exit 1
fi

if ! "${SSH_CMD[@]}" "$REMOTE_HOST" docker exec faulkner-db-falkordb cat /var/lib/falkordb/data/dump.rdb > "$FALKOR_BACKUP" 2>/dev/null; then
    log "ERROR: FalkorDB backup failed (could not stream RDB file from container)"
    rm -f "$FALKOR_BACKUP"
    exit 1
fi

FALKOR_MAGIC=$(head -c5 "$FALKOR_BACKUP" 2>/dev/null)
if [ ! -s "$FALKOR_BACKUP" ] || [ "$FALKOR_MAGIC" != "REDIS" ]; then
    log "ERROR: FalkorDB backup failed verification (empty or missing REDIS magic bytes) - removing $FALKOR_BACKUP"
    rm -f "$FALKOR_BACKUP"
    exit 1
fi
log "FalkorDB backup created and verified: $FALKOR_BACKUP ($(ls -lh "$FALKOR_BACKUP" | awk '{print $5}'), magic=REDIS)"

# 2. PostgreSQL backup using pg_dump (remote, over ssh)
# WARN-only by design: postgres has been empty before now; FalkorDB is the
# critical lane above and hard-fails the run instead.
log "Backing up PostgreSQL..."
PG_BACKUP="$BACKUP_DIR/postgres-$TIMESTAMP.sql.gz"
if "${SSH_CMD[@]}" "$REMOTE_HOST" docker exec faulkner-db-postgres pg_dump -U graphiti graphiti 2>/dev/null | gzip > "$PG_BACKUP"; then
    PG_SIZE=$(stat -c%s "$PG_BACKUP" 2>/dev/null || echo 0)
    if [ "$PG_SIZE" -ge 100 ]; then
        log "PostgreSQL backup created and verified: $PG_BACKUP ($(ls -lh "$PG_BACKUP" | awk '{print $5}'), size=${PG_SIZE}b >= 100b)"
    else
        log "WARNING: postgres dump empty or failed - NOT a valid backup ($PG_BACKUP is ${PG_SIZE}b)"
    fi
else
    log "WARNING: postgres dump empty or failed - NOT a valid backup (ssh/pg_dump command failed)"
fi

# 3. Local SQLite files backup (unchanged)
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

if [ "$OVERALL_STATUS" -eq 0 ]; then
    log "Faulkner-DB backup completed successfully!"
fi
exit "$OVERALL_STATUS"
