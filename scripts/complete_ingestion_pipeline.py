#!/usr/bin/env python3
"""
Complete Faulkner DB ingestion pipeline orchestrator.
Coordinates multi-project markdown scan + Agent Genesis mining.
"""

import asyncio
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class IngestionPipeline:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.log_file = self.project_root / "logs" / f"ingestion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.log_file.parent.mkdir(exist_ok=True)
        
        self.stats = {
            "start_time": datetime.now().isoformat(),
            "phases_completed": [],
            "nodes_before": 0,
            "nodes_after": 0,
            "edges_before": 0,
            "edges_after": 0,
            "errors": []
        }
    
    def log(self, message: str):
        """Log to both console and file"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted = f"[{timestamp}] {message}"
        print(formatted)
        
        with open(self.log_file, 'a') as f:
            f.write(formatted + '\n')
    
    async def get_graph_size(self) -> Dict[str, int]:
        """Get current node and edge counts"""
        from core.graphiti_client import GraphitiClient
        
        client = GraphitiClient()
        
        try:
            # Count nodes
            node_query = "MATCH (n) RETURN count(n) as count"
            node_result = client.db.graph.query(node_query)
            nodes = node_result.result_set[0][0] if node_result.result_set else 0
            
            # Count edges
            edge_query = "MATCH ()-[r]->() RETURN count(r) as count"
            edge_result = client.db.graph.query(edge_query)
            edges = edge_result.result_set[0][0] if edge_result.result_set else 0
            
            return {"nodes": nodes, "edges": edges}
        except Exception as e:
            self.log(f"Warning: Could not query graph size: {e}")
            return {"nodes": 0, "edges": 0}
    
    def run_command(self, cmd: list, phase_name: str) -> bool:
        """Execute shell command with logging"""
        self.log(f"\n{'='*60}")
        self.log(f"PHASE: {phase_name}")
        self.log(f"{'='*60}")
        self.log(f"Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Log output
            if result.stdout:
                self.log("\n--- STDOUT ---")
                self.log(result.stdout)
            
            if result.stderr:
                self.log("\n--- STDERR ---")
                self.log(result.stderr)
            
            self.log(f"✅ {phase_name} completed successfully")
            self.stats["phases_completed"].append(phase_name)
            return True
            
        except subprocess.CalledProcessError as e:
            self.log(f"❌ {phase_name} FAILED")
            self.log(f"Exit code: {e.returncode}")
            self.log(f"Error: {e.stderr}")
            
            self.stats["errors"].append({
                "phase": phase_name,
                "error": str(e),
                "stderr": e.stderr
            })
            
            return False
    
    async def phase_1_assessment(self) -> bool:
        """Run pre-ingestion assessment"""
        self.log("\n" + "="*60)
        self.log("PHASE 1: PRE-INGESTION ASSESSMENT")
        self.log("="*60)
        
        # Get baseline metrics
        baseline = await self.get_graph_size()
        self.stats["nodes_before"] = baseline["nodes"]
        self.stats["edges_before"] = baseline["edges"]
        
        self.log(f"Baseline: {baseline['nodes']} nodes, {baseline['edges']} edges")
        
        # Run assessment script
        return self.run_command(
            ["python3", "scripts/assess_database_state.py"],
            "Pre-Ingestion Assessment"
        )
    
    def phase_2_multi_project_scan(self) -> bool:
        """Run multi-project markdown scanner"""
        self.log("\n" + "="*60)
        self.log("PHASE 2: MULTI-PROJECT MARKDOWN SCAN")
        self.log("="*60)
        
        # First, dry run to see what will be scanned
        self.log("\nRunning dry-run to preview scan scope...")
        self.run_command(
            ["python3", "scripts/run_multi_scan.py", "--dry-run"],
            "Multi-Project Scan (Dry Run)"
        )
        
        # Execute full scan
        self.log("\nExecuting full multi-project scan...")
        return self.run_command(
            ["python3", "scripts/run_multi_scan.py"],
            "Multi-Project Markdown Scan"
        )
    
    def phase_3_agent_genesis(self) -> bool:
        """Run Agent Genesis conversation mining"""
        self.log("\n" + "="*60)
        self.log("PHASE 3: AGENT GENESIS CONVERSATION MINING")
        self.log("="*60)
        
        # Check if we have an agent genesis full conversation script
        ag_script = self.project_root / "ingestion" / "batch_import_agent_genesis.py"
        
        if not ag_script.exists():
            self.log(f"⚠️  Agent Genesis script not found: {ag_script}")
            self.log("Skipping Agent Genesis phase")
            return True
        
        # Run Agent Genesis importer
        return self.run_command(
            ["python3", "ingestion/batch_import_agent_genesis.py"],
            "Agent Genesis Conversation Mining"
        )
    
    def phase_4_relationship_extraction(self) -> bool:
        """Extract relationships between newly added nodes"""
        self.log("\n" + "="*60)
        self.log("PHASE 4: RELATIONSHIP EXTRACTION")
        self.log("="*60)
        
        # Check if relationship extractor exists
        rel_script = self.project_root / "ingestion" / "relationship_extractor.py"
        
        if not rel_script.exists():
            self.log(f"⚠️  Relationship extractor not found: {rel_script}")
            self.log("Skipping relationship extraction phase")
            return True
        
        # Run relationship extraction
        return self.run_command(
            ["python3", "ingestion/relationship_extractor.py"],
            "Relationship Extraction"
        )
    
    async def phase_5_final_analysis(self) -> bool:
        """Generate final statistics and health report"""
        self.log("\n" + "="*60)
        self.log("PHASE 5: FINAL ANALYSIS")
        self.log("="*60)
        
        # Get final metrics
        final = await self.get_graph_size()
        self.stats["nodes_after"] = final["nodes"]
        self.stats["edges_after"] = final["edges"]
        
        # Calculate deltas
        nodes_added = final["nodes"] - self.stats["nodes_before"]
        edges_added = final["edges"] - self.stats["edges_before"]
        
        self.log(f"\n📊 INGESTION RESULTS:")
        self.log(f"  Nodes: {self.stats['nodes_before']} → {self.stats['nodes_after']} (+{nodes_added})")
        self.log(f"  Edges: {self.stats['edges_before']} → {self.stats['edges_after']} (+{edges_added})")
        
        # Run gap detection
        try:
            from mcp_server.networkx_analyzer import NetworkXAnalyzer
            from core.graphiti_client import GraphitiClient
            
            analyzer = NetworkXAnalyzer(GraphitiClient())
            gaps = await analyzer.detect_gaps()
            
            self.log(f"\n📊 STRUCTURAL HEALTH:")
            self.log(f"  Isolated nodes: {gaps['isolated_count']} ({gaps['isolated_count']/gaps['total_nodes']*100:.1f}%)")
            self.log(f"  Disconnected clusters: {gaps['disconnected_clusters']}")
            self.log(f"  Connectivity: {(gaps['total_nodes']-gaps['isolated_count'])/gaps['total_nodes']*100:.1f}%")
            self.log(f"  Bridge nodes: {len(gaps.get('bridge_nodes', []))}")
            
            self.stats["final_gaps"] = gaps
        except Exception as e:
            self.log(f"⚠️  Gap detection failed: {e}")
        
        return True
    
    async def run_pipeline(self, skip_phases: Optional[list] = None):
        """Execute complete ingestion pipeline"""
        skip_phases = skip_phases or []
        
        self.log("="*60)
        self.log("FAULKNER DB COMPLETE INGESTION PIPELINE")
        self.log("="*60)
        self.log(f"Start time: {self.stats['start_time']}")
        self.log(f"Log file: {self.log_file}")
        
        # Phase 1: Assessment
        if "assessment" not in skip_phases:
            if not await self.phase_1_assessment():
                self.log("\n⚠️  Assessment failed, continuing anyway...")
        
        # Phase 2: Multi-project markdown
        if "markdown" not in skip_phases:
            if not self.phase_2_multi_project_scan():
                self.log("\n❌ Markdown scan failed, aborting pipeline")
                return False
        
        # Phase 3: Agent Genesis
        if "agent_genesis" not in skip_phases:
            if not self.phase_3_agent_genesis():
                self.log("\n⚠️  Agent Genesis mining failed, continuing to relationships...")
        
        # Phase 4: Relationships
        if "relationships" not in skip_phases:
            if not self.phase_4_relationship_extraction():
                self.log("\n⚠️  Relationship extraction failed, continuing to analysis...")
        
        # Phase 5: Final analysis
        await self.phase_5_final_analysis()
        
        # Save stats
        self.stats["end_time"] = datetime.now().isoformat()
        stats_file = self.project_root / "logs" / "ingestion_stats.json"
        
        with open(stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
        
        self.log(f"\n📄 Statistics saved: {stats_file}")
        
        # Summary
        self.log("\n" + "="*60)
        self.log("PIPELINE COMPLETE")
        self.log("="*60)
        self.log(f"Phases completed: {len(self.stats['phases_completed'])}")
        self.log(f"Errors encountered: {len(self.stats['errors'])}")
        self.log(f"Nodes added: {self.stats['nodes_after'] - self.stats['nodes_before']}")
        self.log(f"Edges added: {self.stats['edges_after'] - self.stats['edges_before']}")
        
        if self.stats["errors"]:
            self.log("\n⚠️  Errors occurred during pipeline:")
            for error in self.stats["errors"]:
                self.log(f"  - {error['phase']}: {error['error']}")
        
        return len(self.stats["errors"]) == 0


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Complete Faulkner DB ingestion pipeline"
    )
    parser.add_argument(
        "--skip",
        nargs='+',
        choices=["assessment", "markdown", "agent_genesis", "relationships"],
        help="Skip specific phases"
    )
    
    args = parser.parse_args()
    
    pipeline = IngestionPipeline()
    success = await pipeline.run_pipeline(skip_phases=args.skip)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
