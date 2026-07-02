"""Gate tests for the clamp-and-preserve overflow behaviour on add_decision /
add_failure, and the add_decision_json single-parameter escape hatch.

No live FalkorDB is required: the storage boundary (_get_client) is stubbed,
and the FastMCP server's startup FalkorDB health check is stubbed before
import so the module can be imported without a running database.
"""
import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mcp_server.mcp_tools as mcp_tools


class _FakeGraphClient:
    """Stands in for GraphitiClient at the storage boundary."""

    def __init__(self):
        self.added_nodes = []
        self.connections = []

    def add_node(self, model):
        self.added_nodes.append(model)
        return getattr(model, "id", None)

    def connect_decisions(self, decision_a_id, decision_b_id, relationship):
        self.connections.append((decision_a_id, decision_b_id, relationship))


@pytest.fixture
def fake_client(monkeypatch):
    client = _FakeGraphClient()
    monkeypatch.setattr(mcp_tools, "_get_client", lambda: client)
    return client


@pytest.fixture
def overflow_log(tmp_path, monkeypatch):
    log_path = tmp_path / "overflow_capture.jsonl"
    monkeypatch.setattr(mcp_tools, "_OVERFLOW_LOG", log_path)
    return log_path


def _read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _import_server_fastmcp_with_stubbed_health(monkeypatch):
    """Import mcp_server.server_fastmcp with its startup FalkorDB health
    check stubbed out — this environment has no live database, and the real
    health check calls sys.exit(1) on connection failure."""
    import core.config_loader as config_loader
    monkeypatch.setattr(config_loader, "validate_connection", lambda config: None)

    import redis as redis_module
    fake_redis_client = MagicMock()
    fake_redis_client.execute_command.return_value = ["header", [[15]]]
    monkeypatch.setattr(redis_module, "Redis", lambda *a, **kw: fake_redis_client)

    if "mcp_server.server_fastmcp" in sys.modules:
        return importlib.reload(sys.modules["mcp_server.server_fastmcp"])
    return importlib.import_module("mcp_server.server_fastmcp")


# --- (a) description overflow on add_decision ---

@pytest.mark.asyncio
async def test_add_decision_description_overflow_clamps_and_preserves(fake_client, overflow_log):
    long_description = "D" * 3200
    rationale = "A rationale that clears the twenty character minimum length requirement easily."

    result = await mcp_tools.add_decision(
        description=long_description,
        rationale=rationale,
        alternatives=[],
        related_to=[],
        source="manual",
    )

    assert result["status"] == "created"
    assert "warning" in result
    assert "description truncated 3200→2000 chars" in result["warning"]
    assert "data/overflow_capture.jsonl" in result["warning"]

    stored_decision = fake_client.added_nodes[0]
    assert len(stored_decision.description) <= 2000

    lines = _read_jsonl(overflow_log)
    matching = [l for l in lines if l["field"] == "description"]
    assert len(matching) == 1
    assert matching[0]["tool"] == "add_decision"
    assert matching[0]["full_text"] == long_description
    assert len(matching[0]["full_text"]) == 3200
    assert "ts" in matching[0]


# --- (b) rationale overflow on add_decision (same call, both fields over cap) ---

@pytest.mark.asyncio
async def test_add_decision_rationale_overflow_clamps_and_preserves(fake_client, overflow_log):
    description = "A description long enough to pass validation without tripping the cap."
    long_rationale = "R" * 6000

    result = await mcp_tools.add_decision(
        description=description,
        rationale=long_rationale,
        alternatives=[],
        related_to=[],
        source="manual",
    )

    assert result["status"] == "created"
    assert "warning" in result
    assert "rationale truncated 6000→5000 chars" in result["warning"]

    stored_decision = fake_client.added_nodes[0]
    assert len(stored_decision.rationale) <= 5000

    lines = _read_jsonl(overflow_log)
    matching = [l for l in lines if l["field"] == "rationale"]
    assert len(matching) == 1
    assert matching[0]["tool"] == "add_decision"
    assert matching[0]["full_text"] == long_rationale
    assert len(matching[0]["full_text"]) == 6000


# --- clamp also applies to add_failure's max-capped fields ---

@pytest.mark.asyncio
async def test_add_failure_reason_failed_overflow_clamps_and_preserves(fake_client, overflow_log):
    long_reason = "X" * 2500

    result = await mcp_tools.add_failure(
        attempt="Tried a reasonable approach that ultimately did not pan out.",
        reason_failed=long_reason,
        lesson_learned="Learned something useful from this failed attempt for next time.",
        alternative_solution=None,
        source="manual",
    )

    assert result["status"] == "created"
    assert "warning" in result
    assert "reason_failed truncated 2500→2000 chars" in result["warning"]

    stored_failure = fake_client.added_nodes[0]
    assert len(stored_failure.reason_failed) <= 2000

    lines = _read_jsonl(overflow_log)
    matching = [l for l in lines if l["field"] == "reason_failed"]
    assert len(matching) == 1
    assert matching[0]["tool"] == "add_failure"
    assert matching[0]["full_text"] == long_reason


