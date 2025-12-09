import asyncio
import re
import time
from datetime import datetime
from typing import Dict, List, Tuple
from sentence_transformers import SentenceTransformer
from sentence_transformers.cross_encoder import CrossEncoder
from core.graphiti_client import GraphitiClient

# Models loaded lazily on first use
_EMBEDDING_MODEL = None
_RERANKER_MODEL = None

def _get_embedding_model():
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        _EMBEDDING_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    return _EMBEDDING_MODEL

def _get_reranker_model():
    global _RERANKER_MODEL
    if _RERANKER_MODEL is None:
        _RERANKER_MODEL = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    return _RERANKER_MODEL

CACHE = {}

class SearchMetrics:
    def __init__(self):
        self.decomposition_time = 0
        self.search_time = 0
        self.fusion_time = 0
        self.reranking_time = 0
        self.total_time = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.graph_results_count = 0
        self.vector_results_count = 0

    def to_dict(self):
        return {
            'decomposition_ms': self.decomposition_time * 1000,
            'search_ms': self.search_time * 1000,
            'fusion_ms': self.fusion_time * 1000,
            'reranking_ms': self.reranking_time * 1000,
            'total_ms': self.total_time * 1000,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'graph_results': self.graph_results_count,
            'vector_results': self.vector_results_count
        }

def extract_temporal(query: str) -> dict:
    """Extract temporal constraints from query."""
    # Match Q3, Q4, etc.
    q_match = re.search(r'Q([1-4])\s*(\d{4})', query, re.IGNORECASE)
    if q_match:
        quarter = int(q_match.group(1))
        year = int(q_match.group(2))
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3
        return {
            'start': f"{year}-{start_month:02d}-01",
            'end': f"{year}-{end_month:02d}-30"
        }
    return {}

def query_decomposer(query: str) -> dict:
    """Break down natural language query into semantic and keyword parts."""
    temporal = extract_temporal(query)
    # Remove temporal expressions for semantic processing
    semantic_part = re.sub(r'in Q[1-4] \d{4}', '', query, flags=re.IGNORECASE).strip()
    semantic_part = re.sub(r'in (timeframe|period)', '', semantic_part, flags=re.IGNORECASE).strip()
    
    # Extract keywords (filter out stop words)
    stop_words = {'what', 'when', 'where', 'why', 'how', 'in', 'the', 'a', 'an', 'about', 'were', 'was', 'made'}
    keywords = [w for w in re.findall(r'\b\w+\b', semantic_part.lower()) if w not in stop_words][:10]
    
    return {
        'original': query,
        'semantic': semantic_part,
        'keyword': keywords,
        'temporal': temporal
    }

async def vector_search(query_text: str, top_k: int = 50) -> List[Dict]:
    """Perform vector similarity search using embeddings."""
    embedding = _get_embedding_model().encode([query_text])
    # In production, this would query a vector database (FAISS, Pinecone, etc.)
    # For now, return mock data
    return [
        {
            "content": f"Vector match for '{query_text}'",
            "score": 0.8,
            "source": "vector",
            "timestamp": "2024-08-15T12:00:00Z",
            "metadata": {"embedding_model": "all-MiniLM-L6-v2"}
        }
    ]

async def graph_traversal(client: GraphitiClient, query_keywords: List[str], temporal: dict) -> List[Dict]:
    """Perform graph traversal based on keywords and temporal constraints."""
    results = []
    
    # Query actual FalkorDB nodes with full content
    for keyword in query_keywords[:5]:  # Limit to top keywords
        try:
            # Use Cypher CONTAINS for text search across all node types
            cypher_query = f'''
            MATCH (n)
            WHERE (n.description IS NOT NULL AND toLower(n.description) CONTAINS toLower("{keyword}"))
               OR (n.rationale IS NOT NULL AND toLower(n.rationale) CONTAINS toLower("{keyword}"))
               OR (n.implementation IS NOT NULL AND toLower(n.implementation) CONTAINS toLower("{keyword}"))
               OR (n.attempt IS NOT NULL AND toLower(n.attempt) CONTAINS toLower("{keyword}"))
            RETURN n
            LIMIT 10
            '''
            result = client.db.graph.query(cypher_query)
            
            # Parse FalkorDB result set
            nodes = []
            if result.result_set:
                for record in result.result_set:
                    node = record[0]
                    node_dict = {}
                    if hasattr(node, 'properties'):
                        for prop_name, prop_value in node.properties.items():
                            node_dict[prop_name] = prop_value
                    if hasattr(node, 'labels') and node.labels:
                        node_dict['type'] = node.labels[0]
                    nodes.append(node_dict)
            
            # Transform nodes to expected format with full content
            for node in nodes:
                # Combine description, rationale, and alternatives into content
                description = node.get('description', '')
                rationale = node.get('rationale', '')
                alternatives = node.get('alternatives', '')
                
                content = f"{description} {rationale}"
                if alternatives:
                    if isinstance(alternatives, list):
                        content += ' ' + ' '.join(alternatives)
                    else:
                        content += ' ' + str(alternatives)
                
                results.append({
                    "content": content.strip(),
                    "score": 0.7,
                    "source": "graph",
                    "timestamp": node.get('timestamp', '2024-08-20T14:30:00Z'),
                    "metadata": {
                        "keyword": keyword,
                        "temporal": temporal,
                        "node_id": node.get('id', ''),
                        "description": description,
                        "rationale": rationale,
                        "alternatives": alternatives
                    }
                })
        except Exception as e:
            # Log error but continue with other keywords
            print(f"Error querying keyword '{keyword}': {e}")
            continue
    
    return results

