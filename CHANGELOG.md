# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.8.0] - 2026-08-18

### Added

- **`add_decision_json` tool (13th tool)** — records a decision from a single JSON
  string payload, routing around client-side tool-call parsers that drop a second
  parameter on long/multiline values.
- **Clamp-and-preserve on `add_decision` / `add_failure`** — over-length text is
  never rejected: it is clamped to the schema caps and the full original preserved
  to `data/overflow_capture.jsonl`.
- **`INSTALL.md`** — installation guide with three self-contained lanes: humans,
  agentic coders (AGENTS.md routing + machine-checkable gates + MCP registration),
  and MCP-consumer agents connecting to the gateway.
- README architecture and knowledge-graph data-model diagrams (Mermaid, replacing
  the stale ASCII art).

### Fixed

- **`scripts/backup-faulkner.sh` rewritten remote-first.** Since the stack moved to
  a remote Docker host, the nightly backup had silently archived a months-old local
  RDB and empty postgres dumps while logging success. It now triggers `BGSAVE` over
  ssh, polls `LASTSAVE`, streams the RDB, and verifies size + `REDIS` magic bytes —
  hard-failing the FalkorDB lane on any mismatch. Uses a dedicated agentless deploy
  key (`~/.config/faulkner-health/ssh_key`, `FAULKNER_SSH_KEY` override) because
  cron has no ssh-agent; the password is shell-quoted before crossing ssh's
  argument flattening.
- **`scripts/health-check-faulkner.sh` rewritten for the remote host** — remote
  reachability probe (no restart storms), remote container checks/starts, and a
  redis `PING` over ssh, instead of erroring every 5 minutes against a local
  docker daemon that no longer runs the stack.
- `config/graphiti_config.yaml` now points at the live stack host instead of
  `localhost` (env vars still take priority).
- Documentation counts corrected to the live 13-tool surface (README, QUICKSTART,
  TECH_STACK); USAGE_GUIDE's early validation report marked as historical.

### Removed

- `scripts/daily_sync.sh` — superseded legacy ingestion lane (its ingestion branch
  was a placeholder); the live daily pipeline is the Agent Genesis sync's
  incremental Faulkner relationship extractor plus the remote maintenance timer.

## [1.7.4] - 2026-06-22

### Changed

- **Decision input ceilings raised: `description` 1000 → 2000, `rationale`
  2000 → 5000.** The old caps were too tight for rich architectural decisions
  (which routinely landed at ~1100–1300 chars and were rejected before any
  write) and were schema-level `Field(max_length)` constraints, not limits of
  the underlying FalkorDB/Postgres storage. The new ceilings are applied in
  lockstep to **both** Pydantic gates that `add_decision` runs through — the
  `DecisionInput` input model (`common/schemas.py`) and the `Decision` storage
  model (`core/knowledge_types.py`), which re-validates on construct with the
  identical cap. Raising only one would move the `string_too_long` failure from
  the input gate to the storage gate without removing it. The unused duplicate
  `mcp_server/schemas.py` is bumped too for consistency. `description` is kept
  tighter (2000) than `rationale` (5000) by design: it is the field embedded for
  semantic decision-search, where an over-long description dilutes the vector and
  degrades retrieval.

### Fixed

- **`AGENTS.md` routing corrected.** The MCP-tools row had listed the dead,
  imported-by-nobody `mcp_server/schemas.py` as the live schema input and placed
  the live `mcp_server/mcp_tools.py` in the Skip column as legacy — the exact
  mis-routing that points decision-cap/validation work at a no-op file. It now
  points at the real live chain: `server_fastmcp.py` → `mcp_tools.py` →
  `common/schemas.py` + `core/knowledge_types.py`.

## [1.7.3] - 2026-06-12

### Fixed

