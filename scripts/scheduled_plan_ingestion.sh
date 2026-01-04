#!/bin/bash
# Scheduled Claude Plan Ingestion
# Runs bi-weekly to extract knowledge from Claude Code plan files
# and sync to faulkner-db + Serena memories

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/plan_ingestion_$(date +%Y%m%d_%H%M%S).log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

echo "========================================" | tee -a "$LOG_FILE"
echo "Claude Plan Ingestion - $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Activate virtual environment if it exists
if [ -d "$PROJECT_DIR/venv" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
fi

# Change to project directory
cd "$PROJECT_DIR"

# Run the Claude plan extractor
echo "Running Claude plan extraction..." | tee -a "$LOG_FILE"
python -m ingestion.claude_plan_extractor \
    --plans-dir "$HOME/.claude/plans" \
    --db-path "$PROJECT_DIR/data/scanner_tracking.db" \
    2>&1 | tee -a "$LOG_FILE"

# Run Serena memory sync
echo "" | tee -a "$LOG_FILE"
echo "Running Serena memory sync..." | tee -a "$LOG_FILE"
python -m ingestion.serena_memory_sync \
    --plans-dir "$HOME/.claude/plans" \
    --db-path "$PROJECT_DIR/data/scanner_tracking.db" \
    2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "Ingestion complete - $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Cleanup old logs (keep last 10)
cd "$LOG_DIR"
ls -t plan_ingestion_*.log 2>/dev/null | tail -n +11 | xargs -r rm --

echo "Log saved to: $LOG_FILE"
