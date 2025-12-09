import collections
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

from common import schemas
from common.schemas import DecisionInput, PatternInput, FailureInput, TimelineEntry, GapReportOutput
from common import utils
from common.utils import track_tool, knowledge_growth
from core.knowledge_types import Decision, Pattern, Failure
from core.graphiti_client import GraphitiClient
from core.hybrid_search import hybrid_search
from core.gap_detector import GapDetector
from mcp_server.networkx_analyzer import NetworkXAnalyzer

# Lazy client initialization
_client = None
_gap_detector = None
_networkx_analyzer = None

def _get_client():
    global _client
    if _client is None:
        _client = GraphitiClient()
    return _client

def _get_gap_detector():
    global _gap_detector
    if _gap_detector is None:
        _gap_detector = GapDetector(client=_get_client())
    return _gap_detector

def _get_networkx_analyzer():
    global _networkx_analyzer
    if _networkx_analyzer is None:
        _networkx_analyzer = NetworkXAnalyzer(_get_client())
    return _networkx_analyzer


@track_tool
async def add_decision(
    description: str,
    rationale: str,
    alternatives: List[str],
    related_to: List[str],
    source_files: Optional[List[str]] = None
) -> Dict[str, str]:
    """Record an architectural decision with rationale and source tracking."""
    # Validate input
    decision_input = DecisionInput(
        description=description,
        rationale=rationale,
        alternatives=alternatives,
        related_to=related_to
    )
    
    # Create Decision model
    decision_id = f"D-{uuid4().hex[:8]}"
    decision = Decision(
        id=decision_id,
        description=decision_input.description,
        rationale=decision_input.rationale,
        alternatives=decision_input.alternatives,
        related_to=decision_input.related_to,
        source_files=source_files or []
    )
    
    # Store in graph
    client = _get_client()
    client.add_node(decision)

    # Create relationships to related decisions
    for related_id in decision_input.related_to:
        try:
            client.connect_decisions(decision_id, related_id, "RELATES_TO")
        except Exception as e:
            # Log but don't fail if relationship creation fails
            print(f"Warning: Could not create relationship to {related_id}: {e}")

    knowledge_growth['decisions'] += 1

    return {"decision_id": decision_id, "status": "created"}


