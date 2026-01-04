# Faulkner-DB GitHub Cleanup - Handoff Summary

**Date**: 2026-01-04
**Status**: IN PROGRESS (~60% complete)
**Objective**: Remove personal info, make paths auto-detecting, ensure professional GitHub presence

---

## What Was Accomplished

### 1. Claude Plan Ingestion System (NEW FEATURE)
Created a complete system to extract knowledge from Claude Code plan files:

| File | Purpose |
|------|---------|
| `ingestion/claude_plan_extractor.py` | Parses Claude plans, extracts decisions/patterns/failures |
| `ingestion/serena_memory_sync.py` | Syncs to Serena memories per-project |
| `scripts/scheduled_plan_ingestion.sh` | Runner script |
| `scripts/setup_plan_scheduler.sh` | Setup script (auto-generates service files) |
| `scripts/plan-ingestion.service` | Systemd service template |
| `scripts/plan-ingestion.timer` | Bi-weekly timer |

**Initial extraction completed**: 178 plans → 78 decisions, 59 patterns, 26 failures, 44 Serena memories

### 2. Auto-Detection Updates (COMPLETED)

These files now use auto-detection instead of hardcoded paths:

```python
# Pattern used in Python files:
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
DEFAULT_DB_PATH = DATA_DIR / 'scanner_tracking.db'
DEFAULT_PLANS_DIR = Path.home() / '.claude' / 'plans'
PROJECTS_DIR = Path(os.environ.get('FAULKNER_PROJECTS_DIR', PROJECT_ROOT.parent))
```

**Updated files:**
- `ingestion/claude_plan_extractor.py` ✅
- `ingestion/serena_memory_sync.py` ✅
- `ingestion/markdown_scanner.py` ✅
- `ingestion/scanner_config.yaml` ✅ (uses "auto" placeholder)
- `ingestion/scanner_config_priority.yaml` ✅ (uses ~ for home)
- `scripts/setup_plan_scheduler.sh` ✅ (auto-generates service with correct paths)
- `scripts/scheduled_plan_ingestion.sh` ✅ (already used $HOME)

---

## What Remains

### Files Still Containing Personal Paths

Run this to find them:
```bash
cd /path/to/faulkner-db
git ls-files | xargs grep -l "$HOME\|/mnt/c/Users/Aldwin" 2>/dev/null
```

**26 files need updating:**

#### Documentation (replace with generic paths):
- `QUICKSTART.md`
- `docker/ZERO_FRICTION_SETUP.md`
- `docs/MCP_FIX_2025-11-08.md`
- `docs/QUERY_GUIDE.md`
- `docs/TROUBLESHOOTING.md`
- `docs/chromadb_extraction_report.md`
- `ingestion/CHROMADB_EXTRACTOR_MANIFEST.txt`
- `ingestion/CHROMADB_EXTRACTOR_README.md`
- `ingestion/DEPLOYMENT_GUIDE.md`
- `ingestion/QUICK_START_CHROMADB.md`

#### Python Scripts (add auto-detection):
- `ingestion/agent_genesis_chromadb_extractor.py`
- `ingestion/simple_markdown_extractor.py`
- `mcp_server/server.py`
- `mcp_server/server_fastmcp.py`

#### Shell Scripts (use $HOME, $PROJECT_DIR):
- `scripts/backup-faulkner.sh`
- `scripts/complete_ingestion.sh`
- `scripts/comprehensive_validation.sh`
- `scripts/daily_sync.sh`
- `scripts/final_validation.sh`
- `scripts/health-check-faulkner.sh`
- `scripts/relationship_quality.sh`
- `scripts/sync_agent_genesis_docker.sh`
- `test_mcp_startup.sh`

#### Config/Other:
- `claude_desktop_config.json` (example config - use /path/to placeholders)
- `npm/bin/setup.js`

### Files to Delete
```bash
rm README.md.backup.1765254807765
rm README.md.backup.1766108896319
rm mcp_server/server.py.backup
```

### Verify .gitignore
Ensure these are NOT tracked:
- `.serena/` (project memories)
- `.claude/` (local settings)
- `backups/`
- `data/`
- `logs/`

---

## Pattern Replacements

| Find | Replace With |
|------|--------------|
| `/path/to/faulkner-db` | `$PROJECT_ROOT` or `/path/to/faulkner-db` |
| `/path/to/projects` | `$PROJECTS_DIR` or `/path/to/projects` |
| `$HOME/.claude` | `$HOME/.claude` or `~/.claude` |
| `$HOME` | `$HOME` |
| `/mnt/c/Users/Aldwin` | `$HOME` (remove Windows-specific paths) |
| `platano` (username) | `$USER` or remove |

---

## Commit Strategy

After all updates:
```bash
git add -A
git diff --staged | grep -i "platano\|aldwin"  # Verify no personal info
git commit -m "chore: remove personal paths, add auto-detection for portability"
git push
```

---

## Quick Resume Command

To continue this work:
```
Review the faulkner-db GitHub cleanup. Files still need personal path removal.
Check GITHUB_CLEANUP_HANDOFF.md for status. Complete the remaining 26 files,
delete backup files, and commit.
```
