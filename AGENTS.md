# Faulkner DB — AGENTS.md (router / the map)

You are the generic agent. Reading this makes you the **Faulkner DB** agent.
On entry: read this map → route to the area for the task → load ONLY that area's Inputs.

## What this is
A temporal knowledge-graph "architectural memory" system exposed as an MCP server: stores
**Decisions / Patterns / Failures** in a graph, does hybrid (graph + vector) search, and runs
NetworkX structural analysis (gaps, bridges, communities). Python 3.9–3.12, runs as Docker
containers (FalkorDB + Postgres + ChromaDB) on host `ai-utility`. **The live server is
`mcp_server/server_fastmcp.py`** (FastMCP, registers all 13 tools). A legacy stdio path
(`mcp_server/server.py` + `mcp_server/mcp_tools.py`, 7-tool subset) coexists — not the live path.

## Areas (route by task — load Inputs, skip the rest)

| If the task is about… | Read (Inputs) | Skip |
|---|---|---|
| **MCP tools / server behaviour** (add_decision, query_decisions, add_pattern, add_failure, find_related, detect_gaps, get_timeline, find_knowledge_gaps, find_influential_patterns, find_knowledge_communities, find_bridge_patterns, get_graph_summary, query_patterns_semantic) | `mcp_server/server_fastmcp.py` (live; thin tool wrappers that delegate to →) `mcp_server/mcp_tools.py` (shared tool impls + input validation), `common/schemas.py` (input models: DecisionInput/PatternInput/FailureInput), `core/knowledge_types.py` (storage models Decision/Pattern/Failure — also validate on construct), `mcp_server/utils.py` | legacy `mcp_server/server.py` (stdio entrypoint), **unused dup** `mcp_server/schemas.py`, root archival `*.md` |
| **Legacy stdio entrypoint** (only when explicitly asked) | `mcp_server/server.py`, `mcp_server/mcp_tools.py` (TOOL_REGISTRY) | the FastMCP server |
| **Graph store / client + data models** (FalkorDB adapter) | `core/graphiti_client.py` (FalkorDBAdapter, GraphitiClient, MetricsCollector), `core/knowledge_types.py` (Decision/Pattern/Failure), `core/config_loader.py` | `data/` contents |
| **Hybrid search** (graph+vector fusion, reranking) | `core/hybrid_search.py` (reciprocal_rank_fusion, crossencoder_reranker, query_decomposer, extract_temporal) | `data/embeddings/`, `data/chroma/` contents |
| **Structural graph analysis** (gaps/bridges/communities/influence) | `core/gap_detector.py` (GapDetector, GapType, Severity, GapReport), `mcp_server/networkx_analyzer.py` | search/storage dirs |
| **Ingestion / bulk import** (agent-genesis, chromadb extraction) | `ingestion/` (`agent_genesis_*.py`, chromadb extractor scripts), `mcp_server/ingestion_guards.py` | `ingestion/*.log`, `ingestion/*_checkpoint.json` |
| **Deploy / Docker / infra** | `docker/docker-compose.yml`, `docker/Dockerfile`, `docker/redis.conf`, `config/graphiti_config.yaml`, `config/mcp_config.json` | `docker/data/`, `docker/backups/`, source dirs |
| **Ops / health / migrations / sync** | `scripts/` (`health_check.py`, `backup-faulkner.sh`, `migrate_*.py`, `faulkner-health-graph.{service,timer}`) | `logs/` |
| **Tests** | `tests/`, `comprehensive_mcp_test.py` (root) | source dirs unless tracing a failure |

## Verbs
- `pickup`  → read `_pickup-handoff.md` §pickup, then route to the named area.
- `handoff` → read `_pickup-handoff.md` §handoff.

## Naming conventions (locate files, don't grep blindly)
- Root `*.md` (README, CHANGELOG, CONTRIBUTING, QUICKSTART, USAGE_GUIDE, FAULKNER-DB-CHEATSHEET, GITHUB_CLEANUP_HANDOFF — ~59KB/8 files) = **archival, skip by default**.
- `docs/` (QUERY_GUIDE, TROUBLESHOOTING, TECH_STACK, ROADMAP, …) = extended guides; read only when explicitly needed.
- `logs/`, `*.log`, `ingestion/*_checkpoint.json` = runtime logs/checkpoints; never read to understand code.
- `data/` (`knowledge.db`, `scanner_tracking.db`, `chroma/`, `embeddings/`), `dev_context_storage/*.db`, `docker/data/`, `docker/backups/`, `backups/` = **runtime graph/vector stores — DATA not code. Never read to understand the system, never delete.**
- `*.backup.<ts>` (e.g. `visualization/api_routes.py.backup.*`), `*:Zone.Identifier`, `__pycache__/`, `venv/` = stale/generated; ignore.

## Fallback law
Task not on this map → ask which area, or stay here. **Never bulk-read the root archival docs or
wander the `data/` / `logs/` / `ingestion/` runtime trees.** Edits under `mcp_server/**` or
`core/**` require restarting the faulkner-db container/gateway to take effect. Wrong project →
return to `../AGENTS.md` (workspace root).
