#!/usr/bin/env python3
"""Migrate MKG playbook Patterns from Faulkner-DB to MKG's SQLite playbook store.

Read-only against Faulkner. Writes to MKG SQLite via mkg.playbook.PlaybookStore.
Default --dry-run=true: reports mapping plan + 5 sample records, NO writes.

Usage:
  python scripts/migrate_mkg_to_sqlite.py [--dry-run/--no-dry-run]
                                          [--host HOST] [--port PORT]
                                          [--password PASS] [--graph NAME]
                                          [--mkg-repo PATH] [--db-path PATH]
                                          [--limit N]

Manifest: written to logs/migrate_manifest_<UTC-ts>.json so Task 4
(purge_migrated_nodes.py) can target exactly the migrated set.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import uuid
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
LOG_FILE = LOG_DIR / "migrate_mkg_to_sqlite.log"

PLAYBOOK_NAME_RE = re.compile(r"^playbook-(?P<category>[A-Za-z0-9_]+)-(?P<ts>\d{13})$")
DEFAULT_CONFIDENCE = 0.5


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("migrate_mkg_to_sqlite")
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


def connect_falkor(host: str, port: int, password: str | None, graph_name: str):
    kwargs: dict[str, Any] = {"host": host, "port": port}
    if password:
        kwargs["password"] = password
    db = FalkorDB(**kwargs)
    return db.select_graph(graph_name)


def parse_use_cases(raw: Any) -> tuple[str, list[str]]:
    """Faulkner stores use_cases as a JSON-encoded string. Decode safely."""
    if not raw:
        return ("", [])
    if isinstance(raw, list):
        items = [str(x) for x in raw]
    else:
        try:
            decoded = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return (str(raw), [str(raw)])
        if isinstance(decoded, list):
            items = [str(x) for x in decoded]
        else:
            items = [str(decoded)]
    items = [s for s in (i.strip() for i in items) if s]
    return ("; ".join(items), items)


def parse_source_files(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    try:
        decoded = json.loads(raw)
        if isinstance(decoded, list):
            return [str(x) for x in decoded]
    except (TypeError, json.JSONDecodeError):
        pass
    return [str(raw)]


def map_pattern_to_lesson(props: dict[str, Any]) -> dict[str, Any] | None:
    """Map a Faulkner playbook Pattern's props onto the SQLite lesson schema.

    Returns None if the name does not match the MKG playbook signature.
    """
    name = props.get("name") or ""
    m = PLAYBOOK_NAME_RE.match(name)
    if not m:
        return None
    category = m.group("category")
    name_ts = int(m.group("ts"))
    name_iso = datetime.fromtimestamp(name_ts / 1000, tz=timezone.utc).isoformat()

    raw_ts = props.get("timestamp")
    if isinstance(raw_ts, str) and raw_ts:
        try:
            datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            created_at = raw_ts
        except ValueError:
            created_at = name_iso
    else:
        created_at = name_iso

    decision = (props.get("implementation") or "").strip() or None
    context_text, raw_cases = parse_use_cases(props.get("use_cases"))
    if not context_text:
        ctx_fallback = (props.get("context") or "").strip()
        context_text = ctx_fallback or None

    metadata = {
        "faulkner_id": props.get("id"),
        "faulkner_name": name,
        "faulkner_label": "Pattern",
        "project": props.get("project"),
        "raw_use_cases": raw_cases,
        "source_files": parse_source_files(props.get("source_files")),
        "raw_context_field": props.get("context"),
        "name_unix_ms": name_ts,
        "name_derived_iso": name_iso,
        "migrated_at": datetime.now(timezone.utc).isoformat(),
        "migration_source": "scripts/migrate_mkg_to_sqlite.py",
    }

    return {
        "lesson_id": str(uuid.uuid4()),
        "topic": category,
        "context": context_text,
        "decision": decision,
        "outcome": "success",
        "confidence": DEFAULT_CONFIDENCE,
        "created_at": created_at,
        "metadata": metadata,
    }


def fetch_playbook_patterns(graph, limit: int | None) -> list[dict[str, Any]]:
    cypher = (
        "MATCH (p:Pattern) WHERE p.name STARTS WITH 'playbook-' RETURN p"
    )
    if limit and limit > 0:
        cypher += f" LIMIT {int(limit)}"
    rows = graph.query(cypher).result_set
    out: list[dict[str, Any]] = []
    for row in rows:
        node = row[0]
        props = dict(node.properties) if hasattr(node, "properties") else {}
        out.append(props)
    return out


def render_sample_table(samples: list[dict[str, Any]]) -> str:
    lines = [
        "Sample of mapped lessons (5 max):",
        "-" * 80,
    ]
    for i, sample in enumerate(samples, 1):
        lines.append(f"[{i}] faulkner_id={sample['metadata']['faulkner_id']}")
        lines.append(f"    name={sample['metadata']['faulkner_name']}")
        lines.append(f"    topic={sample['topic']!r}  outcome={sample['outcome']!r}")
        lines.append(f"    confidence={sample['confidence']}  created_at={sample['created_at']}")
        decision = (sample.get("decision") or "")[:120]
        context = (sample.get("context") or "")[:120]
        lines.append(f"    decision: {decision}")
        lines.append(f"    context:  {context}")
        lines.append("-" * 80)
    return "\n".join(lines)


def write_manifest(manifest_path: Path, payload: dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    ap.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    ap.add_argument("--host", default=os.getenv("FALKORDB_HOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("FALKORDB_PORT", "6380")))
    ap.add_argument("--password", default=os.getenv("FALKORDB_PASSWORD"))
    ap.add_argument("--graph", default=os.getenv("FAULKNER_GRAPH_NAME", "knowledge_graph"))
    ap.add_argument("--mkg-repo", default=os.getenv("MKG_REPO",
                    str(REPO_ROOT.parent / "deepseek-mcp-bridge")))
    ap.add_argument("--db-path", default=os.getenv("MKG_PLAYBOOK_DB"),
                    help="Override SQLite path (default: <mkg-repo>/data/playbook.db)")
    ap.add_argument("--limit", type=int, default=0,
                    help="Cap number of patterns processed (0 = no cap)")
    ap.add_argument("--force-rewrite", action="store_true", default=False,
                    help="Re-insert even if faulkner_id is already present in SQLite "
                         "(creates duplicate rows; off by default)")
    args = ap.parse_args()

    log = setup_logging()
    log.info("Mode=%s host=%s graph=%s mkg_repo=%s",
             "DRY-RUN" if args.dry_run else "WRITE", args.host, args.graph, args.mkg_repo)

    mkg_repo = Path(args.mkg_repo).resolve()
    if not mkg_repo.is_dir():
        log.error("MKG repo not found: %s", mkg_repo)
        return 1
    if str(mkg_repo) not in sys.path:
        sys.path.insert(0, str(mkg_repo))

    try:
        from mkg.playbook import PlaybookStore  # noqa: WPS433
    except ImportError as e:
        log.error("Cannot import mkg.playbook from %s: %s", mkg_repo, e)
        return 1

    try:
        graph = connect_falkor(args.host, args.port, args.password, args.graph)
    except Exception as e:
        log.error("FalkorDB connection failed: %s", e)
        return 1

    log.info("Fetching MKG-signature Patterns from Faulkner")
    patterns = fetch_playbook_patterns(graph, args.limit)
    log.info("Fetched %d Patterns matching 'playbook-' prefix", len(patterns))

    mapped: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for props in patterns:
        lesson = map_pattern_to_lesson(props)
        if lesson is None:
            skipped.append({"id": props.get("id"), "name": props.get("name"),
                            "reason": "name_did_not_match_playbook_signature"})
            continue
        mapped.append(lesson)

    by_topic: dict[str, int] = {}
    for lesson in mapped:
        by_topic[lesson["topic"]] = by_topic.get(lesson["topic"], 0) + 1

    summary = {
        "mode": "dry_run" if args.dry_run else "write",
        "fetched_patterns": len(patterns),
        "mapped_lessons": len(mapped),
        "skipped": len(skipped),
        "by_topic": dict(sorted(by_topic.items(), key=lambda kv: -kv[1])),
        "mkg_repo": str(mkg_repo),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    print(render_sample_table(mapped[:5]))
    print()
    print("Summary:")
    print(json.dumps(summary, indent=2))

    if args.dry_run:
        log.info("Dry-run complete; no writes performed")
        manifest_path = LOG_DIR / f"migrate_manifest_DRYRUN_{int(datetime.now().timestamp())}.json"
        write_manifest(manifest_path, {
            "summary": summary,
            "samples": mapped[:5],
            "skipped_examples": skipped[:5],
        })
        log.info("Dry-run manifest written to %s", manifest_path)
        return 0

    db_path = args.db_path or str(mkg_repo / "data" / "playbook.db")
    log.info("Opening MKG SQLite store at %s", db_path)

    inserted_ids: list[dict[str, str]] = []
    failed: list[dict[str, Any]] = []
    skipped_duplicate: list[dict[str, Any]] = []

    with PlaybookStore(db_path) as store:
        existing_fids: set[str] = set()
        cur = store._conn.execute(
            "SELECT json_extract(metadata, '$.faulkner_id') FROM lessons "
            "WHERE metadata IS NOT NULL"
        )
        for (fid,) in cur.fetchall():
            if fid:
                existing_fids.add(fid)
        if existing_fids:
            log.warning(
                "SQLite already contains %d migrated lessons; "
                "rows with matching faulkner_id will be skipped (use --force-rewrite to override)",
                len(existing_fids),
            )

        for lesson in mapped:
            fid = lesson["metadata"]["faulkner_id"]
            if fid in existing_fids and not args.force_rewrite:
                skipped_duplicate.append({
                    "faulkner_id": fid,
                    "faulkner_name": lesson["metadata"]["faulkner_name"],
                    "reason": "already_present_in_sqlite",
                })
                continue
            try:
                new_id = store.record_lesson(
                    topic=lesson["topic"],
                    context=lesson["context"],
                    decision=lesson["decision"],
                    outcome=lesson["outcome"],
                    confidence=lesson["confidence"],
                    metadata=lesson["metadata"],
                    lesson_id=lesson["lesson_id"],
                    created_at=lesson["created_at"],
                )
                inserted_ids.append({
                    "lesson_id": new_id,
                    "faulkner_id": lesson["metadata"]["faulkner_id"],
                    "faulkner_name": lesson["metadata"]["faulkner_name"],
                })
            except Exception as e:
                failed.append({
                    "faulkner_id": lesson["metadata"]["faulkner_id"],
                    "faulkner_name": lesson["metadata"]["faulkner_name"],
                    "error": str(e),
                })

        try:
            cur = store._conn.execute("SELECT count(*) FROM lessons")
            sqlite_total = cur.fetchone()[0]
        except Exception as e:
            log.error("Could not count rows in SQLite: %s", e)
            sqlite_total = -1

    log.info("Inserted %d / mapped %d / failed %d", len(inserted_ids), len(mapped), len(failed))

    manifest = {
        "summary": {**summary, "inserted": len(inserted_ids),
                    "skipped_duplicate": len(skipped_duplicate),
                    "failed": len(failed), "sqlite_total_after": sqlite_total},
        "inserted_ids": inserted_ids,
        "skipped_duplicate": skipped_duplicate,
        "failed": failed,
        "skipped": skipped,
    }
    manifest_path = LOG_DIR / f"migrate_manifest_{int(datetime.now().timestamp())}.json"
    write_manifest(manifest_path, manifest)
    log.info("Manifest written to %s", manifest_path)
    print(f"\nManifest: {manifest_path}")

    print("\nVerification:")
    print(f"  Faulkner playbook Patterns fetched: {len(patterns)}")
    print(f"  Mapped (signature matched):         {len(mapped)}")
    print(f"  Inserted into SQLite:               {len(inserted_ids)}")
    print(f"  Failed inserts:                     {len(failed)}")
    print(f"  SQLite total rows after migration:  {sqlite_total}")

    if failed:
        log.warning("Some inserts failed — see manifest.failed[]")
        return 1
    if skipped_duplicate:
        log.info(
            "%d lesson(s) skipped as already present in SQLite (idempotent re-run)",
            len(skipped_duplicate),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())