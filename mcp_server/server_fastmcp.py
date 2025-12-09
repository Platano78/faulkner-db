#!/usr/bin/env python3
"""Faulkner-DB FastMCP Server - Production implementation."""

import sys
import logging

# FIX: Add parent directory to path to resolve import collisions
# When this script runs from mcp_server/, Python needs explicit path to find the mcp_server package
sys.path.insert(0, '/home/platano/project/faulkner-db')

from fastmcp import FastMCP

# Configure logging to stderr (protocol-compliant)
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import existing tool implementations
from mcp_server.mcp_tools import (
    add_decision as impl_add_decision,
    query_decisions as impl_query_decisions,
    add_pattern as impl_add_pattern,
    add_failure as impl_add_failure,
    find_related as impl_find_related,
    detect_gaps as impl_detect_gaps,
    get_timeline as impl_get_timeline
)

# Initialize FastMCP server with MCP 2025-11-25 compliance
mcp = FastMCP(
    name="faulkner-db",
    version="1.1.0",
)

# Tool 1: Add Decision
@mcp.tool()
async def add_decision(
    description: str,
    rationale: str,
    alternatives: list[str] = None,
    related_to: list[str] = None
) -> dict:
    """Record an architectural decision with full context and reasoning."""
    alternatives = alternatives or []
    related_to = related_to or []
    return await impl_add_decision(description, rationale, alternatives, related_to)

# Tool 2: Query Decisions
@mcp.tool()
async def query_decisions(
    query: str,
    timeframe: dict = None
) -> list[dict]:
    """Search decisions using hybrid graph+vector search."""
    return await impl_query_decisions(query, timeframe)

# Tool 3: Add Pattern
@mcp.tool()
async def add_pattern(
    name: str,
    implementation: str,
    context: str,
    use_cases: list[str] = None
) -> dict:
    """Store successful implementation pattern."""
    use_cases = use_cases or []
    return await impl_add_pattern(name, implementation, use_cases, context)

# Tool 4: Add Failure
@mcp.tool()
async def add_failure(
    attempt: str,
    reason_failed: str,
    lesson_learned: str,
    alternative_solution: str = None
) -> dict:
    """Document what didn't work and lessons learned."""
    return await impl_add_failure(attempt, reason_failed, lesson_learned, alternative_solution)

# Tool 5: Find Related
@mcp.tool()
async def find_related(
    node_id: str,
    depth: int = 1
) -> list[dict]:
    """Find related knowledge nodes via graph traversal."""
    return await impl_find_related(node_id, depth)

# Tool 6: Detect Gaps
@mcp.tool()
async def detect_gaps() -> dict:
    """Run NetworkX structural analysis to detect knowledge gaps."""
    return await impl_detect_gaps()

# Tool 7: Get Timeline
@mcp.tool()
async def get_timeline(
    topic: str,
    start_date: str,
    end_date: str
) -> list[dict]:
    """Get temporal view of how knowledge evolved over time."""
    return await impl_get_timeline(topic, start_date, end_date)

# ============================================================
# MCP 2025-11-25: RESOURCES
# ============================================================

@mcp.resource("faulkner://stats")
async def get_stats() -> str:
    """Knowledge graph statistics and health status."""
    try:
        gaps = await impl_detect_gaps()
        return f"""# Faulkner-DB Statistics

Knowledge Graph Status: Active
Gap Analysis Results: {len(gaps.get('gaps', []))} gaps detected
Isolated Nodes: {len(gaps.get('isolated_nodes', []))}
Timestamp: {__import__('datetime').datetime.now().isoformat()}
"""
    except Exception as e:
        return f"Error retrieving stats: {e}"

@mcp.resource("faulkner://gaps")
async def get_current_gaps() -> str:
    """Current gap analysis results from NetworkX."""
    try:
        gaps = await impl_detect_gaps()
        import json
        return json.dumps(gaps, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"

# ============================================================
# MCP 2025-11-25: PROMPTS
# ============================================================

@mcp.prompt()
async def analyze_architecture(topic: str = "system design") -> str:
    """Architecture decision analysis workflow.
    
    Args:
        topic: The architectural topic to analyze
    """
    return f"""Please analyze the following architectural topic: {topic}

Steps:
1. Use query_decisions to find related past decisions
2. Use find_related to explore connected knowledge
3. Use detect_gaps to identify missing information
4. Provide recommendations based on findings

Please proceed with the analysis."""

@mcp.prompt()
async def capture_decision_workflow(decision: str = "") -> str:
    """Decision capture workflow with full context.
    
    Args:
        decision: Brief description of the decision
    """
    return f"""I need to capture an architectural decision: {decision}

Please help me document this decision by:
1. Clarifying the decision context and constraints
2. Identifying alternatives that were considered
3. Documenting the rationale for this choice
4. Linking to related decisions using find_related
5. Recording the decision using add_decision

Let's start with the context."""

@mcp.prompt()
async def find_knowledge_gaps() -> str:
    """Knowledge gap detection workflow."""
    return """Please analyze the knowledge graph for gaps:

1. Run detect_gaps to identify structural issues
2. Review isolated nodes that need connections
3. Identify topics with missing decisions or patterns
4. Suggest areas that need documentation
5. Prioritize gaps by impact

Provide a summary of findings and recommendations."""

if __name__ == "__main__":
    mcp.run()
