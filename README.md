# Faulkner DB - Temporal Knowledge Graph System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://docs.docker.com/get-docker/)
[![npm version](https://img.shields.io/npm/v/faulkner-db-config.svg)](https://www.npmjs.com/package/faulkner-db-config)
[![CI Status](https://github.com/platano78/faulkner-db/workflows/CI/badge.svg)](https://github.com/platano78/faulkner-db/actions)
[![GitHub stars](https://img.shields.io/github/stars/platano78/faulkner-db.svg)](https://github.com/platano78/faulkner-db/stargazers)

**Faulkner DB empowers software teams to capture, query, and analyze architectural decisions, implementation patterns, and failures as they evolve over time.** Built on FalkorDB (CPU-friendly graph database) with hybrid search capabilities, it provides unparalleled insights into your project's history, fostering better decision-making and reducing technical debt.

## 🎯 Value Proposition

- **Improved Decision Tracking** - Capture the rationale behind architectural choices and their impact over time
- **Enhanced Collaboration** - Facilitate knowledge sharing and alignment across teams
- **Reduced Technical Debt** - Identify and address problematic patterns early
- **Faster Onboarding** - Accelerate learning for new team members with comprehensive project history
- **AI-Ready Knowledge Base** - Structure knowledge for AI-powered development tools (Claude Code/Desktop)

## ✨ Key Features

- **Temporal Knowledge Graph** - Track changes to decisions and patterns over time
- **Hybrid Search** - Graph traversal + vector embeddings + CrossEncoder reranking (<2s queries)
- **Gap Detection** - NetworkX-based structural analysis to identify knowledge gaps
- **MCP Integration** - 12 tools for seamless Claude Desktop/Code integration
- **Docker Deployment** - One-command startup with auto-restart support
- **CPU-Friendly** - Built on FalkorDB, no GPU required (gaming-friendly memory footprint)

## 📖 Documentation

- **[Integration Setup Guide](docs/INTEGRATION-SETUP.md)** - Set up Agent Genesis + Faulkner-DB sync
- **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute

## 🚀 Quick Start

### Option 1: Automated NPM Setup (Recommended)

```bash
# Configure Claude Desktop/Code automatically
npx faulkner-db-config setup

# Clone and start the stack
git clone https://github.com/platano78/faulkner-db.git
cd faulkner-db/docker
docker-compose up -d

# Restart Claude Desktop/Code
```

### Option 2: Manual Setup

**1. Start FalkorDB Stack**

```bash
git clone https://github.com/platano78/faulkner-db.git
cd faulkner-db/docker

# Copy environment template
cp .env.example .env

# Edit .env and set POSTGRES_PASSWORD

# Start services
docker-compose up -d
```

**2. Configure Claude (Manual)**

Add to `~/.config/Claude/claude_desktop_config.json` (Linux) or equivalent:

```json
{
  "mcpServers": {
    "faulkner-db": {
      "command": "python3",
      "args": ["-m", "mcp_server.server_fastmcp"],
      "env": {
        "PYTHONPATH": "/path/to/faulkner-db",
        "FALKORDB_HOST": "localhost",
        "FALKORDB_PORT": "6380",
        "FALKORDB_PASSWORD": "changeme"
      }
    }
  }
}
```

**3. Access Services**

- **Network Graph**: http://localhost:VISUALIZATION_PORT/static/index.html
- **Timeline View**: http://localhost:VISUALIZATION_PORT/static/timeline.html
- **Dashboard**: http://localhost:VISUALIZATION_PORT/static/dashboard.html
- **API Health**: http://localhost:VISUALIZATION_PORT/health

Set `VISUALIZATION_PORT` and `FALKORDB_REST_PORT` in `docker/.env`. See `.env.example` for defaults.

## Security Configuration

### Authentication

FalkorDB now requires password authentication for all connections.

| Setting | Value |
|---------|-------|
| **Environment Variable** | `FALKORDB_PASSWORD` |
| **Default (local dev)** | `changeme` |

### Port Configuration

The default port has been changed from 6379 to 6380 to avoid conflicts with standard Redis installations.

| Setting | Value |
|---------|-------|
| **Environment Variable** | `FALKORDB_PORT` |
| **Default Port** | `6380` |

### Connection Examples

**Python**
```python
import os
from core.graphiti_client import GraphitiClient

password = os.environ.get('FALKORDB_PASSWORD')
client = GraphitiClient(host='localhost', port=6380, password=password)
```

**redis-cli**
```bash
redis-cli -p 6380 -a $FALKORDB_PASSWORD
```

**Docker Compose Environment**
```yaml
environment:
  FALKORDB_HOST: falkordb
  FALKORDB_PORT: 6380
  FALKORDB_PASSWORD: ${FALKORDB_PASSWORD}
```

### Destructive Commands Disabled

To prevent accidental data loss, the following commands are disabled in the FalkorDB configuration:

- `FLUSHALL` - Renamed to an obscure command (not directly callable)
- `FLUSHDB` - Renamed to an obscure command (not directly callable)

If you need to clear data during development, recreate the container with a fresh volume.

## 🏗️ Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   Claude Code/      │    │   Faulkner DB       │    │     FalkorDB        │
│   Desktop           │───▶│   (MCP Server)      │───▶│   (Graph DB)        │
│                     │    │   Temporal Logic     │    │   CPU-Friendly      │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
         │                          │                           │
         │                          │                           │
         ▼                          ▼                           ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   12 MCP Tools      │    │   Hybrid Search      │    │   PostgreSQL        │
│   - add_decision    │    │   Graph + Vector     │    │   (Metadata Store)  │
│   - query_decisions │    │   + Reranking        │    │                     │
│   - detect_gaps     │    │                      │    │                     │
│   - get_timeline    │    │                      │    │                     │
│   - graph_summary   │    │                      │    │                     │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

## 📚 MCP Tools Documentation

### 1. add_decision
Record architectural decision with full context and rationale.

```json
{
  "description": "Use FalkorDB for temporal graphs",
  "rationale": "CPU-friendly, Redis-compatible, excellent temporal support",
  "alternatives": ["Neo4j", "ArangoDB"],
  "related_to": [],
  "source": "manual"
}
```

> **`source` is required as of v1.7.0** unless `FAULKNER_ALLOW_AUTOMATED=true`.
> Allowed values: `"manual"` (human-curated) or `"reviewed_automated"`
> (LLM-drafted, human-reviewed). See [Ingestion Guards](#-ingestion-guards-v170).

### 2. query_decisions
Hybrid search for decisions by topic/timeframe.

```json
{
  "query": "authentication decisions",
  "timeframe": {
    "start": "2024-01-01",
    "end": "2024-12-31"
  }
}
```

### 3. add_pattern
Store successful implementation pattern.

```json
{
  "name": "CQRS Pattern",
  "implementation": "Separate read/write models with event sourcing",
  "use_cases": ["High-scale systems", "Event-driven architecture"],
  "context": "Microservices with async communication",
  "source": "manual"
}
```

### 4. add_failure
Document what didn't work and lessons learned.

```json
{
  "attempt": "Used RabbitMQ with 50+ queues",
  "reason_failed": "Performance degradation under load",
  "lesson_learned": "Use Kafka for high-throughput streaming",
  "alternative_solution": "Migrated to Kafka with topic partitioning",
  "source": "manual"
}
```

### 5. find_related
Graph traversal to discover related knowledge nodes.

```json
{
  "node_id": "D-abc123",
  "depth": 2
}
```

### 6. detect_gaps
Run NetworkX structural analysis to identify knowledge gaps (>85% accuracy).

```json
{}
```

### 7. get_timeline
Temporal view showing how understanding evolved over time.

```json
{
  "topic": "Authentication System",
  "start_date": "2023-01-01",
  "end_date": "2024-12-31"
}
```

### 8. find_influential_patterns
Find the most connected/influential patterns using degree centrality.

```json
{
  "limit": 10
}
```

### 9. find_knowledge_communities
Detect communities of related knowledge using connected components analysis.

```json
{
  "min_community_size": 3
}
```

### 10. find_bridge_patterns
Find bridge patterns that connect different knowledge domains.

```json
{
  "limit": 10
}
```

### 11. get_graph_summary
Get comprehensive summary of the knowledge graph structure, including node counts, edge counts, and connectivity metrics.

```json
{}
```

### 12. query_patterns_semantic
Semantic search for patterns using sentence-transformers embeddings. More intelligent than keyword matching.

```json
{
  "query": "authentication middleware",
  "limit": 10
}
```

## 🛡️ Ingestion Guards (v1.7.0)

Every write through `add_decision` / `add_pattern` / `add_failure` is now
gated to prevent re-introduction of two pollution patterns that historically
ballooned the graph (10,781 nodes purged in v1.7.0):

1. **Blocklist regex** on `name` / `context` / `description` / `attempt`
   fields. Defaults block `^playbook-.*-\d{13}$` (MKG playbook signature)
   and `.*-\d{13}$` (any unix-ms timestamp suffix, defensive). Override
   the list via `FAULKNER_INGESTION_BLOCKLIST_FILE` (JSON
   `{"patterns": [...]}` or one regex per line).
2. **`source_files` containing `agent-genesis`** — historically the
   conversation-fragment auto-ingest path. Hard-rejected.
3. **`source` parameter required** — must be `"manual"` or
   `"reviewed_automated"`. Set `FAULKNER_ALLOW_AUTOMATED=true` to bypass
   when running an authorized automated reviewer.

Rejections are logged as one JSON line each to `logs/rejected_writes.jsonl`
(timestamp, label, reason, truncated sample fields, matched pattern).
Override the path via `FAULKNER_REJECTION_LOG`.

## 🩺 Graph Health Check (v1.7.0)

`scripts/health_check.py` is a read-only diagnostic over the live graph:

```bash
FALKORDB_HOST=192.168.1.79 FALKORDB_PORT=6380 FALKORDB_PASSWORD=... \
  python scripts/health_check.py            # human-readable
  python scripts/health_check.py --json     # machine-readable
  python scripts/health_check.py --strict   # exit 1 on any warning
```

Reports node/edge totals, `Failure:Decision` ratio (warn > 5),
`SEMANTICALLY_SIMILAR / structural_edges` ratio (warn > 1.0), avg/max
Pattern degree (warn > 20 / > 50), and the top-10 most-connected
patterns flagged HUMAN-CURATED vs TELEMETRY.

### Schedule via systemd user timer

```bash
mkdir -p ~/.config/faulkner-health
cat > ~/.config/faulkner-health/env <<'EOF'
FALKORDB_HOST=192.168.1.79
FALKORDB_PORT=6380
FALKORDB_PASSWORD=YOUR_PASSWORD
EOF
chmod 600 ~/.config/faulkner-health/env

cp scripts/faulkner-health-graph.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now faulkner-health-graph.timer
```

Runs every 6 hours; output in `journalctl --user -u faulkner-health-graph`.

## 🧪 Maintenance scripts (v1.7.0)

| Script | Purpose |
|---|---|
| `scripts/audit_mkg_pollution.py` | Read-only audit; JSON pollution report by signature & node label. |
| `scripts/migrate_mkg_to_sqlite.py` | One-shot migration of MKG playbook Patterns to MKG's SQLite store. Idempotent on re-run. |
| `scripts/purge_migrated_nodes.py` | Manifest-driven delete (paired with the migration). |
| `scripts/purge_auto_ingest.py` | Criteria-driven delete of Agent Genesis–ingested nodes. |
| `scripts/regenerate_semantic_edges.py` | Re-run sentence-transformers + FAISS at the env-tunable threshold. |

All destructive scripts default to `--dry-run`, take a server-side BGSAVE
plus a paginated local JSON dump before any mutation, and emit a
JSON manifest under `logs/` for traceability.

## 🛠️ Technical Stack

| Component | Technology |
|-----------|------------|
| **Graph Database** | FalkorDB (CPU-only) |
| **Metadata Store** | PostgreSQL |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) |
| **Reranking** | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| **Graph Analysis** | NetworkX |
| **MCP Server** | Python 3.9+ (FastMCP) |
| **Deployment** | Docker Compose |

## ⚡ Performance

- **Query Time**: <2s (hybrid search with reranking)
- **Accuracy**: 90%+ on decision queries
- **Gap Detection**: >85% accuracy
- **Memory**: Gaming-friendly (FalkorDB: 2GB, PostgreSQL: 1GB)
- **Scalability**: Tested with 10,000+ nodes

## 🔧 Configuration

### Environment Variables

Create `docker/.env` from `.env.example`:

```bash
# FalkorDB Configuration
FALKORDB_HOST=falkordb
FALKORDB_PORT=6380
FALKORDB_PASSWORD=changeme
FALKORDB_MEMORY_LIMIT=2gb
FALKORDB_REST_PORT=8082

# PostgreSQL Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=graphiti
POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD
POSTGRES_DB=graphiti

# Visualization
VISUALIZATION_PORT=8086
```

**Note**: The `FALKORDB_PASSWORD` is required for authentication. Change the default password in production environments.

### MCP Server Configuration

The MCP server automatically connects to FalkorDB and PostgreSQL using environment variables. No additional configuration needed.

## 🐛 Troubleshooting

### Docker containers not starting
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f

# Restart services
docker-compose restart
```

### FalkorDB connection errors
- Verify FalkorDB is running: `docker-compose ps`
- Check port 6380 is not in use: `lsof -i :6380`
- Verify password is set: `echo $FALKORDB_PASSWORD`
- Review FalkorDB logs: `docker-compose logs falkordb`

### MCP server not detected in Claude
1. Verify configuration path matches your OS (see npm package docs)
2. Restart Claude Desktop/Code after config changes
3. Check Python path in MCP config is correct
4. Ensure Docker stack is running

### Data persistence issues
- Verify `docker/data/` directory has correct permissions
- Check `FALKORDB_PERSISTENCE=true` in `.env`
- Backup data: `docker-compose exec falkordb redis-cli -a $FALKORDB_PASSWORD BGSAVE`

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

1. **Fork the repository** and create a feature branch
2. **Write tests** for new features (pytest)
3. **Follow code style** (PEP 8 for Python)
4. **Document changes** in code and README
5. **Submit pull request** with clear description

### Development Setup

```bash
# Clone repository
git clone https://github.com/platano78/faulkner-db.git
cd faulkner-db

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=core --cov=mcp_server
```

See `CONTRIBUTING.md` for detailed guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🗺️ Roadmap

- [x] Phase 1: Core Knowledge Graph
- [x] Phase 2: Hybrid Search
- [x] Phase 3: Gap Detection
- [x] Phase 4: MCP Server Integration
- [x] Phase 5: Docker Deployment
- [x] Phase 6: Testing & Validation
- [ ] Phase 7: Advanced Analytics Dashboard
- [ ] Phase 8: Multi-tenant Support
- [ ] Phase 9: Cloud Deployment Options

## 📞 Support

- **Issues**: https://github.com/platano78/faulkner-db/issues
- **Discussions**: https://github.com/platano78/faulkner-db/discussions
- **Documentation**: https://github.com/platano78/faulkner-db/wiki

## 🙏 Acknowledgments

Built with:
- [FalkorDB](https://www.falkordb.com/) - Graph database with temporal support
- [ChromaDB](https://www.trychroma.com/) - Vector embeddings (previous iteration)
- [sentence-transformers](https://www.sbert.net/) - Semantic embeddings
- [NetworkX](https://networkx.org/) - Graph analysis algorithms
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework

---

**Made with ❤️ for software teams who value architectural knowledge**