# --- (c) add_decision_json round-trip with a realistic multiline over-cap payload ---

@pytest.mark.asyncio
async def test_add_decision_json_round_trip_with_overflow(fake_client, overflow_log, monkeypatch):
    server = _import_server_fastmcp_with_stubbed_health(monkeypatch)
    # server_fastmcp imported its own reference to mcp_tools functions; since
    # the underlying module object is shared, patching mcp_tools._get_client
    # (via the fake_client fixture) still applies to calls made through it.
    monkeypatch.setattr(sys.modules["mcp_server.mcp_tools"], "_get_client", lambda: fake_client)

    long_description = ("Line one of a multiline rationale.\n" * 80)[:2500]
    payload = json.dumps({
        "description": long_description,
        "rationale": "This rationale clears the minimum length requirement for a decision record.",
        "alternatives": ["Option A", "Option B"],
        "related_to": [],
    })

    add_decision_json_fn = server.add_decision_json.fn
    result = await add_decision_json_fn(payload)

    assert result["status"] == "created"
    assert "warning" in result
    assert f"description truncated {len(long_description)}→2000 chars" in result["warning"]

    stored_decision = fake_client.added_nodes[-1]
    assert len(stored_decision.description) <= 2000

    lines = _read_jsonl(overflow_log)
    matching = [l for l in lines if l["field"] == "description" and l["tool"] == "add_decision"]
    assert matching[-1]["full_text"] == long_description


@pytest.mark.asyncio
async def test_add_decision_json_rejects_malformed_json(fake_client, overflow_log, monkeypatch):
    server = _import_server_fastmcp_with_stubbed_health(monkeypatch)
    add_decision_json_fn = server.add_decision_json.fn

    result = await add_decision_json_fn("{not valid json")

    assert result["status"] == "error"
    assert "invalid JSON payload" in result["reason"]


# --- (d) in-cap call: unchanged behaviour, no warning ---

@pytest.mark.asyncio
async def test_add_decision_in_cap_no_warning(fake_client, overflow_log):
    result = await mcp_tools.add_decision(
        description="Use Redis for caching hot query results across the service.",
        rationale="Low latency and high throughput are required for this workload to meet SLAs.",
        alternatives=["Memcached", "In-memory cache"],
        related_to=[],
        source="manual",
    )

    assert result["status"] == "created"
    assert "warning" not in result
    assert _read_jsonl(overflow_log) == []


# --- add_decision_json: wrong-typed field surfaces as a clean error, not a raw ValidationError ---

@pytest.mark.asyncio
async def test_add_decision_json_wrong_typed_field_returns_clean_error(fake_client, overflow_log, monkeypatch):
    server = _import_server_fastmcp_with_stubbed_health(monkeypatch)
    monkeypatch.setattr(sys.modules["mcp_server.mcp_tools"], "_get_client", lambda: fake_client)

    payload = json.dumps({
        "description": "A description long enough to pass validation without tripping the cap.",
        "rationale": "This rationale clears the minimum length requirement for a decision record.",
        "alternatives": "Z",
    })

    add_decision_json_fn = server.add_decision_json.fn
    result = await add_decision_json_fn(payload)

    assert result["status"] == "error"
    assert "alternatives" in result["reason"]
    assert fake_client.added_nodes == []


# --- FIX B: clamp math lands exactly at max_length, not max_length - 2 ---

@pytest.mark.asyncio
async def test_add_decision_description_clamped_length_is_exactly_max_length(fake_client, overflow_log):
    result = await mcp_tools.add_decision(
        description="D" * 3200,
        rationale="A rationale that clears the twenty character minimum length requirement easily.",
        alternatives=[],
        related_to=[],
        source="manual",
    )

    assert result["status"] == "created"
    stored_decision = fake_client.added_nodes[0]
    assert len(stored_decision.description) == 2000
    assert stored_decision.description.endswith(mcp_tools._TRUNCATION_MARKER)


@pytest.mark.asyncio
async def test_add_failure_in_cap_no_warning(fake_client, overflow_log):
    result = await mcp_tools.add_failure(
        attempt="Used RabbitMQ with excessive queues under heavy load conditions.",
        reason_failed="Performance degraded badly once queue count crossed a few hundred.",
        lesson_learned="Limit queue count per node or switch to a streaming platform instead.",
        alternative_solution="Migrated to Apache Kafka for the high-fanout topics.",
        source="manual",
    )

    assert result["status"] == "created"
    assert "warning" not in result
    assert _read_jsonl(overflow_log) == []
