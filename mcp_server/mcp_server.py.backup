#!/usr/bin/env python3
"""Faulkner DB MCP Server - Proper MCP Protocol Implementation."""

import asyncio
import sys

from mcp.server import Server
from mcp.types import Tool, TextContent
import json

# Direct imports from mcp_server package
from mcp_server.mcp_tools import (
    add_decision, query_decisions, add_pattern, add_failure,
    find_related, detect_gaps, get_timeline
)


# Initialize MCP server
app = Server("faulkner-db")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="add_decision",
            description="Record an architectural decision with rationale, alternatives, and related decisions",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "What was decided"},
                    "rationale": {"type": "string", "description": "Why this decision was made"},
                    "alternatives": {"type": "array", "items": {"type": "string"}, "description": "Other options considered"},
                    "related_to": {"type": "array", "items": {"type": "string"}, "description": "Related decision IDs"}
                },
                "required": ["description", "rationale"]
            }
        ),
        Tool(
            name="query_decisions",
            description="Search for decisions using hybrid search (graph + vector + reranking)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (e.g., 'authentication decisions in Q3 2024')"},
                    "timeframe": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string", "description": "Start date (ISO format)"},
                            "end": {"type": "string", "description": "End date (ISO format)"}
                        }
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="add_pattern",
            description="Store a successful implementation pattern with use cases and context",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Pattern name"},
                    "implementation": {"type": "string", "description": "How to implement this pattern"},
                    "use_cases": {"type": "array", "items": {"type": "string"}, "description": "When to use this pattern"},
                    "context": {"type": "string", "description": "Why this pattern works"}
                },
                "required": ["name", "implementation", "context"]
            }
        ),
        Tool(
            name="add_failure",
            description="Document what didn't work, why it failed, and lessons learned",
            inputSchema={
                "type": "object",
                "properties": {
                    "attempt": {"type": "string", "description": "What was tried"},
                    "reason_failed": {"type": "string", "description": "Why it failed"},
                    "lesson_learned": {"type": "string", "description": "What was learned"},
                    "alternative_solution": {"type": "string", "description": "What worked instead (optional)"}
                },
                "required": ["attempt", "reason_failed", "lesson_learned"]
            }
        ),
        Tool(
            name="find_related",
            description="Find related knowledge nodes via graph traversal",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "ID of the node to start from"},
                    "depth": {"type": "integer", "description": "How many hops to traverse (default: 1)"}
                },
                "required": ["node_id"]
            }
        ),
        Tool(
            name="detect_gaps",
            description="Run NetworkX structural analysis to detect knowledge gaps (isolated nodes, disconnected clusters, missing bridges)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_timeline",
            description="Get temporal view of how knowledge evolved over time for a topic",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic to track"},
                    "start_date": {"type": "string", "description": "Start date (ISO format)"},
                    "end_date": {"type": "string", "description": "End date (ISO format)"}
                },
                "required": ["topic", "start_date", "end_date"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool execution."""

    try:
        if name == "add_decision":
            result = await add_decision(
                description=arguments["description"],
                rationale=arguments["rationale"],
                alternatives=arguments.get("alternatives", []),
                related_to=arguments.get("related_to", [])
            )
            return [TextContent(
                type="text",
                text=f"✅ Decision created: {result['decision_id']}\n\n{json.dumps(result, indent=2)}"
            )]

        elif name == "query_decisions":
            result = await query_decisions(
                query=arguments["query"],
                timeframe=arguments.get("timeframe")
            )
            formatted = "\n\n".join([
                f"**Result {i+1}** (score: {r['score']:.3f})\n{r['content']}\nSource: {r['source']} | {r['timestamp']}"
                for i, r in enumerate(result[:5])  # Top 5 for readability
            ])
            return [TextContent(
                type="text",
                text=f"Found {len(result)} results:\n\n{formatted}"
            )]

        elif name == "add_pattern":
            result = await add_pattern(
                name=arguments["name"],
                implementation=arguments["implementation"],
                use_cases=arguments.get("use_cases", []),
                context=arguments["context"]
            )
            return [TextContent(
                type="text",
                text=f"✅ Pattern created: {result['pattern_id']}\n\n{json.dumps(result, indent=2)}"
            )]

        elif name == "add_failure":
            result = await add_failure(
                attempt=arguments["attempt"],
                reason_failed=arguments["reason_failed"],
                lesson_learned=arguments["lesson_learned"],
                alternative_solution=arguments.get("alternative_solution")
            )
            return [TextContent(
                type="text",
                text=f"✅ Failure documented: {result['failure_id']}\n\n{json.dumps(result, indent=2)}"
            )]

        elif name == "find_related":
            result = await find_related(
                node_id=arguments["node_id"],
                depth=arguments.get("depth", 1)
            )
            formatted = "\n".join([
                f"- {r['related_node_id']} ({r['relationship_type']})"
                for r in result
            ])
            return [TextContent(
                type="text",
                text=f"Related nodes for {arguments['node_id']}:\n\n{formatted or 'No related nodes found'}"
            )]

        elif name == "detect_gaps":
            result = await detect_gaps()
            formatted = "\n\n".join([
                f"**{g['severity']}**: {g['gap_type']}\n{g['recommendation']}\nAffected nodes: {len(g['affected_nodes'])}"
                for g in result
            ])
            return [TextContent(
                type="text",
                text=f"Detected {len(result)} knowledge gaps:\n\n{formatted or 'No gaps detected'}"
            )]

        elif name == "get_timeline":
            result = await get_timeline(
                topic=arguments["topic"],
                start_date=arguments["start_date"],
                end_date=arguments["end_date"]
            )
            formatted = "\n".join([
                f"- {e['timestamp']}: {e['type']} ({e['id']})"
                for e in result
            ])
            return [TextContent(
                type="text",
                text=f"Timeline for '{arguments['topic']}':\n\n{formatted or 'No entries found'}"
            )]

        else:
            return [TextContent(
                type="text",
                text=f"❌ Unknown tool: {name}"
            )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=f"❌ Error executing {name}: {str(e)}"
        )]


async def main():
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
