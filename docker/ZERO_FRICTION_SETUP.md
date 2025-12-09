# Faulkner DB - Zero-Friction Auto-Start Setup

## The Goal

**"If Docker Desktop is running, Faulkner DB is running"**

No manual startup commands. No batch files to remember. Just start Docker Desktop and go.

---

## How It Works

Faulkner DB uses Docker's built-in `restart: unless-stopped` policy. This means:

1. When Docker Desktop starts → Containers automatically start
2. When you quit Docker Desktop → Containers stop gracefully
3. When you restart Docker Desktop → Containers automatically start again

**No manual intervention required!**

---

## Initial Setup (One-Time)

### Step 1: Start Containers (One Time Only)

```bash
cd ~/projects/faulkner-db/docker
docker-compose up -d
```

This creates and starts the containers. You only need to do this ONCE.

### Step 2: Configure Docker Desktop Settings

Open Docker Desktop:

1. Click **Settings** (gear icon)
2. Go to **General** tab
3. Enable **"Start Docker Desktop when you log in"**
4. Click **Apply & Restart**

### Step 3: Verify Auto-Start Works

Test the auto-start functionality:

```bash
cd ~/projects/faulkner-db/docker
./validate-autostart.sh
```

You should see:
```
✅ All systems operational!

Auto-start is configured correctly.
When you quit and restart Docker Desktop,
containers will automatically start.
```

---

## Your Daily Workflow

### Before Gaming Session

**Just quit Docker Desktop:**

1. Right-click Docker Desktop icon in system tray
2. Click **"Quit Docker Desktop"**
3. Done!

Containers stop gracefully. No data loss.

### After Gaming Session

**Just launch Docker Desktop:**

1. Click Docker Desktop icon
2. Wait 30-60 seconds for containers to start
3. Done!

Containers automatically start. All data persisted.

### Check Status Anytime

```bash
cd ~/projects/faulkner-db/docker
./validate-autostart.sh
```

Or visit: http://localhost:8082/health

---

## What NOT to Do

### ❌ NEVER Use `docker-compose down`

```bash
# ❌ DON'T DO THIS - Removes containers, breaks auto-start
docker-compose down
```

**Why:** This REMOVES containers entirely. Removed containers can't auto-start.

**Use instead:** Just quit Docker Desktop from the system tray.

### ✅ If You Accidentally Ran `docker-compose down`

**Fix:** Just run `docker-compose up -d` again to recreate containers.

---

## Advanced: When to Use `docker-compose stop`

If you want to stop containers but keep Docker Desktop running:

```bash
cd ~/projects/faulkner-db/docker
docker-compose stop
```

To restart:
```bash
docker-compose start
```

Or just restart Docker Desktop (containers will auto-start).

---

## How Docker Desktop Auto-Start Works

### The Mechanism

1. **Restart Policy in docker-compose.yml:**
```yaml
services:
  falkordb:
    restart: unless-stopped  # ← This is the magic
```

2. **What `unless-stopped` Means:**
   - Container auto-starts when Docker Desktop starts
   - Container does NOT restart if you explicitly stopped it
   - Container auto-restarts if it crashes
   - Perfect for your gaming workflow!

3. **How It Differs from `always`:**
```yaml
restart: always          # Restarts even if you stopped it manually
restart: unless-stopped  # Respects manual stops (BETTER)
```

### Container States Explained

**Running State (Good for Auto-Start):**
- Container exists and is running
- Docker Desktop will auto-restart it

**Stopped State (Good for Auto-Start):**
- Container exists but is stopped
- Docker Desktop will auto-restart it

**Removed State (Breaks Auto-Start):**
- Container doesn't exist
- Docker Desktop can't restart what doesn't exist!
- Happens when you run `docker-compose down`

---

## Docker Desktop Settings Checklist

Verify these settings in Docker Desktop:

### Settings → General
- ✅ **Start Docker Desktop when you log in** (CRITICAL)
- ✅ Use the WSL 2 based engine
- ⬜ Open Docker Dashboard when Docker Desktop starts (optional, off is cleaner)

### Settings → Resources → WSL Integration
- ✅ Enable integration with my default WSL distro
- ✅ Enable integration with additional distros: Ubuntu

### Settings → Resources → Advanced
- Memory: At least 4GB (recommended: 8GB)
- CPUs: At least 4
- Swap: 1GB minimum

---

## Testing Auto-Start

### Test Procedure

1. **Ensure containers are running:**
```bash
cd ~/projects/faulkner-db/docker
docker-compose ps
# All should show "Up (healthy)"
```

2. **Quit Docker Desktop:**
   - Right-click Docker Desktop icon
   - Click "Quit Docker Desktop"
   - Wait 10 seconds

3. **Restart Docker Desktop:**
   - Click Docker Desktop icon
   - Wait 30-60 seconds

