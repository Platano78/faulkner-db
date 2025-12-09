#!/usr/bin/env python3
"""
Comprehensive NetworkX Structural Analysis

Replicates InfraNodus functionality for knowledge graph insights.
Detects:
- Concept clusters (communities)
- Disconnected clusters
- Bridge concepts (high betweenness centrality)
- Isolated nodes
- Knowledge gaps with exploration questions
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime
import json
from collections import Counter

try:
    import networkx as nx
except ImportError:
    print("Error: networkx not installed. Run: pip install networkx")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.graphiti_client import GraphitiClient


class ComprehensiveGapAnalyzer:
    """Comprehensive NetworkX-based knowledge graph analysis."""
    
    def __init__(self):
        self.graph = nx.Graph()
        self.nodes_data = {}
        
    def build_graph_from_knowledge_base(self):
        """
        Query all knowledge from Faulkner DB and build NetworkX graph.
        """
        print("🔍 Building graph from knowledge base...")
        
        # Query all nodes from FalkorDB
        try:
            client = GraphitiClient()
            all_results = client.db.query_nodes({})  # Empty query returns all
        except Exception as e:
            print(f"❌ Error querying knowledge base: {e}")
            all_results = []
        
        print(f"✅ Loaded {len(all_results)} nodes from knowledge base")
        
        # Add nodes to graph
        for result in all_results:
            # Extract node ID
            node_id = result.get('id', f"node_{len(self.graph)}")
            
            # Extract description/content
            description = result.get('description', result.get('rationale', result.get('implementation', '')))
            
            # Add node with attributes
            self.graph.add_node(
                node_id,
                type=result.get('type', 'unknown'),
                description=description[:200] if description else '',  # Truncate for memory
                keywords=self.extract_keywords(description) if description else []
            )
            
            self.nodes_data[node_id] = result
            
            # Add edges from related_to field if available
            # related_to might be a JSON string, parse it
            related_to_raw = result.get('related_to', '[]')
            try:
                import json
                if isinstance(related_to_raw, str):
                    related_to = json.loads(related_to_raw)
                else:
                    related_to = related_to_raw if isinstance(related_to_raw, list) else []
            except:
                related_to = []
            
            for related_id in related_to:
                # We'll add the edge later after all nodes are loaded
                # to avoid missing node errors
                pass
        
        # Second pass: Query edges from FalkorDB and add to graph
        try:
            # Query all relationships from FalkorDB
            edge_query = "MATCH (a)-[r]->(b) RETURN a.id AS source, b.id AS target, type(r) AS rel_type, r.weight AS weight"
            edge_result = client.db.graph.query(edge_query)
            
            if edge_result.result_set:
                for edge_row in edge_result.result_set:
                    source_id = edge_row[0]
                    target_id = edge_row[1]
                    rel_type = edge_row[2] if len(edge_row) > 2 else 'RELATED_TO'
                    weight = edge_row[3] if len(edge_row) > 3 else 1.0
                    
                    # Add edge if both nodes exist in graph
                    if source_id in self.graph and target_id in self.graph:
                        self.graph.add_edge(source_id, target_id, 
                                          relationship=rel_type, 
                                          weight=weight)
                        
            print(f"   Loaded {edge_result.result_set.__len__() if edge_result.result_set else 0} edges from relationships")
        except Exception as e:
            print(f"   ⚠️  Error loading edges: {e}")
        
        # Also process related_to field from nodes (legacy support)
        for result in all_results:
            node_id = result.get('id', '')
            related_to_raw = result.get('related_to', '[]')
            try:
                import json
                if isinstance(related_to_raw, str):
                    related_to = json.loads(related_to_raw)
                else:
                    related_to = related_to_raw if isinstance(related_to_raw, list) else []
            except:
                related_to = []
            
            for related_id in related_to:
                if related_id and related_id in self.graph:
                    self.graph.add_edge(node_id, related_id)
        
        print(f"✅ Graph built: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        
    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text for semantic clustering."""
        if not text:
            return []
        
        # Simple keyword extraction
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might',
            'this', 'that', 'these', 'those', 'with', 'from', 'by', 'as', 'of'
        }
        
        words = text.lower().split()
        keywords = [w.strip('.,;:!?()[]{}"') for w in words 
                   if len(w) > 4 and w.lower() not in stopwords]
        return keywords[:10]  # Top 10 keywords
    
    def detect_communities(self) -> List[Set]:
        """
        Detect concept clusters (communities) in the graph.
        """
        print("\n🔍 Detecting concept clusters...")
        
        if self.graph.number_of_nodes() == 0:
            print("⚠️  Empty graph, no communities to detect")
            return []
        
        try:
            from networkx.algorithms import community
            communities = list(community.greedy_modularity_communities(self.graph))
        except Exception as e:
            print(f"⚠️  Community detection failed: {e}")
            return []
        
        print(f"✅ Found {len(communities)} concept clusters")
        
        for i, comm in enumerate(communities[:5]):  # Show top 5
            sample_nodes = list(comm)[:3]
            sample_descriptions = [
                self.graph.nodes[node_id].get('description', '')[:40] 
                for node_id in sample_nodes
            ]
            print(f"   Cluster {i+1}: {len(comm)} nodes - {', '.join(sample_descriptions)}...")
        
        return communities
    
    def find_disconnected_clusters(self, communities: List[Set]) -> List[Dict]:
        """
        Find pairs of clusters with no/weak connections.
        """
        print("\n🔍 Finding disconnected clusters...")
        
        gaps = []
        
        for i, comm1 in enumerate(communities):
            for j, comm2 in enumerate(communities):
                if i >= j:
                    continue
                
                # Count edges between communities
                edges_between = sum(
                    1 for node1 in comm1 for node2 in comm2
                    if self.graph.has_edge(node1, node2)
                )
                
                if edges_between == 0:
                    gaps.append({
                        'type': 'disconnected_clusters',
                        'cluster1': list(comm1)[:5],
                        'cluster2': list(comm2)[:5],
                        'cluster1_size': len(comm1),
                        'cluster2_size': len(comm2),
                        'connection_count': 0,
                        'severity': 'HIGH'
                    })
                elif edges_between <= 2:
                    gaps.append({
                        'type': 'weak_connection',
                        'cluster1': list(comm1)[:5],
                        'cluster2': list(comm2)[:5],
                        'cluster1_size': len(comm1),
                        'cluster2_size': len(comm2),
                        'connection_count': edges_between,
                        'severity': 'MEDIUM'
                    })
        
        print(f"✅ Found {len(gaps)} cluster gaps")
        return gaps
    
    def find_bridge_concepts(self) -> List[Dict]:
        """
        Find concepts with high betweenness centrality (bridges).
        """
        print("\n🔍 Finding bridge concepts...")
        
        if self.graph.number_of_nodes() < 2:
            print("⚠️  Not enough nodes for centrality analysis")
            return []
        
        try:
            betweenness = nx.betweenness_centrality(self.graph)
            bridges = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:10]
        except Exception as e:
            print(f"⚠️  Centrality calculation failed: {e}")
            return []
        
        bridge_concepts = []
        for node_id, score in bridges:
            if score > 0.05:  # Significant bridging
                bridge_concepts.append({
                    'type': 'bridge_concept',
                    'node_id': node_id,
                    'description': self.graph.nodes[node_id].get('description', '')[:60],
                    'betweenness_score': score,
                    'severity': 'INFO'
                })
        
        print(f"✅ Found {len(bridge_concepts)} bridge concepts")
        for bc in bridge_concepts[:5]:
            print(f"   {bc['node_id']}: {bc['description']} (score: {bc['betweenness_score']:.3f})")
        
        return bridge_concepts
    
    def find_isolated_nodes(self) -> List[Dict]:
        """
        Find nodes with no connections.
        """
        print("\n🔍 Finding isolated nodes...")
        
        isolated = [node for node in self.graph.nodes() if self.graph.degree(node) == 0]
        
        print(f"✅ Found {len(isolated)} isolated nodes")
        
        return [{
            'type': 'isolated_node',
            'node_id': node_id,
            'description': self.graph.nodes[node_id].get('description', '')[:60],
            'severity': 'HIGH'
        } for node_id in isolated[:20]]  # Top 20
    
    def generate_exploration_queries(self, gap: Dict) -> List[str]:
        """
        Generate questions to explore knowledge gaps.
        """
        if gap['type'] == 'disconnected_clusters':
            cluster1_topics = self.get_cluster_topics(gap['cluster1'])
            cluster2_topics = self.get_cluster_topics(gap['cluster2'])
            
            topic1 = cluster1_topics[0] if cluster1_topics else "cluster 1"
            topic2 = cluster2_topics[0] if cluster2_topics else "cluster 2"
            
            return [
                f"How do {topic1} concepts relate to {topic2} concepts?",
                f"What patterns connect {topic1} and {topic2}?",
                f"Are there shared principles between {topic1} and {topic2}?"
            ]
        
        elif gap['type'] == 'bridge_concept':
            return [
                f"How does '{gap['description']}' connect different parts of the architecture?",
                f"What makes '{gap['description']}' a central architectural pattern?",
                f"What would break if we changed '{gap['description']}'?"
            ]
        
        elif gap['type'] == 'isolated_node':
            return [
                f"How does '{gap['description']}' fit into the overall architecture?",
                f"What other decisions relate to '{gap['description']}'?",
                f"Should '{gap['description']}' be connected to other concepts?"
            ]
        
        return []
    
    def get_cluster_topics(self, cluster_nodes: List[str]) -> List[str]:
        """Extract main topics from cluster nodes."""
        all_keywords = []
        for node_id in cluster_nodes[:5]:
            if node_id in self.graph.nodes:
                keywords = self.graph.nodes[node_id].get('keywords', [])
                all_keywords.extend(keywords)
        
        # Count frequency
        top_keywords = Counter(all_keywords).most_common(3)
        return [kw for kw, count in top_keywords]
    
    def run_comprehensive_analysis(self):
        """
        Execute full gap analysis pipeline.
        """
        print("="*60)
        print("COMPREHENSIVE NETWORKX GAP ANALYSIS")
        print("="*60)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Build graph
        self.build_graph_from_knowledge_base()
        
        if self.graph.number_of_nodes() == 0:
            print("\n⚠️  No nodes in graph. Please run ingestion first.")
            return
        
        # Run analyses
        communities = self.detect_communities()
        cluster_gaps = self.find_disconnected_clusters(communities) if communities else []
        bridge_concepts = self.find_bridge_concepts()
        isolated_nodes = self.find_isolated_nodes()
        
        # Combine all gaps
        all_gaps = cluster_gaps + bridge_concepts + isolated_nodes
        
        # Generate report
        print("\n" + "="*60)
        print("KNOWLEDGE GAP REPORT")
        print("="*60)
        
        print(f"\n📊 Graph Statistics:")
        print(f"   Nodes: {self.graph.number_of_nodes()}")
        print(f"   Edges: {self.graph.number_of_edges()}")
        print(f"   Communities: {len(communities)}")
        
        if self.graph.number_of_nodes() > 1:
            try:
                avg_clustering = nx.average_clustering(self.graph)
                print(f"   Average clustering: {avg_clustering:.3f}")
            except:
                print(f"   Average clustering: N/A")
        
        print(f"\n🔍 Gaps Detected: {len(all_gaps)}")
        print(f"   Disconnected clusters: {len([g for g in all_gaps if g['type'] == 'disconnected_clusters'])}")
        print(f"   Weak connections: {len([g for g in all_gaps if g['type'] == 'weak_connection'])}")
        print(f"   Bridge concepts: {len([g for g in all_gaps if g['type'] == 'bridge_concept'])}")
        print(f"   Isolated nodes: {len([g for g in all_gaps if g['type'] == 'isolated_node'])}")
        
        # Top 10 gaps
        print(f"\n🎯 Top 10 Critical Gaps:")
        high_severity = [g for g in all_gaps if g.get('severity') == 'HIGH'][:10]
        
        for i, gap in enumerate(high_severity):
            print(f"\n{i+1}. {gap['type'].replace('_', ' ').title()}")
            if 'description' in gap:
                print(f"   {gap['description']}")
            elif 'cluster1_size' in gap:
                print(f"   Cluster 1 size: {gap['cluster1_size']}, Cluster 2 size: {gap['cluster2_size']}")
            
            queries = self.generate_exploration_queries(gap)
            if queries:
                print(f"   Exploration questions:")
                for q in queries[:2]:
                    print(f"      - {q}")
        
        # Save report
        report_path = Path(__file__).parent.parent / "reports" / f"gap_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(exist_ok=True)
        
        report_data = {
            'graph_stats': {
                'nodes': self.graph.number_of_nodes(),
                'edges': self.graph.number_of_edges(),
                'communities': len(communities),
                'avg_clustering': nx.average_clustering(self.graph) if self.graph.number_of_nodes() > 1 else 0
            },
            'gaps': all_gaps,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n💾 Report saved: {report_path}")
        print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    """Main entry point for gap analysis."""
    analyzer = ComprehensiveGapAnalyzer()
    analyzer.run_comprehensive_analysis()


if __name__ == "__main__":
    main()
