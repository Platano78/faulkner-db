#!/usr/bin/env python3
"""Purge Agent Genesis–ingested nodes (auto-extracted conversation fragments)
from Faulkner-DB.

Targets every Pattern, Failure, or Decision whose `source_files` property
contains the substring `agent-genesis`. Catches both legacy `source IS NULL`
records and newer `source='claude_code'` records — they're the same auto-
ingestion pipeline, different versions.

Two-layer backup BEFORE any delete:
  1. Server-side Redis BGSAVE
  2. Per-label JSON dumps (paginated to defeat FalkorDB's 10k result_set cap)
     at backups/falkordb_pre_purge_auto_<label>_<ts>.json

Default --dry-run=true: prints the plan and counts, NO mutations.

Usage:
  python scripts/purge_auto_ingest.py [--dry-run/--no-dry-run]
                                       [--host HOST] [--port PORT]
                                       [--password PASS] [--graph NAME]
                                       [--batch-size N] [--page-size N]
                                       [--labels Pattern,Failure,Decision]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from falkordb import FalkorDB
except ImportError:
    print("ERROR: falkordb not installed. pip install falkordb", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "logs"
BACKUP_DIR = REPO_ROOT / "backups"
LOG_FILE = LOG_DIR / "purge_auto_ingest.log"

CRITERIA = "source_files CONTAINS 'agent-genesis'"
DEFAULT_LABELS = ("Pattern", "Failure", "Decision")


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("purge_auto_ingest")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def connect(host: str, port: int, password: str | None, graph_name: str):
    kwargs: dict[str, Any] = {"host": host, "port": port}
    if password:
        kwargs["password"] = password
    db = FalkorDB(**kwargs)
    return db, db.select_graph(graph_name)


def label_counts(graph) -> dict[str, int]:
    rows = graph.query(
        "MATCH (n) RETURN labels(n)[0] AS lbl, count(n) AS c"
    ).result_set
    return {r[0]: r[1] for r in rows if r[0]}


def edge_counts(graph) -> dict[str, int]:
    rows = graph.query(
        "MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c ORDER BY c DESC"
    ).result_set
    return {r[0]: r[1] for r in rows}


def trigger_bgsave(client_db: Any, log: logging.Logger) -> str:
    try:
        result = client_db.connection.execute_command("BGSAVE")
        log.info("BGSAVE issued: %r", result)
        return str(result)
    except Exception as e:
        log.warning("BGSAVE failed (continuing with JSON local backup only): %s", e)
        return f"FAILED: {e}"


def count_targets(graph, label: str) -> int:
    cypher = f"MATCH (n:{label}) WHERE n.{CRITERIA} RETURN count(n)"
    return graph.query(cypher).result_set[0][0]


def count_incident_edges(graph, label: str) -> int:
    cypher = (
        f"MATCH (n:{label})-[r]-() WHERE n.{CRITERIA} RETURN count(r)"
    )
    return graph.query(cypher).result_set[0][0]


def page_nodes(graph, label: str, page_size: int) -> Iterable[dict[str, Any]]:
    skip = 0
    while True:
        rows = graph.query(
            f"MATCH (n:{label}) WHERE n.{CRITERIA} "
            f"RETURN n ORDER BY n.id SKIP {int(skip)} LIMIT {int(page_size)}"
        ).result_set
        if not rows:
            return
        for row in rows:
            node = row[0]
            props = dict(node.properties) if hasattr(node, "properties") else {}
            yield {
                "id": props.get("id"),
                "labels": list(getattr(node, "labels", [])) or [props.get("type")],
                "properties": props,
            }
        if len(rows) < page_size:
            return
        skip += page_size


def page_edges(graph, label: str, page_size: int) -> Iterable[dict[str, Any]]:
    skip = 0
    while True:
        rows = graph.query(
            f"MATCH (a:{label})-[r]-(b) WHERE a.{CRITERIA} "
            f"RETURN a.id AS src, b.id AS tgt, type(r) AS t, "
            f"properties(r) AS props, labels(b)[0] AS tgt_label, ID(r) AS rid "
            f"ORDER BY rid SKIP {int(skip)} LIMIT {int(page_size)}"
        ).result_set
        if not rows:
            return
        for src, tgt, t, props, tgt_label, _rid in rows:
            yield {
                "src_id": src, "tgt_id": tgt, "type": t,
                "tgt_label": tgt_label,
                "properties": dict(props) if props else {},
            }
        if len(rows) < page_size:
            return
        skip += page_size


def dump_label_subgraph(graph, label: str, ts: str, page_size: int,
                        log: logging.Logger) -> dict[str, Any]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BACKUP_DIR / f"falkordb_pre_purge_auto_{label.lower()}_{ts}.json"
    nodes = list(page_nodes(graph, label, page_size))
    log.info("[%s] Dumped %d nodes", label, len(nodes))
    edges: list[dict[str, Any]] = []
    for i, e in enumerate(page_edges(graph, label, page_size), 1):
        edges.append(e)
        if i % 10000 == 0:
            log.info("[%s] Edge dump progress: %d", label, i)
    log.info("[%s] Dumped %d edges total", label, len(edges))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "criteria": CRITERIA,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    log.info("[%s] Backup written: %s (%d nodes, %d edges)",
             label, out_path, len(nodes), len(edges))
    return {
        "label": label, "path": str(out_path),
        "node_count": len(nodes), "edge_count": len(edges),
    }


def delete_label(graph, label: str, batch_size: int, expected: int,
                 log: logging.Logger) -> int:
    deleted = 0
    while True:
        rows = graph.query(
            f"MATCH (n:{label}) WHERE n.{CRITERIA} "
            f"WITH n LIMIT {int(batch_size)} "
            f"DETACH DELETE n RETURN count(n)"
        ).result_set
        n = rows[0][0] if rows else 0
        if not n:
            break
        deleted += n
        log.info("[%s] Deleted batch of %d (total %d / expected %d)",
                 label, n, deleted, expected)
    return deleted


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    ap.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    ap.add_argument("--host", default=os.getenv("FALKORDB_HOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("FALKORDB_PORT", "6380")))
    ap.add_argument("--password", default=os.getenv("FALKORDB_PASSWORD"))
    ap.add_argument("--graph", default=os.getenv("FAULKNER_GRAPH_NAME", "knowledge_graph"))
    ap.add_argument("--batch-size", type=int, default=500)
    ap.add_argument("--page-size", type=int, default=5000)
    ap.add_argument("--labels", default=",".join(DEFAULT_LABELS),
                    help="Comma-separated labels to scope (default: Pattern,Failure,Decision)")
    args = ap.parse_args()

    labels = [s.strip() for s in args.labels.split(",") if s.strip()]
    log = setup_logging()
    log.info("Mode=%s host=%s graph=%s labels=%s criteria=%s",
             "DRY-RUN" if args.dry_run else "PURGE",
             args.host, args.graph, labels, CRITERIA)

    client_db, graph = connect(args.host, args.port, args.password, args.graph)

    log.info("Snapshot: nodes/edges before any action")
    before = {"nodes_by_label": label_counts(graph), "edges_by_type": edge_counts(graph)}

    per_label_targets: list[dict[str, Any]] = []
    total_target_nodes = 0
    total_target_edges = 0
    for label in labels:
        n = count_targets(graph, label)
        e = count_incident_edges(graph, label)
        per_label_targets.append({"label": label, "target_nodes": n,
                                   "target_incident_edges_undirected": e})
        total_target_nodes += n
        total_target_edges += e
        log.info("[%s] target=%d nodes  incident_edges=%d (undirected)",
                 label, n, e)

    plan = {
        "criteria": CRITERIA,
        "labels": labels,
        "per_label": per_label_targets,
        "total_target_nodes": total_target_nodes,
        "total_target_incident_edges_undirected": total_target_edges,
        "before_totals": before,
    }

    if args.dry_run:
        print(json.dumps({"mode": "dry_run", "plan": plan}, indent=2, default=str))
        log.info("Dry-run complete; no mutations")
        return 0

    if total_target_nodes == 0:
        log.info("Nothing to delete")
        return 0

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log.info("Triggering server-side Redis BGSAVE")
    bgsave_status = trigger_bgsave(client_db, log)

    backups: list[dict[str, Any]] = []
    for label in labels:
        if count_targets(graph, label) == 0:
            log.info("[%s] no targets — skipping backup", label)
            continue
        backups.append(dump_label_subgraph(graph, label, ts, args.page_size, log))

    deletes: list[dict[str, int | str]] = []
    for label in labels:
        expected = count_targets(graph, label)
        if expected == 0:
            continue
        log.info("[%s] DETACH DELETE in batches of %d", label, args.batch_size)
        deleted = delete_label(graph, label, args.batch_size, expected, log)
        deletes.append({"label": label, "expected": expected, "deleted": deleted})

    after = {"nodes_by_label": label_counts(graph), "edges_by_type": edge_counts(graph)}
    remaining: list[dict[str, int | str]] = []
    for label in labels:
        remaining.append({"label": label,
                          "remaining_targeted": count_targets(graph, label)})

    report = {
        "mode": "purge",
        "timestamp": ts,
        "plan": plan,
        "backup": {
            "bgsave_status": bgsave_status,
            "per_label_dumps": backups,
        },
        "delete": deletes,
        "verification": {
            "remaining_targeted_per_label": remaining,
            "after_totals": after,
        },
    }
    report_path = LOG_DIR / f"purge_report_auto_{int(datetime.now().timestamp())}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    log.info("Purge report → %s", report_path)

    bad = [r for r in remaining if r["remaining_targeted"] != 0]
    if bad:
        log.error("FAILED: remaining targeted nodes per label: %s", bad)
        return 3
    log.info("Auto-ingest purge complete: %d nodes deleted, 0 remaining",
             sum(d["deleted"] for d in deletes))
    return 0


if __name__ == "__main__":
    sys.exit(main())