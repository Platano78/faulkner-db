#!/bin/bash

cd /home/platano/project/faulkner-db

echo "======================================================================"
echo "RELATIONSHIP QUALITY ASSESSMENT"
echo "======================================================================"

# Query a sample of relationships
./venv/bin/python3 -c "
from mcp_server.mcp_tools import query_decisions
import asyncio
from collections import Counter

async def assess_relationships():
    result = await query_decisions(query='')
    nodes = result if isinstance(result, list) else []
    
    # Collect relationship metadata
    rel_types = []
    with_reasoning = 0
    with_confidence = 0
    
    for node in nodes:
        for edge in node.get('edges', []):
            rel_types.append(edge.get('type', 'unknown'))
            if edge.get('reasoning'):
                with_reasoning += 1
            if edge.get('confidence'):
                with_confidence += 1
    
    total_edges = len(rel_types)
    
    print(f'\n📊 Relationship Assessment:')
    print(f'   Sample size: {len(nodes)} nodes')
    print(f'   Total edges: {total_edges:,}')
    
    if rel_types:
        print(f'\n🏷️  Type Distribution:')
        for rtype, count in Counter(rel_types).most_common():
            pct = count / total_edges * 100 if total_edges else 0
            print(f'   {rtype}: {count:,} ({pct:.1f}%)')
        
        print(f'\n✨ Quality Metrics:')
        if total_edges > 0:
            print(f'   With reasoning: {with_reasoning}/{total_edges} ({with_reasoning/total_edges*100:.1f}%)')
            print(f'   With confidence: {with_confidence}/{total_edges} ({with_confidence/total_edges*100:.1f}%)')
        
        # LLM enhancement usage
        llm_enhanced = sum(1 for rt in rel_types if rt not in ['SEMANTICALLY_SIMILAR', 'unknown'])
        if llm_enhanced > 0:
            print(f'   LLM-enhanced: {llm_enhanced}/{total_edges} ({llm_enhanced/total_edges*100:.1f}%)')
            print(f'   ✅ MKG local LLM was used')
        else:
            print(f'   ⚠️  No LLM enhancement detected (MKG may not have been available)')
    else:
        print('\n⚠️  No relationships found in current graph')
        print('   Run relationship extraction: ./venv/bin/python3 ingestion/relationship_extractor.py --full')

asyncio.run(assess_relationships())
" 2>&1 | grep -v 'INFO:'

echo "======================================================================"
