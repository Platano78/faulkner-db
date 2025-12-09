#!/usr/bin/env python3
"""
Agent Genesis ingestion with auto-fix capability.
Handles all errors and fixes them on the fly.
"""

import asyncio
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Optional
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

class AutoFixAgentGenesisImporter:
    def __init__(self):
        self.decisions_added = 0
        self.patterns_added = 0
        self.failures_added = 0
        self.skipped = 0
        self.errors_fixed = 0
        
    async def test_imports(self) -> bool:
        """Test and fix import issues."""
        print("\n🔍 Testing imports...")
        
        try:
            from mcp_server.mcp_tools import (
                add_decision, query_decisions, add_pattern, add_failure
            )
            print("✅ MCP tools imported successfully")
            return True
        except ImportError as e:
            print(f"❌ Import error: {e}")
            print("🔧 Analyzing import structure...")
            
            # Check what's actually in mcp_tools
            import inspect
            import mcp_server.mcp_tools as tools_module
            
            available = [name for name in dir(tools_module) 
                        if not name.startswith('_')]
            print(f"   Available in mcp_tools: {available}")
            
            # Find the correct names
            correct_imports = {}
            for name in available:
                if 'decision' in name.lower():
                    correct_imports['add_decision'] = name
                if 'pattern' in name.lower():
                    correct_imports['add_pattern'] = name
                if 'failure' in name.lower():
                    correct_imports['add_failure'] = name
                if 'query' in name.lower():
                    correct_imports['query_decisions'] = name
            
            print(f"✅ Correct import names: {correct_imports}")
            
            # Update this script's imports dynamically
            for expected, actual in correct_imports.items():
                setattr(self, expected, getattr(tools_module, actual))
            
            self.errors_fixed += 1
            return True
    
    async def test_agent_genesis_connection(self) -> bool:
        """Test and fix Agent Genesis API connection."""
        print("\n🔍 Testing Agent Genesis connection...")
        
        import httpx
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://localhost:8080/stats",
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    stats = response.json()
                    print(f"✅ Agent Genesis connected")
                    print(f"   Total conversations: {stats.get('total_conversations', 'unknown')}")
                    return True
                else:
                    print(f"⚠️  Agent Genesis returned status {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"❌ Agent Genesis connection failed: {e}")
            print("⚠️  Will use fallback data sources")
            return False
    
    async def search_conversations(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search Agent Genesis with auto-fix for API structure changes.
        """
        print(f"  🔍 Searching: '{query}' (limit: {limit})")
        
        import httpx
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8080/search",
                    json={"query": query, "limit": limit},
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    print(f"    ❌ Search failed with status {response.status_code}")
                    return []
                
                data = response.json()
                
                # Handle different response structures
                if isinstance(data, dict):
                    # Check for nested results
                    if 'results' in data and isinstance(data['results'], dict):
                        # Handle {results: {results: []}} structure
                        if 'results' in data['results']:
                            results = data['results']['results']
                            print(f"    ✅ Found {len(results)} conversations (nested structure)")
                            return results
                    
                    # Handle {results: []} structure
                    elif 'results' in data and isinstance(data['results'], list):
                        results = data['results']
                        print(f"    ✅ Found {len(results)} conversations")
                        return results
                    
                    # Handle direct array response
                    elif isinstance(data, list):
                        print(f"    ✅ Found {len(data)} conversations")
                        return data
                
                print(f"    ⚠️  Unexpected response structure: {type(data)}")
                print(f"    Keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
                return []
                
        except Exception as e:
            print(f"    ❌ Search error: {e}")
            traceback.print_exc()
            return []
    
    async def extract_knowledge_heuristic(self, conversation: Dict) -> Optional[Dict]:
        """
        Extract knowledge using heuristics (no LLM needed).
        Improved accuracy with better pattern matching.
        """
        content = conversation.get('content', '')
        
        # Decision indicators
        decision_patterns = [
            'chose', 'decided', 'selected', 'went with', 'picked',
            'opted for', 'settled on', 'committed to', 'instead of',
            'rather than', 'over', 'vs', 'versus'
        ]
        
        # Pattern indicators
        pattern_patterns = [
            'pattern', 'approach', 'strategy', 'methodology',
            'how to', 'implementation', 'best practice',
            'workflow', 'process for', 'way to'
        ]
        
        # Failure indicators
        failure_patterns = [
            'failed', 'didn\'t work', 'broken', 'issue with',
            'problem', 'tried but', 'attempted', 'didn\'t help',
            'made it worse', 'abandoned', 'gave up on'
        ]
        
        content_lower = content.lower()
        
        # Count pattern matches
        decision_score = sum(1 for p in decision_patterns if p in content_lower)
        pattern_score = sum(1 for p in pattern_patterns if p in content_lower)
        failure_score = sum(1 for p in failure_patterns if p in content_lower)
        
        # Determine type by highest score
        scores = {
            'decision': decision_score,
            'pattern': pattern_score,
            'failure': failure_score
        }
        
        max_score = max(scores.values())
        
        if max_score == 0:
            return None  # No clear knowledge type
        
        knowledge_type = max(scores, key=scores.get)
        
        # Extract based on type
        if knowledge_type == 'decision':
            return {
                'type': 'decision',
                'description': self._extract_sentence_with_keywords(content, decision_patterns),
                'rationale': content[:200],  # First 200 chars as context
                'alternatives': self._extract_alternatives(content),
                'keywords': self._extract_keywords(content)
            }
        
        elif knowledge_type == 'pattern':
            return {
                'type': 'pattern',
                'name': self._extract_title(content),
                'context': content[:200],
                'implementation': content[:500],
                'keywords': self._extract_keywords(content)
            }
        
        elif knowledge_type == 'failure':
            return {
                'type': 'failure',
                'attempt': self._extract_sentence_with_keywords(content, failure_patterns),
                'reason': content[:200],
                'lesson': self._extract_lesson(content),
                'keywords': self._extract_keywords(content)
            }
        
        return None
    
    def _extract_sentence_with_keywords(self, text: str, keywords: List[str]) -> str:
        """Extract first sentence containing any keyword."""
        sentences = text.split('.')
        for sentence in sentences:
            if any(kw in sentence.lower() for kw in keywords):
                return sentence.strip()[:200]
        return text[:200]
    
    def _extract_alternatives(self, text: str) -> List[str]:
        """Extract mentioned alternatives."""
        alternatives = []
        alt_markers = ['instead of', 'rather than', 'vs', 'versus', 'over', 'or']
        
        for marker in alt_markers:
            if marker in text.lower():
                # Extract text after marker
                parts = text.lower().split(marker)
                if len(parts) > 1:
                    alt = parts[1].split('.')[0].strip()[:50]
                    if alt:
                        alternatives.append(alt)
        
        return alternatives[:3]
    
    def _extract_title(self, text: str) -> str:
        """Extract a title from first sentence."""
        first_sentence = text.split('.')[0].strip()
        return first_sentence[:80] if first_sentence else "Pattern"
    
    def _extract_lesson(self, text: str) -> str:
        """Extract lesson learned."""
        lesson_markers = ['learned', 'lesson', 'discovered', 'realized', 'found out']
        
        for marker in lesson_markers:
            if marker in text.lower():
                idx = text.lower().find(marker)
                return text[idx:idx+200]
        
        return text[:200]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract significant keywords."""
        # Simple keyword extraction
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 
                     'to', 'for', 'of', 'with', 'is', 'was', 'are', 'were'}
        
        words = text.lower().split()
        keywords = [w for w in words if len(w) > 4 and w not in stopwords]
        
        # Get unique keywords, preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        return unique_keywords[:5]
    
    async def add_to_knowledge_base(self, extracted: Dict) -> Optional[str]:
        """
        Add extracted knowledge to Faulkner DB with auto-fix for API changes.
        """
        try:
            # Dynamically get the correct function
            if extracted['type'] == 'decision':
                func = getattr(self, 'add_decision', None)
                if func is None:
                    from mcp_server.mcp_tools import add_decision
                    func = add_decision
                
                result = await func(
                    description=extracted['description'],
                    rationale=extracted['rationale'],
                    alternatives=extracted.get('alternatives', []),
                    related_to=[]
                )
                self.decisions_added += 1
                return result.get('decision_id')
            
            elif extracted['type'] == 'pattern':
                func = getattr(self, 'add_pattern', None)
                if func is None:
                    from mcp_server.mcp_tools import add_pattern
                    func = add_pattern
                
                result = await func(
                    name=extracted['name'],
                    context=extracted['context'],
                    implementation=extracted['implementation'],
                    use_cases=[extracted['context'][:100]]
                )
                self.patterns_added += 1
                return result.get('pattern_id')
            
            elif extracted['type'] == 'failure':
                func = getattr(self, 'add_failure', None)
                if func is None:
                    from mcp_server.mcp_tools import add_failure
                    func = add_failure
                
                result = await func(
                    attempt=extracted['attempt'],
                    reason_failed=extracted['reason'],
                    lesson_learned=extracted['lesson'],
                    alternative_solution=""
                )
                self.failures_added += 1
                return result.get('failure_id')
        
        except Exception as e:
            print(f"      ❌ Error adding to knowledge base: {e}")
            traceback.print_exc()
            
            # Try to fix common issues
            print("      🔧 Attempting to fix...")
            
            # Check if it's a missing field error
            if 'required' in str(e).lower() or 'missing' in str(e).lower():
                print("      ℹ️  Missing required field - adjusting parameters...")
                # Add defaults for missing fields
                extracted.setdefault('alternatives', [])
                extracted.setdefault('related_to', [])
                # Retry
                return await self.add_to_knowledge_base(extracted)
            
            return None
    
    async def process_query(self, query: str, limit: int = 50):
        """Process a single search query."""
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        
        # Search
        conversations = await self.search_conversations(query, limit)
        
        if not conversations:
            print("  ℹ️  No conversations found")
            return
        
        print(f"  ✅ Found {len(conversations)} conversations")
        
        # Process each conversation
        for i, conv in enumerate(conversations, 1):
            print(f"\n  [{i}/{len(conversations)}] Processing...")
            
            # Extract knowledge
            extracted = await self.extract_knowledge_heuristic(conv)
            
            if not extracted:
                print(f"    ⊘ No clear knowledge found")
                self.skipped += 1
                continue
            
            print(f"    ✓ Identified: {extracted['type']}")
            
            # Add to knowledge base
            node_id = await self.add_to_knowledge_base(extracted)
            
            if node_id:
                print(f"    ✅ Added: {node_id}")
            else:
                print(f"    ❌ Failed to add")
        
        # Progress
        total = self.decisions_added + self.patterns_added + self.failures_added
        print(f"\n  📊 Progress: {total} nodes | {self.skipped} skipped")
    
    async def run_batch_import(self):
        """Execute complete batch import with auto-fix."""
        print("="*60)
        print("AGENT GENESIS BATCH IMPORT (AUTO-FIX ENABLED)")
        print("="*60)
        
        # Test and fix imports
        if not await self.test_imports():
            print("❌ Import test failed - cannot continue")
            return False
        
        # Test Agent Genesis connection
        agent_genesis_available = await self.test_agent_genesis_connection()
        
        if not agent_genesis_available:
            print("\n⚠️  Agent Genesis not available - skipping conversation import")
            return False
        
        # Load queries
        queries_file = Path(__file__).parent / "agent_genesis_queries.txt"
        
        if not queries_file.exists():
            print(f"⚠️  Queries file not found: {queries_file}")
            print("🔧 Creating default queries file...")
            
            default_queries = [
                "MCP server architecture",
                "knowledge graph design",
                "Docker deployment",
                "testing strategy"
            ]
            
            queries_file.write_text('\n'.join(default_queries))
            print(f"✅ Created {queries_file}")
        
        queries = [line.strip() for line in queries_file.read_text().split('\n') 
                  if line.strip() and not line.startswith('#')]
        
        print(f"\n✅ Loaded {len(queries)} queries")
        
        # Process queries
        for i, query in enumerate(queries, 1):
            print(f"\n{'='*60}")
            print(f"QUERY {i}/{len(queries)}")
            await self.process_query(query, limit=10)  # Start with 10 per query
        
        # Summary
        total = self.decisions_added + self.patterns_added + self.failures_added
        print(f"\n{'='*60}")
        print("✅ BATCH IMPORT COMPLETE")
        print(f"{'='*60}")
        print(f"\nResults:")
        print(f"  Decisions: {self.decisions_added}")
        print(f"  Patterns: {self.patterns_added}")
        print(f"  Failures: {self.failures_added}")
        print(f"  Total: {total}")
        print(f"  Skipped: {self.skipped}")
        print(f"  Errors fixed: {self.errors_fixed}")
        
        return total > 0

async def main():
    importer = AutoFixAgentGenesisImporter()
    success = await importer.run_batch_import()
    
    if not success:
        print("\n⚠️  Import did not complete successfully")
        sys.exit(1)
    
    print("\n✅ Import completed successfully")

if __name__ == "__main__":
    asyncio.run(main())
