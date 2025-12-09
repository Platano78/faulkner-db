#!/usr/bin/env python3
"""
Populate FalkorDB with sample knowledge graph data.
Creates representative decisions, patterns, and failures to demonstrate system functionality.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.mcp_tools import add_decision, add_pattern, add_failure


SAMPLE_DECISIONS = [
    {
        "description": "Use FalkorDB for temporal knowledge graph storage",
        "rationale": "FalkorDB provides Redis-compatible graph database with CPU-only operation, suitable for gaming workstations. Offers Cypher query language and good performance for relationship traversal.",
        "alternatives": ["Neo4j (GPU requirements)", "PostgreSQL with pg_graph extension", "ArangoDB"],
        "related_to": []
    },
    {
        "description": "Implement FastMCP for MCP server framework",
        "rationale": "FastMCP reduces boilerplate by 80%, handles MCP protocol automatically, and provides clean decorator-based tool registration. Production-ready with official support.",
        "alternatives": ["Custom MCP implementation", "Node.js MCP SDK"],
        "related_to": []
    },
    {
        "description": "Use hybrid search (graph + vector + reranking) for queries",
        "rationale": "Combining graph traversal, vector embeddings, and cross-encoder reranking achieves 90%+ accuracy while maintaining <2s query latency. Best of both worlds.",
        "alternatives": ["Pure graph search", "Pure vector search", "ElasticSearch"],
        "related_to": []
    },
    {
        "description": "Adopt Pydantic v2 for data validation and schema management",
        "rationale": "Pydantic v2 provides runtime type checking, automatic schema generation, and 5-50x performance improvement over v1. Essential for MCP tool parameter validation.",
        "alternatives": ["Marshmallow", "Cerberus", "Manual validation"],
        "related_to": []
    },
    {
        "description": "Use NetworkX for graph analysis and gap detection",
        "rationale": "NetworkX provides extensive graph algorithms for structural analysis, gap detection, and relationship discovery. Pure Python, no GPU required, integrates seamlessly with FalkorDB exports.",
        "alternatives": ["igraph", "graph-tool", "Custom algorithms"],
        "related_to": []
    },
]

SAMPLE_PATTERNS = [
    {
        "name": "MCP Tool Registration Pattern",
        "implementation": "Use FastMCP @mcp.tool() decorator to register async functions as MCP tools. Include type hints for automatic validation and docstrings for tool descriptions.",
        "context": "MCP server development with FastMCP framework",
        "use_cases": ["Rapid MCP tool creation", "Type-safe tool parameters", "Auto-generated tool schemas"]
    },
    {
        "name": "Hybrid Search Pattern",
        "implementation": "Combine graph traversal for exact matches, vector similarity for semantic search, and cross-encoder reranking for final scoring. Return top-k results with confidence scores.",
        "context": "Knowledge retrieval systems requiring high accuracy and relevance",
        "use_cases": ["Decision retrieval", "Pattern matching", "Failure case lookup"]
    },
    {
        "name": "Batched LLM Extraction Pattern",
        "implementation": "Group 20-50 items per LLM call with structured JSON output. Use asyncio for parallel processing across batches. Achieve 95%+ reduction in LLM calls vs sequential.",
        "context": "Large-scale knowledge extraction from conversation corpora",
        "use_cases": ["Agent Genesis extraction", "Bulk knowledge ingestion", "Historical data migration"]
    },
    {
        "name": "Graph + Metadata Dual Storage Pattern",
        "implementation": "Store relationships and structure in FalkorDB graph. Store metadata, embeddings, and large text fields in PostgreSQL. Join on node IDs for complete data retrieval.",
        "context": "Systems requiring both graph traversal and rich metadata",
        "use_cases": ["Temporal knowledge graphs", "Multi-modal data storage", "Hybrid query systems"]
    },
    {
        "name": "Docker Auto-Start Pattern",
        "implementation": "Configure Docker Desktop to start on login. Use 'restart: unless-stopped' policy in docker-compose.yml. Services auto-start within 30-60 seconds of Docker launch.",
        "context": "Development environments requiring zero-friction service availability",
        "use_cases": ["Database services", "Development APIs", "Gaming + coding workflows"]
    },
]

SAMPLE_FAILURES = [
    {
        "attempt": "Used custom MCP server implementation with manual stdout management",
        "reason_failed": "Frequent JSON-RPC protocol violations due to stdout contamination. Debugging output mixed with protocol messages caused parse errors in Claude Desktop.",
        "lesson_learned": "Never mix logging with stdout in MCP servers. Use stderr for logs or adopt FastMCP which handles this automatically.",
        "alternative_solution": "Migrated to FastMCP framework - reduced code by 80% and eliminated all protocol violations"
    },
    {
        "attempt": "Applied aggressive filtering (98.6% rejection rate) during conversation extraction",
        "reason_failed": "Filtered out valuable short conversations and duplicate patterns, resulting in only 49 nodes from 14,705 conversations. Quality filters too strict for diverse corpus.",
        "lesson_learned": "Filter calibration is critical. Volume compensates for slightly lower precision. 30-char minimum and 0.05 relevance threshold works better than 100-char and 0.15.",
        "alternative_solution": "Relaxed filters to 23% rejection rate, extracted 2,076 nodes with 18.7% success rate - 42x improvement"
    },
    {
        "attempt": "Ran sequential LLM extraction calls for each conversation",
        "reason_failed": "Processing 11,000 conversations would take 15+ hours. Unacceptable latency for iterative development and testing.",
        "lesson_learned": "Batch LLM requests 20-50 at a time. Use async parallel processing. Achieve 113x speedup with proper batching strategy.",
        "alternative_solution": "Implemented batched extraction with 100-conversation batches, 20-item LLM sub-batches. Completed in 33 minutes."
    },
    {
        "attempt": "Stored all node content in FalkorDB graph properties",
        "reason_failed": "Large text fields (2000+ chars) bloated graph memory usage. Query performance degraded with verbose node properties.",
        "lesson_learned": "Graph databases excel at relationships, not large content storage. Use separate metadata store for big fields.",
        "alternative_solution": "Moved embeddings and large text to PostgreSQL. FalkorDB stores IDs and relationships only."
    },
]


async def populate_sample_data():
    """Populate graph with representative sample data."""
    print("=" * 70)
    print("📊 POPULATING FAULKNER-DB WITH SAMPLE DATA")
    print("=" * 70)
    print()

    decision_ids = []
    pattern_ids = []
    failure_ids = []

    # Add decisions
    print("💡 Adding sample decisions...")
    for i, dec in enumerate(SAMPLE_DECISIONS, 1):
        try:
            result = await add_decision(
                description=dec["description"],
                rationale=dec["rationale"],
                alternatives=dec.get("alternatives"),
                related_to=dec.get("related_to")
            )
            decision_ids.append(result["node_id"])
            print(f"  ✅ ({i}/{len(SAMPLE_DECISIONS)}) {result['node_id']}: {dec['description'][:60]}...")
        except Exception as e:
            print(f"  ❌ Failed to add decision {i}: {e}")

    print()

    # Add patterns
    print("🏗️  Adding sample patterns...")
    for i, pat in enumerate(SAMPLE_PATTERNS, 1):
        try:
            result = await add_pattern(
                name=pat["name"],
                implementation=pat["implementation"],
                context=pat["context"],
                use_cases=pat.get("use_cases", [])
            )
            pattern_ids.append(result["node_id"])
            print(f"  ✅ ({i}/{len(SAMPLE_PATTERNS)}) {result['node_id']}: {pat['name']}")
        except Exception as e:
            print(f"  ❌ Failed to add pattern {i}: {e}")

    print()

    # Add failures
    print("❗ Adding sample failures...")
    for i, fail in enumerate(SAMPLE_FAILURES, 1):
        try:
            result = await add_failure(
                attempt=fail["attempt"],
                reason_failed=fail["reason_failed"],
                lesson_learned=fail["lesson_learned"],
                alternative_solution=fail.get("alternative_solution")
            )
            failure_ids.append(result["node_id"])
            print(f"  ✅ ({i}/{len(SAMPLE_FAILURES)}) {result['node_id']}: {fail['attempt'][:60]}...")
        except Exception as e:
            print(f"  ❌ Failed to add failure {i}: {e}")

    print()
    print("=" * 70)
    print("✅ SAMPLE DATA POPULATION COMPLETE")
    print("=" * 70)
    print()
    print(f"📊 Summary:")
    print(f"  Decisions: {len(decision_ids)}")
    print(f"  Patterns:  {len(pattern_ids)}")
    print(f"  Failures:  {len(failure_ids)}")
    print(f"  Total:     {len(decision_ids) + len(pattern_ids) + len(failure_ids)} nodes")
    print()
    print("🔍 Next steps:")
    print("  1. Verify graph: query_decisions with various search terms")
    print("  2. Test relationships: find_related on any node ID")
    print("  3. Run gap analysis: detect_gaps to see graph structure")
    print()

    return {
        "decisions": decision_ids,
        "patterns": pattern_ids,
        "failures": failure_ids
    }


if __name__ == "__main__":
    asyncio.run(populate_sample_data())
