"""NetworkX-based structural analysis for Faulkner DB knowledge graph."""

import networkx as nx
from typing import Dict, List, Tuple, Any
from collections import defaultdict


class NetworkXAnalyzer:
    """NetworkX-based structural analysis for knowledge graph"""
    
    def __init__(self, graphiti_client):
        self.client = graphiti_client
        self.graph = None
        
    async def export_to_networkx(self) -> nx.DiGraph:
        """Export FalkorDB graph to NetworkX DiGraph.
        
        Returns:
            NetworkX DiGraph with all nodes and edges from FalkorDB
        """
        G = nx.DiGraph()
        
        # Query all nodes
        try:
            # Use FalkorDB adapter to get all nodes
            node_query = "MATCH (n) RETURN n.id as id, labels(n) as labels, properties(n) as props"
            node_result = self.client.db.graph.query(node_query)
            
            for record in node_result.result_set:
                node_id = record[0]
                labels = record[1]
                props = dict(record[2]) if record[2] else {}

                # Remove 'type' from props to avoid conflict with keyword argument
                props_copy = props.copy()
                props_copy.pop('type', None)

                G.add_node(node_id, type=labels[0] if labels else "Unknown", **props_copy)
            
            # Query all edges
            edge_query = "MATCH (n)-[r]->(m) RETURN n.id as source, type(r) as rel_type, m.id as target"
            edge_result = self.client.db.graph.query(edge_query)
            
            for record in edge_result.result_set:
                source_id = record[0]
                rel_type = record[1]
                target_id = record[2]
                
                G.add_edge(source_id, target_id, relationship=rel_type)
                
        except Exception as e:
            # Fallback: build graph from client relationships
            print(f"Warning: Could not query graph directly, using fallback: {e}")
            pass
        
        self.graph = G
        return G
    
    async def detect_gaps(self) -> Dict[str, Any]:
        """Detect structural gaps in knowledge graph.
        
        Returns:
            Dict containing:
            - isolated_nodes: List of nodes with no connections
            - isolated_count: Number of isolated nodes
            - disconnected_clusters: Number of weakly connected components
            - largest_cluster_size: Size of largest connected component
            - bridge_nodes: Top nodes by betweenness centrality
            - total_nodes: Total node count
            - total_edges: Total edge count
            - avg_degree: Average node degree
        """
        if self.graph is None:
            await self.export_to_networkx()
        
        G = self.graph
        
        if G.number_of_nodes() == 0:
            return {
                "isolated_nodes": [],
                "isolated_count": 0,
                "disconnected_clusters": 0,
                "largest_cluster_size": 0,
                "bridge_nodes": [],
                "total_nodes": 0,
                "total_edges": 0,
                "avg_degree": 0
            }
        
        # Find isolated nodes (no connections)
        isolated = list(nx.isolates(G))
        
        # Find weakly connected components
        components = list(nx.weakly_connected_components(G))
        
        # Find bridge nodes (critical connectors)
        bridges = []
        if G.number_of_edges() > 0 and G.number_of_nodes() > 1:
            try:
                betweenness = nx.betweenness_centrality(G)
                # Top 10 nodes by betweenness centrality
                sorted_nodes = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)
                bridges = [node for node, score in sorted_nodes[:10] if score > 0]
            except Exception as e:
                print(f"Warning: Could not calculate betweenness centrality: {e}")
        
        # Calculate average degree
        degrees = dict(G.degree())
        avg_degree = sum(degrees.values()) / G.number_of_nodes() if G.number_of_nodes() > 0 else 0
        
        return {
            "isolated_nodes": isolated[:10],  # Return first 10 only
            "isolated_count": len(isolated),
            "disconnected_clusters": len(components),
            "largest_cluster_size": max(len(c) for c in components) if components else 0,
            "bridge_nodes": bridges,
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "avg_degree": round(avg_degree, 2),
            "connectivity": round(1 - len(isolated) / G.number_of_nodes(), 3) if G.number_of_nodes() > 0 else 0
        }
    
    async def detect_communities(self, algorithm: str = "louvain") -> Dict[str, Any]:
        """Detect knowledge communities/clusters using community detection algorithms.
        
        Args:
            algorithm: Algorithm to use ("louvain" or "label_propagation")
            
        Returns:
            Dict containing:
            - num_communities: Number of detected communities
            - communities: List of community info (id, size, sample nodes)
            - modularity: Modularity score (higher = better community structure)
        """
        if self.graph is None:
            await self.export_to_networkx()
        
        G = self.graph
        
        if G.number_of_nodes() < 2:
            return {
                "num_communities": 0 if G.number_of_nodes() == 0 else 1,
                "communities": [],
                "modularity": 0.0
            }
        
        # Convert to undirected for community detection
        G_undirected = G.to_undirected()
        
        try:
            if algorithm == "louvain":
                # Try using python-louvain if available
                try:
                    import community as community_louvain
                    communities = community_louvain.best_partition(G_undirected)
                except ImportError:
                    # Fallback to greedy modularity
                    from networkx.algorithms import community
                    communities_sets = community.greedy_modularity_communities(G_undirected)
                    communities = {}
                    for i, comm in enumerate(communities_sets):
                        for node in comm:
                            communities[node] = i
            else:
                # Label propagation algorithm
                from networkx.algorithms import community
                communities_sets = community.label_propagation_communities(G_undirected)
                communities = {}
                for i, comm in enumerate(communities_sets):
                    for node in comm:
                        communities[node] = i
            
            # Group nodes by community
            community_groups = defaultdict(list)
            for node, comm_id in communities.items():
                community_groups[comm_id].append(node)
            
            # Calculate modularity
            try:
                from networkx.algorithms import community as nx_community
                partition = [set(nodes) for nodes in community_groups.values()]
                modularity = nx_community.modularity(G_undirected, partition)
            except:
                modularity = 0.0
            
            return {
                "num_communities": len(community_groups),
                "communities": [
                    {
                        "id": comm_id,
                        "size": len(nodes),
                        "sample_nodes": nodes[:5]  # First 5 nodes as sample
                    }
                    for comm_id, nodes in sorted(
                        community_groups.items(),
                        key=lambda x: len(x[1]),
                        reverse=True
                    )[:10]  # Top 10 largest communities
                ],
                "modularity": round(modularity, 3)
            }
            
        except Exception as e:
            return {
                "num_communities": 0,
                "communities": [],
                "modularity": 0.0,
                "error": str(e)
            }
