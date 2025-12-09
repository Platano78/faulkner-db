#!/usr/bin/env python3
from falkordb import FalkorDB

db = FalkorDB(host='localhost', port=6379)
graph = db.select_graph('knowledge_graph')

print("FAULKNER DB - CURRENT STATE")
print("="*50)

# Query total nodes by type
result = graph.query("MATCH (n) RETURN labels(n)[0] as type, COUNT(n) as count ORDER BY count DESC")
print("\nNodes by Type:")
total_nodes = 0
for record in result.result_set:
    count = record[1]
    total_nodes += count
    print(f"  {record[0]}: {count:,}")

print(f"\nTotal Nodes: {total_nodes:,}")

# Query total edges  
result = graph.query("MATCH ()-[r]->() RETURN COUNT(r) as edges")
edges = result.result_set[0][0]
print(f"Total Edges: {edges:,}")

# Calculate connectivity
if total_nodes > 0:
    result = graph.query("MATCH (n) WHERE EXISTS((n)-[]-()) RETURN COUNT(n) as connected")
    connected = result.result_set[0][0]
    connectivity = (connected / total_nodes) * 100
    print(f"\nConnectivity: {connectivity:.2f}% ({connected:,}/{total_nodes:,} nodes have relationships)")
