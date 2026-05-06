#!/usr/bin/env python3
"""Read-only health-check diagnostic over the live FalkorDB graph."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from falkordb import FalkorDB
except ImportError:
    print("ERROR: falkordb not installed. pip install falkordb", file=sys.stderr)
    sys.exit(2)

GRAPH_NAME = "knowledge_graph"
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "health_check.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("health_check")
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
# Connection
# ---------------------------------------------------------------------------

def connect(host: str, port: int, password: str | None, graph_name: str):
    kwargs: dict = {"host": host, "port": port}
    if password:
        kwargs["password"] = password
    db = FalkorDB(**kwargs)
    return db.select_graph(graph_name)

# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def count_by_label(graph):
    rows = graph.query(
        "MATCH (n) RETURN labels(n)[0] AS lbl, count(n) AS c"
    ).result_set
    return {r[0]: r[1] for r in rows if r[0]}

def count_edges_by_type(graph):
    rows = graph.query(
        "MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c ORDER BY c DESC"
    ).result_set
    return {r[0]: r[1] for r in rows}

def pattern_degree_stats(graph):
    """Return (avg_degree, max_degree, top_10_list)."""
    rows = graph.query(
        "MATCH (p:Pattern)-[e]-() RETURN p.id AS id, p.name AS name, "
        "count(e) AS deg ORDER BY deg DESC LIMIT 10"
    ).result_set
    top10 = []
    for rid, name, deg in rows:
        has_prefix = (name or "").startswith("playbook-")
        has_agent = "agent-genesis" in (name or "")
        source = "TELEMETRY" if (has_prefix or has_agent) else "HUMAN-CURATED suspected"
        top10.append({"id": rid, "name": (name or "")[:80],
                      "degree": deg, "source": source})
    degrees = [r[2] for r in rows]
    avg_deg = sum(degrees) / len(degrees) if degrees else 0
    max_deg = max(degrees) if degrees else 0
    return avg_deg, max_deg, top10

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default=os.getenv("FALKORDB_HOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("FALKORDB_PORT", "6380")))
    ap.add_argument("--password", default=os.getenv("FALKORDB_PASSWORD"))
    ap.add_argument("--graph", default=os.getenv("FAULKNER_GRAPH_NAME", GRAPH_NAME))
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--strict", action="store_true", help="Exit 1 if any warning")
    args = ap.parse_args()

    log = setup_logging()
    log.info("Connecting host=%s port=%d graph=%s", args.host, args.port, args.graph)

    graph = connect(args.host, args.port, args.password, args.graph)
    log.info("Connected.")

    # --- Collect metrics ---
    nodes_by_label = count_by_label(graph)
    edges_by_type = count_edges_by_type(graph)

    failure_count = nodes_by_label.get("Failure", 0)
    decision_count = nodes_by_label.get("Decision", 0)
    pattern_count = nodes_by_label.get("Pattern", 0)
    ss_edges = edges_by_type.get("SEMANTICALLY_SIMILAR", 0)
    other_edges = sum(edges_by_type.get(t, 0) for t in
                      ["RELATES_TO", "SOLVES", "ADDRESSES", "IMPLEMENTS"])

    # Ratios
    fail_dec_ratio = failure_count / decision_count if decision_count > 0 else 0
    ss_ratio = ss_edges / other_edges if other_edges > 0 else 0

    # Pattern degree
    avg_deg, max_deg, top10 = pattern_degree_stats(graph)

    # --- Warnings ---
    warnings: list[str] = []
    if fail_dec_ratio > 5:
        warnings.append(f"Failure:Decision = {fail_dec_ratio:.1f} (warn > 5)")
    if ss_ratio > 1.0:
        warnings.append(f"SS/(REL+SOL+ADD+IMP) = {ss_ratio:.2f} (warn > 1.0)")
    if avg_deg > 20:
        warnings.append(f"Avg Pattern degree = {avg_deg:.1f} (warn > 20)")
    if max_deg > 50:
        warnings.append(f"Max Pattern degree = {max_deg} (warn > 50)")

    # --- Human output ---
    if not args.json:
        print("=" * 60)
        print("  === SUMMARY ===")
        print("=" * 60)
        for lbl, cnt in sorted(nodes_by_label.items()):
            print(f"  {lbl:20s} {cnt}")
        for etype, cnt in sorted(edges_by_type.items(), key=lambda x: -x[1]):
            print(f"  {etype:30s} {cnt}")
        w = ""
        if fail_dec_ratio > 5: w += f" ⚠️  Failure:Decision = {fail_dec_ratio:.1f} (warn > 5)\n"
        else: w += f"  Failure:Decision = {fail_dec_ratio:.1f}\n"
        if ss_ratio > 1.0: w += f" ⚠️  SS/(REL+SOL+ADD+IMP) = {ss_ratio:.2f} (warn > 1.0)\n"
        else: w += f"  SS/(REL+SOL+ADD+IMP) = {ss_ratio:.2f}\n"
        if avg_deg > 20: w += f" ⚠️  Avg Pattern degree = {avg_deg:.1f} (warn > 20)\n"
        else: w += f"  Avg Pattern degree = {avg_deg:.1f}\n"
        if max_deg > 50: w += f" ⚠️  Max Pattern degree = {max_deg} (warn > 50)\n"
        else: w += f"  Max Pattern degree = {max_deg}\n"
        print(w.rstrip())
        print()
        print("=" * 60)
        print("  === TOP 10 PATTERNS BY DEGREE ===")
        print("=" * 60)
        for i, p in enumerate(top10, 1):
            flag = f" [{p['source']}]" if p['source'] == "HUMAN-CURATED suspected" else ""
            print(f"  {i:2d}. {p['id']:30s}  {p['name'][:50]:50s}  deg={p['degree']}{flag}")
        if warnings:
            print(f"\nWARNINGS: {len(warnings)}")
            for w in warnings:
                print(f"  ⚠️  {w}")
        else:
            print("\nOK")
    else:
        # --- JSON output ---
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "nodes_by_label": nodes_by_label,
            "edges_by_type": edges_by_type,
            "failure_decision_ratio": round(fail_dec_ratio, 2),
            "ss_ratio": round(ss_ratio, 4),
            "avg_pattern_degree": round(avg_deg, 2),
            "max_pattern_degree": max_deg,
            "top_10_patterns": top10,
            "warnings": warnings,
        }
        json.dump(report, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")

    # --- Exit code ---
    if args.strict and warnings:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
