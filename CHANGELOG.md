# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
