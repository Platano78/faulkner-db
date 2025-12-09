#!/usr/bin/env python3
"""
Analyze current Faulkner DB state before full ingestion.
Identifies what's already indexed and what's missing.
"""

import asyncio
import sqlite3
import sys
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.graphiti_client import GraphitiClient
from mcp_server.networkx_analyzer import NetworkXAnalyzer


class DatabaseStateAssessor:
    def __init__(self):
        self.graphiti = GraphitiClient()
        self.analyzer = NetworkXAnalyzer(self.graphiti)
        self.tracker_db = Path(__file__).parent.parent / "data" / "scanner_tracking.db"
        
    def get_all_nodes(self) -> List[Dict]:
        """Fetch all nodes from knowledge graph"""
        try:
            # Query all nodes using FalkorDB adapter
            query = "MATCH (n) RETURN n.id as id, labels(n) as labels, n.name as name, n.source_files as source_files, n.created_at as created_at LIMIT 10000"
            result = self.graphiti.db.graph.query(query)
            
            nodes = []
            for record in result.result_set:
                node_id = record[0]
                labels = record[1]
                name = record[2] if len(record) > 2 else None
                source_files = record[3] if len(record) > 3 else None
                created_at = record[4] if len(record) > 4 else None
                
                nodes.append({
                    'id': node_id,
                    'type': labels[0] if labels else 'unknown',
                    'name': name,
                    'source_files': json.loads(source_files) if source_files and isinstance(source_files, str) else (source_files or []),
                    'created_at': created_at
                })
            
            return nodes
        except Exception as e:
            print(f"Error querying nodes: {e}")
            return []
    
    def analyze_source_distribution(self, nodes: List[Dict]) -> Dict:
        """Analyze which sources contributed nodes"""
        
        # Count nodes by source file
        source_counts = Counter()
        nodes_without_sources = 0
        project_distribution = defaultdict(list)
        
        for node in nodes:
            source_files = node.get('source_files', [])
            
            if not source_files or source_files == ['unknown'] or source_files == []:
                nodes_without_sources += 1
                continue
            
            for source_file in source_files:
                if not source_file or source_file == 'unknown':
                    continue
                    
                source_counts[source_file] += 1
                
                # Detect project from path
                if '/project/' in str(source_file):
                    try:
                        project = str(source_file).split('/project/')[1].split('/')[0]
                        project_distribution[project].append(node['id'])
                    except:
                        pass
                elif '/ai-workspace/' in str(source_file):
                    try:
                        project = str(source_file).split('/projects/')[1].split('/')[0]
                        project_distribution[f"ai-workspace/{project}"].append(node['id'])
                    except:
                        pass
        
        return {
            "total_sources": len(source_counts),
            "nodes_without_sources": nodes_without_sources,
            "top_10_sources": source_counts.most_common(10),
            "project_distribution": {
                proj: len(node_ids) 
                for proj, node_ids in project_distribution.items()
            },
            "unique_projects": len(project_distribution)
        }
    
    def check_file_tracker(self) -> Dict:
        """Check what's been scanned in file tracker DB"""
        
        if not self.tracker_db.exists():
            return {
                "tracker_exists": False,
                "files_tracked": 0,
                "projects_scanned": {},
                "scanned_projects_count": 0
            }
        
        try:
            conn = sqlite3.connect(self.tracker_db)
            cursor = conn.cursor()
            
            # Get all tracked files
            cursor.execute("SELECT file_path, last_scanned FROM scanned_files")
            tracked_files = cursor.fetchall()
            
            # Analyze project distribution
            project_counts = Counter()
            for file_path, _ in tracked_files:
                if '/project/' in file_path:
                    try:
                        project = file_path.split('/project/')[1].split('/')[0]
                        project_counts[project] += 1
                    except:
                        pass
                elif '/ai-workspace/' in file_path:
                    try:
                        project = file_path.split('/projects/')[1].split('/')[0]
                        project_counts[f"ai-workspace/{project}"] += 1
                    except:
                        pass
            
            conn.close()
            
            return {
                "tracker_exists": True,
                "files_tracked": len(tracked_files),
                "projects_scanned": dict(project_counts),
                "scanned_projects_count": len(project_counts)
            }
        except Exception as e:
            print(f"Error checking tracker: {e}")
            return {
                "tracker_exists": True,
                "files_tracked": 0,
                "projects_scanned": {},
                "scanned_projects_count": 0,
                "error": str(e)
            }
    
    def check_agent_genesis_coverage(self, nodes: List[Dict]) -> Dict:
        """Check how many Agent Genesis conversations are indexed"""
        
        ag_nodes = 0
        for node in nodes:
            source_files = node.get('source_files', [])
            if source_files:
                for source in source_files:
                    if 'agent-genesis' in str(source).lower() or 'conversation' in str(source).lower():
                        ag_nodes += 1
                        break
        
        return {
            "agent_genesis_nodes": ag_nodes,
            "estimated_total_conversations": 17538,
            "estimated_coverage_percent": (ag_nodes / 17538 * 100) if ag_nodes > 0 else 0
        }
    
    def get_node_type_distribution(self, nodes: List[Dict]) -> Dict:
        """Analyze node types"""
        
        type_counts = Counter(node.get('type', 'unknown') for node in nodes)
        
        return {
            "decisions": type_counts.get('Decision', 0),
            "patterns": type_counts.get('Pattern', 0),
            "failures": type_counts.get('Failure', 0),
            "unknown": type_counts.get('unknown', 0),
            "other": sum(v for k, v in type_counts.items() if k not in ['Decision', 'Pattern', 'Failure', 'unknown']),
            "total": len(nodes),
            "type_breakdown": dict(type_counts)
        }
    
    async def run_assessment(self) -> Dict:
        """Run complete database state assessment"""
        
        print("=" * 60)
        print("FAULKNER DB STATE ASSESSMENT")
        print("=" * 60)
        
        # Fetch all nodes
        print("\n[1/6] Fetching all nodes from graph...")
        nodes = self.get_all_nodes()
        print(f"  ✅ Found {len(nodes)} nodes")
        
        # Analyze node types
        print("\n[2/6] Analyzing node type distribution...")
        type_dist = self.get_node_type_distribution(nodes)
        print(f"  ✅ Decisions: {type_dist['decisions']}")
        print(f"  ✅ Patterns: {type_dist['patterns']}")
        print(f"  ✅ Failures: {type_dist['failures']}")
        print(f"  ✅ Unknown: {type_dist['unknown']}")
        print(f"  ✅ Other: {type_dist['other']}")
        
        # Analyze source distribution
        print("\n[3/6] Analyzing source file distribution...")
        source_dist = self.analyze_source_distribution(nodes)
        print(f"  ✅ Total unique sources: {source_dist['total_sources']}")
        print(f"  ✅ Nodes without sources: {source_dist['nodes_without_sources']}")
        print(f"  ✅ Unique projects: {source_dist['unique_projects']}")
        if source_dist['top_10_sources']:
            print(f"\n  Top 5 contributing sources:")
            for source, count in source_dist['top_10_sources'][:5]:
                # Shorten path for readability
                short_source = str(source).split('/')[-3:] if '/' in str(source) else str(source)
                short_source = '/'.join(short_source) if isinstance(short_source, list) else short_source
                print(f"    - {short_source}: {count} nodes")
        
        # Check file tracker
        print("\n[4/6] Checking file tracker database...")
        tracker_info = self.check_file_tracker()
        print(f"  ✅ Tracker exists: {tracker_info['tracker_exists']}")
        print(f"  ✅ Files tracked: {tracker_info['files_tracked']}")
        print(f"  ✅ Projects scanned: {tracker_info['scanned_projects_count']}")
        if tracker_info['projects_scanned']:
            print(f"\n  Projects in tracker:")
            for proj, count in sorted(tracker_info['projects_scanned'].items()):
                print(f"    - {proj}: {count} files")
        
        # Check Agent Genesis coverage
        print("\n[5/6] Checking Agent Genesis conversation coverage...")
        ag_coverage = self.check_agent_genesis_coverage(nodes)
        print(f"  ✅ Agent Genesis nodes: {ag_coverage['agent_genesis_nodes']}")
        print(f"  ✅ Total conversations available: {ag_coverage['estimated_total_conversations']}")
        print(f"  ✅ Estimated coverage: {ag_coverage['estimated_coverage_percent']:.1f}%")
        
        # Run NetworkX gap detection
        print("\n[6/6] Running structural gap detection...")
        try:
            gaps = await self.analyzer.detect_gaps()
            print(f"  ✅ Isolated nodes: {gaps['isolated_count']}")
            print(f"  ✅ Disconnected clusters: {gaps['disconnected_clusters']}")
            connectivity_pct = ((gaps['total_nodes'] - gaps['isolated_count']) / gaps['total_nodes'] * 100) if gaps['total_nodes'] > 0 else 0
            print(f"  ✅ Connectivity: {connectivity_pct:.1f}%")
        except Exception as e:
            print(f"  ⚠️  Gap detection failed: {e}")
            gaps = {
                'isolated_count': 0,
                'disconnected_clusters': 0,
                'total_nodes': len(nodes),
                'total_edges': 0,
                'error': str(e)
            }
        
        # Compile full report
        report = {
            "timestamp": str(asyncio.get_event_loop().time()),
            "total_nodes": len(nodes),
            "node_types": type_dist,
            "source_distribution": source_dist,
            "file_tracker": tracker_info,
            "agent_genesis": ag_coverage,
            "structural_gaps": gaps
        }
        
        # Summary
        print("\n" + "=" * 60)
        print("ASSESSMENT SUMMARY")
        print("=" * 60)
        
        # Determine what needs ingestion
        missing_projects = []
        if source_dist['unique_projects'] < 5:  # Expecting 5+ projects
            missing_projects.append("Multi-project markdown scan incomplete")
        
        if ag_coverage['estimated_coverage_percent'] < 2:  # Should be 2-3% minimum
            missing_projects.append("Agent Genesis conversations not fully processed")
        
        if missing_projects:
            print("\n⚠️  MISSING DATA SOURCES:")
            for item in missing_projects:
                print(f"  - {item}")
            print("\n📋 RECOMMENDATION: Run full ingestion pipeline")
        else:
            print("\n✅ Database appears well-populated")
            print("   Consider incremental updates only")
        
        return report


async def main():
    assessor = DatabaseStateAssessor()
    report = await assessor.run_assessment()
    
    # Save report
    report_file = Path(__file__).parent.parent / "logs" / "pre_ingestion_assessment.json"
    report_file.parent.mkdir(exist_ok=True)
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Full report saved: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
