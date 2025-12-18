#!/bin/bash
# Restore FalkorDB from a backup file
# Usage: ./restore_falkordb.sh [backup_file]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_DIR/docker/data/falkordb"
BACKUP_DIR="$PROJECT_DIR/backups"
CONTAINER="faulkner-db-falkordb"

# If no argument, show available backups
if [ -z "$1" ]; then
    echo "Available backups:"
    ls -lh "$BACKUP_DIR"/*.rdb 2>/dev/null | awk '{print NR". "$9" ("$5")"}'
    echo ""
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 $BACKUP_DIR/falkordb_20251129_025400.rdb"
    exit 1
fi

BACKUP_FILE="$1"

# Verify backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "=== FalkorDB Restore ==="
echo "Backup file: $BACKUP_FILE"
echo "Size: $(du -h "$BACKUP_FILE" | cut -f1)"
echo ""

# Confirm
read -p "This will replace the current database. Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Stop container if running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "Stopping FalkorDB container..."
    docker stop $CONTAINER
    sleep 2
fi

# Create backup of current state (just in case)
if [ -f "$DATA_DIR/dump.rdb" ]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    cp "$DATA_DIR/dump.rdb" "$BACKUP_DIR/pre-restore_$TIMESTAMP.rdb"
    echo "Current state backed up to: pre-restore_$TIMESTAMP.rdb"
fi

# Copy backup to data directory
echo "Copying backup to data directory..."
sudo cp "$BACKUP_FILE" "$DATA_DIR/dump.rdb"
sudo chown root:root "$DATA_DIR/dump.rdb"

# Start container
echo "Starting FalkorDB container..."
docker start $CONTAINER
sleep 5

# Verify restoration
NODE_COUNT=$(docker exec $CONTAINER redis-cli GRAPH.QUERY knowledge_graph "MATCH (n) RETURN count(n)" 2>/dev/null | grep -E '^[0-9]+$')
EDGE_COUNT=$(docker exec $CONTAINER redis-cli GRAPH.QUERY knowledge_graph "MATCH ()-[r]->() RETURN count(r)" 2>/dev/null | grep -E '^[0-9]+$')

echo ""
echo "=== Restoration Complete ==="
echo "Nodes: $NODE_COUNT"
echo "Edges: $EDGE_COUNT"
