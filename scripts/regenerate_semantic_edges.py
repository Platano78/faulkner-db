#!/usr/bin/env python3
"""Regenerate SEMANTICALLY_SIMILAR edges at the configured threshold.

Connects to FalkorDB, backs up via Redis BGSAVE, deletes existing
SEMANTICALLY_SIMILAR edges, recomputes them via RelationshipExtractor,
and inserts the results.

Usage:
  python scripts/regenerate_semantic_edges.py [--no-dry-run] [--threshold F]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import redis
except ImportError:
    print("ERROR: redis not installed. pip install redis", file=sys.stderr)
    sys.exit(2)
try:
    from falkordb import FalkorDB
except ImportError:
    print("ERROR: falkordb not installed. pip install falkordb", file=sys.stderr)
    sys.exit(2)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingestion.relationship_extractor import RelationshipExtractor

GRAPH_NAME = "knowledge_graph"
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "regenerate_semantic_edges.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("regenerate_semantic_edges")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def connect(host: str, port: int, password: str | None, graph_name: str):
    kwargs: dict = {"host": host, "port": port}
    if password:
        kwargs["password"] = password
    db = FalkorDB(**kwargs)
    return db.select_graph(graph_name)

def redis_client(host: str, port: int, password: str | None):
    kwargs: dict = {"host": host, "port": port}
    if password:
        kwargs["password"] = password
    return redis.Redis(**kwargs)

# ---------------------------------------------------------------------------
# Node loading
# ---------------------------------------------------------------------------

def load_curated_nodes(graph) -> list[dict]:
    """Load Pattern + Failure + Decision nodes with best-text fields."""
    rows = graph.query(
        "MATCH (n) WHERE n:Pattern OR n:Failure OR n:Decision "
        "RETURN n.id AS id, labels(n)[0] AS type, "
        "n.name AS name, n.implementation AS implementation, "
        "n.context AS context, n.attempt AS attempt, "
        "n.reason_failed AS reason_failed, n.lesson_learned AS lesson_learned, "
        "n.description AS description, n.rationale AS rationale"
    ).result_set
    nodes = []
    for row in rows:
        nid, ntype = row[0], row[1]
        if ntype == "Pattern":
            text = f"{row[2] or ''} {row[3] or ''} {row[4] or ''}".strip()
        elif ntype == "Failure":
            text = f"{row[5] or ''} {row[6] or ''} {row[7] or ''}".strip()
        elif ntype == "Decision":
            text = f"{row[8] or ''} {row[9] or ''}".strip()
        else:
            text = ""
        if text:
            nodes.append({"id": nid, "text": text})
    return nodes

# ---------------------------------------------------------------------------
# Edge insertion (batched)
# ---------------------------------------------------------------------------

def insert_edges_batched(graph, edges: list[tuple], batch_size: int, dry_run: bool):
    """Insert SEMANTICALLY_SIMILAR edges in batches of batch_size."""
    cypher = (
        "MATCH (a),(b) WHERE a.id = $sid AND b.id = $tid "
        "MERGE (a)-[r:SEMANTICALLY_SIMILAR {weight: $w}]->(b)"
    )
    inserted = 0
    for i in range(0, len(edges), batch_size):
        batch = edges[i:i + batch_size]
        if not dry_run:
            for sid, tid, _rel, w in batch:
                graph.query(cypher, {"sid": sid, "tid": tid, "w": w})
                inserted += 1
        else:
            inserted += len(batch)
    return inserted

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--no-dry-run", action="store_false", dest="dry_run")
    ap.add_argument("--threshold", type=float, default=None,
                    help="Override SEMANTIC_SIMILARITY_THRESHOLD env / default 0.85")
    ap.add_argument("--host", default=os.getenv("FALKORDB_HOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("FALKORDB_PORT", "6380")))
    ap.add_argument("--password", default=os.getenv("FALKORDB_PASSWORD"))
    ap.add_argument("--graph", default=os.getenv("FAULKNER_GRAPH_NAME", GRAPH_NAME))
    ap.add_argument("--batch-size", type=int, default=200)
    args = ap.parse_args()

    # Resolve dry-run flag (argparse stores dest=dry_run=True for --no-dry-run)
    dry_run = args.dry_run

    log = setup_logging()
    threshold = args.threshold if args.threshold is not None else float(
        os.environ.get("SEMANTIC_SIMILARITY_THRESHOLD", "0.85")
    )

    log.info("Connecting host=%s port=%d graph=%s", args.host, args.port, args.graph)
    graph = connect(args.host, args.port, args.password, args.graph)
    log.info("Connected. threshold=%.2f  dry_run=%s", threshold, dry_run)

    # --- BGSAVE backup via raw Redis ---
    bgsave_status = "skipped"
    try:
        rc = redis_client(args.host, args.port, args.password)
        rc.ping()
        log.info("BGSAVE: issuing background save...")
        result = rc.bgsave()
        log.info("BGSAVE result: %s", result)
        bgsave_status = "ok"
        # Small delay to let persistence start
        time.sleep(1)
    except Exception as e:
        log.warning("BGSAVE failed (non-fatal): %s", e)
        bgsave_status = f"error: {e}"

    # --- Before count ---
    before_rows = graph.query(
        "MATCH ()-[r:SEMANTICALLY_SIMILAR]->() RETURN count(r) AS c"
    ).result_set
    before_ss = before_rows[0][0] if before_rows else 0
    log.info("Before: SEMANTICALLY_SIMILAR edges = %d", before_ss)

    # --- Delete all SEMANTICALLY_SIMILAR edges ---
    if not dry_run:
        graph.query("MATCH ()-[r:SEMANTICALLY_SIMILAR]->() DELETE r")
        log.info("Deleted all SEMANTICALLY_SIMILAR edges")
    else:
        log.info("[DRY-RUN] Would delete all SEMANTICALLY_SIMILAR edges")

    # --- Load curated nodes ---
    nodes = load_curated_nodes(graph)
    log.info("Loaded %d curated nodes", len(nodes))

    # --- Regenerate semantic edges ---
    from core.graphiti_client import GraphitiClient
    fc = GraphitiClient()
    extractor = RelationshipExtractor(fc)
    edges = extractor.extract_semantic_similarity(nodes, threshold=threshold)
    log.info("Generated %d new semantic similarity tuples", len(edges))

    # --- Insert edges ---
    edges_inserted = insert_edges_batched(
        graph, edges, batch_size=args.batch_size, dry_run=dry_run
    )
    log.info("Inserted %d edges (batch_size=%d)", edges_inserted, args.batch_size)

    # --- After count ---
    after_rows = graph.query(
        "MATCH ()-[r:SEMANTICALLY_SIMILAR]->() RETURN count(r) AS c"
    ).result_set
    after_ss = after_rows[0][0] if after_rows else 0
    log.info("After: SEMANTICALLY_SIMILAR edges = %d", after_ss)

    # --- Report JSON ---
    ts = int(time.time())
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "threshold_used": threshold,
        "before": {"ss_edges": before_ss},
        "after": {"ss_edges": after_ss},
        "nodes_processed": len(nodes),
        "edges_inserted": edges_inserted,
        "bgsave_status": bgsave_status,
    }
    report_path = LOG_DIR / f"regenerate_semantic_{ts}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    log.info("Report written to %s", report_path)
    print(f"\n{'='*60}\n"
          f"  BEFORE: {before_ss} SEMANTICALLY_SIMILAR edges\n"
          f"  AFTER:  {after_ss} SEMANTICALLY_SIMILAR edges\n"
          f"  Nodes processed: {len(nodes)}\n"
          f"  Edges inserted:  {edges_inserted}\n"
          f"{'='*60}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