- **`query_decisions` now scopes to `Decision` nodes and honors `limit`**
  (`core/hybrid_search.py`, `mcp_server/mcp_tools.py`). Two defects survived the
  v1.7.2 hygiene pass:
  - **No label scoping.** `graph_traversal()` issued `MATCH (n) WHERE
    n.description CONTAINS ...` across *every* node label, so `query_decisions`
    searched the whole graph — curated `Decision` nodes competed for slots
    against `Pattern`/`Failure` nodes (the ~90% similarity-glue noise reduced in
    v1.7.2 still diluted the decisions lane). The label predicate is now pushed
    into the Cypher query: `graph_traversal()`, `parallel_executor()`, and
    `hybrid_search()` accept a `node_label` argument, and `query_decisions`
    passes `node_label="Decision"`. Filtering happens *in* the search, not as a
    post-filter on the result set, so selective scoping no longer costs recall.
  - **`limit` was capped at 15.** `hybrid_search()` hardcoded `top_k=15` in the
    cross-encoder reranker, so `query_decisions(limit=50)` silently returned
    ≤15. `top_k` is now threaded end-to-end (call site → `hybrid_search` →
    `parallel_executor` → per-keyword Cypher `LIMIT`), and the reranker honors
    the requested `limit`.
  - The in-memory result `CACHE` is now keyed on `(query, node_label, top_k)`
    instead of `query` alone, so scoped and unscoped searches with the same text
    no longer collide.

## [1.7.2] - 2026-06-09

### Fixed

- **Relationship extractor: sane similarity defaults** (`ingestion/relationship_extractor.py`).
  A 2026-06-09 graph audit found ~90% of edges were generic similarity glue (5,155
  SEMANTICALLY_SIMILAR edges across 249 nodes — 60:1 edge:node ratio). Root causes:
  the `run()` function and `--threshold` CLI flag hardcoded `0.7`, overriding the
  module-level `SEMANTIC_SIMILARITY_THRESHOLD` env default of `0.85`; FAISS returned
  up to 50 neighbors per node with no per-node cap; and near-identical pairs created
  redundant edges instead of being flagged. Fixed:
  - `run()` and `--threshold` now default to `SEMANTIC_SIMILARITY_THRESHOLD` env
    (fallback `0.85`) instead of `0.7`.
  - New `MAX_SIMILAR_EDGES_PER_NODE` env (default `5`) caps similarity edges per
    source node.
  - Pairs scoring `>= 0.97` are logged as dedup candidates
    (`near_duplicates_skipped` in stats) rather than written as edges.

- **`query_decisions` output hygiene** (`core/hybrid_search.py`,
  `mcp_server/mcp_tools.py`, `mcp_server/server_fastmcp.py`,
  `mcp_server/mcp_server.py`). Three defects present since the initial
  vector-search stub:
  - `vector_search()` fabricated a mock `"Vector match for '<query>'"` result left
    over from before a real vector index existed; it now returns an empty list until
    a real index is available.
  - Graph results with empty or whitespace-only content passed through to output;
    `hybrid_search()` now filters them after rank fusion.
  - `query_decisions` accepted no `limit` parameter — callers that passed one
    received a pydantic `"unexpected keyword argument"` error. Both entry points
    (`server_fastmcp.py` and `mcp_server.py`) now accept `limit` (clamped 1–50,
    default `15`).

## [1.7.1] - 2026-05-20

### Fixed

- **FastMCP wrappers now forward `source="manual"`** on `add_decision`,
  `add_pattern`, and `add_failure` (`mcp_server/server_fastmcp.py`). The
  v1.7.0 ingestion guard requires `source` to be `"manual"` or
  `"reviewed_automated"`, but the MCP boundary stripped the field before
  calling the impl functions — every MCP-originated write was rejected
  with `missing_or_invalid_source`. MCP tool calls from a live agent
  conversation are by definition human-reviewed, so the wrappers now
  pass `source="manual"` explicitly. Verified end-to-end against all
  three wrappers after a gateway restart.

## [1.7.0] - 2026-05-06

### Removed (mass cleanup)

