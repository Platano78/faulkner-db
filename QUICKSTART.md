# Faulkner DB - Quick Start Guide

## 🚀 Installation & Setup

### Step 1: Install Python Dependencies

```bash
cd ~/projects/faulkner-db
pip install -r requirements.txt
```

### Step 2: Start Docker Stack

```bash
cd docker
chmod +x start.sh stop.sh
./start.sh
```

This starts:
- FalkorDB (port 6379) - Graph database
- PostgreSQL (port 5432) - Metadata storage

### Step 3: Verify Docker Services

```bash
docker-compose ps
```

Expected output:
```
NAME                    STATUS
faulkner-db-falkordb    Up (healthy)
faulkner-db-postgres    Up (healthy)
```

### Step 4: Run MCP Server

```bash
cd ~/projects/faulkner-db/mcp_server
python server.py
```

Expected output:
```
Faulkner DB MCP Server started
Available tools: ['add_decision', 'query_decisions', ...]
```

## 🧪 Running Tests

```bash
cd ~/projects/faulkner-db

# Run all tests
pytest tests/ -v

# Run specific test suite
pytest tests/test_knowledge_types.py -v
pytest tests/test_hybrid_search.py -v
pytest tests/test_gap_detector.py -v
pytest tests/test_mcp_tools.py -v

# Run with coverage
pytest tests/ --cov=core --cov=mcp_server -v
```

## 📊 Usage Examples

### Example 1: Add a Decision

```python
import asyncio
from mcp_server.mcp_tools import add_decision

async def example():
    result = await add_decision(
        description="Use FalkorDB for temporal knowledge graph",
        rationale="CPU-friendly, Redis-compatible, supports temporal queries",
        alternatives=["Neo4j", "ArangoDB", "TigerGraph"],
        related_to=[]
    )
    print(f"Created: {result['decision_id']}")

asyncio.run(example())
```

### Example 2: Query Decisions

```python
from mcp_server.mcp_tools import query_decisions

async def example():
    results = await query_decisions(
        query="database decisions in Q3 2024",
        timeframe={
            "start": "2024-07-01",
            "end": "2024-09-30"
        }
    )
    for r in results:
        print(f"Score: {r['score']:.2f} - {r['content']}")

asyncio.run(example())
```

### Example 3: Detect Knowledge Gaps

```python
from mcp_server.mcp_tools import detect_gaps

async def example():
    gaps = await detect_gaps()
    for gap in gaps:
        print(f"{gap['severity']}: {gap['recommendation']}")

asyncio.run(example())
```

## 🔧 Configuration

### Graphiti Config
Edit `config/graphiti_config.yaml`:
- FalkorDB connection settings
- PostgreSQL metadata store
- Performance tuning

### MCP Config
Edit `config/mcp_config.json`:
- Tool enablement
- Hybrid search parameters
- Gap detection thresholds

## 📈 Performance Targets

- ✅ Hybrid Search: <2s
- ✅ Gap Detection: >85% accuracy
- ✅ Query Precision: 90%+
- ✅ Memory Usage: Gaming-friendly (FalkorDB 2GB, PostgreSQL 1GB)

## 🛑 Stopping Services

```bash
cd ~/projects/faulkner-db/docker
./stop.sh
```

## 🔍 Troubleshooting

### Docker services won't start
```bash
# Check logs
docker-compose logs -f

# Restart services
docker-compose restart
```

### Tests failing
```bash
# Ensure dependencies installed
pip install -r requirements.txt

# Check Python path
export PYTHONPATH=/home/platano/projects/faulkner-db:$PYTHONPATH
```

### MCP server errors
```bash
# Check if FalkorDB is running
redis-cli -p 6379 ping

# Check PostgreSQL
psql -h localhost -U graphiti -d graphiti -c "SELECT 1"
```

## 📚 Next Steps

1. **Add Your First Decision**: Start documenting architectural choices
2. **Build Knowledge Graph**: Add patterns and failures as you learn
3. **Query Your Knowledge**: Use hybrid search to find past decisions
4. **Detect Gaps**: Identify missing connections in your architecture
5. **Integrate with Claude**: Use MCP tools in Claude Desktop

## 🎯 Key Features

- ✅ **Temporal Queries**: Track decisions over time
- ✅ **Hybrid Search**: Graph + vector + reranking
- ✅ **Gap Detection**: NetworkX structural analysis
- ✅ **MCP Integration**: 7 tools for Claude Desktop
- ✅ **Docker Deployment**: One-command startup
- ✅ **CPU-Only**: Gaming-friendly, no GPU required

## 📖 Full Documentation

See [README.md](README.md) for complete documentation.

## 🤝 Support

For issues or questions:
- Check [README.md](README.md)
- Review test files in `tests/`
- Inspect Docker logs: `docker-compose logs`

---

**Built with**: Python 3.11+ • FalkorDB • PostgreSQL • NetworkX • sentence-transformers
