from fastapi import APIRouter, Query
import os
from falkordb import FalkorDB

router = APIRouter()

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", 6379))
GRAPH_NAME = "knowledge_graph"

def get_db_connection():
    db = FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT)
    return db.select_graph(GRAPH_NAME)

def format_graph_result(result):
    """Format query result into nodes and edges"""
    nodes = []
    edges = []
    node_id_map = {}  # Map internal IDs to custom IDs
    
    if not result or not hasattr(result, 'result_set') or len(result.result_set) == 0:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}}
    
    # First pass: collect all nodes and build ID mapping
    for record in result.result_set:
        if len(record) >= 1 and hasattr(record[0], 'properties'):
            node_data = dict(record[0].properties)
            internal_id = str(record[0].id)
            custom_id = node_data.get('id', internal_id)
            
            # Store mapping from internal ID to custom ID
            node_id_map[internal_id] = custom_id
            
            node = {
                "id": custom_id,
                "type": record[0].labels[0] if record[0].labels else "Unknown",
                **node_data
            }
            
            # Avoid duplicates
            if not any(n['id'] == custom_id for n in nodes):
                nodes.append(node)
        
        # Also process target node if it exists
        if len(record) >= 3 and hasattr(record[2], 'properties'):
            node_data = dict(record[2].properties)
            internal_id = str(record[2].id)
            custom_id = node_data.get('id', internal_id)
            
            node_id_map[internal_id] = custom_id
            
            node = {
                "id": custom_id,
                "type": record[2].labels[0] if record[2].labels else "Unknown",
                **node_data
            }
            
            if not any(n['id'] == custom_id for n in nodes):
                nodes.append(node)
    
    # Second pass: create edges using custom IDs
    for record in result.result_set:
        if len(record) >= 3 and hasattr(record[1], 'relation'):
            source_internal = str(record[0].id)
            target_internal = str(record[2].id)
            
            # Map internal IDs to custom IDs
            source_custom = node_id_map.get(source_internal, source_internal)
            target_custom = node_id_map.get(target_internal, target_internal)
            
            edge = {
                "source": source_custom,
                "target": target_custom,
                "type": record[1].relation
            }
            
            # Avoid duplicate edges
            if not any(e['source'] == source_custom and e['target'] == target_custom for e in edges):
                edges.append(edge)
    
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {"node_count": len(nodes), "edge_count": len(edges)}
    }

@router.get("/graph/full")
async def get_full_graph():
    try:
        graph = get_db_connection()
        query = """MATCH (n)
                   OPTIONAL MATCH (n)-[r]->(m)
                   RETURN n, r, m"""
        result = graph.query(query)
        return format_graph_result(result)
    except Exception as e:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}, "error": str(e)}

@router.get("/graph/subgraph")
async def get_subgraph(node_id: str, depth: int = 2):
    try:
        graph = get_db_connection()
        query = f"""MATCH (start) WHERE id(start) = {node_id}
                    MATCH path = (start)-[*1..{depth}]-(neighbor)
                    UNWIND nodes(path) as n
                    UNWIND relationships(path) as r
                    RETURN DISTINCT n, r, null"""
        result = graph.query(query)
        return format_graph_result(result)
    except Exception as e:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}, "error": str(e)}

@router.get("/timeline")
async def get_timeline():
    try:
        graph = get_db_connection()
        query = """MATCH (n)
                   WHERE exists(n.timestamp)
                   OPTIONAL MATCH (n)-[r]->(m)
                   RETURN n, r, m
                   ORDER BY n.timestamp ASC"""
        result = graph.query(query)
        return format_graph_result(result)
    except Exception as e:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}, "error": str(e)}

@router.get("/clusters")
async def get_clusters():
    try:
        graph = get_db_connection()
        query = "MATCH (n) RETURN n, null as r, null as m"
        result = graph.query(query)
        return format_graph_result(result)
    except Exception as e:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}, "error": str(e)}

@router.get("/gaps")
async def get_gaps():
    try:
        graph = get_db_connection()
        query = "MATCH (n) WHERE NOT (n)--() RETURN n, null as r, null as m"
        result = graph.query(query)
        return format_graph_result(result)
    except Exception as e:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}, "error": str(e)}

@router.get("/stats")
async def get_stats():
    try:
        graph = get_db_connection()
        node_result = graph.query("MATCH (n) RETURN count(n) as count")
        edge_result = graph.query("MATCH ()-[r]->() RETURN count(r) as count")
        
        node_count = node_result.result_set[0][0] if node_result.result_set else 0
        edge_count = edge_result.result_set[0][0] if edge_result.result_set else 0
        
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "density": edge_count / (node_count * (node_count - 1)) if node_count > 1 else 0
        }
    except Exception as e:
        return {"node_count": 0, "edge_count": 0, "density": 0, "error": str(e)}

@router.get("/search")
async def search_nodes(q: str = Query(..., min_length=1)):
    try:
        graph = get_db_connection()
        query = f"""MATCH (n)
                    WHERE any(prop IN keys(n) WHERE toString(n[prop]) CONTAINS '{q}')
                    OPTIONAL MATCH (n)-[r]->(m)
                    RETURN n, r, m"""
        result = graph.query(query)
        return format_graph_result(result)
    except Exception as e:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}, "error": str(e)}
