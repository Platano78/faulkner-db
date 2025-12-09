# Faulkner DB Quick Reference Card

**One-page cheat sheet for daily operations**

---

## 🚀 Starting the System

```bash
# Method 1: Automatic (if configured)
# Launch Docker Desktop → Wait 60 seconds → Ready!

# Method 2: Manual
cd ~/projects/faulkner-db/docker
docker-compose up -d

# Verify startup
./validate-autostart.sh
```

**Access Points**:
- Web UI: http://localhost:8082
- FalkorDB UI: http://localhost:8081
- API: http://localhost:8082/api

---

## ⏸️ Stopping the System

```bash
# Method 1: Graceful shutdown
cd ~/projects/faulkner-db/docker
docker-compose down

# Method 2: Just quit Docker Desktop
# Right-click Docker icon → Quit

# Emergency stop
docker-compose kill
```

**Note**: Data persists in volumes, safe to stop anytime.

---

## 🔍 Adding Decisions (Claude Desktop)

```
Use add_decision to record:
Title: "API Gateway Selection"
Decision: "Chose Kong over AWS API Gateway"
Reason: "Need on-premise solution for data sovereignty"
Alternatives: "AWS, Apigee, Tyk"
Consequences: "More maintenance, better control"
```

**Quick Examples**:

```
# Technology decision
Use add_decision: "Selected PostgreSQL for user data storage
because of ACID guarantees and JSON support"

# Pattern adoption
Use add_pattern: "Repository Pattern for data access
to decouple business logic from persistence"

# Failure documentation
Use add_failure: "Payment timeout on 2024-03-15
due to API rate limiting, fixed with circuit breaker"
```

---

## 🔎 Querying Knowledge

```
# Simple search
Use query_decisions to find "database migration"

# Advanced search
Use query_decisions:
- Keywords: "performance optimization"
- Category: "Infrastructure"
- Date: 2024-01-01 to 2024-12-31

# Find related decisions
Use find_related for decision DEC-2024-015

# Get timeline
Use get_timeline from 2024-01-01 to 2024-12-31

# Detect gaps
Use detect_gaps for component "Authentication System"
```

---

## 📊 Visualizations

| View | URL | Purpose |
|------|-----|----------|
| **Network** | http://localhost:8082/static/index.html | Force-directed graph |
| **Timeline** | http://localhost:8082/static/timeline.html | Chronological view |
| **Dashboard** | http://localhost:8082/static/dashboard.html | Metrics & stats |
| **Gaps** | http://localhost:8082/static/gaps.html | Knowledge holes |

**Navigation**:
- Zoom: Mouse wheel
- Pan: Click & drag
- Select: Click node
- Details: Double-click

---

## ✅ System Status Check

```bash
# Quick validation
cd ~/projects/faulkner-db/docker
./validate-autostart.sh

# Expected output:
# ✅ Docker is running
# ✅ All 3 containers exist
# ✅ All containers healthy
# ✅ Restart policies correct
# ✅ APIs responding
```

**Health Checks**:
```bash
# Container status
docker-compose ps

# API health
curl http://localhost:8082/health

# Database stats
curl http://localhost:8082/api/stats

# Resource usage
docker stats --no-stream
```

---

## 📝 View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f falkordb
docker-compose logs -f postgres
docker-compose logs -f visualization

# Last 100 lines
docker-compose logs --tail=100

# With timestamps
docker-compose logs -f -t
```

---

## 💾 Backup & Restore

### Backup
```bash
# FalkorDB (Redis)
docker-compose exec falkordb redis-cli SAVE
docker cp faulkner-db-falkordb:/data/dump.rdb ./backup/

# PostgreSQL
docker-compose exec postgres pg_dump -U faulkner faulkner_db > backup.sql

# Full backup
cd ~/projects/faulkner-db
tar -czf backup-$(date +%Y%m%d).tar.gz docker/
```

### Restore
```bash
# FalkorDB
docker cp ./backup/dump.rdb faulkner-db-falkordb:/data/
docker-compose restart falkordb

# PostgreSQL
cat backup.sql | docker-compose exec -T postgres psql -U faulkner faulkner_db
```

---

## 🔧 Troubleshooting

### Container Issues
```bash
# Restart unhealthy container
docker-compose restart <service_name>

