#!/usr/bin/env python3
"""
Audit MKG playbook pollution in Faulkner DB.

Read-only. Reports:
  - Patterns matching MKG playbook signature (^playbook-.*-\\d{13}$)
  - Sampled Failures + derived auto-generated signature regex(es)
  - Edge incidence by type for the polluted node set
  - Top 20 name prefixes across all Patterns (surface other auto-ingest sources)

Outputs JSON to stdout. Logs to logs/audit_mkg_pollution.log AND stdout.

Usage:
  python scripts/audit_mkg_pollution.py [--host HOST] [--port PORT]
                                        [--password PASS] [--graph NAME]
                                        [--sample-size N]

Env fallbacks: FALKORDB_HOST, FALKORDB_PORT, FALKORDB_PASSWORD,
               FAULKNER_GRAPH_NAME (default: knowledge_graph)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from falkordb import FalkorDB
except ImportError:
    print("ERROR: falkordb not installed. pip install falkordb", file=sys.stderr)
    sys.exit(2)


PLAYBOOK_NAME_RE = re.compile(r"^playbook-.*-\d{13}$")
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "audit_mkg_pollution.log"


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("audit_mkg_pollution")
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
    return db.select_graph(graph_name)


def q(graph, cypher: str, params: dict | None = None):
    return graph.query(cypher, params or {}).result_set


def count_total_by_label(graph) -> dict[str, int]:
    rows = q(graph, "MATCH (n) RETURN labels(n)[0] AS lbl, count(n) AS c")
    return {r[0]: r[1] for r in rows if r[0]}


def count_total_edges_by_type(graph) -> dict[str, int]:
    rows = q(graph, "MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c ORDER BY c DESC")
    return {r[0]: r[1] for r in rows}


def find_playbook_patterns(graph) -> dict[str, Any]:
    """Patterns whose name matches MKG playbook signature.

    FalkorDB has no regex; pull all 'playbook-' prefixed names and filter in Python.
    """
    rows = q(
        graph,
        "MATCH (p:Pattern) WHERE p.name STARTS WITH 'playbook-' "
        "RETURN p.name AS name, p.context AS ctx LIMIT 50000",
    )
    sig = re.compile(r"^playbook-.*-\d{13}$")
    matched = [(r[0], r[1]) for r in rows if r[0] and sig.match(r[0])]
    samples = [
        {"name": n, "context_excerpt": (c or "")[:200]} for n, c in matched[:5]
    ]

    family = Counter()
    fam_re = re.compile(r"^(playbook-[a-zA-Z0-9_]+)-\d{13}$")
    for name, _ in matched:
        m = fam_re.match(name)
        if m:
            family[m.group(1)] += 1

    return {
        "regex": "^playbook-.*-\\d{13}$",
        "starts_with_playbook_total": len(rows),
        "match_count": len(matched),
        "by_family": dict(family.most_common()),
        "samples": samples,
    }


def sample_failures(graph, sample_size: int) -> dict[str, Any]:
    """Sample failures and derive regexes for auto-generated signatures."""
    rows = q(
        graph,
        f"MATCH (f:Failure) RETURN f.name AS name, f.context AS ctx, f.signature AS sig "
        f"LIMIT {sample_size}",
    )
    samples = []
    name_prefixes = Counter()
    sig_present = 0
    timestamp_suffix_count = 0
    candidate_regexes = Counter()

    ts13_suffix = re.compile(r"-\d{13}$")
    ts10_suffix = re.compile(r"-\d{10}$")
    uuid_suffix = re.compile(
        r"-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    leading_token = re.compile(r"^([a-zA-Z][a-zA-Z0-9_]*)[-_]")

    for name, ctx, sig in rows:
        if sig:
            sig_present += 1
        samples.append(
            {
                "name": name,
                "context_excerpt": (ctx or "")[:160],
                "has_signature_field": bool(sig),
            }
        )
        if not name:
            continue
        if ts13_suffix.search(name):
            timestamp_suffix_count += 1
            candidate_regexes[r"-\d{13}$ (unix-ms timestamp suffix)"] += 1
        elif ts10_suffix.search(name):
            candidate_regexes[r"-\d{10}$ (unix-sec timestamp suffix)"] += 1
        elif uuid_suffix.search(name):
            candidate_regexes[r"-<uuid>$ (uuid suffix)"] += 1
        m = leading_token.match(name)
        if m:
            name_prefixes[m.group(1)] += 1

    derived = []
    for token, count in name_prefixes.most_common(10):
        if count >= max(3, sample_size // 50):
            derived.append({
                "regex": f"^{re.escape(token)}-.*-\\d{{13}}$",
                "leading_token": token,
                "occurrences_in_sample": count,
            })

    return {
        "sample_size": len(rows),
        "signature_field_present_count": sig_present,
        "ts13_suffix_count": timestamp_suffix_count,
        "candidate_signature_classes": dict(candidate_regexes),
        "derived_regexes": derived,
        "samples_first_5": samples[:5],
    }


def edge_incidence_for_playbooks(graph) -> dict[str, int]:
    """Count edges incident to playbook-signature nodes, by edge type.

    No regex in FalkorDB: prefilter via STARTS WITH 'playbook-', then aggregate.
    """
    rows = q(
        graph,
        "MATCH (p:Pattern)-[r]-() WHERE p.name STARTS WITH 'playbook-' "
        "RETURN type(r) AS t, count(r) AS c ORDER BY c DESC",
    )
    return {r[0]: r[1] for r in rows}


def edge_incidence_for_failures_with_ts(graph) -> dict[str, int]:
    """Failures with -<13-digit-ts> suffix — likely MKG-generated.

    FalkorDB has no regex. Pull all Failure->edge pairs once with the
    candidate node names, filter in Python by ts13 suffix, aggregate.
    """
    rows = q(
        graph,
        "MATCH (f:Failure)-[r]-() RETURN f.name AS name, type(r) AS t",
    )
    ts13 = re.compile(r"-\d{13}$")
    counter: Counter = Counter()
    for name, t in rows:
        if name and ts13.search(name):
            counter[t] += 1
    return dict(counter.most_common())


def top_pattern_prefixes(graph, top_n: int = 20) -> list[dict[str, Any]]:
    """Top N leading-token prefixes across ALL Patterns."""
    rows = q(graph, "MATCH (p:Pattern) RETURN p.name AS name")
    prefix_counter = Counter()
    leading = re.compile(r"^([a-zA-Z][a-zA-Z0-9_]*)[-_]")
    for (name,) in rows:
        if not name:
            continue
        m = leading.match(name)
        prefix_counter[m.group(1) if m else "(no-prefix)"] += 1
    return [
        {"prefix": p, "count": c} for p, c in prefix_counter.most_common(top_n)
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default=os.getenv("FALKORDB_HOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("FALKORDB_PORT", "6380")))
    ap.add_argument("--password", default=os.getenv("FALKORDB_PASSWORD"))
    ap.add_argument(
        "--graph", default=os.getenv("FAULKNER_GRAPH_NAME", "knowledge_graph")
    )
    ap.add_argument("--sample-size", type=int, default=50)
    args = ap.parse_args()

    log = setup_logging()
    log.info(
        "Connecting host=%s port=%d graph=%s password=%s",
        args.host, args.port, args.graph, "***" if args.password else "(none)",
    )

    try:
        graph = connect(args.host, args.port, args.password, args.graph)
    except Exception as e:
        log.error("Connection failed: %s", e)
        return 1

    log.info("Counting totals by label/edge-type")
    totals_nodes = count_total_by_label(graph)
    totals_edges = count_total_edges_by_type(graph)

    log.info("Scanning playbook-signature Patterns")
    playbook = find_playbook_patterns(graph)

    log.info("Sampling %d Failures", args.sample_size)
    failures = sample_failures(graph, args.sample_size)

    log.info("Counting edges incident to playbook Patterns")
    pb_edges = edge_incidence_for_playbooks(graph)

    log.info("Counting edges incident to ts-suffixed Failures")
    fail_edges = edge_incidence_for_failures_with_ts(graph)

    log.info("Computing top-20 Pattern name prefixes")
    prefixes = top_pattern_prefixes(graph, 20)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "connection": {
            "host": args.host,
            "port": args.port,
            "graph": args.graph,
        },
        "totals": {
            "nodes_by_label": totals_nodes,
            "edges_by_type": totals_edges,
        },
        "mkg_playbook_patterns": playbook,
        "failure_sample_analysis": failures,
        "edge_incidence": {
            "playbook_patterns": pb_edges,
            "ts_suffixed_failures": fail_edges,
        },
        "top_20_pattern_prefixes": prefixes,
    }

    json.dump(report, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    log.info("Audit complete; report written to stdout")
    return 0


if __name__ == "__main__":
    sys.exit(main())