async def parallel_executor(client: GraphitiClient, decomposed_query: dict) -> Tuple[List[Dict], List[Dict]]:
    """Execute graph and vector searches in parallel."""
    tasks = [
        graph_traversal(client, decomposed_query['keyword'], decomposed_query['temporal']),
        vector_search(decomposed_query['semantic'])
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle exceptions
    graph_results = results[0] if not isinstance(results[0], Exception) else []
    vector_results = results[1] if not isinstance(results[1], Exception) else []
    
    return graph_results, vector_results

def reciprocal_rank_fusion(graph_results: List[Dict], vector_results: List[Dict], k=60) -> List[Dict]:
    """Merge results from multiple sources using Reciprocal Rank Fusion."""
    fused_scores = {}
    content_to_result = {}
    
    # Process graph results
    for i, res in enumerate(graph_results):
        content = res["content"]
        fused_scores[content] = fused_scores.get(content, 0) + 1 / (k + i + 1)
        if content not in content_to_result:
            content_to_result[content] = res
    
    # Process vector results
    for i, res in enumerate(vector_results):
        content = res["content"]
        fused_scores[content] = fused_scores.get(content, 0) + 1 / (k + i + 1)
        if content not in content_to_result:
            content_to_result[content] = res
    
    # Sort by fused score
    sorted_items = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Reconstruct results with original metadata
    merged = []
    for content, score in sorted_items:
        result = content_to_result[content].copy()
        result["score"] = score
        merged.append(result)
    
    return merged

def crossencoder_reranker(query: str, candidates: List[dict], top_k=15) -> List[dict]:
    """Rerank candidates using CrossEncoder for better relevance."""
    if not candidates:
        return []
    
    texts = [cand["content"] for cand in candidates]
    query_text_pairs = [(query, text) for text in texts]
    
    # Get reranking scores
    scores = _get_reranker_model().predict(query_text_pairs)
    
    # Combine scores with original results
    scored_candidates = []
    for i, cand in enumerate(candidates):
        result = cand.copy()
        result["rerank_score"] = float(scores[i])
        scored_candidates.append(result)
    
    # Sort by rerank score
    scored_candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
    
    return scored_candidates[:top_k]

async def hybrid_search(query: str, client=None) -> Tuple[List[dict], SearchMetrics]:
    """Main hybrid search function orchestrating all components."""
    metrics = SearchMetrics()
    start_time = time.time()
    
    # Check cache
    if query in CACHE:
        metrics.cache_hits += 1
        metrics.total_time = time.time() - start_time
        return CACHE[query], metrics
    
    metrics.cache_misses += 1
    
    # Initialize client if not provided
    if not client:
        client = GraphitiClient()
    
    # Step 1: Decompose Query
    decomp_start = time.time()
    decomposed = query_decomposer(query)
    metrics.decomposition_time = time.time() - decomp_start
    
    # Step 2: Parallel Execution
    search_start = time.time()
    graph_res, vec_res = await parallel_executor(client, decomposed)
    metrics.search_time = time.time() - search_start
    metrics.graph_results_count = len(graph_res)
    metrics.vector_results_count = len(vec_res)
    
    # Step 3: Reciprocal Rank Fusion
    fusion_start = time.time()
    merged = reciprocal_rank_fusion(graph_res, vec_res)
    metrics.fusion_time = time.time() - fusion_start
    
    # Step 4: Re-ranking
    rerank_start = time.time()
    final_results = crossencoder_reranker(decomposed['semantic'], merged, top_k=15)
    metrics.reranking_time = time.time() - rerank_start
    
    # Calculate total time
    metrics.total_time = time.time() - start_time
    
    # Validate performance
    if metrics.total_time >= 2.0:
        print(f"[WARNING] Search took {metrics.total_time:.2f}s, exceeds 2s target")
    
    # Cache result
    CACHE[query] = final_results
    
    return final_results, metrics
