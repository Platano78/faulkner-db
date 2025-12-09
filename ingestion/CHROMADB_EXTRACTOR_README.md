# Agent Genesis ChromaDB Extractor

Complete extraction pipeline from Agent Genesis ChromaDB into FalkorDB knowledge graph.

## Overview

This script extracts 13,280+ conversations from Agent Genesis ChromaDB (`beta_claude_desktop` collection) and inserts them into FalkorDB as structured knowledge nodes (Decisions, Patterns, Failures).

## Features

### 1. ChromaDB Connection
- Connects to persistent ChromaDB at `/home/platano/project/agent-genesis/knowledge_db/`
- Accesses `beta_claude_desktop` collection (13,280 messages)
- Batch extraction with configurable batch sizes (default: 1000)

### 2. Message Extraction
- Fetches all messages with full metadata
- Groups messages by `conversation_id`
- Preserves metadata: project, git_branch, timestamp, role, cwd

### 3. Knowledge Analysis
Uses regex-based pattern matching to extract:

**Decisions:**
- "decided to", "chose", "selected", "went with"
- "decision was to", "architecture is to"
- Extracts description, rationale, context

**Patterns:**
- "pattern is", "approach is", "strategy for"
- "always", "consistently", "best practice"
- Extracts name, implementation, use cases

**Failures:**
- "failed", "error", "bug", "issue"
- "lesson learned", "don't", "avoid"
- Extracts attempt, reason failed, lesson learned

### 4. FalkorDB Insertion
- Creates properly typed nodes (Decision, Pattern, Failure)
- Preserves conversation_id for traceability
- Validates against Pydantic schemas
- Uses FalkorDBAdapter for safe Cypher queries

### 5. Progress Tracking
- Real-time statistics every 100 conversations
- Comprehensive logging to `chromadb_extraction.log`
- Counts for messages, conversations, nodes, errors

## Installation

### Prerequisites

```bash
# Install required packages
pip install chromadb falkordb pydantic

# Ensure FalkorDB is running
docker ps | grep falkordb
# OR
redis-cli PING  # If running standalone
```

### Verify ChromaDB Data

```bash
cd /home/platano/project/agent-genesis
source venv/bin/activate

python3 -c "
import chromadb
client = chromadb.PersistentClient(path='knowledge_db')
coll = client.get_collection('beta_claude_desktop')
print(f'Messages: {coll.count():,}')
"
```

Expected output: `Messages: 13,280`

## Usage

### Basic Execution

```bash
cd /home/platano/project/faulkner-db/ingestion

# Run with defaults
python3 agent_genesis_chromadb_extractor.py
```

### Advanced Options

```bash
# Custom batch size
python3 agent_genesis_chromadb_extractor.py --batch-size 500

# Custom collection
python3 agent_genesis_chromadb_extractor.py --collection alpha_claude_code

# Custom FalkorDB connection
python3 agent_genesis_chromadb_extractor.py \
  --falkordb-host localhost \
  --falkordb-port 6379 \
  --graph-name knowledge_graph

# All options combined
python3 agent_genesis_chromadb_extractor.py \
  --batch-size 1000 \
  --collection beta_claude_desktop \
  --falkordb-host localhost \
  --falkordb-port 6379 \
  --graph-name knowledge_graph
```

### Command Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--batch-size` | 1000 | ChromaDB fetch batch size |
| `--collection` | beta_claude_desktop | Collection name |
| `--falkordb-host` | localhost | FalkorDB host |
| `--falkordb-port` | 6379 | FalkorDB port |
| `--graph-name` | knowledge_graph | Graph name |

## Testing

### Run Validation Tests

```bash
cd /home/platano/project/faulkner-db/ingestion

# Run test suite
python3 test_chromadb_extractor.py
```

**Tests include:**
1. ChromaDB connection and data access
2. Knowledge extraction pattern matching
3. Full conversation analysis pipeline

**Expected output:**
```
TEST 1: ChromaDB Connection
✓ Connected successfully
✓ Total messages: 13,280
✓ Extracted 100 conversations from first 100 messages

TEST 2: Knowledge Extraction
Decisions extracted: 2
Patterns extracted: 1
Failures extracted: 1

TEST 3: Conversation Analysis
Conversation: [uuid]
  Messages: 5
  Decisions found: 3
  Patterns found: 2
  Failures found: 1

RESULTS: 3/3 tests passed
```

## Output

### Console Output

```
================================================================================
AGENT GENESIS CHROMADB EXTRACTOR
================================================================================
2025-11-29 01:00:00 - Connecting to ChromaDB at /home/platano/project/agent-genesis/knowledge_db
2025-11-29 01:00:01 - Connected to collection 'beta_claude_desktop' with 13,280 documents
2025-11-29 01:00:01 - Stage 1: Extracting messages from ChromaDB...
2025-11-29 01:00:05 - Progress: 5,000/13,280 messages processed, 4,500 conversations found
2025-11-29 01:00:10 - Extraction complete: 12,000 conversations from 13,280 messages
2025-11-29 01:00:10 - Stage 2: Analyzing 12,000 conversations...
2025-11-29 01:00:30 - Progress: 100/12,000 conversations | Nodes: 45 | Decisions: 20 | Patterns: 15 | Failures: 10
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
Errors encountered:      0
================================================================================
```

