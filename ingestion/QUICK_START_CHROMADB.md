# Quick Start: ChromaDB Extractor

5-minute guide to extract Agent Genesis conversations into FalkorDB.

## Prerequisites Check (30 seconds)

```bash
# 1. Verify ChromaDB has data
cd /home/platano/project/agent-genesis
source venv/bin/activate
python3 -c "import chromadb; c=chromadb.PersistentClient(path='knowledge_db'); print(f'Messages: {c.get_collection(\"beta_claude_desktop\").count():,}')"

# Expected: Messages: 13,280

# 2. Verify FalkorDB is running
redis-cli PING
# Expected: PONG

# 3. Install dependencies (if needed)
pip install chromadb falkordb pydantic
```

## Run Extraction (3-5 minutes)

```bash
cd /home/platano/project/faulkner-db/ingestion

# Run the extractor
python3 agent_genesis_chromadb_extractor.py

# Watch progress in real-time
tail -f chromadb_extraction.log
```

## Expected Output

```
================================================================================
AGENT GENESIS CHROMADB EXTRACTOR
================================================================================
Connecting to ChromaDB...
✓ Connected to 'beta_claude_desktop' with 13,280 documents
Stage 1: Extracting messages from ChromaDB...
✓ Extraction complete: 12,000+ conversations
Stage 2: Analyzing conversations...
Progress: 100/12,000 | Nodes: 45 | Decisions: 20 | Patterns: 15 | Failures: 10
...
================================================================================
EXTRACTION COMPLETE
================================================================================
Total messages:          13,280
Conversations processed: 12,000
Decisions extracted:     2,400
Patterns extracted:      1,800
Failures extracted:      1,200
Total nodes created:     5,400
================================================================================
```

## Verify Results

```bash
# Count nodes in FalkorDB
redis-cli GRAPH.QUERY knowledge_graph "MATCH (n) RETURN labels(n)[0] as type, count(*) as count ORDER BY type"

# Expected output:
# Decision: ~2,400
# Pattern: ~1,800
# Failure: ~1,200
```

## Troubleshooting

### ChromaDB Error
```bash
# Issue: Collection not found
# Fix: Check collection name
python3 agent_genesis_chromadb_extractor.py --collection beta_claude_desktop
```

### FalkorDB Error
```bash
# Issue: Connection refused
# Fix: Start FalkorDB
docker start falkordb
# OR
redis-server --loadmodule /path/to/libgraphmodule.so
```

### No Nodes Created
```bash
# Run tests first
python3 test_chromadb_extractor.py

# Check if patterns match your data
# The script looks for:
# - "decided", "chose", "selected" (decisions)
# - "pattern", "always", "best practice" (patterns)
# - "failed", "error", "lesson" (failures)
```

## Custom Execution

```bash
# Smaller batches (slower but safer)
python3 agent_genesis_chromadb_extractor.py --batch-size 500

# Different collection
python3 agent_genesis_chromadb_extractor.py --collection alpha_claude_code

# Remote FalkorDB
python3 agent_genesis_chromadb_extractor.py \
  --falkordb-host 192.168.1.100 \
  --falkordb-port 6379
```

## What Happens

1. **Connects** to ChromaDB (`/home/platano/project/agent-genesis/knowledge_db`)
2. **Extracts** 13,280 messages in batches of 1,000
3. **Groups** messages by conversation_id (~12,000 conversations)
4. **Analyzes** each conversation for knowledge patterns using regex
5. **Creates** FalkorDB nodes (Decision, Pattern, Failure)
6. **Logs** progress every 100 conversations
7. **Reports** final statistics

## Time Estimates

- ChromaDB extraction: ~5 seconds
- Conversation grouping: ~2 seconds
- Knowledge analysis: ~2-3 minutes (100/sec)
- FalkorDB insertion: ~2-3 minutes (50 nodes/sec)
- **Total**: 5-10 minutes

## Next Steps

After extraction completes:

```bash
# 1. Query the knowledge graph
redis-cli GRAPH.QUERY knowledge_graph "MATCH (d:Decision) RETURN d.description LIMIT 5"

# 2. Find patterns by project
redis-cli GRAPH.QUERY knowledge_graph "MATCH (p:Pattern {project: 'faulkner-db'}) RETURN p.name"

# 3. Review failures
redis-cli GRAPH.QUERY knowledge_graph "MATCH (f:Failure) RETURN f.attempt, f.lesson_learned LIMIT 10"
```

## Files Created

- `chromadb_extraction.log` - Detailed execution log
- Nodes in FalkorDB `knowledge_graph` - Structured knowledge

## Get Help

```bash
# Show all options
python3 agent_genesis_chromadb_extractor.py --help

# Run tests
python3 test_chromadb_extractor.py

# Read full docs
cat CHROMADB_EXTRACTOR_README.md
```
