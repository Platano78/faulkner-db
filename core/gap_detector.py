import networkx as nx
from typing import Dict, List, Any, Tuple
from collections import defaultdict
import logging
from enum import Enum
from dataclasses import dataclass, field


class GapType(Enum):
    ISOLATED_NODES = "isolated_nodes"
    DISCONNECTED_CLUSTERS = "disconnected_clusters"
    MISSING_BRIDGES = "missing_bridges"
    WEAK_CONNECTIONS = "weak_connections"


class Severity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class GapReport:
    gap_type: GapType
    affected_nodes: List[str]
    severity: Severity
    recommendation: str
    metrics: Dict[str, Any] = field(default_factory=dict)


class GapDetector:
    def __init__(self, client=None, config=None):
        self.client = client
        self.config = config or {}
        self.G = None  # NetworkX graph
        
        # Default thresholds
        self.thresholds = {
            'modularity_resolution': self.config.get('modularity_resolution', 1.0),
            'betweenness_threshold': self.config.get('betweenness_threshold', 0.1),
            'min_cluster_size': self.config.get('min_cluster_size', 2),
            'similarity_threshold': self.config.get('similarity_threshold', 0.7)
        }

    def detect_gaps(self) -> List[GapReport]:
        """Main method to detect all gaps in the knowledge graph"""
        if not self.G:
            raise ValueError("Graph not initialized. Run build_graph() first.")
            
        reports = []
        
        # Run all detectors
        reports.extend(self._detect_isolated_nodes())
        reports.extend(self._detect_disconnected_clusters())
        reports.extend(self._detect_missing_bridges())
        reports.extend(self._detect_weak_connections())
        
        return reports
    
    def build_graph(self, nodes_data: List[Dict], edges_data: List[Dict]):
        """Convert Graphiti data to NetworkX graph"""
        G = nx.Graph()
        
        # Add nodes
        for node in nodes_data:
            G.add_node(
                node['id'],
                name=node.get('name', ''),
                type=node.get('type', ''),
                attributes=node.get('attributes', {})
            )
            
        # Add edges
        for edge in edges_data:
            G.add_edge(
                edge['source'],
                edge['target'],
                type=edge.get('type', ''),
                weight=edge.get('weight', 1.0),
                attributes=edge.get('attributes', {})
            )
            
        self.G = G
        return G
    
    def _detect_isolated_nodes(self) -> List[GapReport]:
        """Find nodes with no connections"""
        isolated = list(nx.isolates(self.G))
        reports = []
        
        if isolated:
            severity = Severity.CRITICAL if len(isolated) > 5 else Severity.HIGH
            reports.append(GapReport(
                gap_type=GapType.ISOLATED_NODES,
                affected_nodes=isolated,
                severity=severity,
                recommendation=f"Connect {len(isolated)} isolated nodes to relevant concepts",
                metrics={'count': len(isolated)}
            ))
            
        return reports
    
    def _detect_disconnected_clusters(self) -> List[GapReport]:
        """Find disconnected components using modularity"""
        try:
            # Use connected components for disconnected cluster detection
            components = list(nx.connected_components(self.G))
            significant_components = [
                comp for comp in components 
                if len(comp) >= self.thresholds['min_cluster_size']
            ]
            
            reports = []
            if len(significant_components) > 1:
                for i, component in enumerate(significant_components):
                    reports.append(GapReport(
                        gap_type=GapType.DISCONNECTED_CLUSTERS,
                        affected_nodes=list(component),
                        severity=Severity.HIGH,
                        recommendation=f"Bridge cluster {i+1} with other clusters",
                        metrics={
                            'cluster_id': i,
                            'size': len(component)
                        }
                    ))
            return reports
        except Exception as e:
            logging.warning(f"Modularity detection failed: {e}")
            return []
    
    def _detect_missing_bridges(self) -> List[GapReport]:
        """Identify high-betweenness nodes that are potential bridges"""
        if len(self.G.nodes()) < 3:
            return []
            
        # Calculate betweenness centrality
        betweenness = nx.betweenness_centrality(self.G, normalized=True)
        bridge_candidates = {
            node: centrality 
            for node, centrality in betweenness.items() 
            if centrality > self.thresholds['betweenness_threshold']
        }
        
        reports = []
        if bridge_candidates:
            nodes = list(bridge_candidates.keys())
            avg_centrality = sum(bridge_candidates.values()) / len(bridge_candidates)
            
            reports.append(GapReport(
                gap_type=GapType.MISSING_BRIDGES,
                affected_nodes=nodes,
                severity=Severity.MEDIUM,
                recommendation=f"Strengthen connections for {len(nodes)} bridge nodes",
                metrics={
                    'avg_betweenness': avg_centrality,
                    'count': len(nodes)
                }
            ))
            
        return reports
    
    def _detect_weak_connections(self) -> List[GapReport]:
        """Find node pairs that should be connected but aren't"""
        reports = []
        
        # Simple heuristic: nodes in same community should have direct connections
        try:
            communities = nx.community.greedy_modularity_communities(self.G)
            missing_edges = []
            
            for community in communities:
                nodes = list(community)
                for i in range(len(nodes)):
                    for j in range(i+1, len(nodes)):
                        if not self.G.has_edge(nodes[i], nodes[j]):
                            missing_edges.append((nodes[i], nodes[j]))
                            
            if missing_edges:
                affected = list(set([n for pair in missing_edges for n in pair]))
                reports.append(GapReport(
                    gap_type=GapType.WEAK_CONNECTIONS,
                    affected_nodes=affected,
                    severity=Severity.LOW,
                    recommendation=f"Add {len(missing_edges)} missing connections within communities",
                    metrics={'potential_connections': len(missing_edges)}
                ))
        except Exception as e:
            logging.warning(f"Weak connection detection failed: {e}")
            
        return reports
    
    def get_graph_metrics(self) -> Dict[str, float]:
        """Calculate overall graph health metrics"""
        if not self.G:
            return {}
            
        return {
            'connectivity': nx.average_node_connectivity(self.G),
            'density': nx.density(self.G),
            'clustering_coefficient': nx.average_clustering(self.G),
            'node_count': len(self.G.nodes()),
            'edge_count': len(self.G.edges())
        }
