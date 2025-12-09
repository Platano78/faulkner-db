# Faulkner DB Technology Stack

## Core Components

| Component | Version | Purpose | License |
|-----------|---------|---------|----------|
| **Graphiti** | Latest | Temporal knowledge graph framework | MIT |
| **FalkorDB** | Latest | CPU-optimized graph database (Redis module) | Redis Source Available |
| **PostgreSQL** | 15-alpine | Relational metadata storage | PostgreSQL License |
| **NetworkX** | Latest | Graph algorithms & analysis | BSD |

### Why These Choices?

- **FalkorDB**: CPU-only operation (gaming-friendly), Redis-compatible, Cypher query support
- **PostgreSQL**: Robust relational storage for metadata, excellent Docker support
- **Graphiti**: Purpose-built for temporal knowledge graphs with timestamps
- **NetworkX**: Industry-standard Python graph library for gap analysis

## APIs & Services

| Component | Framework | Purpose | Port |
|-----------|-----------|---------|------|
| **Visualization API** | FastAPI | REST endpoints for graph queries | 8082 |
| **MCP Server** | FastMCP | Claude Desktop integration (7 tools) | N/A |
| **WebSocket Server** | FastAPI | Real-time updates (future) | 8082 |

### FastAPI Endpoints

```
GET  /health              - Health check
GET  /api/stats           - Graph statistics
POST /api/query           - Graph queries
GET  /api/nodes           - Node listing
GET  /api/edges           - Edge listing
```

## Frontend Libraries

| Library | Version | Purpose | CDN |
|---------|---------|---------|-----|
| **D3.js** | v7 | Interactive graph visualizations | unpkg |
| **Chart.js** | v4 | Dashboard charts & metrics | unpkg |
| **Tailwind CSS** | v3 | Utility-first styling | CDN |
| **Vanilla JS** | ES6+ | No framework overhead | N/A |

### Visualization Features

- Force-directed graph layout (D3.js)
- Interactive timeline (D3.js)
- Statistical dashboards (Chart.js)
- Gap analysis heatmaps (D3.js)

## Infrastructure

| Tool | Version | Purpose |
|------|---------|----------|
| **Docker** | Latest | Container runtime |
| **Docker Compose** | v2+ | Multi-container orchestration |
| **WSL2** | Latest | Windows development environment |

### Docker Configuration

```yaml
services:
  - falkordb (graph database)
  - postgres (metadata storage)
  - visualization (web server)

volumes:
  - falkordb_data (graph persistence)
  - postgres_data (metadata persistence)

networks:
  - faulkner-network (internal)
```

## Python Dependencies

### AI/ML Stack

```
sentence-transformers>=2.2.0    # Text embeddings
cross-encoder>=3.0.0            # Reranking for search
transformers>=4.30.0            # Hugging Face models
torch>=2.0.0                    # PyTorch backend
```

### Graph & Database

```
redis>=4.5.0                    # FalkorDB connection
psycopg2-binary>=2.9.0          # PostgreSQL driver
networkx>=3.0                   # Graph algorithms
graphiti>=0.1.0                 # Temporal graphs
```

### API & Web

```
fastapi>=0.100.0                # REST API framework
uvicorn>=0.22.0                 # ASGI server
pydantic>=2.0.0                 # Data validation
fastmcp>=0.3.0                  # MCP server framework
```

### Development Tools

```
pytest>=7.3.0                   # Testing framework
pytest-asyncio>=0.21.0          # Async test support
pytest-cov>=4.1.0               # Coverage reporting
black>=23.0.0                   # Code formatting
ruff>=0.0.270                   # Linting
```

## Development Workflow

### Local Development

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest tests/ -v --cov

# Start services
docker-compose up -d

# View logs
docker-compose logs -f
```

### Production Deployment

```bash
# Build
docker-compose build

# Deploy
docker-compose up -d

# Validate
cd docker && ./validate-autostart.sh
```

## Model Sizes & Performance

### Embedding Model

- **Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Size**: 80MB
- **Dimensions**: 384
- **Performance**: ~500 sentences/sec on CPU

### CrossEncoder (Reranking)

- **Model**: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **Size**: 80MB
- **Performance**: ~100 pairs/sec on CPU
- **Accuracy**: 90%+ relevance

## Storage Requirements

### Disk Usage

- Docker images: ~2GB
- FalkorDB data: ~100MB per 10K decisions
- PostgreSQL data: ~50MB per 10K decisions
- Embeddings: ~1.5KB per decision

### Memory Usage

- FalkorDB: 1-2GB (depends on graph size)
- PostgreSQL: 500MB-1GB
- Visualization: 200-400MB
- Python services: 500MB-1GB

**Total**: ~4GB recommended

## Network Architecture

```
┌─────────────────────────────────────┐
│   Host Machine (Windows/Linux)     │
│                                     │
│  ┌──────────────────────────────┐  │
│  │   Docker Network             │  │
│  │                              │  │
│  │  ┌────────┐  ┌──────────┐   │  │
│  │  │FalkorDB│  │PostgreSQL│   │  │
│  │  │:6379   │  │:5432     │   │  │
│  │  └───┬────┘  └────┬─────┘   │  │
│  │      │            │          │  │
│  │      └────┬───────┘          │  │
│  │           │                  │  │
│  │      ┌────┴─────┐            │  │
│  │      │  Viz API │            │  │
│  │      │  :8082   │────────────┼──┼──> Browser
│  │      └──────────┘            │  │
│  │                              │  │
│  └──────────────────────────────┘  │
│                                     │
│  ┌──────────────────────────────┐  │
│  │   MCP Server (Host)          │  │
│  │   FastMCP Framework          │──┼──> Claude Desktop
│  └──────────────────────────────┘  │
│                                     │
└─────────────────────────────────────┘
```

## Version Control

- **Git**: Version control
- **GitHub**: Repository hosting
- **Conventional Commits**: Commit message standard

## Testing Stack

- **Unit Tests**: pytest
- **Integration Tests**: pytest with Docker
- **E2E Tests**: pytest with API calls
- **Coverage**: pytest-cov (target: 95%+)

---

**Last Updated**: 2025-11-08  
**System Version**: 1.0.0 (Production Ready)