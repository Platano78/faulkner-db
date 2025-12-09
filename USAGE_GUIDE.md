# Faulkner DB Usage Guide

## Quick Reference

### Via Claude Code (Natural Language)
```
# Search for decisions
"Use faulkner-db to query: knowledge graph architecture decisions"

# Find related concepts
"Use faulkner-db find_related on decision D-abc123"

# Detect knowledge gaps
"Use faulkner-db detect_gaps to analyze the graph structure"

# View timeline
"Use faulkner-db get_timeline for 'MCP architecture' from 2025-01-01 to 2025-12-31"

# Add new decision
"Use faulkner-db add_decision: We chose Redis for caching because..."
```

### Common Query Patterns

**1. Finding Architectural Decisions**
```
Query: "Why did we choose FalkorDB?"
Tool: query_decisions(query="FalkorDB choice rationale")
```

**2. Exploring Related Concepts**
```
Query: "What other decisions relate to temporal graphs?"
Tool: query_decisions(query="temporal graph") → find_related(node_id=top_result)
```

**3. Discovering Knowledge Gaps**
```
Query: "What areas of our architecture are poorly connected?"
Tool: detect_gaps() → review disconnected_clusters
```

**4. Tracking Evolution**
```
Query: "How has our MCP architecture evolved?"
Tool: get_timeline(topic="MCP architecture", start_date="2025-01-01")
```

**5. Adding New Knowledge**
```
Query: "Document the Redis caching decision"
Tool: add_decision(description="...", rationale="...", alternatives=[...])
```

## Best Practices

### When to Add Decisions
- After making significant architectural choices
- When documenting "why not X" alternatives
- During architecture review sessions
- After resolving technical debates

### When to Add Patterns
- After implementing a reusable solution
- When establishing a new coding standard
- After discovering an effective workflow
- When documenting best practices

### When to Add Failures
- After trying an approach that didn't work
- When abandoning a tool/framework
- After discovering performance issues
- When documenting lessons learned

### Maintaining Graph Quality
1. **Link Related Decisions** - Always use related_to field
2. **Run Incremental Extraction** - After bulk imports
3. **Review Gap Analysis** - Monthly check for isolated clusters
4. **Update Stale Information** - Archive outdated decisions

## Maintenance Schedule

### Daily (Automated)
- Incremental sync from Agent Genesis
- Relationship extraction for new nodes

### Weekly (Manual)
- Review gap analysis report
- Connect high-priority isolated nodes
- Add patterns from recent implementations

### Monthly (Manual)
- Run full gap analysis
- Review bridge concepts (architectural cornerstones)
- Archive deprecated decisions
- Export backup of knowledge graph

## Troubleshooting

### Query Returns No Results
```bash
# Check graph size
./venv/bin/python3 scripts/graph_statistics.py

# Verify MCP server
./venv/bin/python3 -c "from mcp_server.mcp_tools import query_decisions; import asyncio; print(asyncio.run(query_decisions('test')))"
```

### Relationships Not Appearing
```bash
# Check extraction state
cat reports/extraction_state.json

# Re-run extraction
./venv/bin/python3 ingestion/relationship_extractor.py --full
```

### MKG Not Available
```bash
# Check MKG health
curl http://localhost:8000/health

# Extraction still works without MKG (falls back to semantic similarity only)
./venv/bin/python3 ingestion/relationship_extractor.py --no-llm
```

## Current System Status

**Validated Components:**
- ✅ Docker services (FalkorDB + PostgreSQL)
- ✅ Virtual environment with all dependencies
- ✅ MCP server responsiveness
- ✅ 4 out of 7 MCP tools fully functional
- ✅ Extraction state tracking

**Known Limitations:**
- ⚠️ Graph traversal (find_related) needs adapter updates
- ⚠️ Knowledge graph currently small (1 node) - needs data import
- ⚠️ MKG local LLM not running (semantic similarity only)

**Next Steps:**
1. Import historical conversation data
2. Run relationship extraction on imported data
3. Fix find_related adapter method
4. Start MKG for enhanced relationship detection