- **10,781 polluted nodes purged.** Graph went from 11,018 → 237 nodes
  (-97.8%) and 113,868 → 5,241 edges (-95.4%). Two pollution sources
  identified by audit:
  - 586 MKG playbook Patterns named `playbook-${category}-${unix_ms}` —
    migrated to MKG's own SQLite store before deletion (manifest in
    `logs/migrate_manifest_*.json`).
  - 10,195 nodes (906 Patterns + 9,139 Failures + 150 Decisions) with
    `source_files` containing `agent-genesis` — auto-extracted
    conversation fragments, deleted (raw conversations remain in Agent
    Genesis itself).
- Both purges took a server-side Redis BGSAVE plus a paginated local
  JSON dump before any mutation; reports in `logs/purge_report_*.json`.

### Added

- **Ingestion guards** (`mcp_server/ingestion_guards.py`) reject writes
  that match the playbook regex, contain `agent-genesis` in
  `source_files`, or omit the new required `source` parameter.
  Rejections logged to `logs/rejected_writes.jsonl`. 10/10 unit tests.
- **Required `source` parameter** on `add_decision` / `add_pattern` /
  `add_failure` — must be `"manual"` or `"reviewed_automated"`. Bypass
  via `FAULKNER_ALLOW_AUTOMATED=true` when running an authorized
  automated reviewer.
- **Configurable blocklist** via `FAULKNER_INGESTION_BLOCKLIST_FILE`
  (JSON `{"patterns": [...]}` or plain text, one regex per line).
- **`SEMANTIC_SIMILARITY_THRESHOLD` env var** in
  `ingestion/relationship_extractor.py` (default `0.85`, was hardcoded
  `0.7`). Tighter threshold by default; existing callers can still pass
  an explicit `threshold=` to override.
- **`scripts/regenerate_semantic_edges.py`** — re-runs the embedding
  step on the cleaned corpus at the new threshold. SEMANTICALLY_SIMILAR
  edges went 4,658 → 1,398 (-70%).
- **`scripts/health_check.py`** — read-only graph diagnostic with
  `--json` and `--strict` modes. Reports totals, ratios, Pattern degree
  stats, top-10 most-connected patterns flagged HUMAN-CURATED vs
  TELEMETRY.
- **systemd user timer** (`scripts/faulkner-health-graph.{service,timer}`)
  runs the health check every 6 hours. Credentials live in
  `~/.config/faulkner-health/env` (mode 600); the wrapper
  `scripts/run-health-check.sh` enforces presence and exits clean if
  missing.
- **Maintenance scripts** in `scripts/` for the cleanup itself:
  `audit_mkg_pollution.py`, `migrate_mkg_to_sqlite.py`,
  `purge_migrated_nodes.py`, `purge_auto_ingest.py`. All default to
  `--dry-run`; all emit JSON manifests under `logs/`.

### Migration notes

- **Existing callers of `add_*` will break** unless they (a) add
  `source: "manual"` to every payload, or (b) export
  `FAULKNER_ALLOW_AUTOMATED=true`. The default is the secure-by-default
  reject-without-source behavior. This is a breaking API contract
  change but is gated behind a documented env var escape hatch.
- The MKG playbook persistence has moved out of Faulkner-DB entirely.
  Consumers of Faulkner-DB no longer see playbook-* Patterns. MKG's new
  store lives in the `deepseek-mcp-bridge` repo at
  `mkg/playbook/store.py` (Python) and
  `src/intelligence/playbook-store.js` (Node). Both bind to the same
  SQLite file.

## [1.6.0] - 2026-04-23

### Fixed

