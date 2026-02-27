#!/usr/bin/env python3
"""
Extract and create relationships between Faulkner-DB nodes.

Phase 1: Create SOLVES relationships between Patterns and Failures
- Match Pattern.name appearing in Failure.alternative_solution
- Use fuzzy matching for better recall

Usage:
    python scripts/extract_relationships.py --dry-run   # Preview matches
    python scripts/extract_relationships.py --execute   # Create relationships
    python scripts/extract_relationships.py --stats     # Show current state
"""

import sys
import argparse
import re
from pathlib import Path
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.graphiti_client import FalkorDBAdapter


def get_all_nodes_by_type(adapter: FalkorDBAdapter) -> dict[str, list[dict]]:
    """Fetch all nodes grouped by type."""
    # Query all nodes
    result = adapter.graph.query("MATCH (n) RETURN n")

    nodes_by_type = defaultdict(list)
    for record in result.result_set:
        node = record[0]
        node_dict = {}

        if hasattr(node, 'properties'):
            for prop_name, prop_value in node.properties.items():
                node_dict[prop_name] = prop_value

        if hasattr(node, 'labels') and node.labels:
            node_type = node.labels[0]
            node_dict['type'] = node_type
            nodes_by_type[node_type].append(node_dict)

    return dict(nodes_by_type)


def normalize_text(text: str) -> str:
    """Normalize text for matching."""
    if not text:
        return ""
    # Lowercase, collapse whitespace
    return re.sub(r'\s+', ' ', text.lower().strip())


def extract_words(text: str) -> set[str]:
    """Extract meaningful words from text (>3 chars, excluding stopwords)."""
    if not text:
        return set()

    # Common stopwords to exclude
    STOPWORDS = {
        'the', 'and', 'for', 'with', 'that', 'this', 'from', 'have', 'been',
        'are', 'was', 'were', 'will', 'would', 'could', 'should', 'can', 'not',
        'but', 'all', 'any', 'some', 'when', 'what', 'which', 'where', 'how',
        'than', 'then', 'into', 'over', 'also', 'more', 'most', 'such', 'only',
        'just', 'very', 'much', 'each', 'other', 'being', 'here', 'there',
        'after', 'before', 'above', 'below', 'between', 'through', 'during',
        'about', 'using', 'used', 'need', 'needs', 'make', 'made', 'does', 'did',
        'based', 'like', 'work', 'works', 'without', 'because', 'however',
        'instead', 'different', 'multiple', 'various', 'specific', 'current',
        'new', 'same', 'first', 'last', 'next', 'previous', 'default', 'time',
        'way', 'case', 'cases', 'issue', 'issues', 'problem', 'problems',
        'solution', 'solutions', 'value', 'values', 'data', 'type', 'types',
    }

    words = re.findall(r'\b[a-z][a-z0-9_-]{2,}\b', text.lower())
    return set(w for w in words if w not in STOPWORDS and len(w) >= 4)


def find_solves_relationships(
    patterns: list[dict],
    failures: list[dict],
    min_word_overlap: int = 3
) -> list[tuple[str, str, dict]]:
    """
    Find SOLVES relationships: Pattern -> Failure

    Matching strategies:
    1. Exact name match in alternative_solution
    2. Word overlap between pattern name/context and failure text

    Returns: List of (pattern_id, failure_id, properties)
    """
    relationships = []

    for pattern in patterns:
        pattern_id = pattern.get('id')
        pattern_name = pattern.get('name', '')
        pattern_context = pattern.get('context', '')

        if not pattern_id:
            continue

        # Extract pattern keywords
        pattern_words = extract_words(pattern_name) | extract_words(pattern_context)
        pattern_name_normalized = normalize_text(pattern_name)

        for failure in failures:
            failure_id = failure.get('id')
            alt_solution = failure.get('alternative_solution', '')
            lesson = failure.get('lesson_learned', '')

            if not failure_id:
                continue

            match_score = 0
            match_type = None

            # Strategy 1: Exact name match in alternative_solution
            if pattern_name_normalized and alt_solution:
                alt_normalized = normalize_text(alt_solution)
                if pattern_name_normalized in alt_normalized:
                    match_score = 100
                    match_type = "exact_name_match"

            # Strategy 2: Word overlap (if no exact match found)
            if match_score == 0 and pattern_words:
                failure_text = f"{alt_solution} {lesson}"
                failure_words = extract_words(failure_text)

                overlap = pattern_words & failure_words
                if len(overlap) >= min_word_overlap:
                    match_score = len(overlap) * 10
                    match_type = f"word_overlap:{','.join(sorted(overlap)[:5])}"

            if match_score > 0:
                relationships.append((
                    pattern_id,
                    failure_id,
                    {
                        'match_score': match_score,
                        'match_type': match_type
                    }
                ))

    return relationships