# Rebuild and restart
docker-compose up -d --force-recreate <service_name>

# Full reset (CAUTION: deletes data!)
docker-compose down -v
docker-compose up -d
```

### Common Fixes

| Problem | Solution |
|---------|----------|
| Container unhealthy | `docker-compose restart <service>` |
| Port already in use | Change port in docker-compose.yml |
| Out of memory | Increase Docker RAM allocation |
| Slow queries | Check `docker stats`, optimize data |
| Connection refused | Verify containers running: `docker ps` |
| Data not persisting | Check volumes: `docker volume ls` |

---

## 📊 Generate Reports

```bash
cd ~/projects/faulkner-db
source venv/bin/activate
python scripts/generate_report.py

# View reports
cat reports/current_state.md
cat reports/knowledge_map.json
```

**Reports Include**:
- Total nodes and edges
- Decision statistics
- Knowledge clusters
- Structural gaps
- Recommendations

---

## 🔑 Important Ports

| Service | Port | Purpose |
|---------|------|---------|
| Visualization UI | 8082 | Web interface |
| FalkorDB UI | 8081 | Graph database admin |
| FalkorDB Redis | 6379 | Database connection |
| PostgreSQL | 5432 | Metadata storage |

---

## ⚡ Performance Targets

| Metric | Target | Check |
|--------|--------|---------|
| Query response | <2s | `curl -w "Time: %{time_total}s\n" http://localhost:8082/api/stats` |
| Viz load time | <1s | Browser DevTools Network tab |
| Memory usage | <4GB | `docker stats --no-stream` |
| Startup time | ~60s | `./validate-autostart.sh` |

---

## 📚 MCP Tools (7 Total)

| Tool | Purpose | Example |
|------|---------|----------|
| `add_decision` | Record decision | "Chose Redis for caching" |
| `query_decisions` | Search | "Find database decisions" |
| `add_pattern` | Document pattern | "Repository Pattern usage" |
| `add_failure` | Log failure | "API timeout incident" |
| `find_related` | Relationships | "Related to DEC-001" |
| `detect_gaps` | Find holes | "Auth system gaps" |
| `get_timeline` | History | "2024 decisions" |

---

## 🐞 Emergency Procedures

### System Won't Start
```bash
# 1. Check Docker Desktop is running
# 2. Check resource allocation (6GB+ RAM)
# 3. Try full restart
docker-compose down
docker-compose up -d

# 4. Check logs for errors
docker-compose logs
```

### Data Corruption
```bash
# 1. Stop services
docker-compose down

# 2. Restore from backup
cd ~/projects/faulkner-db
./scripts/restore-backup.sh

# 3. Restart
docker-compose up -d
```

### Performance Degradation
```bash
# 1. Check resources
docker stats

# 2. Restart services
docker-compose restart

# 3. If persistent, rebuild
docker-compose down
docker-compose up -d --build
```

---

## 📌 Quick Reference URLs

**Documentation**:
- User Guide: `~/projects/faulkner-db/docs/USER_GUIDE.md`
- Troubleshooting: `~/projects/faulkner-db/docs/TROUBLESHOOTING.md`
- Tech Stack: `~/projects/faulkner-db/docs/TECH_STACK.md`

**Web Access**:
- Main UI: http://localhost:8082
- FalkorDB: http://localhost:8081
- Health: http://localhost:8082/health
- Stats API: http://localhost:8082/api/stats

**Key Scripts**:
- Validate: `~/projects/faulkner-db/docker/validate-autostart.sh`
- Report: `~/projects/faulkner-db/scripts/generate_report.py`
- Backup: `~/projects/faulkner-db/scripts/backup.sh`

---

## 🔗 Directory Structure

```
~/projects/faulkner-db/
├── docker/
│   ├── docker-compose.yml
│   └── validate-autostart.sh
├── docs/
│   ├── USER_GUIDE.md
│   ├── QUICK_REFERENCE.md (this file)
│   ├── TROUBLESHOOTING.md
│   └── ...
├── scripts/
│   ├── generate_report.py
│   └── backup.sh
├── reports/
│   ├── current_state.md
│   └── knowledge_map.json
└── venv/
    └── ...
```

---

**📌 Print this page and keep it handy!**

**Version**: 1.0  
**Updated**: 2025-11-08  
**Support**: See TROUBLESHOOTING.md