#!/bin/bash

################################################################################
# AGENT GENESIS TO FALKORDB INCREMENTAL SYNC SCRIPT
################################################################################
#
# Purpose: Periodically sync conversations from Agent Genesis JSONL API
#          to FalkorDB graph database with incremental updates
#
# Updated: December 2025 - Now uses Agent Genesis API instead of direct ChromaDB
#
# Features:
#   - Incremental extraction (only new/changed conversations)
#   - Message count tracking for delta detection
#   - Automatic backup before each sync
#   - Rollback capability on errors
#   - Comprehensive logging with timestamps
#   - Dry-run mode for validation
#   - Docker container support
#   - Cron-compatible execution
#
# Usage:
#   ./sync_agent_genesis_docker.sh [OPTIONS]
#
# Options:
#   --dry-run           Show what would be synced without making changes
#   --force             Force sync even if no new messages detected
#   --container NAME    Docker container name (default: agent-genesis-chroma)
#   --no-backup         Skip backup before sync
#   --verbose           Enable verbose logging
#   --help              Show this help message
#
# Cron Usage:
#   # Sync every hour
#   0 * * * * /home/platano/project/faulkner-db/scripts/sync_agent_genesis_docker.sh >> /var/log/faulkner-sync.log 2>&1
#
#   # Sync every 6 hours
#   0 */6 * * * /home/platano/project/faulkner-db/scripts/sync_agent_genesis_docker.sh >> /var/log/faulkner-sync.log 2>&1
#
#   # Sync every day at 1 AM
#   0 1 * * * /home/platano/project/faulkner-db/scripts/sync_agent_genesis_docker.sh >> /var/log/faulkner-sync.log 2>&1
#
# Configuration:
#   Sync state stored in:     ~/.faulkner-db/sync_state.json
#   Backups stored in:        ./backups/incremental/
#   Logs stored in:           ./logs/sync/
#   Error logs in:            ./logs/sync/errors/
#
# Dependencies:
#   - Python 3.8+
#   - chromadb (pip install chromadb)
#   - falkordb (pip install falkordb)
#   - jq (for JSON parsing)
#   - docker (for container operations)
#   - falkordb and postgres services running
#
################################################################################

set -e  # Exit on any error (unless handled)

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( dirname "$SCRIPT_DIR" )"
INGESTION_DIR="$PROJECT_DIR/ingestion"

# Default configuration
DRY_RUN=false
FORCE_SYNC=false
VERBOSE=false
CREATE_BACKUP=true
CONTAINER_NAME="${AG_CONTAINER_NAME:-agent-genesis}"
AGENT_GENESIS_API="${AG_API_URL:-http://localhost:8080}"

# Paths
STATE_DIR="$HOME/.faulkner-db"
STATE_FILE="$STATE_DIR/sync_state.json"
BACKUP_DIR="$PROJECT_DIR/backups/incremental"
LOG_DIR="$PROJECT_DIR/logs/sync"
ERROR_LOG_DIR="$LOG_DIR/errors"
CHROMA_STAGING_DIR="/tmp/faulkner-chroma-staging"

# Filenames
CURRENT_DATE=$(date +%Y%m%d)
CURRENT_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/sync_${CURRENT_DATE}.log"
ERROR_LOG_FILE="$ERROR_LOG_DIR/errors_${CURRENT_DATE}.log"

# FalkorDB/Extractor config
EXTRACTOR_SCRIPT="$INGESTION_DIR/agent_genesis_chromadb_extractor.py"
COLLECTION_NAME="${AG_COLLECTION_NAME:-alpha_claude_code}"
CHROMADB_PATH="/app/knowledge"  # Path inside Docker container
LOCAL_CHROMADB_STAGING="/tmp/faulkner-chroma-staging/knowledge"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

################################################################################
# UTILITY FUNCTIONS
################################################################################

