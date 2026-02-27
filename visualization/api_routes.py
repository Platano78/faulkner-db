from fastapi import APIRouter, Query
import os
import logging
from falkordb import FalkorDB

logger = logging.getLogger(__name__)
router = APIRouter()

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", 6379))
FALKORDB_PASSWORD = os.getenv("FALKORDB_PASSWORD", None)
GRAPH_NAME = "knowledge_graph"

_db_instance = None
_graph_instance = None

LABELS = ["Pattern", "Failure", "Decision"]

FT_INDEX_FIELDS = {
    "Pattern": ["name", "description", "implementation"],
    "Failure": ["attempt", "reason_failed", "lesson_learned"],
    "Decision": ["name", "description", "rationale"],
}


def get_db():
    global _db_instance
    if _db_instance is None:
        _db_instance = FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT, password=FALKORDB_PASSWORD)
    return _db_instance


def get_graph():
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = get_db().select_graph(GRAPH_NAME)
    return _graph_instance


def ensure_indexes():
    """Create property and full-text indexes if they don't exist. Safe to call multiple times."""
    graph = get_graph()
    for label in LABELS:
        try:
            graph.query(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
        except Exception:
            pass
        fields = FT_INDEX_FIELDS.get(label, [])
        if fields:
            field_args = ", ".join(f"'{f}'" for f in fields)
            try:
                graph.query(f"CALL db.idx.fulltext.createNodeIndex('{label}', {field_args})")
            except Exception:
                pass


def configure_server_limits():
    """Set FalkorDB server-side safety limits via GRAPH.CONFIG."""
    try:
        import redis
        r = redis.Redis(host=FALKORDB_HOST, port=FALKORDB_PORT, password=FALKORDB_PASSWORD, decode_responses=True)
        limits = [("TIMEOUT", "30000"), ("RESULTSET_SIZE", "50000"), ("QUERY_MEM_CAPACITY", "536870912")]
        for key, val in limits:
            try:
                r.execute_command("GRAPH.CONFIG", "SET", key, val)
            except Exception:
                pass
        r.close()
    except Exception:
        pass


def _process_node(node_obj, nodes_map, node_id_map):
    if not hasattr(node_obj, 'properties'):
        return
    props = dict(node_obj.properties)
    internal_id = str(node_obj.id)
    custom_id = props.get('id', internal_id)
    node_id_map[internal_id] = custom_id
    if custom_id not in nodes_map:
        nodes_map[custom_id] = {
            "id": custom_id,
            "type": node_obj.labels[0] if node_obj.labels else "Unknown",
            **props,
        }


def format_graph_result(result):
    """Format query result into nodes and edges using dict-based dedup."""
    nodes_map = {}
    edges_set = set()
    edges = []
    node_id_map = {}

    if not result or not hasattr(result, 'result_set') or len(result.result_set) == 0:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}}

    for record in result.result_set:
        if len(record) >= 1 and record[0] is not None:
            _process_node(record[0], nodes_map, node_id_map)
        if len(record) >= 3 and record[2] is not None:
            _process_node(record[2], nodes_map, node_id_map)

    for record in result.result_set:
        if len(record) >= 3 and record[1] is not None and hasattr(record[1], 'relation'):
            src = node_id_map.get(str(record[0].id), str(record[0].id))
            tgt = node_id_map.get(str(record[2].id), str(record[2].id))
            edge_key = (src, tgt, record[1].relation)
            if edge_key not in edges_set:
                edges_set.add(edge_key)
                edges.append({"source": src, "target": tgt, "type": record[1].relation})

    return {
        "nodes": list(nodes_map.values()),
        "edges": edges,
        "stats": {"node_count": len(nodes_map), "edge_count": len(edges)},
    }


@router.get("/graph/full")
async def get_full_graph(limit: int = Query(default=500, ge=1, le=5000)):
    try:
        graph = get_graph()
        query = f"""MATCH (n)
                   WITH n LIMIT {limit}
                   OPTIONAL MATCH (n)-[r]->(m)
                   RETURN n, r, m"""
        result = graph.ro_query(query)
        return format_graph_result(result)
    except Exception as e:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}, "error": str(e)}


@router.get("/graph/subgraph")
async def get_subgraph(node_id: str, depth: int = Query(default=2, ge=1, le=3)):
    try:
        graph = get_graph()
        safe_id = node_id.replace('"', '\\"')
        query = f"""MATCH (start {{id: "{safe_id}"}})
                    OPTIONAL MATCH path = (start)-[*1..{depth}]-(neighbor)
                    WITH start, path
                    UNWIND CASE WHEN path IS NULL THEN [start] ELSE nodes(path) END as n
                    WITH DISTINCT n LIMIT 200
                    OPTIONAL MATCH (n)-[r]->(m)
                    RETURN DISTINCT n, r, m"""
        result = graph.ro_query(query)
        return format_graph_result(result)
    except Exception as e:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}, "error": str(e)}


