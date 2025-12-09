#!/usr/bin/env python3
"""
Agent Genesis Enhanced Extraction using MKG semantic analysis.
Processes conversations with DeepSeek/Qwen3 for high-quality knowledge extraction.
"""

import asyncio
import sys
import json
import httpx
from pathlib import Path
from typing import List, Dict, Optional
import time
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.mcp_tools import add_decision, add_pattern, add_failure


class AgentGenesisMKGExtractor:
    """Enhanced Agent Genesis extractor using MKG for semantic analysis."""
    
    def __init__(self, queries_file: str, batch_size: int = 20, use_mkg: bool = True):
        self.queries_file = Path(queries_file)
        self.batch_size = batch_size
        self.use_mkg = use_mkg
        
        # Statistics
        self.decisions_added = 0
        self.patterns_added = 0
        self.failures_added = 0
        self.skipped = 0
        self.errors = 0
        self.total_processed = 0
        
        # MKG configuration - Qwen3 14B local model with unlimited tokens
        self.mkg_url = "http://100.80.229.35:1234"  # MKG local model endpoint (Qwen3 14B)
        
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
        """Search Agent Genesis conversations."""
        print(f"  🔍 Searching: '{query}' (limit: {limit})")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "http://localhost:8080/search",
                    json={"query": query, "limit": limit}
                )
                response.raise_for_status()
                result = response.json()
                
                # Extract conversations
                nested_results = result.get("results", {})
                conversations = nested_results.get("results", [])
                print(f"    ✅ Found {len(conversations)} conversations")
                
                # Transform to expected format
                transformed = []
                for conv in conversations:
                    transformed.append({
                        'conversation_id': conv.get('id', 'unknown'),
                        'content': conv.get('document', ''),
                        'metadata': conv.get('metadata', {}),
                        'relevance_score': 1.0 - conv.get('distance', 0.5)
                    })
                
                return transformed
                
        except Exception as e:
            print(f"    ❌ Search failed: {e}")
            return []
    
    async def extract_with_mkg(self, conversation: Dict) -> Optional[Dict]:
        """Extract knowledge using MKG semantic analysis via MCP."""
        content = conversation.get('content', '')
        
        if len(content) < 100:
            return None  # Too short for meaningful extraction
        
        # Use MKG via MCP tool directly - Improved prompt for Qwen3 14B
        prompt = f"""Analyze this technical conversation and extract EXACTLY ONE of these three types of insights:

TYPE 1 - TECHNICAL DECISION: A deliberate choice between technical alternatives
Examples: "We chose Redis over MongoDB", "Decided to use TypeScript instead of JavaScript"
Format: {{"type": "decision", "description": "brief summary", "rationale": "why this choice", "alternatives": ["option1", "option2"]}}

TYPE 2 - RECURRING PATTERN: A repeated approach or solution pattern
Examples: "Always implement health checks", "Use dependency injection for testability"
Format: {{"type": "pattern", "name": "pattern name", "context": "when to use", "implementation": "how to apply"}}

TYPE 3 - SYSTEMATIC FAILURE: A consistent problem or anti-pattern
Examples: "Timeouts during cache invalidation", "Memory leaks in event handlers"
Format: {{"type": "failure", "attempt": "what was tried", "reason": "why it failed", "lesson": "what we learned"}}

Conversation:
{content[:2000]}

Respond with ONLY valid JSON. If none of these patterns are clearly present, return {{"type": "none"}}.
No markdown, no explanation, just JSON."""

        try:
            import json as json_lib
            import re
            
            # Use MKG local model directly (unlimited tokens)
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.mkg_url}/v1/chat/completions",
                    json={
                        "model": "local",
                        "messages": [
                            {"role": "system", "content": "You are a JSON extraction assistant. Respond with ONLY valid JSON, no markdown, no thinking tags, no explanation. Just the JSON object."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 500
                    },
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    return None
                
                result = response.json()
                
                # Extract content from OpenAI-compatible response
                choices = result.get('choices', [])
                if not choices:
                    return None
                
                answer = choices[0].get('message', {}).get('content', '').strip()
                
                # Debug: print first response
                if not hasattr(self, '_debug_shown'):
                    print(f"\n    [DEBUG] Sample response: {answer[:200]}...")
                    self._debug_shown = True
                
                # Robust cleaning to handle thinking tags, markdown, etc.
                cleaned = answer
                
                # Remove thinking tags
                cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
                cleaned = re.sub(r'<think>.*', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
                
                # Remove markdown code blocks
                cleaned = re.sub(r'```json\s*', '', cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r'```\s*', '', cleaned)
                cleaned = re.sub(r'`+', '', cleaned)
                
                # Remove leading/trailing non-JSON text
                cleaned = re.sub(r'^[^\{\[]*', '', cleaned)
                cleaned = re.sub(r'[^\}\]]*
                
        except Exception as e:
            # Silent fallback to heuristic
            return None
    
    async def process_conversation(self, conversation: Dict, query: str) -> bool:
        """Process a single conversation and add to knowledge base."""
        
        # Extract knowledge
        if self.use_mkg:
            extracted = await self.extract_with_mkg(conversation)
        else:
            # Fallback to simple heuristic
            extracted = self._simple_extract(conversation)
        
        if not extracted or extracted.get('type') == 'none':
            self.skipped += 1
            return False
        
        try:
            conv_id = conversation.get('conversation_id', 'unknown')
            source_ref = f"agent-genesis:conversation:{conv_id}:query:{query}"
            
            # Add to knowledge base based on type
            if extracted['type'] == 'decision':
                result = await add_decision(
                    description=extracted.get('description', '')[:200],
                    rationale=extracted.get('rationale', '')[:500],
                    alternatives=extracted.get('alternatives', [])[:5],
                    related_to=[]
                )
                self.decisions_added += 1
                node_id = result['decision_id']
                print(f"    ✅ Added decision: {node_id}")
                
            elif extracted['type'] == 'pattern':
                result = await add_pattern(
                    name=extracted.get('name', '')[:100],
                    context=extracted.get('context', '')[:200],
                    implementation=extracted.get('implementation', '')[:1000],
                    use_cases=[extracted.get('context', '')[:200]]
                )
                self.patterns_added += 1
                node_id = result['pattern_id']
                print(f"    ✅ Added pattern: {node_id}")
                
            elif extracted['type'] == 'failure':
                result = await add_failure(
                    attempt=extracted.get('attempt', '')[:200],
                    reason_failed=extracted.get('reason', '')[:500],
                    lesson_learned=extracted.get('lesson', '')[:500],
                    alternative_solution=""
                )
                self.failures_added += 1
                node_id = result['failure_id']
                print(f"    ✅ Added failure: {node_id}")
            
            return True
            
        except Exception as e:
            print(f"    ❌ Failed to add: {e}")
            self.errors += 1
            return False
    
    def _simple_extract(self, conversation: Dict) -> Optional[Dict]:
        """Simple fallback extraction without MKG."""
        content = conversation.get('content', '').lower()
        
        if any(word in content for word in ['chose', 'decided', 'selected']):
            return {
                "type": "decision",
                "description": content[:100],
                "rationale": "Extracted from conversation",
                "alternatives": []
            }
        elif any(word in content for word in ['pattern', 'approach', 'implementation']):
            return {
                "type": "pattern",
                "name": content[:50],
                "context": "From conversation",
                "implementation": content[:200]
            }
        elif any(word in content for word in ['failed', 'error', 'problem']):
            return {
                "type": "failure",
                "attempt": content[:100],
                "reason": "See conversation",
                "lesson": "Documented in conversation"
            }
        
        return None
    
    async def process_query_batch(self, query: str, limit: int = 50):
        """Process all conversations for a query in batches."""
        print(f"\n{'='*60}")
        print(f"Processing: {query}")
        print(f"{'='*60}")
        
        # Search
        conversations = await self.search_agent_genesis(query, limit)
        
        if not conversations:
            print(f"  ℹ️  No conversations found")
            return
        
        print(f"  ✅ Found {len(conversations)} conversations")
        print(f"  🤖 Using: {'MKG DeepSeek' if self.use_mkg else 'Simple heuristics'}")
        
        # Process in batches
        for i in range(0, len(conversations), self.batch_size):
            batch = conversations[i:i+self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(conversations) + self.batch_size - 1) // self.batch_size
            
            print(f"\n  📦 Batch {batch_num}/{total_batches} ({len(batch)} conversations)")
            
            for j, conv in enumerate(batch):
                print(f"    [{i+j+1}/{len(conversations)}] Processing...", end=' ')
                
                success = await self.process_conversation(conv, query)
                self.total_processed += 1
                
                # Rate limiting for MKG
                if success and self.use_mkg:
                    await asyncio.sleep(1.0)  # Be gentle on MKG
            
            # Batch summary
            total = self.decisions_added + self.patterns_added + self.failures_added
            success_rate = (total / self.total_processed * 100) if self.total_processed > 0 else 0
            print(f"\n  📊 Progress: {total} nodes | {success_rate:.1f}% success | {self.skipped} skipped | {self.errors} errors")
    
    async def run_enhanced_extraction(self, max_queries: Optional[int] = None):
        """Execute enhanced batch extraction with MKG."""
        print("="*60)
        print("AGENT GENESIS ENHANCED EXTRACTION (MKG)")
        print("="*60)
        print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Mode: {'MKG Semantic Analysis' if self.use_mkg else 'Simple Heuristics'}")
        print(f"Batch Size: {self.batch_size}")
        
        # Check MKG availability
        if self.use_mkg:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{self.mkg_url}/v1/models")
                    models = response.json()
                    print(f"\n✅ MKG Local Model: Available at {self.mkg_url}")
                    print(f"   Model: {models.get('data', [{}])[0].get('id', 'local')}")
            except Exception as e:
                print(f"\n⚠️  MKG Local Model: Not available ({e}), falling back to heuristics")
                self.use_mkg = False
        
        # Load queries
        queries = self.load_queries()
        if max_queries:
            queries = queries[:max_queries]
        
        print(f"\n✅ Loaded {len(queries)} search queries")
        
        start_time = time.time()
        
        # Process each query
        for i, query in enumerate(queries):
            print(f"\n{'='*60}")
            print(f"QUERY {i+1}/{len(queries)}")
            print(f"{'='*60}")
            
            await self.process_query_batch(query, limit=self.batch_size)
        
        # Final summary
        elapsed = time.time() - start_time
        total = self.decisions_added + self.patterns_added + self.failures_added
        success_rate = (total / self.total_processed * 100) if self.total_processed > 0 else 0
        
        print("\n" + "="*60)
        print("✅ ENHANCED EXTRACTION COMPLETE")
        print("="*60)
        print(f"\nResults:")
        print(f"  Conversations processed: {self.total_processed}")
        print(f"  Decisions: {self.decisions_added}")
        print(f"  Patterns: {self.patterns_added}")
        print(f"  Failures: {self.failures_added}")
        print(f"  Total nodes: {total}")
        print(f"  Success rate: {success_rate:.1f}%")
        print(f"  Skipped: {self.skipped}")
        print(f"  Errors: {self.errors}")
        print(f"\nTime: {elapsed/60:.1f} minutes")
        print(f"Avg per conversation: {elapsed/self.total_processed:.1f}s")
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Enhanced Agent Genesis extraction with MKG"
    )
    parser.add_argument(
        '--queries-file',
        default='ingestion/agent_genesis_queries.txt',
        help='Search queries file'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=20,
        help='Conversations per batch'
    )
    parser.add_argument(
        '--max-queries',
        type=int,
        help='Maximum queries to process (for testing)'
    )
    parser.add_argument(
        '--no-mkg',
        action='store_true',
        help='Disable MKG, use simple heuristics'
    )
    
    args = parser.parse_args()
    
    extractor = AgentGenesisMKGExtractor(
        queries_file=args.queries_file,
        batch_size=args.batch_size,
        use_mkg=not args.no_mkg
    )
    
    await extractor.run_enhanced_extraction(max_queries=args.max_queries)


if __name__ == "__main__":
    asyncio.run(main())
, '', cleaned)
                cleaned = cleaned.strip()
                
                # Try to parse cleaned JSON
                try:
                    extracted = json_lib.loads(cleaned)
                    if extracted.get('type') in ['decision', 'pattern', 'failure']:
                        return extracted
                    if extracted.get('type') == 'none':
                        return None
                except json_lib.JSONDecodeError:
                    pass
                
                # Fallback: find JSON objects in the response
                json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', answer, re.DOTALL)
                for json_str in reversed(json_matches):  # Try from end first (most likely correct)
                    try:
                        extracted = json_lib.loads(json_str)
                        if extracted.get('type') in ['decision', 'pattern', 'failure']:
                            return extracted
                    except json_lib.JSONDecodeError:
                        continue
                
                return None
                
        except Exception as e:
            # Silent fallback to heuristic
            return None
    
    async def process_conversation(self, conversation: Dict, query: str) -> bool:
        """Process a single conversation and add to knowledge base."""
        
        # Extract knowledge
        if self.use_mkg:
            extracted = await self.extract_with_mkg(conversation)
        else:
            # Fallback to simple heuristic
            extracted = self._simple_extract(conversation)
        
        if not extracted or extracted.get('type') == 'none':
            self.skipped += 1
            return False
        
        try:
            conv_id = conversation.get('conversation_id', 'unknown')
            source_ref = f"agent-genesis:conversation:{conv_id}:query:{query}"
            
            # Add to knowledge base based on type
            if extracted['type'] == 'decision':
                result = await add_decision(
                    description=extracted.get('description', '')[:200],
                    rationale=extracted.get('rationale', '')[:500],
                    alternatives=extracted.get('alternatives', [])[:5],
                    related_to=[]
                )
                self.decisions_added += 1
                node_id = result['decision_id']
                print(f"    ✅ Added decision: {node_id}")
                
            elif extracted['type'] == 'pattern':
                result = await add_pattern(
                    name=extracted.get('name', '')[:100],
                    context=extracted.get('context', '')[:200],
                    implementation=extracted.get('implementation', '')[:1000],
                    use_cases=[extracted.get('context', '')[:200]]
                )
                self.patterns_added += 1
                node_id = result['pattern_id']
                print(f"    ✅ Added pattern: {node_id}")
                
            elif extracted['type'] == 'failure':
                result = await add_failure(
                    attempt=extracted.get('attempt', '')[:200],
                    reason_failed=extracted.get('reason', '')[:500],
                    lesson_learned=extracted.get('lesson', '')[:500],
                    alternative_solution=""
                )
                self.failures_added += 1
                node_id = result['failure_id']
                print(f"    ✅ Added failure: {node_id}")
            
            return True
            
        except Exception as e:
            print(f"    ❌ Failed to add: {e}")
            self.errors += 1
            return False
    
    def _simple_extract(self, conversation: Dict) -> Optional[Dict]:
        """Simple fallback extraction without MKG."""
        content = conversation.get('content', '').lower()
        
        if any(word in content for word in ['chose', 'decided', 'selected']):
            return {
                "type": "decision",
                "description": content[:100],
                "rationale": "Extracted from conversation",
                "alternatives": []
            }
        elif any(word in content for word in ['pattern', 'approach', 'implementation']):
            return {
                "type": "pattern",
                "name": content[:50],
                "context": "From conversation",
                "implementation": content[:200]
            }
        elif any(word in content for word in ['failed', 'error', 'problem']):
            return {
                "type": "failure",
                "attempt": content[:100],
                "reason": "See conversation",
                "lesson": "Documented in conversation"
            }
        
        return None
    
    async def process_query_batch(self, query: str, limit: int = 50):
        """Process all conversations for a query in batches."""
        print(f"\n{'='*60}")
        print(f"Processing: {query}")
        print(f"{'='*60}")
        
        # Search
        conversations = await self.search_agent_genesis(query, limit)
        
        if not conversations:
            print(f"  ℹ️  No conversations found")
            return
        
        print(f"  ✅ Found {len(conversations)} conversations")
        print(f"  🤖 Using: {'MKG DeepSeek' if self.use_mkg else 'Simple heuristics'}")
        
        # Process in batches
        for i in range(0, len(conversations), self.batch_size):
            batch = conversations[i:i+self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(conversations) + self.batch_size - 1) // self.batch_size
            
            print(f"\n  📦 Batch {batch_num}/{total_batches} ({len(batch)} conversations)")
            
            for j, conv in enumerate(batch):
                print(f"    [{i+j+1}/{len(conversations)}] Processing...", end=' ')
                
                success = await self.process_conversation(conv, query)
                self.total_processed += 1
                
                # Rate limiting for MKG
                if success and self.use_mkg:
                    await asyncio.sleep(1.0)  # Be gentle on MKG
            
            # Batch summary
            total = self.decisions_added + self.patterns_added + self.failures_added
            success_rate = (total / self.total_processed * 100) if self.total_processed > 0 else 0
            print(f"\n  📊 Progress: {total} nodes | {success_rate:.1f}% success | {self.skipped} skipped | {self.errors} errors")
    
    async def run_enhanced_extraction(self, max_queries: Optional[int] = None):
        """Execute enhanced batch extraction with MKG."""
        print("="*60)
        print("AGENT GENESIS ENHANCED EXTRACTION (MKG)")
        print("="*60)
        print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Mode: {'MKG Semantic Analysis' if self.use_mkg else 'Simple Heuristics'}")
        print(f"Batch Size: {self.batch_size}")
        
        # Check MKG availability
        if self.use_mkg:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{self.mkg_url}/v1/models")
                    models = response.json()
                    print(f"\n✅ MKG Local Model: Available at {self.mkg_url}")
                    print(f"   Model: {models.get('data', [{}])[0].get('id', 'local')}")
            except Exception as e:
                print(f"\n⚠️  MKG Local Model: Not available ({e}), falling back to heuristics")
                self.use_mkg = False
        
        # Load queries
        queries = self.load_queries()
        if max_queries:
            queries = queries[:max_queries]
        
        print(f"\n✅ Loaded {len(queries)} search queries")
        
        start_time = time.time()
        
        # Process each query
        for i, query in enumerate(queries):
            print(f"\n{'='*60}")
            print(f"QUERY {i+1}/{len(queries)}")
            print(f"{'='*60}")
            
            await self.process_query_batch(query, limit=self.batch_size)
        
        # Final summary
        elapsed = time.time() - start_time
        total = self.decisions_added + self.patterns_added + self.failures_added
        success_rate = (total / self.total_processed * 100) if self.total_processed > 0 else 0
        
        print("\n" + "="*60)
        print("✅ ENHANCED EXTRACTION COMPLETE")
        print("="*60)
        print(f"\nResults:")
        print(f"  Conversations processed: {self.total_processed}")
        print(f"  Decisions: {self.decisions_added}")
        print(f"  Patterns: {self.patterns_added}")
        print(f"  Failures: {self.failures_added}")
        print(f"  Total nodes: {total}")
        print(f"  Success rate: {success_rate:.1f}%")
        print(f"  Skipped: {self.skipped}")
        print(f"  Errors: {self.errors}")
        print(f"\nTime: {elapsed/60:.1f} minutes")
        print(f"Avg per conversation: {elapsed/self.total_processed:.1f}s")
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Enhanced Agent Genesis extraction with MKG"
    )
    parser.add_argument(
        '--queries-file',
        default='ingestion/agent_genesis_queries.txt',
        help='Search queries file'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=20,
        help='Conversations per batch'
    )
    parser.add_argument(
        '--max-queries',
        type=int,
        help='Maximum queries to process (for testing)'
    )
    parser.add_argument(
        '--no-mkg',
        action='store_true',
        help='Disable MKG, use simple heuristics'
    )
    
    args = parser.parse_args()
    
    extractor = AgentGenesisMKGExtractor(
        queries_file=args.queries_file,
        batch_size=args.batch_size,
        use_mkg=not args.no_mkg
    )
    
    await extractor.run_enhanced_extraction(max_queries=args.max_queries)


if __name__ == "__main__":
    asyncio.run(main())
, '', cleaned)
                cleaned = cleaned.strip()
                
        except Exception as e:
            # Silent fallback to heuristic
            return None
    
    async def process_conversation(self, conversation: Dict, query: str) -> bool:
        """Process a single conversation and add to knowledge base."""
        
        # Extract knowledge
        if self.use_mkg:
            extracted = await self.extract_with_mkg(conversation)
        else:
            # Fallback to simple heuristic
            extracted = self._simple_extract(conversation)
        
        if not extracted or extracted.get('type') == 'none':
            self.skipped += 1
            return False
        
        try:
            conv_id = conversation.get('conversation_id', 'unknown')
            source_ref = f"agent-genesis:conversation:{conv_id}:query:{query}"
            
            # Add to knowledge base based on type
            if extracted['type'] == 'decision':
                result = await add_decision(
                    description=extracted.get('description', '')[:200],
                    rationale=extracted.get('rationale', '')[:500],
                    alternatives=extracted.get('alternatives', [])[:5],
                    related_to=[]
                )
                self.decisions_added += 1
                node_id = result['decision_id']
                print(f"    ✅ Added decision: {node_id}")
                
            elif extracted['type'] == 'pattern':
                result = await add_pattern(
                    name=extracted.get('name', '')[:100],
                    context=extracted.get('context', '')[:200],
                    implementation=extracted.get('implementation', '')[:1000],
                    use_cases=[extracted.get('context', '')[:200]]
                )
                self.patterns_added += 1
                node_id = result['pattern_id']
                print(f"    ✅ Added pattern: {node_id}")
                
            elif extracted['type'] == 'failure':
                result = await add_failure(
                    attempt=extracted.get('attempt', '')[:200],
                    reason_failed=extracted.get('reason', '')[:500],
                    lesson_learned=extracted.get('lesson', '')[:500],
                    alternative_solution=""
                )
                self.failures_added += 1
                node_id = result['failure_id']
                print(f"    ✅ Added failure: {node_id}")
            
            return True
            
        except Exception as e:
            print(f"    ❌ Failed to add: {e}")
            self.errors += 1
            return False
    
    def _simple_extract(self, conversation: Dict) -> Optional[Dict]:
        """Simple fallback extraction without MKG."""
        content = conversation.get('content', '').lower()
        
        if any(word in content for word in ['chose', 'decided', 'selected']):
            return {
                "type": "decision",
                "description": content[:100],
                "rationale": "Extracted from conversation",
                "alternatives": []
            }
        elif any(word in content for word in ['pattern', 'approach', 'implementation']):
            return {
                "type": "pattern",
                "name": content[:50],
                "context": "From conversation",
                "implementation": content[:200]
            }
        elif any(word in content for word in ['failed', 'error', 'problem']):
            return {
                "type": "failure",
                "attempt": content[:100],
                "reason": "See conversation",
                "lesson": "Documented in conversation"
            }
        
        return None
    
    async def process_query_batch(self, query: str, limit: int = 50):
        """Process all conversations for a query in batches."""
        print(f"\n{'='*60}")
        print(f"Processing: {query}")
        print(f"{'='*60}")
        
        # Search
        conversations = await self.search_agent_genesis(query, limit)
        
        if not conversations:
            print(f"  ℹ️  No conversations found")
            return
        
        print(f"  ✅ Found {len(conversations)} conversations")
        print(f"  🤖 Using: {'MKG DeepSeek' if self.use_mkg else 'Simple heuristics'}")
        
        # Process in batches
        for i in range(0, len(conversations), self.batch_size):
            batch = conversations[i:i+self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(conversations) + self.batch_size - 1) // self.batch_size
            
            print(f"\n  📦 Batch {batch_num}/{total_batches} ({len(batch)} conversations)")
            
            for j, conv in enumerate(batch):
                print(f"    [{i+j+1}/{len(conversations)}] Processing...", end=' ')
                
                success = await self.process_conversation(conv, query)
                self.total_processed += 1
                
                # Rate limiting for MKG
                if success and self.use_mkg:
                    await asyncio.sleep(1.0)  # Be gentle on MKG
            
            # Batch summary
            total = self.decisions_added + self.patterns_added + self.failures_added
            success_rate = (total / self.total_processed * 100) if self.total_processed > 0 else 0
            print(f"\n  📊 Progress: {total} nodes | {success_rate:.1f}% success | {self.skipped} skipped | {self.errors} errors")
    
    async def run_enhanced_extraction(self, max_queries: Optional[int] = None):
        """Execute enhanced batch extraction with MKG."""
        print("="*60)
        print("AGENT GENESIS ENHANCED EXTRACTION (MKG)")
        print("="*60)
        print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Mode: {'MKG Semantic Analysis' if self.use_mkg else 'Simple Heuristics'}")
        print(f"Batch Size: {self.batch_size}")
        
        # Check MKG availability
        if self.use_mkg:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{self.mkg_url}/v1/models")
                    models = response.json()
                    print(f"\n✅ MKG Local Model: Available at {self.mkg_url}")
                    print(f"   Model: {models.get('data', [{}])[0].get('id', 'local')}")
            except Exception as e:
                print(f"\n⚠️  MKG Local Model: Not available ({e}), falling back to heuristics")
                self.use_mkg = False
        
        # Load queries
        queries = self.load_queries()
        if max_queries:
            queries = queries[:max_queries]
        
        print(f"\n✅ Loaded {len(queries)} search queries")
        
        start_time = time.time()
        
        # Process each query
        for i, query in enumerate(queries):
            print(f"\n{'='*60}")
            print(f"QUERY {i+1}/{len(queries)}")
            print(f"{'='*60}")
            
            await self.process_query_batch(query, limit=self.batch_size)
        
        # Final summary
        elapsed = time.time() - start_time
        total = self.decisions_added + self.patterns_added + self.failures_added
        success_rate = (total / self.total_processed * 100) if self.total_processed > 0 else 0
        
        print("\n" + "="*60)
        print("✅ ENHANCED EXTRACTION COMPLETE")
        print("="*60)
        print(f"\nResults:")
        print(f"  Conversations processed: {self.total_processed}")
        print(f"  Decisions: {self.decisions_added}")
        print(f"  Patterns: {self.patterns_added}")
        print(f"  Failures: {self.failures_added}")
        print(f"  Total nodes: {total}")
        print(f"  Success rate: {success_rate:.1f}%")
        print(f"  Skipped: {self.skipped}")
        print(f"  Errors: {self.errors}")
        print(f"\nTime: {elapsed/60:.1f} minutes")
        print(f"Avg per conversation: {elapsed/self.total_processed:.1f}s")
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Enhanced Agent Genesis extraction with MKG"
    )
    parser.add_argument(
        '--queries-file',
        default='ingestion/agent_genesis_queries.txt',
        help='Search queries file'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=20,
        help='Conversations per batch'
    )
    parser.add_argument(
        '--max-queries',
        type=int,
        help='Maximum queries to process (for testing)'
    )
    parser.add_argument(
        '--no-mkg',
        action='store_true',
        help='Disable MKG, use simple heuristics'
    )
    
    args = parser.parse_args()
    
    extractor = AgentGenesisMKGExtractor(
        queries_file=args.queries_file,
        batch_size=args.batch_size,
        use_mkg=not args.no_mkg
    )
    
    await extractor.run_enhanced_extraction(max_queries=args.max_queries)


