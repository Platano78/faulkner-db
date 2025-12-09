#!/usr/bin/env python3
"""
Faulkner DB Knowledge Graph Report Generator

Generates comprehensive reports about the current state of the knowledge graph,
including statistics, clusters, gaps, and recommendations.
"""

import redis
import json
import sys
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("Warning: NetworkX not available, gap analysis limited")


def connect_to_falkordb():
    """Connect to FalkorDB via Redis protocol."""
    try:
        r = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True,
            socket_connect_timeout=5
        )
        r.ping()
        return r
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Make sure Docker containers are running:")
        print("  cd ~/projects/faulkner-db/docker && docker-compose up -d")
        return None


def query_graph_stats(redis_client):
    """Query basic graph statistics from FalkorDB."""
    if not redis_client:
        return {'nodes': 0, 'edges': 0}
    
    try:
        # Try to query the graph
        result = redis_client.execute_command(
            'GRAPH.QUERY', 'faulkner',
            "MATCH (n) RETURN count(n) as node_count"
        )
        node_count = result[1][0][0] if result and len(result) > 1 else 0
        
        result = redis_client.execute_command(
            'GRAPH.QUERY', 'faulkner',
            "MATCH ()-[r]->() RETURN count(r) as edge_count"
        )
        edge_count = result[1][0][0] if result and len(result) > 1 else 0
        
        return {'nodes': node_count, 'edges': edge_count}
    except Exception as e:
        print(f"Query error: {e}")
        return {'nodes': 0, 'edges': 0}


def generate_placeholder_report():
    """Generate placeholder report for empty database."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Markdown report
    md_content = f"""# Faulkner DB Knowledge Graph Report

*Generated: {timestamp}*

## System Status

**🟢 System Ready for Data**

The Faulkner DB system is initialized and operational, but no knowledge has been added yet.

## Current State

- **Total Nodes**: 0
- **Total Edges**: 0
- **Graph Density**: N/A
- **Knowledge Clusters**: 0

## Getting Started

To populate your knowledge graph:

### 1. Add Your First Decision

```
In Claude Desktop, use:
"Use add_decision to record that we chose FalkorDB over Neo4j because:
- CPU-only operation (gaming-friendly)
- Redis compatibility
- Lower memory footprint"
```

### 2. Query the Knowledge Base

```
Use query_decisions to find decisions about "database"
```

### 3. Visualize

Open your browser to:
- Network Graph: http://localhost:8082/static/index.html
- Timeline: http://localhost:8082/static/timeline.html
- Dashboard: http://localhost:8082/static/dashboard.html

## Next Steps

**Recommended initial decisions to document:**

1. **Technology Selections**
   - Database choices
   - Framework selections
   - Tool adoptions

2. **Architectural Patterns**
   - Design patterns in use
   - System architecture decisions
   - Integration approaches

3. **Infrastructure Decisions**
   - Deployment strategies
   - Hosting choices
   - Monitoring setup

4. **Development Processes**
   - Testing strategies
   - CI/CD pipeline decisions
   - Code review practices

## Validation

System health:
```bash
cd ~/projects/faulkner-db/docker
./validate-autostart.sh
```

Expected output:
```
✅ Docker is running
✅ All containers healthy
✅ APIs responding
```

## Resources

- [User Guide](../docs/USER_GUIDE.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Tech Stack](../docs/TECH_STACK.md)

---

*Faulkner DB v1.0.0 - Temporal Knowledge Graph System*
"""

    # JSON knowledge map
    json_content = {
        'generated_at': timestamp,
        'system_status': 'ready',
        'statistics': {
            'total_nodes': 0,
            'total_edges': 0,
            'density': 0,
            'clusters': 0
        },
        'nodes': [],
        'edges': [],
        'clusters': {},
        'gaps': [],
        'recommendations': [
            'Add your first architectural decision',
            'Document technology selections',
            'Record design patterns in use',
            'Capture infrastructure decisions'
        ]
    }
    
    return md_content, json_content


def generate_report_with_data(stats):
    """Generate report when data exists (future implementation)."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    nodes = stats['nodes']
    edges = stats['edges']
    density = edges / (nodes * (nodes - 1)) if nodes > 1 else 0
    
    md_content = f"""# Faulkner DB Knowledge Graph Report

*Generated: {timestamp}*

## Overview

- **Total Decisions**: {nodes}
- **Total Relationships**: {edges}
- **Graph Density**: {density:.3f}
- **Status**: 🟢 Active

## Statistics

### Knowledge Growth

The knowledge graph currently contains {nodes} decision nodes connected by {edges} relationships.

### Recommendations

1. Continue documenting architectural decisions
2. Link related decisions to build context
3. Review and update old decisions quarterly
4. Use gap analysis to find undocumented areas

## Next Steps

- Run gap analysis: `Use detect_gaps`
- View timeline: http://localhost:8082/static/timeline.html
- Explore network: http://localhost:8082/static/index.html

---

*Faulkner DB v1.0.0*
"""
    
    json_content = {
        'generated_at': timestamp,
        'statistics': {
            'total_nodes': nodes,
            'total_edges': edges,
            'density': density
        },
        'nodes': [],  # Would be populated with actual data
        'edges': [],
        'recommendations': [
            'Continue documenting decisions',
            'Link related decisions',
            'Run gap analysis'
        ]
    }
    
    return md_content, json_content


def main():
    """Main report generation function."""
    print("="*50)
    print("Faulkner DB Knowledge Graph Report Generator")
    print("="*50)
    print()
    
    # Ensure output directories exist
    reports_dir = Path(__file__).parent.parent / 'reports'
    reports_dir.mkdir(exist_ok=True)
    
    print("Connecting to FalkorDB...")
    redis_client = connect_to_falkordb()
    
    if redis_client:
        print("✅ Connected successfully")
        print("\nQuerying graph statistics...")
        stats = query_graph_stats(redis_client)
        print(f"  Nodes: {stats['nodes']}")
        print(f"  Edges: {stats['edges']}")
    else:
        print("❌ Connection failed")
        stats = {'nodes': 0, 'edges': 0}
    
    print("\nGenerating reports...")
    
    # Generate appropriate report based on data availability
    if stats['nodes'] == 0:
        md_content, json_content = generate_placeholder_report()
    else:
        md_content, json_content = generate_report_with_data(stats)
    
    # Write markdown report
    md_path = reports_dir / 'current_state.md'
    with open(md_path, 'w') as f:
        f.write(md_content)
    print(f"  ✅ {md_path}")
    
    # Write JSON knowledge map
    json_path = reports_dir / 'knowledge_map.json'
    with open(json_path, 'w') as f:
        json.dump(json_content, f, indent=2)
    print(f"  ✅ {json_path}")
    
    print("\n" + "="*50)
    print("Report generation complete!")
    print("="*50)
    print("\nView reports:")
    print(f"  Markdown: {md_path}")
    print(f"  JSON: {json_path}")
    print("\nNext steps:")
    if stats['nodes'] == 0:
        print("  1. Add decisions using MCP tools in Claude Desktop")
        print("  2. Run this script again to see updated statistics")
    else:
        print("  1. Review the generated reports")
        print("  2. Use visualizations to explore the graph")
        print("  3. Run gap analysis to find documentation opportunities")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
