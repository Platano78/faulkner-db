#!/bin/bash

set -e  # Exit on error

echo "======================================================================"
echo "FAULKNER DB - COMPLETE HISTORICAL INGESTION PIPELINE"
echo "======================================================================"
echo ""
echo "This will:"
echo "  1. Mine Agent Genesis conversations (30-60 min)"
echo "  2. Scan project documentation (5-10 min)"
echo "  3. Extract relationships (5-30 min)"
echo "  4. Run gap analysis (2-5 min)"
echo "  5. Validate system (1-2 min)"
echo ""
echo "Total estimated time: 45-90 minutes"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted"
    exit 1
fi

# Auto-detect project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

cd "$PROJECT_ROOT"

START_TIME=$(date +%s)
LOG_FILE="logs/complete_ingestion_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

log() {
    echo "$1" | tee -a "$LOG_FILE"
}

log "======================================================================"
log "Started: $(date)"
log "======================================================================"

# Phase 1: Agent Genesis
log ""
log "[1/5] Agent Genesis Conversation Mining..."
if ./venv/bin/python3 ingestion/batch_import_agent_genesis.py 2>&1 | tee -a "$LOG_FILE"; then
    log "✅ Agent Genesis complete"
else
    log "⚠️  Agent Genesis had errors (check log)"
fi

# Phase 2: Markdown Documentation
log ""
log "[2/5] Project Documentation Scanning..."
if ./venv/bin/python3 ingestion/markdown_scanner.py 2>&1 | tee -a "$LOG_FILE"; then
    log "✅ Documentation scanning complete"
else
    log "⚠️  Documentation scanning had errors (check log)"
fi

# Phase 3: Relationship Extraction
log ""
log "[3/5] Relationship Extraction..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    log "  Using MKG LLM enhancement"
    MKG_FLAG=""
else
    log "  MKG not available, using semantic similarity only"
    MKG_FLAG="--no-llm"
fi

if ./venv/bin/python3 ingestion/relationship_extractor.py $MKG_FLAG 2>&1 | tee -a "$LOG_FILE"; then
    log "✅ Relationship extraction complete"
else
    log "⚠️  Relationship extraction had errors (check log)"
fi

# Phase 4: Gap Analysis
log ""
log "[4/5] NetworkX Gap Analysis..."
if ./venv/bin/python3 analysis/comprehensive_gap_analysis.py 2>&1 | tee -a "$LOG_FILE"; then
    log "✅ Gap analysis complete"
else
    log "⚠️  Gap analysis had errors (check log)"
fi

# Phase 5: Validation
log ""
log "[5/5] Final Validation..."
if ./scripts/final_validation.sh 2>&1 | tee -a "$LOG_FILE"; then
    log "✅ Validation complete"
else
    log "⚠️  Validation had warnings (check log)"
fi

# Summary
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

log ""
log "======================================================================"
log "✅ COMPLETE INGESTION PIPELINE FINISHED"
log "======================================================================"
log "Completed: $(date)"
log "Total time: ${MINUTES}m ${SECONDS}s"
log ""

# Final statistics
log "📊 Final Knowledge Graph Statistics:"
./venv/bin/python3 scripts/graph_statistics.py 2>&1 | tee -a "$LOG_FILE"

log ""
log "📄 Full log: $LOG_FILE"
log ""
log "Next steps:"
log "  1. Review gap analysis: ls -t reports/gap_analysis_*.json | head -1"
log "  2. Test MCP tools in Claude Code"
log "  3. Set up daily incremental sync (already in cron)"
log "  4. Start using the knowledge base!"
