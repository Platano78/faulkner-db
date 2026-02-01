#!/usr/bin/env python3
"""Faulkner-DB FastMCP Server - Production implementation."""

import sys
import logging
import os

# FIX: Auto-detect project root for portable installation
# When this script runs from mcp_server/, Python needs explicit path to find the mcp_server package
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

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
    version="1.1.1",
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


# =============================================================================
# Graph Algorithm Tools (Phase 4)
# =============================================================================

@mcp.tool()
async def find_influential_patterns(limit: int = 10) -> dict:
    """Find most connected/influential patterns using PageRank algorithm.
    
    Returns patterns ranked by their influence in the knowledge graph,
    based on how many other nodes reference them.
    """
    from core.graphiti_client import FalkorDBAdapter
    
    host = os.environ.get('FALKORDB_HOST', 'localhost')
    port = int(os.environ.get('FALKORDB_PORT', 6380))
    password = os.environ.get('FALKORDB_PASSWORD')
    adapter = FalkorDBAdapter(host=host, port=port, password=password)
    
    # Use degree centrality as PageRank proxy (count incoming + outgoing edges)
    query = f"""
    MATCH (p:Pattern)
    OPTIONAL MATCH (p)-[r]-()
    WITH p, count(r) as connections
    RETURN p.id as id, p.name as name, p.context as context, connections
    ORDER BY connections DESC
    LIMIT {limit}
    """
    
    result = adapter.graph.query(query)
    patterns = []
    for record in result.result_set:
        patterns.append({
            'id': record[0],
            'name': record[1],
            'context': record[2][:200] + '...' if record[2] and len(record[2]) > 200 else record[2],
            'influence_score': record[3]
        })
    
    return {
        'influential_patterns': patterns,
        'algorithm': 'degree_centrality',
        'description': 'Patterns ranked by number of connections (SOLVES + RELATES_TO)'
    }


@mcp.tool()
async def find_knowledge_communities(min_community_size: int = 3) -> dict:
    """Detect communities of related knowledge using connected components.
    
    Groups patterns that are strongly connected to each other,
    revealing clusters of related knowledge.
    """
    from core.graphiti_client import FalkorDBAdapter
    from collections import defaultdict
    
    host = os.environ.get('FALKORDB_HOST', 'localhost')
    port = int(os.environ.get('FALKORDB_PORT', 6380))
    password = os.environ.get('FALKORDB_PASSWORD')
    adapter = FalkorDBAdapter(host=host, port=port, password=password)
    
    # Find connected components via RELATES_TO relationships
    query = """
    MATCH (p1:Pattern)-[:RELATES_TO]-(p2:Pattern)
    RETURN p1.id as id1, p1.name as name1, p2.id as id2, p2.name as name2
    """
    
    result = adapter.graph.query(query)
    
    # Build adjacency and use union-find to detect communities
    parent = {}
    
    def find(x):
        if x not in parent:
            parent[x] = x
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    
    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py
    
    node_names = {}
    for record in result.result_set:
        id1, name1, id2, name2 = record
        node_names[id1] = name1
        node_names[id2] = name2
        union(id1, id2)
    
    # Group by community
    communities = defaultdict(list)
    for node_id in node_names:
        root = find(node_id)
        communities[root].append({'id': node_id, 'name': node_names[node_id]})
    
    # Filter by minimum size and sort by size
    filtered = [
        {'community_id': i+1, 'size': len(members), 'members': members[:10]}  # Limit members shown
        for i, (root, members) in enumerate(sorted(communities.items(), key=lambda x: -len(x[1])))
        if len(members) >= min_community_size
    ]
    
    return {
        'communities': filtered[:20],  # Top 20 communities
        'total_communities': len(filtered),
        'algorithm': 'connected_components',
        'description': 'Clusters of patterns connected via RELATES_TO relationships'
    }


@mcp.tool()
async def find_bridge_patterns(limit: int = 10) -> dict:
    """Find bridge patterns that connect different knowledge domains.
    
    These patterns have high betweenness - they connect otherwise
    separate clusters of knowledge.
    """
    from core.graphiti_client import FalkorDBAdapter
    
    host = os.environ.get('FALKORDB_HOST', 'localhost')
    port = int(os.environ.get('FALKORDB_PORT', 6380))
    password = os.environ.get('FALKORDB_PASSWORD')
    adapter = FalkorDBAdapter(host=host, port=port, password=password)
    
    # Find patterns with diverse connections (proxy for betweenness)
    # Patterns that connect to many different other patterns
    query = f"""
    MATCH (p:Pattern)-[:RELATES_TO]-(other:Pattern)
    WITH p, count(DISTINCT other) as unique_connections
    WHERE unique_connections > 5
    RETURN p.id as id, p.name as name, p.context as context, unique_connections
    ORDER BY unique_connections DESC
    LIMIT {limit}
    """
    
    result = adapter.graph.query(query)
    bridges = []
    for record in result.result_set:
        bridges.append({
            'id': record[0],
            'name': record[1],
            'context': record[2][:200] + '...' if record[2] and len(record[2]) > 200 else record[2],
            'bridge_score': record[3]
        })
    
    return {
        'bridge_patterns': bridges,
        'algorithm': 'unique_neighbor_count',
        'description': 'Patterns connecting many different knowledge areas'
    }


