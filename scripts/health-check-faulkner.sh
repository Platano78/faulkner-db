#!/bin/bash
# Faulkner-DB Health Check Script
# Run every 5 minutes via cron: */5 * * * * /home/platano/project/faulkner-db/scripts/health-check-faulkner.sh

set -euo pipefail

LOG_FILE="/tmp/faulkner-health.log"
POSTGRES_CONTAINER="faulkner-db-postgres"
FALKORDB_CONTAINER="faulkner-db-falkordb"
BACKUP_DIR="/home/platano/project/faulkner-db/backups"
BACKUP_SCRIPT="/home/platano/project/faulkner-db/scripts/backup-faulkner.sh"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

check_container() {
    local container=$1
    local check_cmd=$2
    
    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        log "WARNING: Container $container is not running. Attempting to start..."
        docker start "$container" 2>&1 >> "$LOG_FILE" || {
            log "ERROR: Failed to start container $container"
            return 1
        }
        log "Container $container started successfully"
        sleep 5  # Give it time to initialize
    fi
    
    # Run health check command
    if ! docker exec "$container" $check_cmd > /dev/null 2>&1; then
        log "ALERT: Health check failed for $container. Restarting..."
        docker restart "$container" 2>&1 >> "$LOG_FILE" || {
            log "ERROR: Failed to restart $container"
            return 1
        }
        log "Container $container restarted successfully"
    fi
    
    return 0
}

# Check PostgreSQL
check_container "$POSTGRES_CONTAINER" "pg_isready -U faulkner"

# Check FalkorDB (Redis-based)
check_container "$FALKORDB_CONTAINER" "redis-cli ping"

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

exit 0
