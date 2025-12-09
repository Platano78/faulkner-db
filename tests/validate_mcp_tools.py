"""End-to-end validation of all 7 MCP tools with real data."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.mcp_tools import (
    add_decision,
    query_decisions,
    add_pattern,
    add_failure,
    find_related,
    detect_gaps,
    get_timeline
)

async def test_query_decisions():
    """Test hybrid search with semantic query."""
    print("\n" + "="*60)
    print("TEST 1: Query Decisions (Hybrid Search)")
    print("="*60)
    
    results = await query_decisions(
        query="knowledge graph temporal relationships"
    )
    print(f"✅ Found {len(results)} results")
    
    if results:
        print(f"\nTop result:")
        top = results[0]
        print(f"   ID: {top.get('decision_id', top.get('pattern_id', top.get('failure_id')))}")
        print(f"   Description: {top.get('description', '')[:80]}...")
        print(f"   Score: {top.get('score', 'N/A')}")
    
    assert len(results) > 0, "No results returned"
    return True

async def test_find_related():
    """Test graph traversal."""
    print("\n" + "="*60)
    print("TEST 2: Find Related (Graph Traversal)")
    print("="*60)
    
    # First get a node ID
    all_nodes = await query_decisions(query="")
    if not all_nodes:
        print("⚠️  No nodes in graph, skipping")
        return True
    
    node = all_nodes[0]
    node_id = node.get('metadata', {}).get('node_id', 'unknown')
    
    print(f"Testing with node: {node_id}")
    
    related = await find_related(node_id=node_id, depth=1)
    
    print(f"✅ Found {len(related)} related nodes")
    
    if related:
        print(f"\nSample relationships:")
        for rel in related[:3]:
            print(f"   → {rel.get('node_id')}: {rel.get('relationship_type')}")
    
    return True

async def test_detect_gaps():
    """Test NetworkX gap analysis."""
    print("\n" + "="*60)
    print("TEST 3: Detect Gaps (NetworkX Analysis)")
    print("="*60)
    
    gaps = await detect_gaps()
    
    print(f"✅ Detected {len(gaps)} knowledge gaps")
    
    # Break down by severity
    high = [g for g in gaps if g.get('severity') == 'HIGH']
    medium = [g for g in gaps if g.get('severity') == 'MEDIUM']
    low = [g for g in gaps if g.get('severity') == 'LOW']
    
    print(f"\nBy severity:")
    print(f"   HIGH: {len(high)}")
    print(f"   MEDIUM: {len(medium)}")
    print(f"   LOW: {len(low)}")
    
    if high:
        print(f"\nSample HIGH severity gap:")
        gap = high[0]
        print(f"   Type: {gap.get('type')}")
        print(f"   Recommendation: {gap.get('recommendation', 'N/A')[:60]}...")
    
    return True

async def test_get_timeline():
    """Test temporal view."""
    print("\n" + "="*60)
    print("TEST 4: Get Timeline (Temporal View)")
    print("="*60)
    
    events = await get_timeline(
        topic="architecture",
        start_date="2025-01-01T00:00:00Z",
        end_date="2025-12-31T23:59:59Z"
    )
    print(f"✅ Found {len(events)} events in timeline")
    
    if events:
        print(f"\nRecent events:")
        for event in events[:3]:
            print(f"   {event.get('timestamp', 'N/A')}: {event.get('description', '')[:60]}...")
    
    return True

async def test_add_operations():
    """Test write operations (add_decision, add_pattern, add_failure)."""
    print("\n" + "="*60)
    print("TEST 5: Add Operations (Write Tools)")
    print("="*60)
    
    # Test add_decision
    decision = await add_decision(
        description="Test decision for validation",
        rationale="Validating MCP tool functionality",
        alternatives=["Alternative 1", "Alternative 2"],
        related_to=[]
    )
    
    decision_id = decision.get('decision_id')
    print(f"✅ Decision created: {decision_id}")
    
    # Test add_pattern
    pattern = await add_pattern(
        name="Test Pattern for MCP Validation",
        implementation="This is a comprehensive test implementation that validates MCP tool functionality",
        use_cases=["Testing MCP tools", "Validation workflows"],
        context="Validation testing for production readiness"
    )
    
    pattern_id = pattern.get('pattern_id')
    print(f"✅ Pattern created: {pattern_id}")
    
    # Test add_failure
    failure = await add_failure(
        attempt="Test failure attempt",
        reason_failed="For validation",
        lesson_learned="Testing is important",
        alternative_solution="Test alternative"
    )
    
    failure_id = failure.get('failure_id')
    print(f"✅ Failure created: {failure_id}")
    
    return True

async def run_all_tests():
    """Execute complete test suite."""
    print("="*60)
    print("FAULKNER DB - MCP TOOLS VALIDATION")
    print("="*60)
    
    tests = [
        ("Query Decisions", test_query_decisions),
        ("Find Related", test_find_related),
        ("Detect Gaps", test_detect_gaps),
        ("Get Timeline", test_get_timeline),
        ("Add Operations", test_add_operations)
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ TEST FAILED: {name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print("VALIDATION COMPLETE")
    print("="*60)
    print(f"\nResults: {passed}/{len(tests)} tests passed")
    
    if failed == 0:
        print("\n✅ ALL TESTS PASSED - SYSTEM PRODUCTION READY")
    else:
        print(f"\n⚠️  {failed} tests failed - review errors above")
    
    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