def find_relates_to_relationships(
    patterns: list[dict],
    similarity_threshold: int = 3
) -> list[tuple[str, str, dict]]:
    """
    Find RELATES_TO relationships: Pattern -> Pattern

    Match by shared keywords in context or use_cases.

    Returns: List of (pattern1_id, pattern2_id, properties)
    """
    relationships = []

    # Pre-compute pattern word sets
    pattern_info = []
    for p in patterns:
        pid = p.get('id')
        if not pid:
            continue
        context_words = extract_words(p.get('context', ''))
        use_cases = p.get('use_cases', [])
        if isinstance(use_cases, str):
            # Handle JSON string
            import json
            try:
                use_cases = json.loads(use_cases)
            except:
                use_cases = []
        use_case_words = set()
        for uc in (use_cases or []):
            use_case_words |= extract_words(uc)

        all_words = context_words | use_case_words
        pattern_info.append((pid, all_words))

    # Find pairs with sufficient overlap
    for i, (pid1, words1) in enumerate(pattern_info):
        for pid2, words2 in pattern_info[i+1:]:
            overlap = words1 & words2
            if len(overlap) >= similarity_threshold:
                relationships.append((
                    pid1,
                    pid2,
                    {
                        'shared_keywords': ','.join(sorted(overlap)[:10]),
                        'overlap_count': len(overlap)
                    }
                ))

    return relationships


def count_existing_relationships(adapter: FalkorDBAdapter) -> dict[str, int]:
    """Count existing relationships by type."""
    result = adapter.graph.query(
        "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS cnt"
    )
    counts = {}
    for record in result.result_set:
        counts[record[0]] = record[1]
    return counts


def create_relationships_batch(
    adapter: FalkorDBAdapter,
    relationships: list[tuple[str, str, dict]],
    rel_type: str,
    batch_size: int = 100
) -> int:
    """Create relationships in batches."""
    created = 0

    for i in range(0, len(relationships), batch_size):
        batch = relationships[i:i+batch_size]

        for from_id, to_id, props in batch:
            try:
                adapter.create_relationship(from_id, to_id, rel_type, props)
                created += 1
            except Exception as e:
                print(f"  Error creating {rel_type} {from_id}->{to_id}: {e}")

    return created


