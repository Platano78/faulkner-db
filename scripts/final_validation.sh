#!/bin/bash

echo "======================================================================"
echo "FAULKNER DB - FINAL VALIDATION"
echo "======================================================================"
echo ""

cd /home/platano/project/faulkner-db

# Test MCP tools
echo "[1/4] Testing MCP Tools..."
./venv/bin/python3 -c "
from mcp_server.mcp_tools import add_decision, query_decisions
import asyncio

# Test query
result = asyncio.run(query_decisions('test'))
print(f'  ✅ Query working: {len(result)} results')
" 2>&1 | grep -v INFO || echo "  ❌ MCP tools failed"

# Check graph size
echo ""
echo "[2/4] Checking Graph Size..."
./venv/bin/python3 -c "
from core.graphiti_client import GraphitiClient

client = GraphitiClient()
result = client.db.graph.query('MATCH (n) RETURN count(n) as count')
node_count = result.result_set[0][0]

if node_count > 100:
    print(f'  ✅ Graph size: {node_count:,} nodes')
else:
    print(f'  ⚠️  Small graph: {node_count} nodes')
"

# Check connectivity
echo ""
echo "[3/4] Checking Connectivity..."
./venv/bin/python3 -c "
from core.graphiti_client import GraphitiClient

client = GraphitiClient()

total = client.db.graph.query('MATCH (n) RETURN count(n)').result_set[0][0]
connected = client.db.graph.query('MATCH (n)-[r]-() RETURN count(DISTINCT n)').result_set[0][0]

connectivity = (connected / total * 100) if total > 0 else 0

if connectivity > 50:
    print(f'  ✅ Connectivity: {connectivity:.1f}%')
else:
    print(f'  ⚠️  Low connectivity: {connectivity:.1f}%')
"

# Check Docker services
echo ""
echo "[4/4] Checking Docker Services..."
docker ps --format "{{.Names}}\t{{.Status}}" | grep -E "falkordb|postgres" | while read line; do
    echo "  ✅ $line"
done

echo ""
echo "======================================================================"
echo "✅ VALIDATION COMPLETE"
echo "======================================================================"
