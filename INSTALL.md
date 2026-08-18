# Installation

Faulkner DB is a temporal knowledge-graph MCP server (FalkorDB + PostgreSQL, Docker
Compose). Pick the section for your situation.

## For humans

**Prerequisites**: Python 3.9–3.12, Docker + Docker Compose, `ssh` (if pointing at a
remote host instead of self-hosting).

**1. Clone and install Python deps**

```bash
git clone https://github.com/platano78/faulkner-db.git
cd faulkner-db
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

**2. Start the stack**

Self-hosted (Docker on this machine):

```bash
cd docker
cp .env.example .env
# edit .env, set POSTGRES_PASSWORD and FALKORDB_PASSWORD
docker-compose up -d
```

Or point at an existing remote host running the stack already — skip `docker-compose up`
and set `FALKORDB_HOST` / `FALKORDB_PORT` / `FALKORDB_PASSWORD` to that host's values
wherever the MCP server or scripts run.

**3. Create the health/backup credentials file**

Scripts under `scripts/` (health checks, backups) read credentials from a file outside
the repo so they don't depend on `docker/.env` or docker-compose internal hostnames:

```bash
mkdir -p ~/.config/faulkner-health
cat > ~/.config/faulkner-health/env <<'EOF'
FALKORDB_HOST=192.168.1.79
FALKORDB_PORT=6380
FALKORDB_PASSWORD=YOUR_PASSWORD_HERE
EOF
chmod 600 ~/.config/faulkner-health/env
```

cron runs without an interactive `ssh-agent`, so the scripts authenticate to the DB
host with a dedicated passwordless deploy key instead of your regular identity:

```bash
ssh-keygen -t ed25519 -N "" -f ~/.config/faulkner-health/ssh_key
ssh-copy-id -i ~/.config/faulkner-health/ssh_key.pub <DB_HOST>
```

`FAULKNER_SSH_KEY` overrides the default key path (`~/.config/faulkner-health/ssh_key`)
if you need a non-default location.

**4. Schedule health checks and backups**

Cron (add via `crontab -e`):

```
0 3 * * * /path/to/faulkner-db/scripts/backup-faulkner.sh
*/5 * * * * /path/to/faulkner-db/scripts/health-check-faulkner.sh
```

Or the systemd user timer for the graph health check (runs every 6 hours):

```bash
cp scripts/faulkner-health-graph.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now faulkner-health-graph.timer
```

**5. Verify**

```bash
scripts/health-check-faulkner.sh; echo "exit=$?"   # expect exit=0
tail -3 /tmp/faulkner-health.log                    # expect an OK line
venv/bin/python scripts/health_check.py             # human-readable graph report
```

## For agentic coders (Claude Code, Codex, etc.)

`AGENTS.md` in this repo is the canonical router — **read it first**, before touching
any file. It maps tasks to the exact files to load and tells you what to skip.

Deterministic install:

```bash
git clone https://github.com/platano78/faulkner-db.git && cd faulkner-db
python3 -m venv venv && venv/bin/pip install -r requirements.txt
```

Machine-checkable verification gates:

```bash
venv/bin/python3 --version                          # expect 3.9–3.12
bash -n scripts/backup-faulkner.sh                   # expect no output, exit 0
bash -n scripts/health-check-faulkner.sh             # expect no output, exit 0
```

MCP registration (pointing at the live gateway on `ai-utility`):

```json
{
  "mcpServers": {
    "faulkner-db": {
      "url": "http://192.168.1.79:8070/mcp"
    }
  }
}
```

A self-hosted deployment substitutes its own host in place of `192.168.1.79:8070`.

Warnings:
- `docker/.env` and anything under `data/` (`knowledge.db`, `scanner_tracking.db`,
  `chroma/`, `embeddings/`) are runtime data, not code — never read them to understand
  the system, never delete them.
- Edits under `mcp_server/**` or `core/**` require a container/gateway restart on the
  host running the stack to take effect.

## For MCP-consumer agents (e.g. Hermes)

There is nothing to install — connect to the running gateway:

```
http://192.168.1.79:8070/mcp
```

The gateway exposes 13 tools, grouped by purpose (see `mcp_server/server_fastmcp.py`
for the authoritative list):

- **Write**: `add_decision`, `add_decision_json`, `add_pattern`, `add_failure`
- **Query**: `query_decisions`, `query_patterns_semantic`, `find_related`, `get_timeline`
- **Structural analysis**: `detect_gaps`, `find_influential_patterns`,
  `find_knowledge_communities`, `find_bridge_patterns`, `get_graph_summary`

Usage contract:
- Prefer `add_decision_json` over `add_decision` for long or multiline content — some
  harnesses' tool-call parsers drop the second parameter on long/multiline values.
- `query_decisions` is the curated high-signal lane; `query_patterns_semantic` is noisy
  pending a prune.
- `description` clamps at 2000 chars and `rationale` at 5000 chars; overflow is never
  rejected, it's preserved to `data/overflow_capture.jsonl` (clamp-and-preserve).
