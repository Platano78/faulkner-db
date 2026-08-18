#!/bin/bash
# Faulkner-DB Health Check Script (remote: containers live on ai-utility, not locally)
# Run every 5 minutes via cron: */5 * * * * /path/to/faulkner-db/scripts/health-check-faulkner.sh

set -uo pipefail  # no -e: lanes handle their own failures explicitly

# Auto-detect project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

LOG_FILE="/tmp/faulkner-health.log"
POSTGRES_CONTAINER="faulkner-db-postgres"
FALKORDB_CONTAINER="faulkner-db-falkordb"
BACKUP_DIR="$PROJECT_ROOT/backups"
BACKUP_SCRIPT="$PROJECT_ROOT/scripts/backup-faulkner.sh"

ENV_FILE="${FAULKNER_HEALTH_ENV_FILE:-$HOME/.config/faulkner-health/env}"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
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

if ! "${SSH_CMD[@]}" "$REMOTE_HOST" true 2>/dev/null; then
    log "ERROR: cannot reach $REMOTE_HOST over ssh"
    exit 1
fi

FAILED=0
RUNNING=$("${SSH_CMD[@]}" "$REMOTE_HOST" docker ps --format '{{.Names}}' 2>/dev/null)

check_running() {
    local container=$1
    if ! echo "$RUNNING" | grep -q "^${container}$"; then
        log "WARNING: Container $container is not running. Attempting to start..."
        if "${SSH_CMD[@]}" "$REMOTE_HOST" docker start "$container" >/dev/null 2>&1; then
            log "Container $container started successfully"
            sleep 5
        else
            log "ERROR: Failed to start container $container"
            FAILED=1
        fi
    fi
}

check_running "$POSTGRES_CONTAINER"
check_running "$FALKORDB_CONTAINER"

# FalkorDB responsiveness (redis-cli PING)
PONG=$("${SSH_CMD[@]}" "$REMOTE_HOST" "docker exec $FALKORDB_CONTAINER redis-cli -a $PW_Q --no-auth-warning PING" 2>/dev/null)
if [ "$PONG" != "PONG" ]; then
    log "ALERT: FalkorDB health check failed for $FALKORDB_CONTAINER (PING != PONG). Restarting..."
    if "${SSH_CMD[@]}" "$REMOTE_HOST" docker restart "$FALKORDB_CONTAINER" >/dev/null 2>&1; then
        log "Container $FALKORDB_CONTAINER restarted successfully"
    else
        log "ERROR: Failed to restart $FALKORDB_CONTAINER"
        FAILED=1
    fi
fi

# Check if today's backup exists - if not, create one
TODAY=$(date +%Y%m%d)
if ! ls "$BACKUP_DIR"/sqlite-${TODAY}*.tar.gz >/dev/null 2>&1; then
    log "No backup found for today ($TODAY). Triggering backup..."
    if [ -x "$BACKUP_SCRIPT" ]; then
        "$BACKUP_SCRIPT" >> "$LOG_FILE" 2>&1 && log "Catch-up backup completed" || log "WARNING: Catch-up backup failed"
    else
        log "WARNING: Backup script not found or not executable"
    fi
fi

if [ "$FAILED" -eq 0 ]; then
    log "OK: $REMOTE_HOST reachable, $POSTGRES_CONTAINER and $FALKORDB_CONTAINER running, FalkorDB PING=PONG"
fi

exit "$FAILED"
