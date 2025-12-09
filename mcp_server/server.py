#!/usr/bin/env python3
"""Faulkner DB MCP Server - Main entry point."""

import asyncio
import json
import sys
from typing import Any

sys.path.insert(0, '/home/platano/project/faulkner-db')

from mcp_server.mcp_tools import TOOL_REGISTRY
from mcp_server.utils import get_metrics


class MCPServer:
    """Simple MCP server implementation."""
    
    def __init__(self):
        self.tools = TOOL_REGISTRY
    
    async def handle_request(self, request: dict) -> dict:
        """Handle incoming MCP tool requests."""
        tool_name = request.get('tool')
        params = request.get('params', {})
        
        if tool_name not in self.tools:
            return {
                'error': f'Unknown tool: {tool_name}',
                'available_tools': list(self.tools.keys())
            }
        
        try:
            tool_func = self.tools[tool_name]
            result = await tool_func(**params)
            return {'success': True, 'result': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def get_tool_list(self) -> dict:
        """Return list of available tools."""
        return {
            'tools': [
                {
                    'name': name,
                    'description': func.__doc__ or 'No description'
                }
                for name, func in self.tools.items()
            ]
        }
    
    async def get_server_metrics(self) -> dict:
        """Return server metrics."""
        return get_metrics()


async def main():
    """Main server loop."""
    server = MCPServer()
    
    print("Faulkner DB MCP Server started")
    print(f"Available tools: {list(server.tools.keys())}")
    
    # Example usage
    test_request = {
        'tool': 'add_decision',
        'params': {
            'description': 'Use FalkorDB for temporal knowledge graph',
            'rationale': 'CPU-friendly graph database with Redis compatibility',
            'alternatives': ['Neo4j', 'ArangoDB'],
            'related_to': []
        }
    }
    
    result = await server.handle_request(test_request)
    print(f"Test result: {json.dumps(result, indent=2)}")
    
    # Show metrics
    metrics = await server.get_server_metrics()
    print(f"Metrics: {json.dumps(metrics, indent=2)}")


if __name__ == '__main__':
    asyncio.run(main())
