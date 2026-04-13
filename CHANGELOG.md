# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
