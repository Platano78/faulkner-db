"""Ingestion guards — prevent re-pollution of the knowledge graph."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

# --- Public exceptions ---

class IngestionRejected(Exception):
    """Raised when a write is blocked by ingestion guards."""
    def __init__(self, reason, fields):
        super().__init__(reason)
        self.reason = reason
        self.fields = fields

# --- Default blocklist patterns ---

_DEFAULT_BLOCKLIST_PATTERNS = [
    r"^playbook-.*-\d{13}$",
    r".*-\d{13}$",
]

# --- Private helpers ---


def _load_blocklist() -> list:
    """Return compiled regexes from env file or defaults."""
    blocklist_file = os.environ.get("FAULKNER_INGESTION_BLOCKLIST_FILE")
    if blocklist_file:
        path = Path(blocklist_file)
        text = path.read_text(encoding="utf-8")
        # Try JSON first
        try:
            data = json.loads(text)
            patterns = data.get("patterns", [])
            return [re.compile(p) for p in patterns]
        except (json.JSONDecodeError, KeyError):
            pass
        # Plain text: one regex per line, skip comments and blanks
        return [re.compile(line.strip()) for line in text.splitlines()
                if line.strip() and not line.strip().startswith("#")]
    return [re.compile(p) for p in _DEFAULT_BLOCKLIST_PATTERNS]


def _get_rejection_log_path() -> Path:
    """Return the rejection log path from env, never cached."""
    raw = os.environ.get("FAULKNER_REJECTION_LOG")
    if raw:
        return Path(raw)
    return Path("logs/rejected_writes.jsonl")


def _log_rejection(payload: dict) -> None:
    """Append one JSON line to the rejection log. Never raises."""
    try:
        log_path = _get_rejection_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


# --- Public API ---


def validate_write(
    label: str,
    *,
    name_fields: dict,
    source_files=None,
    source=None,
) -> None:
    """Raise IngestionRejected if the write looks polluted.

    Checks:
      A. name_field values against blocklist regexes.
      B. source_files containing 'agent-genesis'.
      C. source must be 'manual' or 'reviewed_automated' unless
         FAULKNER_ALLOW_AUTOMATED is truthy.
    """
    # --- A. Blocklist check ---
    blocklist = _load_blocklist()
    for field_name, field_value in name_fields.items():
        if field_value is None:
            continue
        for pat in blocklist:
            if pat.search(str(field_value)):
                reason = "blocklist_match"
                _log_rejection({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "label": label,
                    "reason": reason,
                    "sample_name_fields": {
                        k: (str(v)[:200] if v else None)
                        for k, v in name_fields.items()
                    },
                    "source": source,
                    "source_files": source_files,
                    "blocklist_pattern_matched": pat.pattern,
                })
                raise IngestionRejected(reason, fields={"name_fields": name_fields})

    # --- B. agent-genesis in source_files ---
    if source_files:
        for sf in source_files:
            if "agent-genesis" in str(sf):
                reason = "agent_genesis_source_files"
                _log_rejection({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "label": label,
                    "reason": reason,
                    "sample_name_fields": {
                        k: (str(v)[:200] if v else None)
                        for k, v in name_fields.items()
                    },
                    "source": source,
                    "source_files": source_files,
                    "blocklist_pattern_matched": None,
                })
                raise IngestionRejected(reason, fields={"source_files": source_files})

    # --- C. source validation ---
    allow_auto_raw = os.environ.get("FAULKNER_ALLOW_AUTOMATED")
    allow_automated = (
        allow_auto_raw is not None
        and allow_auto_raw.strip().lower() in ("true", "1")
    )
    if not allow_automated:
        if source not in ("manual", "reviewed_automated"):
            reason = "missing_or_invalid_source"
            _log_rejection({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "label": label,
                "reason": reason,
                "sample_name_fields": {
                    k: (str(v)[:200] if v else None)
                    for k, v in name_fields.items()
                },
                "source": source,
                "source_files": source_files,
                "blocklist_pattern_matched": None,
            })
            raise IngestionRejected(reason, fields={"source": source})
