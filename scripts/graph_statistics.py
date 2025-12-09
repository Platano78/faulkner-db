"""Generate comprehensive knowledge graph statistics."""
import asyncio
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.mcp_tools import query_decisions

async def get_graph_statistics():
    print("="*60)
    print("FAULKNER DB - KNOWLEDGE GRAPH STATISTICS")
    print("="*60)
    
    # Query all nodes
    print("\n📊 Querying knowledge base...")
    nodes = await query_decisions(query="")
    
    print(f"✅ Loaded {len(nodes)} total nodes\n")
    
    # Node type breakdown
    node_types = Counter(node.get('type', 'unknown') for node in nodes)
    print("📋 Node Types:")
    for ntype, count in node_types.most_common():
        print(f"   {ntype}: {count}")
    
    # Relationship statistics
    total_edges = 0
    nodes_with_edges = 0
    relationship_types = Counter()
    
    for node in nodes:
        edges = node.get('edges', [])
        if edges:
            nodes_with_edges += 1
            total_edges += len(edges)
            for edge in edges:
                relationship_types[edge.get('type', 'unknown')] += 1
    
    connectivity_pct = (nodes_with_edges / len(nodes) * 100) if nodes else 0
    
    print(f"\n🔗 Relationships:")
    print(f"   Total edges: {total_edges:,}")
    print(f"   Connected nodes: {nodes_with_edges:,} ({connectivity_pct:.1f}%)")
    print(f"   Isolated nodes: {len(nodes) - nodes_with_edges:,}")
    print(f"   Avg edges/node: {total_edges / len(nodes):.1f}" if nodes else "   N/A")
    
    print(f"\n📊 Relationship Types:")
    for rtype, count in relationship_types.most_common():
        print(f"   {rtype}: {count:,}")
    
    # Temporal analysis (if timestamps available)
    dated_nodes = [n for n in nodes if n.get('timestamp')]
    if dated_nodes:
        dates = [datetime.fromisoformat(n['timestamp'].replace('Z', '+00:00')) for n in dated_nodes]
        earliest = min(dates)
        latest = max(dates)
        print(f"\n📅 Temporal Range:")
        print(f"   Earliest: {earliest.strftime('%Y-%m-%d')}")
        print(f"   Latest: {latest.strftime('%Y-%m-%d')}")
        print(f"   Span: {(latest - earliest).days} days")
    
    # Top keywords (if available)
    all_keywords = []
    for node in nodes:
        keywords = node.get('keywords', [])
        all_keywords.extend(keywords)
    
    if all_keywords:
        keyword_counts = Counter(all_keywords)
        print(f"\n🏷️  Top Keywords:")
        for keyword, count in keyword_counts.most_common(10):
            print(f"   {keyword}: {count}")
    
    # Quality metrics
    nodes_with_rationale = sum(1 for n in nodes if n.get('rationale'))
    nodes_with_alternatives = sum(1 for n in nodes if n.get('alternatives'))
    
    print(f"\n✨ Data Quality:")
    print(f"   With rationale: {nodes_with_rationale}/{len(nodes)} ({nodes_with_rationale/len(nodes)*100:.1f}%)")
    print(f"   With alternatives: {nodes_with_alternatives}/{len(nodes)} ({nodes_with_alternatives/len(nodes)*100:.1f}%)")
    
    print("\n" + "="*60)
    print("STATISTICS COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(get_graph_statistics())