@router.get("/node/{node_id}")
async def get_node(node_id: str):
    """Get a single node by ID with all its properties."""
    try:
        graph = get_graph()
        safe_id = node_id.replace('"', '\\"')
        query = f'MATCH (n {{id: "{safe_id}"}}) RETURN n'
        result = graph.ro_query(query)

        if not result.result_set:
            return {"node": None, "error": "Node not found"}

        node = result.result_set[0][0]
        node_data = dict(node.properties) if hasattr(node, 'properties') else {}
        node_data['type'] = node.labels[0] if hasattr(node, 'labels') and node.labels else 'Unknown'
        return {"node": node_data}
    except Exception as e:
        return {"node": None, "error": str(e)}


@router.get("/timeline")
async def get_timeline(limit: int = Query(default=500, ge=1, le=5000)):
    try:
        graph = get_graph()
        query = f"""MATCH (n)
                   WHERE exists(n.timestamp)
                   WITH n ORDER BY n.timestamp ASC LIMIT {limit}
                   OPTIONAL MATCH (n)-[r]->(m)
                   RETURN n, r, m"""
        result = graph.ro_query(query)
        return format_graph_result(result)
    except Exception as e:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}, "error": str(e)}


@router.get("/clusters")
async def get_clusters(limit: int = Query(default=500, ge=1, le=5000)):
    try:
        graph = get_graph()
        query = f"MATCH (n) WITH n LIMIT {limit} RETURN n, null as r, null as m"
        result = graph.ro_query(query)
        return format_graph_result(result)
    except Exception as e:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}, "error": str(e)}


@router.get("/gaps")
async def get_gaps(limit: int = Query(default=500, ge=1, le=5000)):
    try:
        graph = get_graph()
        query = f"MATCH (n) WHERE NOT (n)--() WITH n LIMIT {limit} RETURN n, null as r, null as m"
        result = graph.ro_query(query)
        return format_graph_result(result)
    except Exception as e:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}, "error": str(e)}


@router.get("/stats")
async def get_stats():
    try:
        graph = get_graph()
        node_result = graph.ro_query("MATCH (n) RETURN count(n) as count")
        edge_result = graph.ro_query("MATCH ()-[r]->() RETURN count(r) as count")

        node_count = node_result.result_set[0][0] if node_result.result_set else 0
        edge_count = edge_result.result_set[0][0] if edge_result.result_set else 0

        label_result = graph.ro_query("MATCH (n) RETURN labels(n)[0] as label, count(n) as cnt")
        labels = {r[0]: r[1] for r in label_result.result_set} if label_result.result_set else {}

        rel_result = graph.ro_query("MATCH ()-[r]->() RETURN type(r) as rel, count(r) as cnt")
        relationships = {r[0]: r[1] for r in rel_result.result_set} if rel_result.result_set else {}

        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "density": edge_count / (node_count * (node_count - 1)) if node_count > 1 else 0,
            "labels": labels,
            "relationships": relationships,
        }
    except Exception as e:
        return {"node_count": 0, "edge_count": 0, "density": 0, "error": str(e)}


@router.get("/search")
async def search_nodes(q: str = Query(..., min_length=1), limit: int = Query(default=100, ge=1, le=1000)):
    """Search nodes using full-text indexes with fallback to property scan."""
    try:
        graph = get_graph()
        all_nodes = {}
        all_edges_set = set()
        all_edges = []

        safe_q = q.replace("\\", "\\\\").replace("'", "\\\'")

        for label in LABELS:
            try:
                ft_query = f"""CALL db.idx.fulltext.queryNodes('{label}', '{safe_q}')
                              YIELD node
                              WITH node LIMIT {limit}
                              OPTIONAL MATCH (node)-[r]->(m)
                              RETURN node, r, m"""
                result = graph.ro_query(ft_query)
                partial = format_graph_result(result)
                for n in partial["nodes"]:
                    all_nodes[n["id"]] = n
                for e in partial["edges"]:
                    ek = (e["source"], e["target"], e["type"])
                    if ek not in all_edges_set:
                        all_edges_set.add(ek)
                        all_edges.append(e)
            except Exception:
                pass

        if all_nodes:
            return {
                "nodes": list(all_nodes.values()),
                "edges": all_edges,
                "stats": {"node_count": len(all_nodes), "edge_count": len(all_edges)},
            }

        # Fallback: property scan if FT indexes not ready or no results
        query = f"""MATCH (n)
                    WHERE any(prop IN keys(n) WHERE toString(n[prop]) CONTAINS '{safe_q}')
                    WITH n LIMIT {limit}
                    OPTIONAL MATCH (n)-[r]->(m)
                    RETURN n, r, m"""
        result = graph.ro_query(query)
        return format_graph_result(result)
    except Exception as e:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}, "error": str(e)}


@router.get("/schema")
async def get_schema():
    """Return the graph schema: labels, relationship types, property keys."""
    try:
        graph = get_graph()
        labels = graph.ro_query("CALL db.labels()").result_set
        rels = graph.ro_query("CALL db.relationshipTypes()").result_set
        props = graph.ro_query("CALL db.propertyKeys()").result_set
        return {
            "labels": [r[0] for r in labels] if labels else [],
            "relationship_types": [r[0] for r in rels] if rels else [],
            "property_keys": [r[0] for r in props] if props else [],
        }
    except Exception as e:
        return {"error": str(e)}
