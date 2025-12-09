#!/bin/bash

set -e  # Exit on error

echo "======================================================================"
echo "FAULKNER DB - COMPLETE KNOWLEDGE INGESTION & ANALYSIS PIPELINE"
echo "======================================================================"

cd "$(dirname "$0")/.."  # Navigate to project root

# Check prerequisites
echo ""
echo "[0/4] Checking prerequisites..."
docker ps | grep -q falkordb || { echo "❌ FalkorDB not running"; exit 1; }
test -f venv/bin/python3 || { echo "❌ Venv not found"; exit 1; }
echo "✅ Prerequisites OK"

# Phase 1: Agent Genesis
echo ""
echo "[1/4] Agent Genesis Ingestion (estimated 10-30 min)..."
./venv/bin/python3 ingestion/agent_genesis_importer.py
echo "✅ Agent Genesis complete"

# Phase 2: Markdown Documentation
echo ""
echo "[2/4] Markdown Documentation Scanning (estimated 5-10 min)..."
./venv/bin/python3 ingestion/markdown_scanner.py
echo "✅ Markdown scanning complete"

# Phase 3: Relationship Extraction
# Note: Markdown scanner and Agent Genesis now trigger incremental extraction automatically
# This phase runs full extraction to catch any missed relationships
echo ""
echo "[3/5] Full relationship extraction (estimated 1-2 min)..."
echo "ℹ️  Note: Individual importers already ran incremental extraction"
./venv/bin/python3 ingestion/relationship_extractor.py --threshold 0.7 --no-llm
echo "✅ Relationship extraction complete"

# Phase 4: Knowledge Graph Statistics
echo ""
echo "[4/5] Querying knowledge graph statistics..."
./venv/bin/python3 -c "
import sys
sys.path.insert(0, '.')
from mcp_server.mcp_tools import query_decisions
import asyncio
result = asyncio.run(query_decisions(''))
print(f'📊 Total nodes in graph: {len(result)}')
"

# Phase 5: NetworkX Analysis
echo ""
echo "[5/5] Comprehensive NetworkX Analysis (estimated 2-5 min)..."
./venv/bin/python3 analysis/comprehensive_gap_analysis.py
echo "✅ Gap analysis complete"

# Summary
echo ""
echo "======================================================================"
echo "✅ COMPLETE INGESTION & ANALYSIS PIPELINE FINISHED"
echo "======================================================================"
echo ""
echo "Next steps:"
echo "  1. Review gap analysis report in reports/"
echo "  2. Use faulkner-db:query_decisions to explore the knowledge graph"
echo "  3. Use faulkner-db:detect_gaps to identify structural gaps"
echo "  4. Use faulkner-db:find_related to navigate relationships"
echo "  5. Begin DevOracle training when 100+ decisions accumulated"
echo ""