- **Extractor was creating duplicate edges on every re-run.** `FalkorDBAdapter.create_relationship` used `CREATE` unconditionally, so re-running the relationship extractor (manually or via nightly cron) inflated edge counts. Changed to `MERGE` keyed on a content fingerprint = `sha256(src|tgt|type|evidence)[:16]`. Reruns with identical inputs are now idempotent; legitimately distinct same-type edges (different evidence) are preserved.
- **Extractor LLM endpoint was hard-coded.** `RelationshipExtractor.__init__` hard-coded `http://localhost:8081/v1` as the OpenAI-compatible base URL for relationship classification. Now read from the `FAULKNER_LLM_ENDPOINT` env var (same localhost default). Override to any OpenAI-compatible endpoint — llama.cpp, vLLM, LM Studio, NVIDIA NIM, etc. **Pass the base URL only** (e.g. `http://host:port/v1`); the extractor appends `/models` for health detection and `/chat/completions` for enhancement.
- **Graph name was inconsistent across codebase.** `default_graph_name` in `config/graphiti_config.yaml` said `faulkner_knowledge_graph` (doesn't exist on any running instance); `scripts/generate_report.py` hard-coded `faulkner` (empty leftover from earlier testing); actual data lived in `knowledge_graph`. All three now aligned on `knowledge_graph`.

### Notes

- The MERGE-on-fingerprint change is a behavioural fix, not a schema migration — existing graphs continue to work. New duplicates simply won't be created on subsequent extractor runs.
- If you were relying on the hard-coded `localhost:8081` endpoint, no change is needed; the default is unchanged. If you want to point the extractor elsewhere, export `FAULKNER_LLM_ENDPOINT=http://your-host:port/v1` before running.

## [1.5.0] - 2026-04-13

### Fixed

- `find_related` returned results dominated by auto-generated `SEMANTICALLY_SIMILAR`
  embedding edges, drowning structural relationships. Now traverses only
  structural edges (RELATES_TO, SOLVES, IMPLEMENTS, DEPENDS_ON, REFERENCES,
  ADDRESSES, SIMILAR_TO, CONTRADICTS) by default.
- `detect_gaps` hung or timed out on non-trivial graphs due to unbounded
  NetworkX betweenness centrality. Now uses sampled betweenness (k=500) and
  excludes `SEMANTICALLY_SIMILAR` from the exported subgraph by default.

### Changed

- `find_related(node_id, depth)` -> `find_related(node_id, depth, include_similar=False)`.
  Pass `include_similar=True` to restore the pre-1.5 behaviour of traversing
  every edge type including embedding-derived ones.
- `detect_gaps()` -> `detect_gaps(include_similar=False)`. Same flag semantics.
- `NetworkXAnalyzer.export_to_networkx` and `detect_gaps` accept the same flag
  internally; the cached graph is reset per call so the flag takes effect.

### Notes

This is a behaviour change with a backwards-compatible signature. Callers who
relied on the pre-1.5 "all edges" traversal must now opt in with
`include_similar=True`. Public API callers that only used the positional
`(node_id, depth)` form continue to compile and run without modification.

## [1.2.0] - 2026-02-01

### Security

- Added password authentication for FalkorDB (requirepass)
- Disabled destructive commands (FLUSHALL, FLUSHDB, DEBUG, CONFIG renamed)
- Changed default port from 6379 to 6380 to prevent conflicts with standard Redis
- Bound ports to localhost only (127.0.0.1) for network isolation

### Changed

- Updated FalkorDBAdapter to support password parameter
- Updated MCP server connections to use password authentication
- Updated health check scripts to use authenticated connections

### Fixed

- Fixed data loss vulnerability caused by port conflict with other Redis-using applications

## [1.1.1] - Previous release

### Fixed

- Redirect print() to stderr for MCP protocol compliance
- Version bump

## [1.1.0] - Previous features

### Added

- Claude plan ingestion system with Serena memory sync
- Startup health check for database validation
- Integration documentation
- CI/CD workflows and contributing guidelines

### Fixed

- Migrated sync script to Agent Genesis JSONL API
- Removed hardcoded PostgreSQL password (security fix)

## [1.0.0] - Initial Release

### Added

- Temporal Knowledge Graph System
- FalkorDB integration
- 7 MCP tools for Claude Desktop/Code
- Docker Compose deployment
- Network visualization
- Hybrid search (graph + vector + reranking)
