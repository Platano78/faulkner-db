# Faulkner DB Troubleshooting Guide

Quick solutions for common issues. Each section includes symptoms, diagnosis steps, solutions, and prevention measures.

## Table of Contents

- [Docker Desktop Issues](#docker-desktop-issues)
- [Container Health Problems](#container-health-problems)
- [Visualization Not Loading](#visualization-not-loading)
- [MCP Tools Not Responding](#mcp-tools-not-responding)
- [Data Persistence Issues](#data-persistence-issues)
- [Performance Degradation](#performance-degradation)
- [Network Connectivity](#network-connectivity)
- [Database Errors](#database-errors)

---

## Docker Desktop Issues

### Problem: Docker Desktop Won't Start

**Symptoms:**
- Error: "Docker Desktop starting" stuck forever
- Error: "WSL 2 installation is incomplete"
- Error: "Hardware assisted virtualization and data execution protection must be enabled"
- Docker icon red/yellow, not green

**Diagnosis Steps:**

1. **Check WSL2 status** (Windows):
   ```powershell
   wsl --list --verbose
   wsl --status
   ```

2. **Check Docker version:**
   ```bash
   docker --version
   docker info
   ```

3. **Check system resources:**
   - Task Manager → Performance tab
   - Verify CPU virtualization enabled
   - Check available RAM and disk space

4. **Review Docker logs:**
   - Windows: `%APPDATA%\Docker\log.txt`
   - Mac: `~/Library/Containers/com.docker.docker/Data/log`
   - Linux: `journalctl -u docker`

**Solutions:**

**For WSL2 issues (Windows):**
```powershell
# Update WSL2 kernel
wsl --update
wsl --set-default-version 2

# Restart WSL
wsl --shutdown
```

**For virtualization issues:**
1. Restart computer
2. Enter BIOS/UEFI (usually F2, Del, or F10 during boot)
3. Enable "Intel VT-x" or "AMD-V"
4. Enable "Hyper-V" in Windows Features:
   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
   ```

**For general Docker issues:**
```bash
# Restart Docker Desktop
# Windows/Mac: Right-click Docker icon → Restart

# Linux:
sudo systemctl restart docker

# If that fails, reinstall Docker Desktop
# Download latest from: https://www.docker.com/products/docker-desktop
```

**Prevention:**
- Keep Windows updated
- Don't disable virtualization in BIOS
- Allocate sufficient resources:
  - RAM: 6GB minimum, 8GB recommended
  - Disk: 20GB minimum
- Regular Docker Desktop updates

---

## Container Health Problems

### Problem: Containers Showing Unhealthy

**Symptoms:**
- `docker-compose ps` shows "unhealthy" status
- Services not responding
- Application features broken
- Validation script fails health checks

**Diagnosis Steps:**

1. **Check container status:**
   ```bash
   cd ~/projects/faulkner-db/docker
   docker-compose ps
   docker ps --filter health=unhealthy
   ```

2. **View container logs:**
   ```bash
   docker-compose logs falkordb
   docker-compose logs postgres
   docker-compose logs visualization
   ```

3. **Check resource usage:**
   ```bash
   docker stats --no-stream
   ```

4. **Inspect health check:**
   ```bash
   docker inspect faulkner-db-falkordb | grep -A 10 Health
   ```

**Solutions:**

**Quick fix - Restart unhealthy containers:**
```bash
cd ~/projects/faulkner-db/docker
docker-compose restart falkordb
docker-compose restart postgres
docker-compose restart visualization
```

**Deep fix - Recreate containers:**
```bash
# Stop all containers
docker-compose down

# Clear any orphaned resources
docker system prune -f

# Restart with fresh containers
docker-compose up -d

# Wait for health checks
sleep 30
./validate-autostart.sh
```

**If PostgreSQL is unhealthy:**
```bash
# Check if database initialized properly
docker-compose exec postgres pg_isready -U faulkner

# Check database logs
docker-compose logs postgres | grep ERROR

# If corrupted, restore from backup
docker-compose down
docker volume rm faulkner-db_postgres_data
docker-compose up -d
```

**If FalkorDB is unhealthy:**
```bash
# Test Redis connectivity
docker-compose exec falkordb redis-cli PING

# Check graph existence
docker-compose exec falkordb redis-cli GRAPH.LIST

# Restart FalkorDB
docker-compose restart falkordb
```

**Prevention:**
- Monitor `docker stats` regularly
- Allocate sufficient memory (4GB minimum)
- Keep >5GB disk space free
- Set up log rotation:
  ```yaml
  # In docker-compose.yml
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
  ```

---

## Visualization Not Loading

### Problem: Web UI Blank or Not Loading

**Symptoms:**
- Browser shows blank page
- Loading spinner never completes
- Network errors in browser console
- "Cannot connect" error
- HTTP 502 Bad Gateway

**Diagnosis Steps:**

1. **Test API directly:**
   ```bash
   curl http://localhost:8082/health
   curl http://localhost:8082/api/stats
   ```

2. **Check if port is bound:**
   ```bash
   # Windows
   netstat -an | findstr 8082
   
   # Linux/Mac
   netstat -an | grep 8082
   lsof -i :8082
   ```

3. **Check visualization logs:**
   ```bash
   docker-compose logs visualization | tail -50
   ```

4. **Browser console:**
   - Open browser DevTools (F12)
   - Check Console tab for errors
   - Check Network tab for failed requests

**Solutions:**

**Restart visualization service:**
```bash
cd ~/projects/faulkner-db/docker
docker-compose restart visualization

# Wait a moment
sleep 10

# Test
curl http://localhost:8082/health
```

**Clear browser cache:**
- Chrome: Ctrl+Shift+Del → Clear cached images and files
- Firefox: Ctrl+Shift+Del → Cached Web Content
- Or use incognito/private mode

**Check firewall settings:**
```bash
# Windows: Allow port 8082
netsh advfirewall firewall add rule name="Faulkner Viz" dir=in action=allow protocol=TCP localport=8082

# Linux: UFW
sudo ufw allow 8082/tcp

# Linux: iptables
sudo iptables -A INPUT -p tcp --dport 8082 -j ACCEPT
```

**Verify Docker network:**
```bash
# Check network exists
docker network ls | grep faulkner

# Recreate network if missing
docker-compose down
docker-compose up -d
```

**Test from different browser:**
- Sometimes browser extensions block content
- Try Chrome, Firefox, Edge to isolate issue

**Prevention:**
- Configure firewall exceptions during setup
- Don't change port mappings in docker-compose.yml
- Regular browser cache clearing
- Test immediately after startup

---

## MCP Tools Not Responding

### Problem: MCP Commands Not Working in Claude Desktop

**Symptoms:**
- "Command not found" errors
- No response after command execution
- "Server not available" messages
- Tools not appearing in Claude Desktop

**Diagnosis Steps:**

1. **Check Claude Desktop is running:**
   - Windows: Task Manager → Claude Desktop
   - Mac: Activity Monitor → Claude Desktop

2. **Verify MCP configuration:**
   ```bash
   # Windows
   cat %APPDATA%/Claude/claude_desktop_config.json
   
   # Mac
   cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
   
   # Linux
   cat ~/.config/Claude/claude_desktop_config.json
   ```

3. **Test MCP server directly:**
   ```bash
   cd ~/projects/faulkner-db
   python -c "from mcp_server import FaulknerMCP; print('OK')"
   ```

4. **Check Claude Desktop logs:**
   - Settings → Advanced → View Logs

**Solutions:**

**Restart Claude Desktop:**
1. Completely quit Claude Desktop
2. Wait 5 seconds
3. Restart Claude Desktop
4. Wait for MCP servers to reconnect (~10 seconds)

**Verify MCP configuration:**
```json
// claude_desktop_config.json should include:
{
  "mcpServers": {
    "faulkner-db": {
      "command": "python",
      "args": [
        "/home/platano/projects/faulkner-db/mcp_server/server.py"
      ],
      "env": {
        "PYTHONPATH": "/home/platano/projects/faulkner-db"
      }
    }
  }
}
```

**Reinstall MCP server:**
```bash
cd ~/projects/faulkner-db
source venv/bin/activate
pip install -e .

# Test import
python -c "from mcp_server import FaulknerMCP; print('MCP OK')"
```

**Check Python environment:**
```bash
# Verify Python version (3.9+)
python --version

# Verify required packages
pip list | grep -E "fastmcp|redis|psycopg2"

# Reinstall if missing
pip install -r requirements.txt
```

**Prevention:**
- Keep Claude Desktop updated
- Don't modify MCP server code without testing
- Backup claude_desktop_config.json
- Test MCP tools after Claude Desktop updates

---

## Data Persistence Issues

### Problem: Data Lost After Restart

**Symptoms:**
- Previous decisions disappeared
- Fresh/empty database state
- Volume mount errors in logs
- "No such file or directory" errors

**Diagnosis Steps:**

1. **Check volumes exist:**
   ```bash
   docker volume ls | grep faulkner
   ```

2. **Inspect volume configuration:**
   ```bash
   docker volume inspect faulkner-db_falkordb_data
   docker volume inspect faulkner-db_postgres_data
   ```

3. **Check docker-compose.yml:**
   ```bash
   cat docker/docker-compose.yml | grep -A 5 volumes
   ```

4. **Verify data directory permissions:**
   ```bash
   docker-compose exec falkordb ls -la /data
   docker-compose exec postgres ls -la /var/lib/postgresql/data
   ```

**Solutions:**

**Ensure volumes are named (not bind mounts):**
```yaml
# docker-compose.yml should have:
volumes:
  falkordb_data:
  postgres_data:

services:
  falkordb:
    volumes:
      - falkordb_data:/data
  postgres:
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

**Restore from backup:**
```bash
# FalkorDB
docker cp backup/dump.rdb faulkner-db-falkordb:/data/
docker-compose restart falkordb

# PostgreSQL
cat backup.sql | docker-compose exec -T postgres psql -U faulkner faulkner_db
```

**Fix permissions:**
```bash
# If permission denied errors
docker-compose exec falkordb chown -R redis:redis /data
docker-compose exec postgres chown -R postgres:postgres /var/lib/postgresql/data
```

**Recreate volumes (CAUTION: deletes data):**
```bash
# Backup first!
docker-compose down
docker volume rm faulkner-db_falkordb_data
docker volume rm faulkner-db_postgres_data
docker-compose up -d
```

**Prevention:**
- **Always use named volumes**, not bind mounts
- Regular backups (daily recommended):
  ```bash
  # Add to crontab
  0 2 * * * cd ~/projects/faulkner-db/docker && ./backup.sh
  ```
- Test restore procedure monthly
- Never run `docker-compose down -v` (deletes volumes!)
- Use `docker-compose down` instead (preserves volumes)

---

## Performance Degradation

### Problem: Slow Queries or Responses

**Symptoms:**
- API responses >2 seconds
- Visualization takes >5 seconds to load
- Search queries timeout
- High CPU/memory usage

**Diagnosis Steps:**

1. **Check resource usage:**
   ```bash
   docker stats
   ```

2. **Monitor query times:**
   ```bash
   curl -w "Time: %{time_total}s\n" http://localhost:8082/api/stats
   ```

3. **Check database size:**
   ```bash
   # FalkorDB
   docker-compose exec falkordb redis-cli INFO memory
   
   # PostgreSQL
   docker-compose exec postgres psql -U faulkner -c "\l+"
   ```

4. **Review logs for slow queries:**
   ```bash
   docker-compose logs visualization | grep -i slow
   ```

**Solutions:**

**Increase Docker resources:**
1. Docker Desktop → Settings → Resources
2. Increase:
   - CPUs: 4+ cores
   - Memory: 6-8GB
   - Swap: 2GB
   - Disk: 20GB+

**Optimize database:**
```bash
# PostgreSQL VACUUM
docker-compose exec postgres psql -U faulkner faulkner_db -c "VACUUM ANALYZE;"

# FalkorDB compaction
docker-compose exec falkordb redis-cli BGSAVE
```

**Clear old data:**
```python
# Archive decisions older than 2 years
# Use query_decisions with date filter
# Export to JSON, then delete from live system
```

**Add indexes** (if using custom queries):
```sql
-- PostgreSQL
CREATE INDEX idx_decisions_category ON decisions(category);
CREATE INDEX idx_decisions_created_at ON decisions(created_at);
```

**Restart services:**
```bash
# Fresh start clears memory leaks
docker-compose restart
```

**Prevention:**
- Monitor docker stats weekly
- Archive old data quarterly
- Run VACUUM monthly
- Limit search results (use pagination)
- Set up alerting for >2s query times

---

## Network Connectivity

### Problem: Containers Can't Communicate

**Symptoms:**
- "Connection refused" errors
- "Host not found" errors
- Visualization can't reach FalkorDB
- MCP server can't reach databases

**Diagnosis Steps:**

1. **Check Docker network:**
   ```bash
   docker network ls
   docker network inspect faulkner-db_default
   ```

2. **Test container connectivity:**
   ```bash
   # From visualization to FalkorDB
   docker-compose exec visualization ping falkordb
   
   # From visualization to PostgreSQL
   docker-compose exec visualization ping postgres
   ```

3. **Check port bindings:**
   ```bash
   docker-compose ps
   ```

**Solutions:**

**Recreate network:**
```bash
docker-compose down
docker network prune -f
docker-compose up -d
```

**Use service names (not localhost):**
```python
# WRONG (from container)
redis.Redis(host='localhost', port=6379)

# CORRECT (from container)
redis.Redis(host='falkordb', port=6379)
```

**Check docker-compose.yml network config:**
```yaml
services:
  falkordb:
    networks:
      - faulkner-network
  postgres:
    networks:
      - faulkner-network
  visualization:
    networks:
      - faulkner-network

networks:
  faulkner-network:
    driver: bridge
```

**Prevention:**
- Always use service names for inter-container communication
- Don't modify network configuration unless necessary
- Test connectivity after docker-compose changes

---

## Database Errors

### Problem: FalkorDB or PostgreSQL Errors

**Symptoms:**
- "Could not connect to database"
- "Authentication failed"
- "Database does not exist"
- Graph query errors

**Diagnosis Steps:**

1. **Test FalkorDB:**
   ```bash
   docker-compose exec falkordb redis-cli PING
   docker-compose exec falkordb redis-cli GRAPH.LIST
   ```

2. **Test PostgreSQL:**
   ```bash
   docker-compose exec postgres pg_isready -U faulkner
   docker-compose exec postgres psql -U faulkner -l
   ```

3. **Check credentials:**
   ```bash
   # Review docker-compose.yml environment variables
   cat docker/docker-compose.yml | grep -A 5 POSTGRES
   ```

**Solutions:**

**FalkorDB connection issues:**
```bash
# Restart FalkorDB
docker-compose restart falkordb

# If corrupted, rebuild
docker-compose stop falkordb
docker volume rm faulkner-db_falkordb_data
docker-compose up -d falkordb
```

**PostgreSQL authentication:**
```bash
# Reset password
docker-compose exec postgres psql -U postgres -c "ALTER USER faulkner WITH PASSWORD 'new_password';"

# Update docker-compose.yml
```

**Database initialization:**
```bash
# If database not created
docker-compose exec postgres psql -U postgres -c "CREATE DATABASE faulkner_db;"
docker-compose exec postgres psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE faulkner_db TO faulkner;"
```

**Prevention:**
- Don't modify database credentials without updating all services
- Use environment variables for configuration
- Regular database backups
- Test database connections after changes

---

## Getting Help

**Documentation:**
- [User Guide](USER_GUIDE.md) - Complete usage instructions
- [System Status](SYSTEM_STATUS.md) - Current state and architecture
- [Tech Stack](TECH_STACK.md) - Technology details

**Quick Validation:**
```bash
cd ~/projects/faulkner-db/docker
./validate-autostart.sh
```

**Logs:**
```bash
# All services
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Specific service
docker-compose logs -f visualization
```

**Health Check:**
```bash
curl http://localhost:8082/health
```

**Emergency Reset:**
```bash
# CAUTION: This deletes all data!
cd ~/projects/faulkner-db/docker
docker-compose down -v
docker-compose up -d
./validate-autostart.sh
```

---

**Last Updated:** 2025-11-08  
**Version:** 1.0.0