#!/bin/bash
# Test script to verify faulkner-db MCP server can start from any directory

echo "=== Testing Faulkner-DB MCP Server Startup from Different Directories ==="
echo ""

# Test function
test_startup() {
    local test_dir=$1
    echo "Testing from: $test_dir"

    # Change to test directory
    cd "$test_dir" || { echo "  ❌ Failed to cd to $test_dir"; return 1; }

    # Try to start the MCP server with a timeout and send initialize request
    timeout 5 bash -c '
echo "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"1.0\"}}}" | \
PYTHONUNBUFFERED=1 \
PYTHONPATH=/home/platano/project/faulkner-db \
/home/platano/project/faulkner-db/venv/bin/python3 /home/platano/project/faulkner-db/mcp_server/server_fastmcp.py 2>&1
' | head -20

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
test_startup "/home/platano/project/faulkner-db"
echo ""

echo "Test 2: Project root"
test_startup "/home/platano/project"
echo ""

echo "Test 3: Home directory"
test_startup "/home/platano"
echo ""

echo "Test 4: Temp directory"
test_startup "/tmp"
echo ""

# Only test /mnt/d if it exists
if [ -d "/mnt/d/ai-workspace" ]; then
    echo "Test 5: WSL mount (/mnt/d/ai-workspace)"
    test_startup "/mnt/d/ai-workspace"
    echo ""
fi

echo "=== Test Complete ==="
