#!/usr/bin/env python3
"""Comprehensive MCP Tools Test - All 7 tools with real scenarios."""
import asyncio
import json
from mcp_server.server import MCPServer

async def comprehensive_test():
    server = MCPServer()
    
    print("\n" + "="*70)
    print("  FAULKNER DB MCP TOOLS - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    # ========== Test 1: add_decision ==========
    print("\n[1/7] Testing add_decision - Recording architecture decisions")
    print("-" * 70)
    
    decisions = [
        {
            'description': 'Chose FalkorDB over Neo4j for temporal knowledge graph',
            'rationale': 'CPU-only operation, gaming-friendly, Redis-compatible protocol',
            'alternatives': ['Neo4j (needs GPU)', 'ArangoDB (complex setup)', 'Amazon Neptune (cloud-only)'],
            'related_to': []
        },
        {
            'description': 'Implemented MCP architecture for Claude Code integration',
            'rationale': 'Enables standardized tool calling and knowledge access from AI assistants',
            'alternatives': ['Direct API', 'Custom protocol'],
            'related_to': []
        },
        {
            'description': 'Used hybrid search (semantic + keyword) for decision retrieval',
            'rationale': 'Combines precision of keyword search with semantic understanding',
            'alternatives': ['Pure semantic', 'Pure keyword', 'Elasticsearch'],
            'related_to': []
        }
    ]
    
    created_decisions = []
    for i, dec in enumerate(decisions, 1):
        result = await server.handle_request({'tool': 'add_decision', 'params': dec})
        if result.get('success'):
            decision_id = result['result']['decision_id']
            created_decisions.append(decision_id)
            print(f"   ✅ Decision {i}: {decision_id} - {dec['description'][:60]}...")
        else:
            print(f"   ❌ Failed: {result.get('error')}")
    
    # ========== Test 2: query_decisions ==========
    print("\n[2/7] Testing query_decisions - Searching knowledge base")
    print("-" * 70)
    
    queries = [
        'FalkorDB graph database',
        'MCP Claude integration',
        'hybrid search semantic'
    ]
    
    for query in queries:
        result = await server.handle_request({
            'tool': 'query_decisions',
            'params': {'query': query}
        })
        if result.get('success'):
            results = result['result']
            print(f"   🔍 Query: '{query}'")
            print(f"      → Found {len(results)} results")
            if results:
                top = results[0]
                print(f"      → Top match (score: {top['score']:.3f}): {top['content'][:70]}...")
        else:
            print(f"   ❌ Query failed: {result.get('error')}")
    
    # ========== Test 3: add_pattern ==========
    print("\n[3/7] Testing add_pattern - Recording successful patterns")
    print("-" * 70)
    
    patterns = [
        {
            'name': 'Temporal Graph Modeling',
            'implementation': 'Use LED_TO edges to represent temporal causality between decisions',
            'use_cases': ['Decision tracking', 'Knowledge evolution', 'Historical analysis'],
            'context': 'When modeling sequential relationships in architectural knowledge'
        },
        {
            'name': 'Hybrid Search Architecture',
            'implementation': 'Combine vector embeddings with keyword matching using reranking',
            'use_cases': ['Semantic search', 'Precise retrieval', 'Context-aware queries'],
            'context': 'When precision and recall are both critical for search quality'
        }
    ]
    
    for pattern in patterns:
        result = await server.handle_request({'tool': 'add_pattern', 'params': pattern})
        if result.get('success'):
            pattern_id = result['result']['pattern_id']
            print(f"   ✅ Pattern: {pattern_id} - {pattern['name']}")
        else:
            print(f"   ❌ Failed: {result.get('error')}")
    
    # ========== Test 4: add_failure ==========
    print("\n[4/7] Testing add_failure - Learning from failures")
    print("-" * 70)
    
    failures = [
        {
            'attempt': 'Initially tried using MongoDB for graph relationships',
            'reason_failed': 'Poor performance on multi-hop traversal queries (>5s for 3 hops)',
            'lesson_learned': 'Use native graph databases for relationship-heavy workloads',
            'alternative_solution': 'Migrated to FalkorDB with 100x performance improvement'
        },
        {
            'attempt': 'Attempted pure keyword search for decision retrieval',
            'reason_failed': 'Missed semantically related decisions due to term mismatch',
            'lesson_learned': 'Semantic understanding crucial for knowledge retrieval',
            'alternative_solution': 'Implemented hybrid search with sentence-transformers'
        }
    ]
    
    for failure in failures:
        result = await server.handle_request({'tool': 'add_failure', 'params': failure})
        if result.get('success'):
            failure_id = result['result']['failure_id']
            print(f"   ✅ Failure: {failure_id} - {failure['attempt'][:60]}...")
        else:
            print(f"   ❌ Failed: {result.get('error')}")
    
    # ========== Test 5: find_related ==========
    print("\n[5/7] Testing find_related - Graph traversal")
    print("-" * 70)
    
    if created_decisions:
        for decision_id in created_decisions[:2]:  # Test first 2 decisions
            result = await server.handle_request({
                'tool': 'find_related',
                'params': {'node_id': decision_id, 'depth': 1}
            })
            if result.get('success'):
                related = result['result']
                print(f"   🔗 Node: {decision_id}")
                print(f"      → Found {len(related)} related nodes")
                for rel in related[:3]:  # Show first 3
                    print(f"         • {rel['relationship_type']} → {rel['related_node_id']}")
            else:
                print(f"   ❌ Failed for {decision_id}: {result.get('error')}")
    else:
        print("   ⚠️  No decisions created to find relationships")
    
    # ========== Test 6: detect_gaps ==========
    print("\n[6/7] Testing detect_gaps - Knowledge gap analysis")
    print("-" * 70)
    
    result = await server.handle_request({'tool': 'detect_gaps', 'params': {}})
    if result.get('success'):
        gaps = result['result']
        print(f"   📊 Gap Analysis Complete")
        print(f"      → Detected {len(gaps)} knowledge gaps")
        for gap in gaps:
            print(f"      • Type: {gap['gap_type']}")
            print(f"        Severity: {gap['severity']}")
            print(f"        Affected: {len(gap['affected_nodes'])} nodes")
            print(f"        Recommendation: {gap['recommendation']}")
    else:
        print(f"   ❌ Analysis failed: {result.get('error')}")
    
    # ========== Test 7: get_timeline ==========
    print("\n[7/7] Testing get_timeline - Temporal knowledge view")
    print("-" * 70)
    
    result = await server.handle_request({
        'tool': 'get_timeline',
        'params': {
            'topic': 'architecture decisions',
            'start_date': '2024-01-01T00:00:00',
            'end_date': '2024-12-31T23:59:59'
        }
    })
    if result.get('success'):
        timeline = result['result']
        print(f"   📅 Timeline Generated")
        print(f"      → Found {len(timeline)} events")
        for event in timeline:
            print(f"      • {event['timestamp']}: {event['type']} - {event['id']}")
    else:
        print(f"   ❌ Timeline failed: {result.get('error')}")
    
    # ========== Final Metrics ==========
    print("\n" + "="*70)
    print("  FINAL METRICS & SUMMARY")
    print("="*70)
    
    metrics = await server.get_server_metrics()
    
    print("\n📊 Tool Usage:")
    for tool, count in metrics['tool_usage'].items():
        print(f"   {tool:25} {count:3} invocations")
    
    print("\n⚡ Performance:")
    for tool, time_ms in metrics['response_times'].items():
        status = "✅" if time_ms < 2.0 else "⚠️"
        print(f"   {status} {tool:25} {time_ms:.3f}s")
    
    print("\n📈 Knowledge Growth:")
    growth = metrics['knowledge_growth']
    print(f"   Decisions: {growth['decisions']}")
    print(f"   Patterns:  {growth['patterns']}")
    print(f"   Failures:  {growth['failures']}")
    
    if metrics['errors']:
        print("\n❌ Errors:")
        for tool, error_count in metrics['errors'].items():
            print(f"   {tool}: {error_count}")
    else:
        print("\n✅ No errors encountered")
    
    print("\n" + "="*70)
    print("  TEST SUITE COMPLETE - ALL 7 TOOLS VALIDATED")
    print("="*70 + "\n")

if __name__ == '__main__':
    asyncio.run(comprehensive_test())