4. **Verify containers auto-started:**
```bash
cd ~/projects/faulkner-db/docker
./validate-autostart.sh
```

### Expected Results

After Docker Desktop restarts:

```
NAME                        STATUS              PORTS
faulkner-db-falkordb        Up (healthy)        0.0.0.0:6379->6379/tcp
faulkner-db-postgres        Up (healthy)        0.0.0.0:5432->5432/tcp
faulkner-db-visualization   Up (healthy)        0.0.0.0:8082->8082/tcp
```

✅ All services automatically running!

---

## Troubleshooting

### Containers Don't Auto-Start After Docker Desktop Restart

**Diagnosis:**
```bash
cd ~/projects/faulkner-db/docker
docker ps -a | grep faulkner
```

**If you see containers in "Exited" state:**
- ✅ This is normal during startup
- Wait 30-60 seconds, they should transition to "Up"

**If you don't see any containers:**
- ❌ Containers were removed (probably ran `docker-compose down`)
- **Fix:** Run `docker-compose up -d`

**If containers show "Up" but not "healthy":**
- ⏳ Still starting up
- Wait another 30 seconds
- Check logs: `docker-compose logs -f`

### Restart Policy Not Working

**Check restart policy:**
```bash
docker inspect faulkner-db-falkordb | grep -A 5 "RestartPolicy"
```

**Should show:**
```json
"RestartPolicy": {
    "Name": "unless-stopped",
    "MaximumRetryCount": 0
}
```

**If it shows `"Name": "no"`:**
- Update docker-compose.yml (should already have `restart: unless-stopped`)
- Recreate containers: `docker-compose up -d --force-recreate`

### Docker Desktop Not Starting on Windows Boot

**Check Windows Task Scheduler:**
1. Press `Win+R`, type `taskschd.msc`, press Enter
2. Navigate to: Task Scheduler Library → Docker Desktop
3. Verify "Docker Desktop Scheduled Task" is **Enabled**

**If task doesn't exist or is disabled:**
- Reinstall Docker Desktop
- Or manually enable "Start Docker Desktop when you log in" in Docker Desktop settings

---

## Data Persistence

### Where Data is Stored

```bash
~/projects/faulkner-db/docker/data/
├── falkordb/    # Graph database data
└── postgres/    # Metadata storage
```

### Data Persists Across:

✅ Docker Desktop restarts  
✅ Container restarts  
✅ Windows reboots  
✅ `docker-compose stop` / `docker-compose start`  

### Data is LOST if:

❌ You run `docker-compose down -v` (removes volumes)  
❌ You delete the `data/` directory  
❌ You run `docker volume rm` commands  

**Bottom line:** Just quit/restart Docker Desktop. Never use `docker-compose down`.

---

## Performance Optimization for WSL2

For best performance on Windows with WSL2:

### 1. Keep Project in WSL2 Filesystem

✅ Current location (GOOD): `/home/platano/projects/faulkner-db`  
❌ Avoid: `/mnt/c/Users/...` (slow cross-filesystem access)

### 2. Configure WSL2 Memory Limits

Create/edit `C:\Users\YourUsername\.wslconfig` in Windows:

```ini
[wsl2]
memory=8GB
processors=4
swap=2GB
localhostForwarding=true
```

Restart WSL after changes:
```powershell
# In Windows PowerShell (as Administrator)
wsl --shutdown
```

### 3. Docker Desktop Resource Allocation

Settings → Resources → Advanced:
- **Memory:** 8GB (leave headroom for Windows and gaming)
- **CPUs:** 4-6 cores
- **Swap:** 1-2GB

---

## Summary

### What You Have Now:

✅ **Auto-start on Docker Desktop launch** via `restart: unless-stopped`  
✅ **Optimized startup order** with health check dependencies  
✅ **Log rotation** to prevent disk bloat  
✅ **WSL2-optimized volume mounts** with delegated consistency  
✅ **Validation script** to test auto-start functionality  
✅ **Data persistence** across restarts  

### Your Zero-Friction Workflow:

1. **Gaming time?** → Quit Docker Desktop  
2. **Back to work?** → Launch Docker Desktop  
3. **That's it!**  

No commands. No scripts. No friction.

### Access Your Services:

- **Network Graph:** http://localhost:8082/static/index.html
- **Timeline:** http://localhost:8082/static/timeline.html
- **Dashboard:** http://localhost:8082/static/dashboard.html
- **API Health:** http://localhost:8082/health
- **FalkorDB UI:** http://localhost:8081

### Need Help?

Run the validation script:
```bash
cd ~/projects/faulkner-db/docker
./validate-autostart.sh
```

Check detailed logs:
```bash
docker-compose logs -f
```

See full documentation:
```bash
cat DOCKER_USAGE.md
```

---

## Enjoy Zero-Friction Development! 🎯