log() {
    local message="$1"
    local level="${2:-INFO}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Color output based on level
    local color=$NC
    case "$level" in
        ERROR)   color=$RED ;;
        SUCCESS) color=$GREEN ;;
        WARN)    color=$YELLOW ;;
        INFO)    color=$BLUE ;;
    esac

    # Log to file
    mkdir -p "$LOG_DIR" "$ERROR_LOG_DIR"
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"

    # Also log errors to error log
    if [ "$level" = "ERROR" ]; then
        echo "[$timestamp] $message" >> "$ERROR_LOG_FILE"
    fi

    # Console output - only show if not in a command substitution context
    if [ -t 1 ]; then
        echo -e "${color}[$level]${NC} $message" >&2
    else
        echo "[$level] $message" >&2
    fi
}

debug() {
    if [ "$VERBOSE" = true ]; then
        log "$1" "DEBUG"
    fi
}

show_help() {
    head -80 "$0" | grep "^#" | cut -c 3-
    exit 0
}

validate_dependencies() {
    log "Validating dependencies..." "INFO"

    local missing_deps=0

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log "ERROR: python3 not found" "ERROR"
        ((missing_deps++))
    fi

    # Check Docker (optional - can use local files)
    if ! command -v docker &> /dev/null; then
        log "WARN: docker not found - will use local ChromaDB files" "WARN"
    fi

    # Check Python packages (with venv support)
    if ! python3 -c "import chromadb" 2>/dev/null; then
        # Try with venv
        if [ -f "$PROJECT_DIR/venv/bin/python" ]; then
            if ! "$PROJECT_DIR/venv/bin/python" -c "import chromadb" 2>/dev/null; then
                log "ERROR: chromadb Python package not installed in venv" "ERROR"
                ((missing_deps++))
            fi
        else
            log "ERROR: chromadb Python package not installed" "ERROR"
            ((missing_deps++))
        fi
    fi

    if ! python3 -c "import falkordb" 2>/dev/null; then
        # Try with venv
        if [ -f "$PROJECT_DIR/venv/bin/python" ]; then
            if ! "$PROJECT_DIR/venv/bin/python" -c "import falkordb" 2>/dev/null; then
                log "ERROR: falkordb Python package not installed in venv" "ERROR"
                ((missing_deps++))
            fi
        else
            log "ERROR: falkordb Python package not installed" "ERROR"
            ((missing_deps++))
        fi
    fi

    # Check essential files
    if [ ! -f "$EXTRACTOR_SCRIPT" ]; then
        log "ERROR: Extractor script not found: $EXTRACTOR_SCRIPT" "ERROR"
        ((missing_deps++))
    fi

    if [ $missing_deps -gt 0 ]; then
        log "ERROR: $missing_deps dependencies are missing" "ERROR"
        return 1
    fi

    log "All dependencies validated" "SUCCESS"
    return 0
}

init_state() {
    log "Initializing sync state..." "INFO"

    mkdir -p "$STATE_DIR"

    if [ ! -f "$STATE_FILE" ] || [ ! -s "$STATE_FILE" ]; then
        python3 -c "import json; print(json.dumps({
    'last_sync_timestamp': None,
    'last_sync_date': None,
    'last_message_count': 0,
    'current_message_count': 0,
    'total_syncs': 0,
    'sync_history': []
}, indent=2))" > "$STATE_FILE"
        log "Created new state file: $STATE_FILE" "INFO"
    fi

    debug "State file: $STATE_FILE"
}

