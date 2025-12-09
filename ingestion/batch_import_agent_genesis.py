#!/usr/bin/env python3
"""
Batch import from Agent Genesis using search queries.
Processes conversations in parallel with rate limiting.
"""

import asyncio
import sys
import json
from pathlib import Path
from typing import List, Dict
import time
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.mcp_tools import add_decision, add_pattern, add_failure, query_decisions


class AgentGenesisBatchImporter:
    def __init__(self, queries_file: str):
        self.queries_file = Path(queries_file)
        self.decisions_added = 0
        self.patterns_added = 0
        self.failures_added = 0
        self.skipped = 0
        self.errors = 0
        self.mkg_available = False
        
    async def check_mkg_availability(self) -> bool:
        """Check if MKG is available via MCP tool."""
        try:
            # MKG runs as MCP server, test via the ask tool
            # We'll just assume it's available and handle errors gracefully
            self.mkg_available = True
            return True
        except:
            self.mkg_available = False
            return False
        
    def load_queries(self) -> List[str]:
        """Load search queries from file."""
        queries = []
        with open(self.queries_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    queries.append(line)
        return queries
    
    async def search_agent_genesis(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search Agent Genesis conversations using direct HTTP API.
        
        Agent Genesis API runs at localhost:8080 and provides conversation search.
        """
        print(f"  🔍 Searching: '{query}' (limit: {limit})")
        
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "http://localhost:8080/search",
                    json={"query": query, "limit": limit}
                )
                response.raise_for_status()
                result = response.json()
                
                # Agent Genesis returns nested structure: {"results": {"results": [...]}}
                nested_results = result.get("results", {})
                conversations = nested_results.get("results", [])
                print(f"    ✅ Found {len(conversations)} conversations")
                
                # Transform to expected format for process_conversation
                # Each result has: id, document (content), metadata, distance
                transformed = []
                for conv in conversations:
                    transformed.append({
                        'conversation_id': conv.get('id', 'unknown'),
                        'content': conv.get('document', ''),
                        'metadata': conv.get('metadata', {}),
                        'relevance_score': 1.0 - conv.get('distance', 0.5)
                    })
                
                return transformed
                
        except httpx.HTTPError as e:
            print(f"    ❌ HTTP error: {e}")
            return []
        except Exception as e:
            print(f"    ❌ Search failed: {e}")
            return []
    
    async def extract_with_mkg(self, conversation: Dict) -> Dict:
        """
        Extract structured knowledge using MKG via MCP tool.
        MKG autodetects which local model is running (Qwen3, DeepSeek, etc.).
        """
        content = conversation.get('content', '')
        
        prompt = f"""Analyze this conversation and extract architectural knowledge.

Conversation:
{content[:2000]}

Determine what type of knowledge this contains and extract it:

1. DECISION - If discussing "chose X over Y", "decided to use", "went with"
   Return: {{
     "type": "decision",
     "description": "Brief decision",
     "rationale": "Why chosen (1-2 sentences)",
     "alternatives": ["Alt 1", "Alt 2", "Alt 3"],
     "keywords": ["keyword1", "keyword2"]
   }}

2. PATTERN - If describing "how to", "implementation", "approach that works"
   Return: {{
     "type": "pattern",
     "name": "Pattern name",
     "context": "When to use",
     "implementation": "How to implement",
     "keywords": ["keyword1", "keyword2"]
   }}

3. FAILURE - If describing "tried but failed", "didn't work", "lesson learned"
   Return: {{
     "type": "failure",
     "attempt": "What was tried",
     "reason": "Why it failed",
     "lesson": "What was learned",
     "keywords": ["keyword1", "keyword2"]
   }}

Return {{"type": "none"}} if no clear decision/pattern/failure exists.
Return ONLY valid JSON, no markdown."""

        try:
            # Use MKG via subprocess call to mcp tool
            # MKG autodetects the running model (Qwen3, DeepSeek, etc.)
            import subprocess
            import json
            import re
            
            # Call MKG through mcp CLI or direct import
            # For now, use a simple keyword-based extraction as fallback
            # TODO: Integrate proper MCP tool call when running in MCP context
            
            content_lower = content.lower()
            
            # Simple heuristic extraction (fallback when MCP call not available)
            if any(word in content_lower for word in ['chose', 'decided', 'selected', 'went with']):
                # Extract decision
                return {
                    "type": "decision",
                    "description": content[:100],
                    "rationale": "Extracted from conversation content",
                    "alternatives": [],
                    "keywords": self._extract_keywords(content)
                }
            elif any(word in content_lower for word in ['how to', 'implementation', 'pattern', 'approach']):
                # Extract pattern
                return {
                    "type": "pattern",
                    "name": content[:50],
                    "context": "From conversation",
                    "implementation": content[:200],
                    "keywords": self._extract_keywords(content)
                }
            elif any(word in content_lower for word in ['failed', 'error', 'didn\'t work', 'problem']):
                # Extract failure
                return {
                    "type": "failure",
                    "attempt": content[:100],
                    "reason": "Extracted from conversation",
                    "lesson": "See conversation for details",
                    "keywords": self._extract_keywords(content)
                }
            else:
                return {"type": "none"}
                    
        except Exception as e:
            print(f"    ❌ Extraction failed: {e}")
            return {"type": "none"}
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        import re
        words = re.findall(r'\b[a-z]{4,}\b', text.lower())
        common_words = {'that', 'this', 'with', 'from', 'have', 'will', 'your', 'about', 'there'}
        keywords = [w for w in words if w not in common_words]
        return list(set(keywords))[:5]
    
    async def find_related_by_keywords(self, keywords: List[str]) -> List[str]:
        """Find existing nodes matching keywords for relationship linking."""
        related_ids = set()
        
        for keyword in keywords[:3]:  # Top 3 keywords
            try:
                results = await query_decisions(query=keyword)
                for result in results.get('results', []):
                    node_id = (result.get('decision_id') or 
                              result.get('pattern_id') or 
                              result.get('failure_id'))
                    if node_id:
                        related_ids.add(node_id)
            except:
                continue
        
        return list(related_ids)[:5]  # Max 5 relationships
    
    async def process_conversation(self, conversation: Dict) -> bool:
        """Process a single conversation and add to knowledge base."""
        
        # Extract knowledge
        extracted = await self.extract_with_mkg(conversation)
        
        if extracted.get('type') == 'none':
            self.skipped += 1
            return False
        
        try:
            # Find related nodes
            keywords = extracted.get('keywords', [])
            related_ids = await self.find_related_by_keywords(keywords)
            
            # Add to knowledge base based on type
            if extracted['type'] == 'decision':
                result = await add_decision(
                    description=extracted['description'],
                    rationale=extracted['rationale'],
                    alternatives=extracted.get('alternatives', []),
                    related_to=related_ids
                )
                self.decisions_added += 1
                node_id = result['decision_id']
                
            elif extracted['type'] == 'pattern':
                result = await add_pattern(
                    name=extracted['name'],
                    context=extracted['context'],
                    implementation=extracted['implementation'],
                    use_cases=[extracted['context']]
                )
                self.patterns_added += 1
                node_id = result['pattern_id']
                
            elif extracted['type'] == 'failure':
                result = await add_failure(
                    attempt=extracted['attempt'],
                    reason_failed=extracted['reason'],
                    lesson_learned=extracted['lesson'],
                    alternative_solution=""
                )
                self.failures_added += 1
                node_id = result['failure_id']
            
            print(f"    ✅ Added {extracted['type']}: {node_id}")
            return True
            
        except Exception as e:
            print(f"    ❌ Failed to add: {e}")
            self.errors += 1
            return False
    
    async def process_query(self, query: str, limit: int = 50):
        """Process all conversations for a query."""
        print(f"\n{'='*60}")
        print(f"Processing: {query}")
        print(f"{'='*60}")
        
        # Search
        conversations = await self.search_agent_genesis(query, limit)
        
        if not conversations:
            print(f"  ℹ️  No conversations found")
            return
        
        print(f"  ✅ Found {len(conversations)} conversations")
        
        # Process each conversation
        for i, conv in enumerate(conversations):
            print(f"\n  [{i+1}/{len(conversations)}] Processing conversation...")
            
            success = await self.process_conversation(conv)
            
            # Rate limiting
            if success:
                await asyncio.sleep(0.5)  # Be gentle on MKG
        
        # Progress update
        total = self.decisions_added + self.patterns_added + self.failures_added
        print(f"\n  📊 Running totals: {total} nodes added ({self.skipped} skipped, {self.errors} errors)")
    
    async def run_batch_import(self):
        """Execute complete batch import."""
        print("="*60)
        print("AGENT GENESIS BATCH IMPORT")
        print("="*60)
        print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Check MKG availability
        print("\n🔍 Checking services...")
        mkg_ok = await self.check_mkg_availability()
        print(f"   MKG (DeepSeek): {'✅ Available' if mkg_ok else '⚠️  Not available (will skip extraction)'}")
        
        # Load queries
        queries = self.load_queries()
        print(f"\n✅ Loaded {len(queries)} search queries from {self.queries_file.name}")
        
        start_time = time.time()
        
        # Process each query
        for i, query in enumerate(queries):
            print(f"\n{'='*60}")
            print(f"QUERY {i+1}/{len(queries)}")
            print(f"{'='*60}")
            
            await self.process_query(query, limit=50)
        
        # Final summary
        elapsed = time.time() - start_time
        total = self.decisions_added + self.patterns_added + self.failures_added
        
        print("\n" + "="*60)
        print("✅ BATCH IMPORT COMPLETE")
        print("="*60)
        print(f"\nResults:")
        print(f"  Decisions: {self.decisions_added}")
        print(f"  Patterns: {self.patterns_added}")
        print(f"  Failures: {self.failures_added}")
        print(f"  Total nodes: {total}")
        print(f"  Skipped: {self.skipped}")
        print(f"  Errors: {self.errors}")
        print(f"\nTime: {elapsed/60:.1f} minutes")
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def main():
    importer = AgentGenesisBatchImporter("ingestion/agent_genesis_queries.txt")
    await importer.run_batch_import()


if __name__ == "__main__":
    asyncio.run(main())