@track_tool
async def query_decisions(
    query: str,
    timeframe: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """Query decisions using hybrid search."""
    # Build query string with timeframe if provided
    if timeframe:
        query_with_time = f"{query} in {timeframe.get('start', '')} to {timeframe.get('end', '')}"
    else:
        query_with_time = query
    
    # Execute hybrid search
    results, metrics = await hybrid_search(query_with_time, _get_client())
    
    return [
        {
            'content': r['content'],
            'score': r.get('rerank_score', r.get('score', 0)),
            'source': r.get('source', 'unknown'),
            'timestamp': r.get('timestamp', ''),
            'metadata': r.get('metadata', {})
        }
        for r in results[:15]
    ]


@track_tool
async def add_pattern(
    name: str,
    implementation: str,
    use_cases: List[str],
    context: str,
    source_files: Optional[List[str]] = None
) -> Dict[str, str]:
    """Store a successful implementation pattern with source tracking."""
    # Validate input
    pattern_input = PatternInput(
        name=name,
        implementation=implementation,
        use_cases=use_cases,
        context=context
    )
    
    # Create Pattern model
    pattern_id = f"P-{uuid4().hex[:8]}"
    pattern = Pattern(
        id=pattern_id,
        name=pattern_input.name,
        implementation=pattern_input.implementation,
        use_cases=pattern_input.use_cases,
        context=pattern_input.context,
        source_files=source_files or []
    )
    
    # Store in graph
    _get_client().add_node(pattern)
    knowledge_growth['patterns'] += 1
    
    return {"pattern_id": pattern_id, "status": "created"}


@track_tool
async def add_failure(
    attempt: str,
    reason_failed: str,
    lesson_learned: str,
    alternative_solution: Optional[str] = None,
    source_files: Optional[List[str]] = None
) -> Dict[str, str]:
    """Document what didn't work and why with source tracking."""
    # Validate input
    failure_input = FailureInput(
        attempt=attempt,
        reason_failed=reason_failed,
        lesson_learned=lesson_learned,
        alternative_solution=alternative_solution
    )
    
    # Create Failure model
    failure_id = f"F-{uuid4().hex[:8]}"
    failure = Failure(
        id=failure_id,
        attempt=failure_input.attempt,
        reason_failed=failure_input.reason_failed,
        lesson_learned=failure_input.lesson_learned,
        alternative_solution=failure_input.alternative_solution,
        source_files=source_files or []
    )
    
    # Store in graph
    _get_client().add_node(failure)
    knowledge_growth['failures'] += 1
    
    return {"failure_id": failure_id, "status": "created"}


@track_tool
async def find_related(
    node_id: str,
    depth: int = 1
) -> List[Dict[str, Any]]:
    """Find related knowledge nodes via graph traversal up to specified depth."""
    if depth < 1:
        return []
    
    try:
        # Use Cypher to get related nodes with full content in one query
        client = _get_client()
        
        # Query for nodes within specified depth, returning full node properties
        cypher_query = f'''
        MATCH path = (start {{id:"{node_id}"}})-[r*1..{depth}]-(related)
        RETURN DISTINCT 
            related.id AS id,
            related.description AS description,
            related.rationale AS rationale,
            related.alternatives AS alternatives,
            related.implementation AS implementation,
            related.attempt AS attempt,
            related.lesson_learned AS lesson_learned,
            related.type AS type,
            labels(related)[0] AS node_type,
            length(path) AS distance
        ORDER BY distance
        LIMIT 50
        '''
        
        result = client.db.graph.query(cypher_query)
        
        results = []
        if result.result_set:
            for record in result.result_set:
                (node_id, description, rationale, alternatives, 
                 implementation, attempt, lesson_learned, node_type_prop,
                 node_type_label, distance) = record
                
                # Build node data with available properties
                node_data = {
                    'id': node_id,
                    'distance': distance,
                    'type': node_type_label or node_type_prop
                }
                
                # Add content properties if they exist
                if description:
                    node_data['description'] = description
                if rationale:
                    node_data['rationale'] = rationale
                if alternatives:
                    node_data['alternatives'] = alternatives
                if implementation:
                    node_data['implementation'] = implementation
                if attempt:
                    node_data['attempt'] = attempt
                if lesson_learned:
                    node_data['lesson_learned'] = lesson_learned
                
                results.append(node_data)
        
        return results
        
    except Exception as e:
        # Log error and return empty list
        print(f"Error in find_related for node {node_id}: {e}")
        return []


@track_tool
async def detect_gaps() -> Dict[str, Any]:
    """Run NetworkX structural gap analysis on knowledge graph.
    
    Returns comprehensive analysis including:
    - Isolated nodes (no connections)
    - Disconnected clusters
    - Bridge nodes (critical connectors)
    - Connectivity metrics
    """
    return await _get_networkx_analyzer().detect_gaps()


@track_tool
async def get_timeline(
    topic: str,
    start_date: str,
    end_date: str
) -> List[Dict[str, Any]]:
    """Get timeline view of knowledge nodes matching topic, filtered by date range.
    
    Args:
        topic: Topic to filter nodes by (searches in content)
        start_date: Start date in ISO8601 format
        end_date: End date in ISO8601 format
        
    Returns:
        List of timeline entries sorted chronologically
    """
    import time
    start_time = time.time()
    
    try:
        # Validate date inputs
        try:
            datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError as e:
            print(f"Invalid date format for timeline query: {start_date} to {end_date}: {e}")
            return []

        if start_date > end_date:
            print(f"Invalid date range: start_date {start_date} after end_date {end_date}")
            return []

        # Get client
        client = _get_client()

        # Query nodes with temporal filtering and topic matching
        cypher_query = '''
        MATCH (n)
        WHERE n.timestamp >= $start_date
          AND n.timestamp <= $end_date
        RETURN
            n.id AS id,
            labels(n)[0] AS type,
            n.timestamp AS timestamp,
            n.description AS description,
            n.name AS name,
            n.implementation AS implementation,
            n.attempt AS attempt,
            n.rationale AS rationale
        ORDER BY n.timestamp ASC
        LIMIT 1000
        '''

        # Use parameterized query for safety
        result = client.db.graph.query(cypher_query, {'start_date': start_date, 'end_date': end_date})

        timeline = []
        if result.result_set:
            for record in result.result_set:
                (node_id, node_type, timestamp, description, name,
                 implementation, attempt, rationale) = record

                # Build content based on node type
                content = {}
                if description:
                    content['description'] = description
                if name:
                    content['name'] = name
                if implementation:
                    content['implementation'] = implementation
                if attempt:
                    content['attempt'] = attempt
                if rationale:
                    content['rationale'] = rationale

                # Filter by topic if content matches (case-insensitive)
                if topic:
                    content_str = str(content).lower()
                    if topic.lower() not in content_str:
                        continue

                timeline.append({
                    'timestamp': timestamp if timestamp else start_date,
                    'type': node_type.lower() if node_type else 'unknown',
                    'id': node_id,
                    'content': content
                })

        # Log performance metrics
        execution_time = time.time() - start_time
        print(f"Timeline query executed in {execution_time:.3f}s, returned {len(timeline)} results")
        
        return timeline

    except Exception as e:
        execution_time = time.time() - start_time
        print(f"Error fetching timeline after {execution_time:.3f}s: {e}")
        return []


# Tool registry for MCP server
TOOL_REGISTRY = {
    'add_decision': add_decision,
    'query_decisions': query_decisions,
    'add_pattern': add_pattern,
    'add_failure': add_failure,
    'find_related': find_related,
    'detect_gaps': detect_gaps,
    'get_timeline': get_timeline,
}