if __name__ == "__main__":
    asyncio.run(main())
, '', cleaned)
                cleaned = cleaned.strip()
                
                # Try to parse cleaned JSON
                try:
                    extracted = json_lib.loads(cleaned)
                    if extracted.get('type') in ['decision', 'pattern', 'failure']:
                        return extracted
                    if extracted.get('type') == 'none':
                        return None
                except json_lib.JSONDecodeError:
                    pass
                
                # Fallback: find JSON objects in the response
                json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', answer, re.DOTALL)
                for json_str in reversed(json_matches):  # Try from end first (most likely correct)
                    try:
                        extracted = json_lib.loads(json_str)
                        if extracted.get('type') in ['decision', 'pattern', 'failure']:
                            return extracted
                    except json_lib.JSONDecodeError:
                        continue
                
                return None
                
        except Exception as e:
            # Silent fallback to heuristic
            return None
    
    async def process_conversation(self, conversation: Dict, query: str) -> bool:
        """Process a single conversation and add to knowledge base."""
        
        # Extract knowledge
        if self.use_mkg:
            extracted = await self.extract_with_mkg(conversation)
        else:
            # Fallback to simple heuristic
            extracted = self._simple_extract(conversation)
        
        if not extracted or extracted.get('type') == 'none':
            self.skipped += 1
            return False
        
        try:
            conv_id = conversation.get('conversation_id', 'unknown')
            source_ref = f"agent-genesis:conversation:{conv_id}:query:{query}"
            
            # Add to knowledge base based on type
            if extracted['type'] == 'decision':
                result = await add_decision(
                    description=extracted.get('description', '')[:200],
                    rationale=extracted.get('rationale', '')[:500],
                    alternatives=extracted.get('alternatives', [])[:5],
                    related_to=[]
                )
                self.decisions_added += 1
                node_id = result['decision_id']
                print(f"    ✅ Added decision: {node_id}")
                
            elif extracted['type'] == 'pattern':
                result = await add_pattern(
                    name=extracted.get('name', '')[:100],
                    context=extracted.get('context', '')[:200],
                    implementation=extracted.get('implementation', '')[:1000],
                    use_cases=[extracted.get('context', '')[:200]]
                )
                self.patterns_added += 1
                node_id = result['pattern_id']
                print(f"    ✅ Added pattern: {node_id}")
                
            elif extracted['type'] == 'failure':
                result = await add_failure(
                    attempt=extracted.get('attempt', '')[:200],
                    reason_failed=extracted.get('reason', '')[:500],
                    lesson_learned=extracted.get('lesson', '')[:500],
                    alternative_solution=""
                )
                self.failures_added += 1
                node_id = result['failure_id']
                print(f"    ✅ Added failure: {node_id}")
            
            return True
            
        except Exception as e:
            print(f"    ❌ Failed to add: {e}")
            self.errors += 1
            return False
    
    def _simple_extract(self, conversation: Dict) -> Optional[Dict]:
        """Simple fallback extraction without MKG."""
        content = conversation.get('content', '').lower()
        
        if any(word in content for word in ['chose', 'decided', 'selected']):
            return {
                "type": "decision",
                "description": content[:100],
                "rationale": "Extracted from conversation",
                "alternatives": []
            }
        elif any(word in content for word in ['pattern', 'approach', 'implementation']):
            return {
                "type": "pattern",
                "name": content[:50],
                "context": "From conversation",
                "implementation": content[:200]
            }
        elif any(word in content for word in ['failed', 'error', 'problem']):
            return {
                "type": "failure",
                "attempt": content[:100],
                "reason": "See conversation",
                "lesson": "Documented in conversation"
            }
        
        return None
    
    async def process_query_batch(self, query: str, limit: int = 50):
        """Process all conversations for a query in batches."""
        print(f"\n{'='*60}")
        print(f"Processing: {query}")
        print(f"{'='*60}")
        
        # Search
        conversations = await self.search_agent_genesis(query, limit)
        
        if not conversations:
            print(f"  ℹ️  No conversations found")
            return
        
        print(f"  ✅ Found {len(conversations)} conversations")
        print(f"  🤖 Using: {'MKG DeepSeek' if self.use_mkg else 'Simple heuristics'}")
        
        # Process in batches
        for i in range(0, len(conversations), self.batch_size):
            batch = conversations[i:i+self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(conversations) + self.batch_size - 1) // self.batch_size
            
            print(f"\n  📦 Batch {batch_num}/{total_batches} ({len(batch)} conversations)")
            
            for j, conv in enumerate(batch):
                print(f"    [{i+j+1}/{len(conversations)}] Processing...", end=' ')
                
                success = await self.process_conversation(conv, query)
                self.total_processed += 1
                
                # Rate limiting for MKG
                if success and self.use_mkg:
                    await asyncio.sleep(1.0)  # Be gentle on MKG
            
            # Batch summary
            total = self.decisions_added + self.patterns_added + self.failures_added
            success_rate = (total / self.total_processed * 100) if self.total_processed > 0 else 0
            print(f"\n  📊 Progress: {total} nodes | {success_rate:.1f}% success | {self.skipped} skipped | {self.errors} errors")
    
    async def run_enhanced_extraction(self, max_queries: Optional[int] = None):
        """Execute enhanced batch extraction with MKG."""
        print("="*60)
        print("AGENT GENESIS ENHANCED EXTRACTION (MKG)")
        print("="*60)
        print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Mode: {'MKG Semantic Analysis' if self.use_mkg else 'Simple Heuristics'}")
        print(f"Batch Size: {self.batch_size}")
        
        # Check MKG availability
        if self.use_mkg:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{self.mkg_url}/v1/models")
                    models = response.json()
                    print(f"\n✅ MKG Local Model: Available at {self.mkg_url}")
                    print(f"   Model: {models.get('data', [{}])[0].get('id', 'local')}")
            except Exception as e:
                print(f"\n⚠️  MKG Local Model: Not available ({e}), falling back to heuristics")
                self.use_mkg = False
        
        # Load queries
        queries = self.load_queries()
        if max_queries:
            queries = queries[:max_queries]
        
        print(f"\n✅ Loaded {len(queries)} search queries")
        
        start_time = time.time()
        
        # Process each query
        for i, query in enumerate(queries):
            print(f"\n{'='*60}")
            print(f"QUERY {i+1}/{len(queries)}")
            print(f"{'='*60}")
            
            await self.process_query_batch(query, limit=self.batch_size)
        
        # Final summary
        elapsed = time.time() - start_time
        total = self.decisions_added + self.patterns_added + self.failures_added
        success_rate = (total / self.total_processed * 100) if self.total_processed > 0 else 0
        
        print("\n" + "="*60)
        print("✅ ENHANCED EXTRACTION COMPLETE")
        print("="*60)
        print(f"\nResults:")
        print(f"  Conversations processed: {self.total_processed}")
        print(f"  Decisions: {self.decisions_added}")
        print(f"  Patterns: {self.patterns_added}")
        print(f"  Failures: {self.failures_added}")
        print(f"  Total nodes: {total}")
        print(f"  Success rate: {success_rate:.1f}%")
        print(f"  Skipped: {self.skipped}")
        print(f"  Errors: {self.errors}")
        print(f"\nTime: {elapsed/60:.1f} minutes")
        print(f"Avg per conversation: {elapsed/self.total_processed:.1f}s")
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Enhanced Agent Genesis extraction with MKG"
    )
    parser.add_argument(
        '--queries-file',
        default='ingestion/agent_genesis_queries.txt',
        help='Search queries file'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=20,
        help='Conversations per batch'
    )
    parser.add_argument(
        '--max-queries',
        type=int,
        help='Maximum queries to process (for testing)'
    )
    parser.add_argument(
        '--no-mkg',
        action='store_true',
        help='Disable MKG, use simple heuristics'
    )
    
    args = parser.parse_args()
    
    extractor = AgentGenesisMKGExtractor(
        queries_file=args.queries_file,
        batch_size=args.batch_size,
        use_mkg=not args.no_mkg
    )
    
    await extractor.run_enhanced_extraction(max_queries=args.max_queries)


if __name__ == "__main__":
    asyncio.run(main())