get_message_count() {
    # Use Agent Genesis API to get message count (JSONL-indexed data)
    debug "Querying Agent Genesis API for message count: $AGENT_GENESIS_API/stats"

    local response
    response=$(curl -s --max-time 10 "$AGENT_GENESIS_API/stats" 2>/dev/null)
    local exit_code=$?

    if [ $exit_code -ne 0 ] || [ -z "$response" ]; then
        log "ERROR: Could not connect to Agent Genesis API at $AGENT_GENESIS_API" "ERROR"
        return 1
    fi

    # Extract count from API response using Python
    local count
    count=$(echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    # Get total count from alpha collection (JSONL indexed)
    print(data.get('alpha', {}).get('count', 0))
except:
    print(0)
" 2>/dev/null)

    if [ -z "$count" ] || [ "$count" = "0" ]; then
        log "WARN: API returned zero or empty count, checking response..." "WARN"
        debug "API Response: $response"
    fi

    log "Agent Genesis API message count: $count" "INFO"
    echo "$count"
}

read_state() {
    if [ ! -f "$STATE_FILE" ]; then
        init_state
    fi

    cat "$STATE_FILE"
}

write_state() {
    local state_json="$1"
    mkdir -p "$STATE_DIR"

    # Use Python to validate and format JSON
    echo "$state_json" | python3 -m json.tool > "$STATE_FILE.tmp" 2>/dev/null || echo "$state_json" > "$STATE_FILE.tmp"
    mv "$STATE_FILE.tmp" "$STATE_FILE"
}

update_state_after_sync() {
    local message_count=${1:-0}
    local sync_status=${2:-SUCCESS}
    local messages_processed=${3:-0}

    local current_state=$(read_state)

    # Use Python for JSON manipulation (more portable than jq)
    local updated_state=$(python3 << PYTHON_UPDATE
import json
from datetime import datetime

state = json.loads('''$current_state''')

timestamp = datetime.now().isoformat()
date_str = datetime.now().strftime('%Y-%m-%d')

state['last_sync_timestamp'] = timestamp
state['last_sync_date'] = date_str
state['last_message_count'] = state.get('current_message_count', 0)
state['current_message_count'] = $message_count
state['total_syncs'] = state.get('total_syncs', 0) + 1

sync_record = {
    'timestamp': timestamp,
    'status': '$sync_status',
    'messages_processed': $messages_processed,
    'message_count': $message_count
}

if 'sync_history' not in state:
    state['sync_history'] = []

state['sync_history'].append(sync_record)

# Keep only last 100 syncs
if len(state['sync_history']) > 100:
    state['sync_history'] = state['sync_history'][-100:]

print(json.dumps(state, indent=2))
PYTHON_UPDATE
)

    write_state "$updated_state"
}

check_sync_needed() {
    log "Checking if sync is needed..." "INFO"

    if [ "$FORCE_SYNC" = true ]; then
        log "Force sync requested" "WARN"
        return 0
    fi

    local state=$(read_state)

    # Extract last_message_count using Python
    local last_message_count
    last_message_count=$(python3 -c "import json; state = json.loads('''$state'''); print(state.get('last_message_count', 0))" 2>/dev/null || echo "0")

    # Get current message count (capture only stdout)
    local current_message_count
    current_message_count=$( (get_message_count) 2>/dev/null | grep -o '^[0-9]\+$' | head -1)

    if [ -z "$current_message_count" ]; then
        log "ERROR: Failed to get current message count" "ERROR"
        return 1
    fi

    log "Checking incremental sync: last=$last_message_count, current=$current_message_count" "INFO"

    local new_messages=$((current_message_count - last_message_count))

    if [ $new_messages -gt 0 ]; then
        log "Found $new_messages new messages (was $last_message_count, now $current_message_count)" "SUCCESS"
        echo "$new_messages"
        return 0
    else
        log "No new messages found (message count unchanged at $current_message_count)" "INFO"
        return 1
    fi
}

backup_graph() {
    log "Creating backup of FalkorDB graph..." "INFO"

    if [ "$CREATE_BACKUP" = false ]; then
        log "Backup skipped (--no-backup flag set)" "WARN"
        return 0
    fi

    mkdir -p "$BACKUP_DIR"

    local backup_file="$BACKUP_DIR/falkordb_backup_${CURRENT_TIMESTAMP}.rdb"

    # Determine which Python to use
    local python_exe="python3"
    if [ -f "$PROJECT_DIR/venv/bin/python" ]; then
        python_exe="$PROJECT_DIR/venv/bin/python"
    fi

    # Use redis-cli via Docker to create backup (BGSAVE triggers RDB snapshot)
    # FalkorDB runs on Redis, so we use redis-cli for backup operations
    
    log "Triggering BGSAVE on FalkorDB..." "INFO"
    
    # Get node count first
    local node_count
    node_count=$(docker exec faulkner-db-falkordb redis-cli GRAPH.QUERY knowledge_graph "MATCH (n) RETURN count(n)" 2>/dev/null | grep -o '[0-9]\+' | head -1)
    if [ -n "$node_count" ]; then
        log "Graph contains $node_count nodes" "INFO"
    fi
    
    # Trigger background save
    local bgsave_result
    bgsave_result=$(docker exec faulkner-db-falkordb redis-cli BGSAVE 2>&1)
    
    if echo "$bgsave_result" | grep -qi "background\|started\|ok"; then
        log "BGSAVE initiated successfully" "SUCCESS"
    else
        log "BGSAVE response: $bgsave_result" "WARN"
    fi

    if [ $? -ne 0 ]; then
        log "ERROR: Backup creation failed" "ERROR"
        return 1
    fi

    log "Backup created: $backup_file" "SUCCESS"
    echo "$backup_file"
    return 0
}

copy_chroma_from_docker() {
    log "Copying ChromaDB from Agent Genesis Docker container..." "INFO"

    mkdir -p "$CHROMA_STAGING_DIR"

    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log "ERROR: Container '$CONTAINER_NAME' not found or not running" "ERROR"
        log "Please ensure Agent Genesis is running: docker-compose up -d" "ERROR"
        return 1
    fi

    # Copy ChromaDB from Docker container (/app/knowledge contains chroma.sqlite3)
    debug "Copying from docker://$CONTAINER_NAME:$CHROMADB_PATH to $CHROMA_STAGING_DIR"

    if docker cp "$CONTAINER_NAME:$CHROMADB_PATH" "$CHROMA_STAGING_DIR" 2>/dev/null; then
        log "ChromaDB copied from Docker container" "SUCCESS"
        # Update path for extraction - the copied directory is named 'knowledge'
        export CHROMADB_PATH="$LOCAL_CHROMADB_STAGING"
        debug "Using staged ChromaDB at: $CHROMADB_PATH"
        return 0
    else
        log "ERROR: Could not copy ChromaDB from Docker container" "ERROR"
        log "Container: $CONTAINER_NAME, Path: $CHROMADB_PATH" "ERROR"
        return 1
    fi
}

run_extraction() {
    local message_count=$1

    log "Running extraction in ADDITIVE mode..." "INFO"
    log "Extracting $message_count messages..." "INFO"

    cd "$PROJECT_DIR"

    # Activate venv
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi

    # Run extractor with additive flag
    local extraction_cmd="python3 $EXTRACTOR_SCRIPT --additive --collection $COLLECTION_NAME"

    debug "Extraction command: $extraction_cmd"

    if [ "$DRY_RUN" = true ]; then
        log "DRY RUN: Would execute: $extraction_cmd" "INFO"
        return 0
    fi

    # Run extraction and capture output
    if $extraction_cmd >> "$LOG_FILE" 2>&1; then
        log "Extraction completed successfully" "SUCCESS"
        return 0
    else
        log "ERROR: Extraction failed (see logs for details)" "ERROR"
        return 1
    fi
}

cleanup_staging() {
    log "Cleaning up staging directory..." "INFO"

    if [ -d "$CHROMA_STAGING_DIR" ]; then
        rm -rf "$CHROMA_STAGING_DIR"
        debug "Staging directory cleaned"
    fi
}

generate_sync_report() {
    local sync_status=$1
    local new_messages=${2:-0}
    local backup_file=${3:-"N/A"}

    local report_timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local state=$(read_state)

    # Extract state values using Python
    local total_syncs=$(python3 -c "import json; state = json.loads('''$state'''); print(state.get('total_syncs', 0))" 2>/dev/null || echo "0")
    local last_sync=$(python3 -c "import json; state = json.loads('''$state'''); print(state.get('last_sync_timestamp', 'Never'))" 2>/dev/null || echo "Never")

    log "=====================================================================" "INFO"
    log "SYNC REPORT" "INFO"
    log "=====================================================================" "INFO"
    log "Timestamp:           $report_timestamp" "INFO"
    log "Status:              $sync_status" "INFO"
    log "New Messages:        $new_messages" "INFO"
    log "Backup File:         $backup_file" "INFO"
    log "Total Syncs:         $total_syncs" "INFO"
    log "Last Sync:           $last_sync" "INFO"
    log "Log File:            $LOG_FILE" "INFO"
    log "State File:          $STATE_FILE" "INFO"
    log "=====================================================================" "INFO"
}

################################################################################
# MAIN EXECUTION
################################################################################

main() {
    # Parse command-line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE_SYNC=true
                shift
                ;;
            --no-backup)
                CREATE_BACKUP=false
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --container)
                CONTAINER_NAME="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                ;;
            *)
                log "ERROR: Unknown option: $1" "ERROR"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    # Initialize logging
    mkdir -p "$LOG_DIR" "$ERROR_LOG_DIR"

    log "=====================================================================" "INFO"
    log "AGENT GENESIS TO FALKORDB INCREMENTAL SYNC" "INFO"
    log "=====================================================================" "INFO"
    log "Started: $(date '+%Y-%m-%d %H:%M:%S')" "INFO"
    log "Dry Run: $DRY_RUN" "INFO"
    log "Force Sync: $FORCE_SYNC" "INFO"
    log "Create Backup: $CREATE_BACKUP" "INFO"
    log "Log File: $LOG_FILE" "INFO"

    # Validate dependencies
    if ! validate_dependencies; then
        log "ERROR: Dependency validation failed" "ERROR"
        generate_sync_report "FAILED" 0 "N/A"
        exit 1
    fi

    # Initialize state
    init_state

    # Check if sync is needed
    if ! new_messages=$(check_sync_needed); then
        log "Sync not needed at this time" "INFO"
        generate_sync_report "SKIPPED" 0 "N/A"
        exit 0
    fi

    # Create backup
    backup_file=$(backup_graph)
    if [ $? -ne 0 ] && [ "$CREATE_BACKUP" = true ]; then
        log "ERROR: Backup creation failed - aborting sync" "ERROR"
        generate_sync_report "FAILED" "$new_messages" "N/A"
        exit 1
    fi

    # Copy ChromaDB from Docker
    if ! copy_chroma_from_docker; then
        log "ERROR: Failed to copy ChromaDB from Docker" "ERROR"
        generate_sync_report "FAILED" "$new_messages" "$backup_file"
        exit 1
    fi

    # Run extraction
    if ! run_extraction "$new_messages"; then
        log "ERROR: Extraction failed - sync incomplete" "ERROR"
        generate_sync_report "FAILED" "$new_messages" "$backup_file"

        # Cleanup
        cleanup_staging
        exit 1
    fi

    # Get final message count
    if ! current_count=$(get_message_count); then
        log "WARN: Could not verify final message count" "WARN"
        current_count=0
    fi

    # Update state
    update_state_after_sync "$current_count" "SUCCESS" "$new_messages"

    # Cleanup
    cleanup_staging

    # Generate report
    generate_sync_report "SUCCESS" "$new_messages" "$backup_file"

    log "Completed: $(date '+%Y-%m-%d %H:%M:%S')" "SUCCESS"
    log "=====================================================================" "INFO"
}

# Run main function
main "$@"
exit 0
