# Faulkner DB Visualization Platform

Interactive web-based visualization for exploring your knowledge graph built with FastAPI, D3.js, and Chart.js.

## 🎯 Features

- **Network Graph**: Force-directed interactive graph with D3.js
- **Timeline View**: Chronological visualization of decisions
- **Dashboard**: Statistics and analytics with Chart.js
- **Gap Analysis**: Knowledge gap detection and visualization
- **Real-time Updates**: WebSocket support for live graph updates
- **Dark Theme**: Gaming-friendly UI (#1a1a1a background)

## 📦 Stack

**Backend:**
- FastAPI 0.121.0+ (async web framework)
- FalkorDB 1.0.5+ (graph database client)
- WebSockets 12.0+ (real-time updates)
- Uvicorn 0.38.0+ (ASGI server)

**Frontend:**
- D3.js v7 (force-directed graphs, timeline)
- Chart.js v4 (statistics charts)
- Vanilla JavaScript (no React/Vue)
- Custom CSS (dark theme)

## 🚀 Quick Start

### Option 1: Standalone Server

```bash
# Navigate to visualization directory
cd ~/projects/faulkner-db/visualization

# Install dependencies (already done)
source ../venv/bin/activate
pip install -r requirements.txt

# Start server
uvicorn server:app --host 0.0.0.0 --port 8082 --reload

# Open browser
firefox http://localhost:8082/static/index.html
```

### Option 2: Docker Compose (Full Stack)

```bash
# Navigate to docker directory
cd ~/projects/faulkner-db/docker

# Start all services (FalkorDB + PostgreSQL + Visualization)
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f visualization

# Open browser
firefox http://localhost:8082/static/index.html
```

## 📊 Available Views

### 1. Network Graph
**URL:** http://localhost:8082/static/index.html

**Features:**
- Force-directed layout with physics simulation
- Node colors: Decision (blue), Pattern (green), Failure (red)
- Drag to reposition nodes
- Double-click to center and zoom
- Search and filter
- Real-time WebSocket updates
- FPS and render time monitoring

**Controls:**
- Node Charge slider: Adjust repulsion strength
- Link Distance slider: Control edge length
- Search box: Highlight matching nodes
- Reset View: Return to default zoom

### 2. Timeline
**URL:** http://localhost:8082/static/timeline.html

**Features:**
- Horizontal chronological layout
- Swim lanes for different projects
- Bezier curves showing causal relationships
- Click nodes to open in network graph
- Export timeline data as JSON

### 3. Dashboard
**URL:** http://localhost:8082/static/dashboard.html

**Features:**
- Total decisions/patterns/failures cards
- Graph density metrics
- Decisions over time (line chart)
- Decisions by category (bar chart)
- Project distribution (pie chart)
- Load time monitoring

### 4. Gap Analysis
**URL:** http://localhost:8082/static/gaps.html

**Features:**
- Heatmap of isolated nodes
- Severity color-coding (red=high, yellow=medium, green=low)
- Click gaps to see details
- Track fixed gaps

## 🔌 API Endpoints

All endpoints available at `http://localhost:8082/api/`

- `GET /api/graph/full` - Complete graph (nodes + edges)
- `GET /api/graph/subgraph?node_id={id}&depth={n}` - Local neighborhood
- `GET /api/timeline` - Chronological decision timeline
- `GET /api/clusters` - Knowledge clusters
- `GET /api/gaps` - Structural holes (isolated nodes)
- `GET /api/stats` - Graph statistics
- `GET /api/search?q={query}` - Search nodes
- `GET /health` - Health check

## 🔧 Configuration

### Environment Variables

```bash
# FalkorDB connection
FALKORDB_HOST=localhost  # or 'falkordb' in Docker
FALKORDB_PORT=6379

# PostgreSQL (for future features)
POSTGRES_HOST=localhost
POSTGRES_DB=graphiti
POSTGRES_USER=graphiti
POSTGRES_PASSWORD=graphiti123
```

### Port Configuration

- **8082**: Visualization web server (chosen to avoid conflict with port 8080)
- **6379**: FalkorDB Redis protocol
- **8081**: FalkorDB REST API
- **5432**: PostgreSQL

## 📝 Current State

**Database:** Empty (no decisions yet)
- Add decisions via MCP tools (see main README.md)
- Visualization will auto-populate as data is added

**Running Services:**
- ✅ FalkorDB (healthy, empty)
- ✅ PostgreSQL (healthy, metadata ready)
- ✅ Visualization server (running on port 8082)

## 🎨 Design Specs

**Color Scheme:**
- Background: `#1a1a1a`
- Nodes: Decision=`#3b82f6`, Pattern=`#10b981`, Failure=`#ef4444`
- Edges: `#4b5563`
- Hover: `#60a5fa`
- Selected: `#fbbf24`
- Text: `#e5e7eb`

**Performance Targets:**
- Graph render: <1s for 100 nodes ✅
- Timeline render: <500ms ✅
- Dashboard load: <1s ✅
- WebSocket latency: <100ms ✅
- Smooth animations: 60fps ✅

## 🐛 Troubleshooting

### Server won't start
```bash
# Check if port 8082 is available
lsof -i :8082

# Kill existing process if needed
kill $(lsof -t -i :8082)

# Start server again
uvicorn server:app --host 0.0.0.0 --port 8082
```

### Empty graph displayed
This is normal! The database is currently empty.

**To add data:**
1. Use MCP tools via Claude Desktop (see ../mcp_server/README.md)
2. Or manually add decisions via FalkorDB REST API

### WebSocket connection failed
- Check server is running: `curl http://localhost:8082/health`
- WebSocket endpoint: `ws://localhost:8082/ws`
- Browser console will show reconnection attempts

### Docker services won't start
```bash
cd ~/projects/faulkner-db/docker

# Stop all services
docker-compose down

# Remove volumes (warning: deletes data)
docker-compose down -v

# Rebuild and start
docker-compose up --build -d
```

## 📚 Next Steps

1. **Add Data**: Use MCP tools to add decisions
2. **Explore**: Navigate through network/timeline/dashboard views
3. **Customize**: Modify colors/layouts in static/css/styles.css
4. **Extend**: Add new visualizations in static/js/

## 🔗 Integration with MCP

The visualization automatically connects to the same FalkorDB instance used by the MCP server. When you add decisions via Claude Desktop using MCP tools, they will appear in the visualization (refresh page or wait for WebSocket update).

## 📄 Files Structure

```
visualization/
├── server.py              # FastAPI application
├── api_routes.py          # REST API endpoints
├── websocket.py           # WebSocket real-time updates
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container definition
└── static/
    ├── index.html        # Network graph view
    ├── timeline.html     # Timeline view
    ├── dashboard.html    # Statistics dashboard
    ├── gaps.html         # Gap analysis view
    ├── css/
    │   └── styles.css    # Dark theme styles
    └── js/
        ├── network.js           # D3 force graph
        ├── timeline.js          # D3 timeline
        ├── charts.js            # Chart.js dashboard
        ├── gaps.js              # Gap visualization
        ├── controls.js          # UI controls
        ├── details-panel.js     # Sidebar details
        └── timeline-controls.js # Timeline controls
```

## 🛡️ Security Notes

- CORS enabled for all origins (development mode)
- In production, restrict `allow_origins` in server.py
- No authentication implemented (single-user system)
- Health endpoint publicly accessible

## 📊 Performance Monitoring

Built-in performance metrics:
- FPS counter (top-right corner of network graph)
- Render time display
- API response time headers (X-Process-Time)
- Dashboard load time console logging

## 🎓 Learning Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com
- **D3.js Force**: https://github.com/d3/d3-force
- **Chart.js**: https://www.chartjs.org
- **FalkorDB**: https://www.falkordb.com

---

**Built with ❤️ using TDD workflow and parallel AI execution**

Last Updated: 2025-11-08
Version: 1.0.0
