# Faulkner DB - Docker Desktop Usage Guide

## Prerequisites

- **Docker Desktop for Windows** installed and running
- **WSL2 backend** enabled in Docker Desktop settings
- **WSL2 integration** enabled for Ubuntu distribution

## Quick Start

### From WSL Terminal

```bash
cd ~/projects/faulkner-db/docker
docker-compose up -d
```

Access visualization: http://localhost:8082

### From Windows (Double-Click)

1. Navigate to `~/projects/faulkner-db/docker/` in Windows Explorer
2. Double-click `start-faulkner.bat` to start services
3. Double-click `stop-faulkner.bat` to stop services

### From Docker Desktop GUI

1. Open Docker Desktop
2. Navigate to **Containers** section
3. Find the **faulkner-db** project group
4. Click **Start** or **Stop** buttons
5. View logs and health status in the GUI

## Port Mappings

| Service | Port | Purpose |
|---------|------|----------|
| FalkorDB | 6379 | Redis protocol |
| FalkorDB UI | 8081 | Web interface |
| PostgreSQL | 5432 | Database connection |
| Visualization | 8082 | Web visualization |

## Volume Locations

- **FalkorDB data**: `~/projects/faulkner-db/docker/data/falkordb`
- **PostgreSQL data**: `~/projects/faulkner-db/docker/data/postgres`

## Common Commands

### Start Services
```bash
cd ~/projects/faulkner-db/docker
docker-compose up -d
```

### Stop Services
```bash
cd ~/projects/faulkner-db/docker
docker-compose down
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f visualization
docker-compose logs -f falkordb
docker-compose logs -f postgres
```

### Check Status
```bash
# Using docker-compose
docker-compose ps

# Using monitoring script
./status.sh
```

### Rebuild Images
```bash
# Rebuild visualization service
docker-compose build visualization

# Rebuild and restart
docker-compose up -d --build
```

### Reset Data (DANGER!)
```bash
# Stop services and remove volumes
docker-compose down -v

# Restart with fresh databases
docker-compose up -d
```

## Troubleshooting

### Services Don't Start

1. **Check Docker Desktop is running**
   - Look for Docker icon in system tray
   - Should show "Docker Desktop is running"

2. **Check WSL2 integration**
   - Docker Desktop → Settings → Resources → WSL Integration
   - Enable Ubuntu distribution

3. **Check port conflicts**
   ```bash
   # From Windows PowerShell
   netstat -ano | findstr "8082 6379 5432"
   ```

4. **View service logs**
   ```bash
   docker-compose logs [service_name]
   ```

### Visualization Can't Connect to FalkorDB

1. **Verify network**
   ```bash
   docker network inspect faulkner-network
   ```

2. **Test service connectivity**
   ```bash
   docker-compose exec visualization ping falkordb
   ```

3. **Check environment variables**
   ```bash
   docker-compose config
   ```

### Data Doesn't Persist

1. **Check volumes**
   ```bash
   docker volume ls | grep faulkner
   ```

2. **Verify volume mounts**
   ```bash
   docker inspect faulkner-db-falkordb | grep Mounts -A 20
   ```

3. **Don't use `-v` flag when stopping**
   ```bash
   # ❌ DON'T DO THIS (removes volumes)
   docker-compose down -v
   
   # ✅ DO THIS (preserves data)
   docker-compose down
   ```

### Health Checks Failing

1. **Check health status**
   ```bash
   docker inspect faulkner-db-falkordb --format='{{.State.Health.Status}}'
   docker inspect faulkner-db-postgres --format='{{.State.Health.Status}}'
   docker inspect faulkner-db-visualization --format='{{.State.Health.Status}}'
   ```

2. **Wait for startup**
   - Services have a 40-second start period
   - Health checks run every 30 seconds
   - May take 1-2 minutes to show "healthy"

3. **View health check logs**
   ```bash
   docker inspect faulkner-db-falkordb | grep -A 10 Health
   ```

## Gaming Workflow

Optimized for minimal resource usage when gaming:

### Before Gaming
```bash
cd ~/projects/faulkner-db/docker
docker-compose down
```

### After Gaming
```bash
cd ~/projects/faulkner-db/docker
docker-compose up -d
```

Data persists across restarts!

## Resource Limits

Configured to leave headroom for gaming:

- **FalkorDB**: 2GB max memory, 2 CPU cores max
- **PostgreSQL**: 1GB max memory
- **Visualization**: 512MB max memory, 2 CPU cores max

Total max usage: ~3.5GB RAM, 4 CPU cores

## Access URLs

Once services are running:

- **Network Graph**: http://localhost:8082/static/index.html
- **Timeline View**: http://localhost:8082/static/timeline.html
- **Dashboard**: http://localhost:8082/static/dashboard.html
- **Gap Analysis**: http://localhost:8082/static/gaps.html
- **API Health**: http://localhost:8082/health
- **FalkorDB UI**: http://localhost:8081

## Updating Configuration

Edit environment variables in `docker/.env`, then:

```bash
docker-compose down
docker-compose up -d
```

## Advanced

### Auto-Start on Windows Boot

1. Press `Win+R`, type `shell:startup`
2. Create shortcut to `start-faulkner.bat`
3. Services will start when Windows boots

### Desktop Shortcuts

**Start Faulkner DB**:
- Target: `"C:\Windows\System32\cmd.exe" /c "wsl.exe bash -c 'cd ~/projects/faulkner-db/docker && docker-compose up -d && echo Services started! && docker-compose ps && read -p Press_Enter'"`

**Stop Faulkner DB**:
- Target: `"C:\Windows\System32\cmd.exe" /c "wsl.exe bash -c 'cd ~/projects/faulkner-db/docker && docker-compose down && echo Services stopped! && read -p Press_Enter'"`