@mcp.tool()
async def get_graph_summary() -> dict:
    """Get comprehensive summary of the knowledge graph structure.
    
    Returns node counts, edge counts, relationship types, and connectivity metrics.
    """
    from core.graphiti_client import FalkorDBAdapter
    
    host = os.environ.get('FALKORDB_HOST', 'localhost')
    port = int(os.environ.get('FALKORDB_PORT', 6380))
    password = os.environ.get('FALKORDB_PASSWORD')
    adapter = FalkorDBAdapter(host=host, port=port, password=password)
    
    # Node counts by type
    node_query = "MATCH (n) RETURN labels(n)[0] as type, count(n) as count"
    node_result = adapter.graph.query(node_query)
    node_counts = {record[0]: record[1] for record in node_result.result_set}
    
    # Edge counts by type
    edge_query = "MATCH ()-[r]->() RETURN type(r) as type, count(r) as count"
    edge_result = adapter.graph.query(edge_query)
    edge_counts = {record[0]: record[1] for record in edge_result.result_set}
    
    # Connectivity metrics
    connected_query = """
    MATCH (p:Pattern)
    OPTIONAL MATCH (p)-[r]-()
    WITH p, count(r) as degree
    RETURN 
        count(p) as total,
        sum(CASE WHEN degree > 0 THEN 1 ELSE 0 END) as connected,
        avg(degree) as avg_degree,
        max(degree) as max_degree
    """
    conn_result = adapter.graph.query(connected_query)
    conn_data = conn_result.result_set[0] if conn_result.result_set else [0, 0, 0, 0]
    
    return {
        'nodes': node_counts,
        'edges': edge_counts,
        'total_nodes': sum(node_counts.values()),
        'total_edges': sum(edge_counts.values()),
        'connectivity': {
            'patterns_total': conn_data[0],
            'patterns_connected': conn_data[1],
            'avg_degree': round(conn_data[2], 2) if conn_data[2] else 0,
            'max_degree': conn_data[3]
        }
    }


@mcp.tool()
async def query_patterns_semantic(query: str, limit: int = 10) -> dict:
    """Semantic search for patterns using embeddings.
    
    Uses sentence-transformers embeddings for similarity-based search.
    More intelligent than keyword matching - understands concepts.
    
    Args:
        query: Natural language query describing what you're looking for
        limit: Maximum number of results (default: 10)
    
    Returns:
        List of patterns ranked by semantic similarity
    """
    import pickle
    import numpy as np
    from pathlib import Path
    
    cache_file = Path(PROJECT_ROOT) / "data" / "embeddings" / "pattern_embeddings.pkl"
    
    if not cache_file.exists():
        return {
            'error': 'Embeddings cache not found. Run: python scripts/generate_embeddings.py --generate',
            'results': []
        }
    
    # Load cache
    with open(cache_file, 'rb') as f:
        cache = pickle.load(f)
    
    # Load model and encode query
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(cache['model'])
    query_embedding = model.encode([query], convert_to_numpy=True)[0]
    
    # Compute cosine similarity
    embeddings = cache['embeddings']
    similarities = np.dot(embeddings, query_embedding) / (
        np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_embedding)
    )
    
    # Get top results
    top_indices = np.argsort(similarities)[::-1][:limit]
    
    results = []
    for idx in top_indices:
        pattern_id = cache['ids'][idx]
        pattern = cache['patterns'][pattern_id]
        score = float(similarities[idx])
        results.append({
            'id': pattern_id,
            'name': pattern['name'],
            'context': pattern['context'],
            'similarity': round(score, 3)
        })
    
    return {
        'query': query,
        'model': cache['model'],
        'results': results
    }

# ============================================================
# STARTUP HEALTH CHECK
# ============================================================

def startup_health_check():
    """Validate FalkorDB has data on startup. Warn if database appears empty."""
    import redis

    try:
        host = os.environ.get('FALKORDB_HOST', 'localhost')
        port = int(os.environ.get('FALKORDB_PORT', 6380))
        password = os.environ.get('FALKORDB_PASSWORD')

        client = redis.Redis(host=host, port=port, password=password, decode_responses=True)
        client.ping()
        
        # Check node count
        result = client.execute_command('GRAPH.QUERY', 'knowledge_graph', 'MATCH (n) RETURN count(n)')
        # Parse result - format varies but count is usually in result[1][0][0]
        node_count = 0
        if result and len(result) > 1 and result[1]:
            node_count = result[1][0][0] if result[1][0] else 0
        
        if node_count < 10:
            logging.warning(f"⚠️  FAULKNER-DB HEALTH WARNING: Database appears empty or corrupted!")
            logging.warning(f"   Node count: {node_count} (expected 1000+)")
            logging.warning(f"   Consider restoring from backup: {PROJECT_ROOT}/scripts/restore_falkordb.sh")
        else:
            logging.info(f"✓ FalkorDB health check passed: {node_count} nodes")
            
    except redis.ConnectionError as e:
        logging.error(f"✗ FalkorDB connection failed: {e}")
        logging.error(f"  Ensure FalkorDB container is running: docker start faulkner-db-falkordb")
    except Exception as e:
        logging.warning(f"⚠️  FalkorDB health check error: {e}")

# Run health check on import (when server starts)
startup_health_check()

if __name__ == "__main__":
    mcp.run()
