#!/bin/bash

# Daily incremental sync - add to crontab
# Suggested: 0 1 * * * /home/platano/project/faulkner-db/scripts/daily_sync.sh

set -e

cd /home/platano/project/faulkner-db

LOG_FILE="logs/daily_sync_$(date +%Y%m%d).log"
mkdir -p logs

echo "=====================================================================" | tee -a "$LOG_FILE"
echo "FAULKNER DB - DAILY INCREMENTAL SYNC" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "=====================================================================" | tee -a "$LOG_FILE"

# Check if new conversations exist in Agent Genesis
# (This would query Agent Genesis API/DB for conversations since last sync)
echo -e "\n[1/3] Checking for new conversations..." | tee -a "$LOG_FILE"
# TODO: Implement Agent Genesis query for new conversations
# NEW_CONVS=$(query_agent_genesis_since_last_sync)
NEW_CONVS=0  # Placeholder

if [ "$NEW_CONVS" -gt 0 ]; then
    echo "✅ Found $NEW_CONVS new conversations" | tee -a "$LOG_FILE"
    
    # Run incremental Agent Genesis import
    echo -e "\n[2/3] Importing new conversations..." | tee -a "$LOG_FILE"
    ./venv/bin/python3 ingestion/agent_genesis_importer.py --incremental 2>&1 | tee -a "$LOG_FILE"
    
    # Run incremental relationship extraction
    echo -e "\n[3/3] Extracting relationships..." | tee -a "$LOG_FILE"
    ./venv/bin/python3 ingestion/relationship_extractor.py --incremental 2>&1 | tee -a "$LOG_FILE"
    
    echo -e "\n✅ Sync complete: $NEW_CONVS conversations processed" | tee -a "$LOG_FILE"
else
    echo "ℹ️  No new conversations found" | tee -a "$LOG_FILE"
fi

echo "=====================================================================" | tee -a "$LOG_FILE"
echo "Completed: $(date)" | tee -a "$LOG_FILE"
echo "=====================================================================" | tee -a "$LOG_FILE"
