#!/bin/bash
# Faulkner DB Persistence Validation Script
# Run this to verify all persistence fixes are working correctly

# Don't use set -e because arithmetic can return non-zero
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}"

echo "============================================================"
echo "Faulkner DB Persistence Validation"
echo "============================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

success_count=0
failure_count=0

# Test 1: Docker containers
echo "[Test 1] Docker Container Health"
echo "------------------------------------------------------------"
if docker ps --filter "name=faulkner-db-falkordb" --filter "health=healthy" | grep -q "faulkner-db-falkordb"; then
    echo -e "${GREEN}✅ FalkorDB container healthy${NC}"
    ((success_count++))
elif docker ps --filter "name=faulkner-db-falkordb" | grep -q "faulkner-db-falkordb"; then
    echo -e "${YELLOW}⚠️  FalkorDB container running but health check not available${NC}"
    ((success_count++))
else
    echo -e "${RED}❌ FalkorDB container not running${NC}"
    ((failure_count++))
fi

if docker ps --filter "name=faulkner-db-postgres" --filter "health=healthy" | grep -q "faulkner-db-postgres"; then
    echo -e "${GREEN}✅ PostgreSQL container healthy${NC}"
    ((success_count++))
elif docker ps --filter "name=faulkner-db-postgres" | grep -q "faulkner-db-postgres"; then
    echo -e "${YELLOW}⚠️  PostgreSQL container running but health check not available${NC}"
    ((success_count++))
else
    echo -e "${RED}❌ PostgreSQL container not running${NC}"
    ((failure_count++))
fi

# Test 2: FalkorDB connectivity
echo ""
echo "[Test 2] FalkorDB Connectivity"
echo "------------------------------------------------------------"
if docker exec faulkner-db-falkordb redis-cli ping | grep -q "PONG"; then
    echo -e "${GREEN}✅ FalkorDB responding${NC}"
    ((success_count++))
else
    echo -e "${RED}❌ FalkorDB not responding${NC}"
    ((failure_count++))
fi

# Test 3: PostgreSQL connectivity
echo ""
echo "[Test 3] PostgreSQL Connectivity"
echo "------------------------------------------------------------"
if docker exec faulkner-db-postgres pg_isready | grep -q "accepting connections"; then
    echo -e "${GREEN}✅ PostgreSQL accepting connections${NC}"
    ((success_count++))
else
    echo -e "${RED}❌ PostgreSQL not accepting connections${NC}"
    ((failure_count++))
fi

# Test 4: Node count in database
echo ""
echo "[Test 4] FalkorDB Node Count"
echo "------------------------------------------------------------"
node_count=$("${SCRIPT_DIR}/venv/bin/python3" -c "
from core.graphiti_client import GraphitiClient
client = GraphitiClient()
result = client.db.graph.query('MATCH (n) RETURN count(n)')
print(result.result_set[0][0] if result.result_set else 0)
")

if [ "$node_count" -gt 0 ]; then
    echo -e "${GREEN}✅ Database contains $node_count nodes${NC}"
    ((success_count++))
else
    echo -e "${RED}❌ Database is empty${NC}"
    ((failure_count++))
fi

# Test 5: Relationship count
echo ""
echo "[Test 5] FalkorDB Relationship Count"
echo "------------------------------------------------------------"
rel_count=$("${SCRIPT_DIR}/venv/bin/python3" -c "
from core.graphiti_client import GraphitiClient
client = GraphitiClient()
result = client.db.graph.query('MATCH ()-[r]->() RETURN count(r)')
print(result.result_set[0][0] if result.result_set else 0)
")

echo -e "${YELLOW}ℹ️  Database contains $rel_count relationships${NC}"
if [ "$rel_count" -gt 0 ]; then
    echo -e "${GREEN}✅ Relationships exist in graph${NC}"
    ((success_count++))
else
    echo -e "${YELLOW}⚠️  No relationships yet (may be expected for new setup)${NC}"
fi

# Test 6: Direct FalkorDB test
echo ""
echo "[Test 6] Direct FalkorDB Operations"
echo "------------------------------------------------------------"
if "${SCRIPT_DIR}/venv/bin/python3" "${SCRIPT_DIR}/test_falkordb_direct.py" > /tmp/faulkner_test_direct.log 2>&1; then
    if grep -q "✅ Decision retrieved" /tmp/faulkner_test_direct.log; then
        echo -e "${GREEN}✅ Direct FalkorDB test passed${NC}"
        ((success_count++))
    else
        echo -e "${RED}❌ Direct FalkorDB test failed (check log)${NC}"
        ((failure_count++))
    fi
else
    echo -e "${RED}❌ Direct FalkorDB test crashed${NC}"
    ((failure_count++))
fi

# Test 7: detect_gaps functionality
echo ""
echo "[Test 7] detect_gaps Functionality"
echo "------------------------------------------------------------"
if "${SCRIPT_DIR}/venv/bin/python3" "${SCRIPT_DIR}/test_detect_gaps.py" > /tmp/faulkner_test_gaps.log 2>&1; then
    detected_nodes=$(grep "Total nodes:" /tmp/faulkner_test_gaps.log | tail -1 | awk '{print $3}')
    if [ "$detected_nodes" -gt 0 ] 2>/dev/null; then
        echo -e "${GREEN}✅ detect_gaps reports $detected_nodes nodes${NC}"
        ((success_count++))
    else
        echo -e "${RED}❌ detect_gaps reports 0 nodes${NC}"
        ((failure_count++))
    fi
else
    echo -e "${RED}❌ detect_gaps test crashed${NC}"
    ((failure_count++))
fi

# Test 8: Complete pipeline test
echo ""
echo "[Test 8] Complete Pipeline Test"
echo "------------------------------------------------------------"
if "${SCRIPT_DIR}/venv/bin/python3" "${SCRIPT_DIR}/test_pipeline_fixed.py" > /tmp/faulkner_test_pipeline.log 2>&1; then
    if grep -q "SUCCESS: Nodes are being counted" /tmp/faulkner_test_pipeline.log && \
       grep -q "SUCCESS: Relationships are working" /tmp/faulkner_test_pipeline.log; then
        echo -e "${GREEN}✅ Complete pipeline test passed${NC}"
        ((success_count++))
    else
        echo -e "${RED}❌ Pipeline test failed (check log)${NC}"
        cat /tmp/faulkner_test_pipeline.log
        ((failure_count++))
    fi
else
    echo -e "${RED}❌ Pipeline test crashed${NC}"
    cat /tmp/faulkner_test_pipeline.log
    ((failure_count++))
fi

# Summary
echo ""
echo "============================================================"
echo "Validation Summary"
echo "============================================================"
echo -e "${GREEN}✅ Passed: $success_count${NC}"
echo -e "${RED}❌ Failed: $failure_count${NC}"

if [ $failure_count -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 All validation tests passed!${NC}"
    echo -e "${GREEN}Faulkner DB persistence is working correctly.${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}⚠️  Some validation tests failed.${NC}"
    echo "Check logs in /tmp/faulkner_test_*.log for details"
    exit 1
fi