### Log File

Detailed logs written to `chromadb_extraction.log`:
- Timestamp for each operation
- Progress milestones
- Error details with stack traces
- Final statistics

## Data Flow

```
ChromaDB (13K messages)
         ↓
  Group by conversation_id (12K conversations)
         ↓
  Extract knowledge patterns (regex analysis)
         ↓
  Validate with Pydantic schemas
         ↓
  Insert to FalkorDB (Decision/Pattern/Failure nodes)
         ↓
  Statistics & Logging
```

## Schema Mapping

### ChromaDB Message → Analysis

```python
{
  'id': 'uuid',
  'content': 'message text',
  'role': 'human|assistant',
  'timestamp': 'ISO timestamp',
  'conversation_id': 'conversation uuid',
  'project': 'project name',
  'cwd': 'working directory',
  'git_branch': 'branch name'
}
```

### Analysis → FalkorDB Nodes

**Decision Node:**
```cypher
CREATE (n:Decision {
  id: 'uuid',
  type: 'Decision',
  description: 'decision text (max 1000 chars)',
  rationale: 'context (max 2000 chars)',
  alternatives: '[]',
  related_to: '[]',
  source_files: '["conversation:uuid"]',
  conversation_id: 'conversation uuid',
  project: 'project name',
  timestamp: 'ISO timestamp'
})
```

**Pattern Node:**
```cypher
CREATE (n:Pattern {
  id: 'uuid',
  type: 'Pattern',
  name: 'pattern name (max 100 chars)',
  implementation: 'pattern text (max 3000 chars)',
  context: 'context (max 1000 chars)',
  use_cases: '[]',
  source_files: '["conversation:uuid"]',
  conversation_id: 'conversation uuid',
  project: 'project name',
  timestamp: 'ISO timestamp'
})
```

**Failure Node:**
```cypher
CREATE (n:Failure {
  id: 'uuid',
  type: 'Failure',
  attempt: 'failure description (max 1000 chars)',
  reason_failed: 'context (max 2000 chars)',
  lesson_learned: 'lesson text (max 2000 chars)',
  alternative_solution: null,
  source_files: '["conversation:uuid"]',
  conversation_id: 'conversation uuid',
  project: 'project name',
  timestamp: 'ISO timestamp'
})
```

## Performance

### Expected Metrics
- **ChromaDB extraction**: ~2-5 seconds for 13K messages
- **Conversation grouping**: ~1-2 seconds for 12K conversations
- **Knowledge analysis**: ~100 conversations/second
- **FalkorDB insertion**: ~50 nodes/second
- **Total runtime**: ~5-10 minutes for full extraction

### Resource Usage
- **Memory**: ~200-500 MB
- **CPU**: Single-threaded (can be parallelized)
- **Network**: Local connections only (no external APIs)

## Error Handling

### Graceful Degradation
- Continues on individual conversation failures
- Logs errors without stopping extraction
- Final statistics include error counts

### Recovery
- Idempotent node creation (unique IDs)
- Can be re-run safely
- Skips invalid knowledge patterns

### Interrupt Handling
```bash
# Ctrl+C during execution
^C
Extraction interrupted by user
Progress: 5,432 conversations processed
```

## Troubleshooting

### ChromaDB Connection Failed

```bash
# Check ChromaDB exists
ls -la /home/platano/project/agent-genesis/knowledge_db/

# Verify collection
cd /home/platano/project/agent-genesis
source venv/bin/activate
python3 -c "import chromadb; client = chromadb.PersistentClient(path='knowledge_db'); print(client.list_collections())"
```

### FalkorDB Connection Failed

```bash
# Check FalkorDB running
redis-cli PING
# OR
docker ps | grep falkordb

# Test connection
redis-cli GRAPH.QUERY knowledge_graph "RETURN 1"
```

### No Knowledge Extracted

This is expected for some conversations. The script only creates nodes when patterns match:
- Decisions: "decided", "chose", etc.
- Patterns: "pattern", "always", "best practice"
- Failures: "failed", "error", "lesson learned"

Conversations without these keywords won't create nodes.

## Future Enhancements

### Potential Improvements
1. **Parallel processing**: Process conversations concurrently
2. **Relationship extraction**: Link related decisions/patterns
3. **Semantic analysis**: Use embeddings for similarity
4. **Incremental updates**: Only process new conversations
5. **Deduplication**: Detect and merge similar knowledge

### Integration Points
- Export to other formats (JSON, CSV)
- REST API for on-demand extraction
- Real-time indexing with file watchers
- Integration with Agent Genesis search API

## License

Part of FaulknerDB project - Internal tool for knowledge extraction.

## Support

For issues or questions:
1. Check logs: `tail -f chromadb_extraction.log`
2. Run tests: `python3 test_chromadb_extractor.py`
3. Review this README
4. Check FalkorDB and ChromaDB connectivity
