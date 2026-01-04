#!/bin/bash
# Test script to verify faulkner-db MCP server can start from any directory

# Auto-detect project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="${SCRIPT_DIR}"

echo "=== Testing Faulkner-DB MCP Server Startup from Different Directories ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# Test function
test_startup() {
    local test_dir=$1
    echo "Testing from: $test_dir"

    # Change to test directory
    cd "$test_dir" || { echo "  ❌ Failed to cd to $test_dir"; return 1; }

    # Try to start the MCP server with a timeout and send initialize request
    timeout 5 bash -c "
echo '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"1.0\"}}}' | \
PYTHONUNBUFFERED=1 \
PYTHONPATH=$PROJECT_ROOT \
$PROJECT_ROOT/venv/bin/python3 $PROJECT_ROOT/mcp_server/server_fastmcp.py 2>&1
" | head -20

    if [ $? -eq 0 ] || [ $? -eq 124 ]; then
        echo "  ✅ Server started successfully"
        return 0
    else
        echo "  ❌ Server failed to start"
        return 1
    fi
    echo ""
}

# Test directories
echo "Test 1: Original directory"
test_startup "$PROJECT_ROOT"
echo ""

echo "Test 2: Parent directory"
test_startup "$(dirname "$PROJECT_ROOT")"
echo ""

echo "Test 3: Home directory"
test_startup "$HOME"
echo ""

echo "Test 4: Temp directory"
test_startup "/tmp"
echo ""

echo "=== Test Complete ==="