def main():
    parser = argparse.ArgumentParser(description="Extract relationships for Faulkner-DB")
    parser.add_argument('--dry-run', action='store_true', help='Preview without creating')
    parser.add_argument('--execute', action='store_true', help='Create relationships')
    parser.add_argument('--stats', action='store_true', help='Show current statistics')
    parser.add_argument('--host', default='localhost', help='FalkorDB host')
    parser.add_argument('--port', type=int, default=6379, help='FalkorDB port')
    parser.add_argument('--min-overlap', type=int, default=3, help='Min word overlap for matching')
    parser.add_argument('--max-rels', type=int, default=50000, help='Max relationships to create')
    parser.add_argument('--min-score', type=int, default=30, help='Min match score for SOLVES')

    args = parser.parse_args()

    if not any([args.dry_run, args.execute, args.stats]):
        parser.print_help()
        print("\nError: Specify --dry-run, --execute, or --stats")
        return 1

    # Connect to FalkorDB
    print(f"Connecting to FalkorDB at {args.host}:{args.port}...")
    adapter = FalkorDBAdapter(host=args.host, port=args.port)

    # Show current stats
    if args.stats:
        print("\n=== Current Graph State ===")
        nodes = get_all_nodes_by_type(adapter)
        total_nodes = sum(len(v) for v in nodes.values())
        print(f"Total nodes: {total_nodes:,}")
        for ntype, nlist in sorted(nodes.items()):
            print(f"  {ntype}: {len(nlist):,}")

        print("\nRelationships:")
        rel_counts = count_existing_relationships(adapter)
        if rel_counts:
            for rtype, count in sorted(rel_counts.items()):
                print(f"  {rtype}: {count:,}")
        else:
            print("  (none)")
        return 0

    # Fetch nodes
    print("Fetching nodes...")
    nodes = get_all_nodes_by_type(adapter)

    patterns = nodes.get('Pattern', [])
    failures = nodes.get('Failure', [])

    print(f"  Patterns: {len(patterns):,}")
    print(f"  Failures: {len(failures):,}")

    if not patterns:
        print("Error: No patterns found")
        return 1

    # Find SOLVES relationships
    print(f"\nFinding SOLVES relationships (Pattern -> Failure)...")
    solves_rels = find_solves_relationships(patterns, failures, args.min_overlap)
    print(f"  Found: {len(solves_rels):,} potential relationships")

    # Filter by minimum score
    solves_rels = [(f, t, p) for f, t, p in solves_rels if p['match_score'] >= args.min_score]
    print(f"  After min_score filter ({args.min_score}): {len(solves_rels):,}")

    # Sort by score descending and limit
    solves_rels.sort(key=lambda x: x[2]['match_score'], reverse=True)
    solves_rels = solves_rels[:args.max_rels]
    print(f"  After max_rels limit ({args.max_rels}): {len(solves_rels):,}")

    # Find RELATES_TO relationships
    print(f"\nFinding RELATES_TO relationships (Pattern -> Pattern)...")
    relates_rels = find_relates_to_relationships(patterns)
    print(f"  Found: {len(relates_rels):,} potential relationships")

    # Sort by overlap count and limit
    relates_rels.sort(key=lambda x: x[2]['overlap_count'], reverse=True)
    max_relates = min(args.max_rels, len(relates_rels))
    relates_rels = relates_rels[:max_relates]
    print(f"  After limit ({max_relates}): {len(relates_rels):,}")

    # Dry run output
    if args.dry_run:
        print("\n=== DRY RUN - Preview ===")

        print("\nSample SOLVES relationships (first 10):")
        for from_id, to_id, props in solves_rels[:10]:
            print(f"  Pattern[{from_id[:20]}...] -> Failure[{to_id[:20]}...] ({props['match_type']})")

        print("\nSample RELATES_TO relationships (first 10):")
        for from_id, to_id, props in relates_rels[:10]:
            print(f"  Pattern[{from_id[:20]}...] <-> Pattern[{to_id[:20]}...] (overlap: {props['overlap_count']})")

        print("\n=== Summary ===")
        print(f"SOLVES to create: {len(solves_rels):,}")
        print(f"RELATES_TO to create: {len(relates_rels):,}")
        print(f"Total new relationships: {len(solves_rels) + len(relates_rels):,}")
        print("\nRun with --execute to create these relationships")
        return 0

    # Execute
    if args.execute:
        print("\n=== Creating Relationships ===")

        print("Creating SOLVES relationships...")
        solves_created = create_relationships_batch(adapter, solves_rels, 'SOLVES')
        print(f"  Created: {solves_created:,}")

        print("Creating RELATES_TO relationships...")
        relates_created = create_relationships_batch(adapter, relates_rels, 'RELATES_TO')
        print(f"  Created: {relates_created:,}")

        print("\n=== Verification ===")
        rel_counts = count_existing_relationships(adapter)
        for rtype, count in sorted(rel_counts.items()):
            print(f"  {rtype}: {count:,}")

        total_created = solves_created + relates_created
        print(f"\nTotal relationships created: {total_created:,}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
