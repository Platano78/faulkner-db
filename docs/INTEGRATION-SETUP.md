# Agent Genesis + Faulkner-DB Integration Setup

This guide covers setting up the automated sync between Agent Genesis and Faulkner-DB. For individual project setup, see:
- [Agent Genesis README](https://github.com/Platano78/agent-genesis)
- [Faulkner-DB README](../README.md)

## Overview

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Claude Code       │     │   Agent Genesis     │     │   Faulkner-DB       │
│   Conversations     │────▶│   (Search Index)    │────▶│   (Knowledge Graph) │
│   ~/.claude/        │     │   ChromaDB + API    │     │   FalkorDB          │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
        JSONL                    57,615 msgs              Decisions, Patterns
                                 33 projects              Failures, Timelines
```

**Agent Genesis** indexes your Claude conversations for semantic search.
**Faulkner-DB** structures that knowledge into a queryable graph of decisions, patterns, and failures.

## Prerequisites

- Docker and Docker Compose
- Python 3.10+
- Git
- ~4GB RAM available for both services

### WSL-Specific Paths

```bash
# Claude Code projects (Linux path)
~/.claude/projects/

# Claude Desktop LevelDB (Windows path via WSL mount)
/mnt/c/Users/YOUR_USERNAME/AppData/Roaming/Claude/Local Storage/leveldb
```

## Step 1: Clone Both Repositories

```bash
cd ~/project  # or your preferred location

git clone https://github.com/Platano78/agent-genesis.git
git clone https://github.com/Platano78/faulkner-db.git
```

## Step 2: Start Agent Genesis

```bash
cd agent-genesis

# Copy and configure environment
cp .env.example .env

# Edit .env - set your Claude paths
# CLAUDE_PROJECTS_PATH=~/.claude/projects
# CLAUDE_DESKTOP_LEVELDB_PATH=/mnt/c/Users/...  (if using Claude Desktop)

# Start the service
docker-compose up -d

# Trigger initial indexing
curl -X POST http://localhost:8080/index/trigger

# Verify (wait 2-3 minutes for indexing)
curl http://localhost:8080/stats
# Should show message count > 0
```

## Step 3: Start Faulkner-DB

```bash
cd ../faulkner-db/docker

# Copy and configure environment
cp .env.example .env

# Edit .env - set POSTGRES_PASSWORD
nano .env

# Start the stack
docker-compose up -d

# Verify
curl http://localhost:8082/health
docker exec faulkner-db-falkordb redis-cli PING
# Should return "PONG"
```

## Step 4: Run Initial Sync

```bash
cd ../  # Back to faulkner-db root

# Install Python dependencies (if not using Docker)
pip install -r requirements.txt

# Run sync with backup
./scripts/sync_agent_genesis_docker.sh --force

# Or without backup (faster)
./scripts/sync_agent_genesis_docker.sh --force --no-backup
```

### Sync Output Explanation

```
[INFO] Agent Genesis API message count: 57615    # Messages in Agent Genesis
[SUCCESS] ChromaDB copied from Docker container  # Data copied for processing
[SUCCESS] Extraction completed successfully      # Nodes created in Faulkner
[INFO] Status: SUCCESS                           # Sync completed
```

## Step 5: Set Up Automatic Sync (Cron)

```bash
# Edit crontab
crontab -e

# Add this line (syncs every 6 hours)
0 */6 * * * /home/YOUR_USER/project/faulkner-db/scripts/sync_agent_genesis_docker.sh --no-backup >> /home/YOUR_USER/project/faulkner-db/logs/sync/cron.log 2>&1
```

### Recommended Cron Schedule

| Frequency | Cron Expression | Use Case |
|-----------|-----------------|----------|
| Every 6 hours | `0 */6 * * *` | Standard usage (recommended) |
| Every hour | `0 * * * *` | Heavy Claude usage |
| Daily at 2 AM | `0 2 * * *` | Light usage |

## Step 6: Set Up Health Monitoring (Optional)

Add health checks to cron:

```bash
# Add to crontab
*/5 * * * * /home/YOUR_USER/project/agent-genesis/scripts/health-check.sh
*/5 * * * * /home/YOUR_USER/project/faulkner-db/scripts/health-check-faulkner.sh
```

## Verification

### Check Agent Genesis

```bash
# API health
curl http://localhost:8080/health

# Message count
curl http://localhost:8080/stats | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Messages: {d[\"alpha\"][\"count\"]}')"

# Search test
curl -X POST http://localhost:8080/search \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication", "limit": 3}'
```

### Check Faulkner-DB

```bash
# API health
curl http://localhost:8082/health

# Node count
docker exec faulkner-db-falkordb redis-cli GRAPH.QUERY knowledge_graph "MATCH (n) RETURN count(n)"

# Container status
docker ps | grep faulkner
```

### Check Sync Status

```bash
# View sync state
cat ~/.faulkner-db/sync_state.json | python3 -m json.tool

# View recent sync logs
tail -50 ~/project/faulkner-db/logs/sync/cron.log
```

## Configuration Reference

### Sync Script Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview sync without making changes |
| `--force` | Force sync even if no new messages |
| `--no-backup` | Skip FalkorDB backup before sync |
| `--verbose` | Enable debug logging |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AG_CONTAINER_NAME` | `agent-genesis` | Agent Genesis Docker container |
| `AG_API_URL` | `http://localhost:8080` | Agent Genesis API URL |
| `FALKORDB_HOST` | `localhost` | FalkorDB host |
| `FALKORDB_PORT` | `6379` | FalkorDB port |

### File Locations

| File | Purpose |
|------|---------|
| `~/.faulkner-db/sync_state.json` | Sync state tracking |
| `logs/sync/sync_YYYYMMDD.log` | Daily sync logs |
| `logs/sync/cron.log` | Cron execution logs |
| `logs/sync/errors/` | Error logs |

## Backup & Recovery

### Create Manual Backup

```bash
# FalkorDB backup
docker exec faulkner-db-falkordb redis-cli BGSAVE

# The RDB file is saved in the Docker volume
```

### Restore from Backup

```bash
# Use the restore script
./scripts/restore_falkordb.sh /path/to/backup.rdb
```

## Troubleshooting

### Sync shows 0 new messages

1. Check Agent Genesis has indexed messages:
   ```bash
   curl http://localhost:8080/stats
   ```

2. Force a full sync:
   ```bash
   ./scripts/sync_agent_genesis_docker.sh --force --no-backup
   ```

### Agent Genesis container not found

1. Check container name:
   ```bash
   docker ps | grep genesis
   ```

2. Update container name if different:
   ```bash
   export AG_CONTAINER_NAME=your-container-name
   ./scripts/sync_agent_genesis_docker.sh
   ```

### ChromaDB copy fails

1. Verify Agent Genesis is running:
   ```bash
   docker ps | grep agent-genesis
   ```

2. Check the ChromaDB path inside container:
   ```bash
   docker exec agent-genesis ls -la /app/knowledge/
   ```

### FalkorDB connection errors

1. Check container is running:
   ```bash
   docker ps | grep falkordb
   ```

2. Test Redis connection:
   ```bash
   docker exec faulkner-db-falkordb redis-cli PING
   ```

## MCP Integration

Both services provide MCP tools for Claude Code:

### Agent Genesis MCP Tools
- `search_conversations` - Search past conversations
- `get_api_stats` - Get index statistics
- `index_conversations` - Trigger indexing

### Faulkner-DB MCP Tools
- `add_decision` - Record architectural decisions
- `query_decisions` - Search decisions
- `add_pattern` - Store implementation patterns
- `add_failure` - Document failures and lessons
- `detect_gaps` - Find knowledge gaps
- `get_timeline` - View knowledge evolution

## Support

- **Agent Genesis Issues**: https://github.com/Platano78/agent-genesis/issues
- **Faulkner-DB Issues**: https://github.com/Platano78/faulkner-db/issues
