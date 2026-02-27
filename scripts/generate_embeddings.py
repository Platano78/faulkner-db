#!/usr/bin/env python3
"""
Generate and cache embeddings for Faulkner-DB patterns.

Uses sentence-transformers to create embeddings for semantic search.
Embeddings are cached to disk for fast loading.

Usage:
    python scripts/generate_embeddings.py --generate   # Generate embeddings
    python scripts/generate_embeddings.py --stats      # Show cache stats
"""

import sys
import argparse
import pickle
import json
from pathlib import Path
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

CACHE_DIR = Path(__file__).parent.parent / "data" / "embeddings"
CACHE_FILE = CACHE_DIR / "pattern_embeddings.pkl"
MODEL_NAME = "all-MiniLM-L6-v2"  # Fast, 384-dim embeddings


def get_all_patterns():
    """Fetch all patterns from FalkorDB."""
    from core.graphiti_client import FalkorDBAdapter
    import os

    host = os.environ.get('FALKORDB_HOST', 'localhost')
    port = int(os.environ.get('FALKORDB_PORT', 6379))
    adapter = FalkorDBAdapter(host=host, port=port)

    query = """
    MATCH (p:Pattern)
    RETURN p.id as id, p.name as name, p.implementation as impl, p.context as context
    """
    result = adapter.graph.query(query)

    patterns = []
    for record in result.result_set:
        patterns.append({
            'id': record[0],
            'name': record[1] or '',
            'implementation': record[2] or '',
            'context': record[3] or ''
        })

    return patterns


def generate_embeddings(patterns: list[dict], model) -> dict:
    """Generate embeddings for patterns."""
    embeddings_data = {
        'model': MODEL_NAME,
        'dimension': 384,
        'patterns': {},
        'embeddings': None,
        'ids': []
    }

    # Combine text fields for embedding
    texts = []
    ids = []
    for p in patterns:
        text = f"{p['name']} {p['context']} {p['implementation']}"
        text = text[:1000]  # Truncate for efficiency
        texts.append(text)
        ids.append(p['id'])
        embeddings_data['patterns'][p['id']] = {
            'name': p['name'],
            'context': p['context'][:200] if p['context'] else ''
        }

    print(f"Generating embeddings for {len(texts)} patterns...")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    embeddings_data['embeddings'] = embeddings
    embeddings_data['ids'] = ids

    return embeddings_data


def save_cache(data: dict):
    """Save embeddings cache to disk."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, 'wb') as f:
        pickle.dump(data, f)
    print(f"Cache saved to {CACHE_FILE}")


def load_cache() -> dict | None:
    """Load embeddings cache from disk."""
    if not CACHE_FILE.exists():
        return None
    with open(CACHE_FILE, 'rb') as f:
        return pickle.load(f)


def main():
    parser = argparse.ArgumentParser(description="Generate pattern embeddings")
    parser.add_argument('--generate', action='store_true', help='Generate embeddings')
    parser.add_argument('--stats', action='store_true', help='Show cache statistics')
    parser.add_argument('--test', type=str, help='Test semantic search with query')

    args = parser.parse_args()

    if not any([args.generate, args.stats, args.test]):
        parser.print_help()
        return 1

    if args.stats:
        cache = load_cache()
        if cache:
            print(f"=== Embeddings Cache Stats ===")
            print(f"Model: {cache['model']}")
            print(f"Dimension: {cache['dimension']}")
            print(f"Patterns: {len(cache['ids'])}")
            print(f"Cache file: {CACHE_FILE}")
            print(f"Cache size: {CACHE_FILE.stat().st_size / 1024 / 1024:.2f} MB")
        else:
            print("No cache found. Run with --generate first.")
        return 0

    if args.generate:
        from sentence_transformers import SentenceTransformer

        print(f"Loading model: {MODEL_NAME}")
        model = SentenceTransformer(MODEL_NAME)

        print("Fetching patterns from FalkorDB...")
        patterns = get_all_patterns()
        print(f"Found {len(patterns)} patterns")

        data = generate_embeddings(patterns, model)
        save_cache(data)

        print(f"\n=== Generation Complete ===")
        print(f"Patterns embedded: {len(data['ids'])}")
        print(f"Embedding dimension: {data['dimension']}")
        return 0

    if args.test:
        from sentence_transformers import SentenceTransformer

        cache = load_cache()
        if not cache:
            print("No cache found. Run with --generate first.")
            return 1

        print(f"Loading model: {MODEL_NAME}")
        model = SentenceTransformer(MODEL_NAME)

        print(f"Searching for: '{args.test}'")
        query_embedding = model.encode([args.test], convert_to_numpy=True)[0]

        # Compute cosine similarity
        embeddings = cache['embeddings']
        similarities = np.dot(embeddings, query_embedding) / (
            np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Get top 5 results
        top_indices = np.argsort(similarities)[::-1][:5]

        print(f"\n=== Top 5 Results ===")
        for i, idx in enumerate(top_indices):
            pattern_id = cache['ids'][idx]
            pattern = cache['patterns'][pattern_id]
            score = similarities[idx]
            print(f"{i+1}. [{score:.3f}] {pattern['name'][:60]}...")

        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
