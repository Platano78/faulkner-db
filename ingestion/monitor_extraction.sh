#!/bin/bash
# Real-time extraction monitoring script

CHECKPOINT_FILE="ingestion/extraction_checkpoint.json"
LOG_FILE="ingestion/extraction_log.txt"

echo "====================================================================="
echo "🔍 AGENT GENESIS EXTRACTION MONITOR"
echo "====================================================================="
echo ""

# Check if process is running
if pgrep -f "agent_genesis_full_scale.py" > /dev/null; then
    echo "✅ Extraction process: RUNNING"
    PID=$(pgrep -f "agent_genesis_full_scale.py")
    echo "   PID: $PID"
else
    echo "⚠️  Extraction process: NOT RUNNING"
fi

echo ""

# Parse checkpoint
if [ -f "$CHECKPOINT_FILE" ]; then
    echo "📊 PROGRESS FROM CHECKPOINT:"
    echo "---------------------------------------------------------------------"
    
    COMPLETED=$(jq -r '.completed_conversations | length' "$CHECKPOINT_FILE" 2>/dev/null || echo "0")
    DECISIONS=$(jq -r '.extraction_stats.decisions' "$CHECKPOINT_FILE" 2>/dev/null || echo "0")
    PATTERNS=$(jq -r '.extraction_stats.patterns' "$CHECKPOINT_FILE" 2>/dev/null || echo "0")
    FAILURES=$(jq -r '.extraction_stats.failures' "$CHECKPOINT_FILE" 2>/dev/null || echo "0")
    SUCCESS_RATE=$(jq -r '.extraction_stats.success_rate' "$CHECKPOINT_FILE" 2>/dev/null || echo "0.0")
    LAST_UPDATE=$(jq -r '.extraction_stats.processing_timestamp' "$CHECKPOINT_FILE" 2>/dev/null || echo "N/A")
    
    TOTAL_NODES=$((DECISIONS + PATTERNS + FAILURES))
    SUCCESS_PCT=$(echo "scale=1; $SUCCESS_RATE * 100" | bc 2>/dev/null || echo "0.0")
    
    echo "   Conversations processed: $COMPLETED"
    echo "   Nodes extracted: $TOTAL_NODES"
    echo "     - Decisions: $DECISIONS"
    echo "     - Patterns: $PATTERNS"
    echo "     - Failures: $FAILURES"
    echo "   Success rate: ${SUCCESS_PCT}%"
    echo "   Last update: $LAST_UPDATE"
else
    echo "⚠️  Checkpoint file not found: $CHECKPOINT_FILE"
fi

echo ""
echo "---------------------------------------------------------------------"
echo "📝 RECENT LOG ACTIVITY (last 20 lines):"
echo "---------------------------------------------------------------------"

if [ -f "$LOG_FILE" ]; then
    tail -20 "$LOG_FILE" | sed 's/^/   /'
else
    echo "   ⚠️  Log file not found: $LOG_FILE"
fi

echo ""
echo "====================================================================="
echo "💡 Commands:"
echo "   Monitor live:  watch -n 5 ./ingestion/monitor_extraction.sh"
echo "   View full log: tail -f ingestion/extraction_log.txt"
echo "   Stop process:  pkill -f agent_genesis_full_scale.py"
echo "====================================================================="
