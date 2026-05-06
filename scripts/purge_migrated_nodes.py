#!/usr/bin/env python3
"""Delete migrated MKG playbook nodes from Faulkner-DB after Task 3 migration.

Reads a migration manifest produced by scripts/migrate_mkg_to_sqlite.py and
DETACH-DELETEs the corresponding Pattern nodes (and all incident edges) from
FalkorDB.

Two-layer backup runs BEFORE any delete:
  1. Server-side Redis BGSAVE   — captures full instance to FalkorDB's RDB
  2. Local JSON subgraph dump   — backups/falkordb_pre_purge_<ts>.json
                                  contains every node + every adjacent edge
                                  that would be deleted, parseable for
                                  restore.

Default --dry-run=true: prints the plan and counts, NO mutations.

Usage:
  python scripts/purge_migrated_nodes.py --manifest logs/migrate_manifest_*.json
                                         [--dry-run/--no-dry-run]
                                         [--host HOST] [--port PORT]
                                         [--password PASS] [--graph NAME]
                                         [--batch-size N]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from falkordb import FalkorDB
except ImportError:
    print("ERROR: falkordb not installed. pip install falkordb", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "logs"
BACKUP_DIR = REPO_ROOT / "backups"
LOG_FILE = LOG_DIR / "purge_migrated_nodes.log"


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("purge_migrated_nodes")
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
    """Issue Redis BGSAVE on the FalkorDB instance.

    Returns a textual status. Server-side dump file lives on the FalkorDB
    host and is not retrieved here; presence of a successful BGSAVE is the
    safety net.
    """
    try:
        raw_client = client_db.connection
        result = raw_client.execute_command("BGSAVE")
        log.info("BGSAVE issued: %r", result)
        return str(result)
    except Exception as e:
        log.warning("BGSAVE failed (continuing with JSON local backup only): %s", e)
        return f"FAILED: {e}"


def dump_subgraph_json(graph, faulkner_ids: list[str], path: Path,
                       log: logging.Logger) -> dict[str, int]:
    """Dump every Pattern node with id in faulkner_ids + every adjacent edge.

    JSON shape:
      {"generated_at": ..., "node_count": N, "edge_count": M,
       "nodes": [{"id": "P-…", "labels": [...], "properties": {...}}, ...],
       "edges": [{"src_id": ..., "tgt_id": ..., "type": ..., "properties": {...}}, ...]}
    """
    if not faulkner_ids:
        path.write_text(json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "node_count": 0, "edge_count": 0, "nodes": [], "edges": [],
        }, indent=2))
        return {"node_count": 0, "edge_count": 0}

    rows_n = graph.query(
        "MATCH (p:Pattern) WHERE p.id IN $ids RETURN p",
        {"ids": faulkner_ids},
    ).result_set
    nodes_out = []
    for row in rows_n:
        node = row[0]
        props = dict(node.properties) if hasattr(node, "properties") else {}
        labels = list(getattr(node, "labels", [])) or [props.get("type")]
        nodes_out.append({
            "id": props.get("id"),
            "labels": labels,
            "properties": props,
        })

    edges_out = []
    page_size = 5000
    skip = 0
    while True:
        rows_e = graph.query(
            "MATCH (a:Pattern)-[r]-(b) WHERE a.id IN $ids "
            "RETURN a.id AS src, b.id AS tgt, type(r) AS t, "
            "properties(r) AS props, labels(b)[0] AS tgt_label, ID(r) AS rid "
            f"ORDER BY rid SKIP {int(skip)} LIMIT {int(page_size)}",
            {"ids": faulkner_ids},
        ).result_set
        if not rows_e:
            break
        for src, tgt, t, props, tgt_label, _rid in rows_e:
            edges_out.append({
                "src_id": src, "tgt_id": tgt, "type": t,
                "tgt_label": tgt_label,
                "properties": dict(props) if props else {},
            })
        if len(rows_e) < page_size:
            break
        skip += page_size
        log.info("Edge dump pagination: %d rows so far", len(edges_out))

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "purge_migrated_nodes",
        "criteria": "Pattern.id IN manifest.inserted_ids[].faulkner_id",
        "node_count": len(nodes_out),
        "edge_count": len(edges_out),
        "nodes": nodes_out,
        "edges": edges_out,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))
    log.info("Local subgraph backup: %d nodes, %d edges → %s",
             len(nodes_out), len(edges_out), path)
    return {"node_count": len(nodes_out), "edge_count": len(edges_out)}


def delete_in_batches(graph, ids: list[str], batch_size: int,
                      log: logging.Logger) -> dict[str, int]:
    deleted_nodes = 0
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        before = graph.query(
            "MATCH (p:Pattern) WHERE p.id IN $ids RETURN count(p)",
            {"ids": batch},
        ).result_set[0][0]
        graph.query(
            "MATCH (p:Pattern) WHERE p.id IN $ids DETACH DELETE p",
            {"ids": batch},
        )
        log.info("Batch %d-%d: deleted %d Pattern node(s)",
                 i, i + len(batch) - 1, before)
        deleted_nodes += before
    return {"nodes_deleted": deleted_nodes}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True, type=Path,
                    help="Path to migration manifest from migrate_mkg_to_sqlite.py")
    ap.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    ap.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    ap.add_argument("--host", default=os.getenv("FALKORDB_HOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("FALKORDB_PORT", "6380")))
    ap.add_argument("--password", default=os.getenv("FALKORDB_PASSWORD"))
    ap.add_argument("--graph", default=os.getenv("FAULKNER_GRAPH_NAME", "knowledge_graph"))
    ap.add_argument("--batch-size", type=int, default=100)
    args = ap.parse_args()

    log = setup_logging()
    log.info("Mode=%s manifest=%s host=%s graph=%s",
             "DRY-RUN" if args.dry_run else "PURGE",
             args.manifest, args.host, args.graph)

    if not args.manifest.is_file():
        log.error("Manifest not found: %s", args.manifest)
        return 1
    with args.manifest.open() as fh:
        manifest = json.load(fh)
    inserted = manifest.get("inserted_ids") or []
    faulkner_ids = sorted({row["faulkner_id"] for row in inserted if row.get("faulkner_id")})
    log.info("Manifest claims %d migrated lessons → %d distinct faulkner_ids",
             len(inserted), len(faulkner_ids))

    if not faulkner_ids:
        log.error("No faulkner_ids in manifest; nothing to do")
        return 1

    client_db, graph = connect(args.host, args.port, args.password, args.graph)

    log.info("Snapshot: nodes/edges before any action")
    before = {"nodes_by_label": label_counts(graph), "edges_by_type": edge_counts(graph)}

    actually_present = graph.query(
        "MATCH (p:Pattern) WHERE p.id IN $ids RETURN count(p)",
        {"ids": faulkner_ids},
    ).result_set[0][0]
    incident_edges = graph.query(
        "MATCH (p:Pattern)-[r]-() WHERE p.id IN $ids RETURN count(r)",
        {"ids": faulkner_ids},
    ).result_set[0][0]
    log.info("Targeted: %d / %d Pattern nodes still present in Faulkner",
             actually_present, len(faulkner_ids))
    log.info("Incident edges (undirected count, will be deleted via DETACH): %d",
             incident_edges)

    plan = {
        "manifest_path": str(args.manifest),
        "manifest_size": len(faulkner_ids),
        "currently_present_in_faulkner": actually_present,
        "incident_edges_undirected": incident_edges,
        "before_totals": before,
    }

    if args.dry_run:
        print(json.dumps({"mode": "dry_run", "plan": plan}, indent=2, default=str))
        log.info("Dry-run complete; no mutations")
        return 0

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log.info("Triggering server-side Redis BGSAVE")
    bgsave_status = trigger_bgsave(client_db, log)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_json_path = BACKUP_DIR / f"falkordb_pre_purge_migrated_{ts}.json"
    backup_stats = dump_subgraph_json(graph, faulkner_ids, backup_json_path, log)
    if backup_stats["node_count"] == 0 and actually_present > 0:
        log.error("Local backup produced 0 nodes but %d are present — aborting",
                  actually_present)
        return 2

    log.info("Beginning DETACH DELETE in batches of %d", args.batch_size)
    delete_stats = delete_in_batches(graph, faulkner_ids, args.batch_size, log)

    after = {"nodes_by_label": label_counts(graph), "edges_by_type": edge_counts(graph)}
    after_present = graph.query(
        "MATCH (p:Pattern) WHERE p.id IN $ids RETURN count(p)",
        {"ids": faulkner_ids},
    ).result_set[0][0]

    report = {
        "mode": "purge",
        "timestamp": ts,
        "plan": plan,
        "backup": {
            "bgsave_status": bgsave_status,
            "local_subgraph_json": str(backup_json_path),
            "local_subgraph_node_count": backup_stats["node_count"],
            "local_subgraph_edge_count": backup_stats["edge_count"],
        },
        "delete": delete_stats,
        "verification": {
            "remaining_targeted_nodes": after_present,
            "after_totals": after,
        },
    }
    report_path = LOG_DIR / f"purge_report_migrated_{int(datetime.now().timestamp())}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    log.info("Purge report → %s", report_path)

    if after_present != 0:
        log.error("FAILED: %d targeted nodes still remain", after_present)
        return 3
    log.info("Purge complete: %d nodes deleted, 0 remaining", delete_stats["nodes_deleted"])
    return 0


if __name__ == "__main__":
    sys.exit(main())