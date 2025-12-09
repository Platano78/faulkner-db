#!/usr/bin/env python3
"""
Agent Genesis → Faulkner DB Ingestion Pipeline

Extracts architectural decisions from Agent Genesis conversation corpus.
Uses agent-genesis:search_conversations to find relevant discussions,
then AI (DeepSeek via MKG) to extract structured decisions.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Faulkner DB tools
from mcp_server.mcp_tools import add_decision, add_pattern, add_failure, query_decisions


class AgentGenesisImporter:
    """Import architectural knowledge from Agent Genesis conversations."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.decisions_added = 0
        self.patterns_added = 0
        self.failures_added = 0
        self.skipped = 0
        
    async def search_conversations(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Use agent-genesis:search_conversations MCP tool.
        
        NOTE: This would call the actual MCP tool in production.
        For now, we simulate the structure.
        """
        print(f"🔍 Searching Agent Genesis: '{query}' (limit: {limit})")
        
        # In production, this would be:
        # from mcp_client import call_mcp_tool
        # results = await call_mcp_tool('agent-genesis', 'search_conversations', 
        #                                query=query, limit=limit)
        
        # Simulated response for now
        return [
            {
                "conversation_id": f"conv_{i:03d}",
                "content": f"Discussion about {query} - sample content {i}",
                "created_at": datetime.now().isoformat(),
                "relevance_score": 0.9 - (i * 0.01)
            }
            for i in range(min(3, limit))  # Return 3 samples for testing
        ]
    
    async def extract_decision_with_ai(self, conversation: Dict) -> Optional[Dict]:
        """
        Use AI (DeepSeek/Qwen via MKG or direct) to extract structured decision.
        
        Returns structured decision data or None if no clear decision found.
        """
        prompt = f"""Extract architectural decision from this conversation.

Conversation ID: {conversation['conversation_id']}
Content:
{conversation['content'][:1000]}

Return ONLY a JSON object with these fields (or {{"decision": null}} if no clear decision):
{{
  "description": "Brief decision description",
  "rationale": "Why this was chosen (1-2 sentences)",
  "alternatives": ["Option 1", "Option 2", "Option 3"],
  "context": "Project/component affected",
  "related_keywords": ["keyword1", "keyword2"]
}}

Rules:
- Only extract ACTUAL decisions (chose X over Y), not discussions
- Keep rationale concise (1-2 sentences)
- List 2-4 concrete alternatives
- Include 2-4 keywords for relationship discovery"""

        # For production, call MKG's ask tool:
        # from mcp_client import call_mcp_tool
        # response = await call_mcp_tool('mecha-king-ghidorah-global', 'ask',
        #                                model='deepseek3.1', prompt=prompt, thinking=False)
        # decision_data = json.loads(response)
        
        # Simulated extraction for testing
        decision_data = {
            "description": f"Decision extracted from {conversation['conversation_id']}",
            "rationale": "This approach was chosen for better performance and maintainability.",
            "alternatives": ["Option A", "Option B"],
            "context": "MCP architecture",
            "related_keywords": ["mcp", "architecture", "performance"]
        }
        
        return decision_data
    
    async def find_related_decisions(self, keywords: List[str]) -> List[str]:
        """
        Find existing decision IDs that match keywords (for related_to field).
        """
        related_ids = []
        
        for keyword in keywords[:3]:  # Top 3 keywords
            try:
                results = await query_decisions(query=keyword)
                
                # Extract decision IDs from results
                for result in results[:2]:  # Top 2 matches per keyword
                    # Results structure may vary, adapt as needed
                    decision_id = result.get('metadata', {}).get('decision_id')
                    if decision_id and decision_id not in related_ids:
                        related_ids.append(decision_id)
            except Exception as e:
                print(f"  Warning: Could not search for keyword '{keyword}': {e}")
                continue
        
        return related_ids[:5]  # Max 5 relationships
    
    async def ingest_from_query(self, query: str, limit: int = 50):
        """
        Execute full ingestion pipeline for a search query.
        """
        print(f"\n{'='*60}")
        print(f"INGESTING: {query}")
        print(f"{'='*60}")
        
        # Search Agent Genesis
        conversations = await self.search_conversations(query, limit)
        print(f"✅ Found {len(conversations)} relevant conversations")
        
        # Process each conversation
        for i, conv in enumerate(conversations):
            print(f"\n[{i+1}/{len(conversations)}] Processing {conv['conversation_id']}")
            
            # Extract decision
            try:
                decision_data = await self.extract_decision_with_ai(conv)
            except Exception as e:
                print(f"  ❌ Extraction failed: {e}")
                self.skipped += 1
                continue
            
            if not decision_data or decision_data.get('decision') is None:
                print(f"  ✗ No decision found, skipping")
                self.skipped += 1
                continue
            
            print(f"  ✓ Extracted: {decision_data['description'][:60]}...")
            
            # Find related decisions
            related_keywords = decision_data.get('related_keywords', [])
            related_ids = await self.find_related_decisions(related_keywords)
            
            if related_ids:
                print(f"  🔗 Found {len(related_ids)} related decisions")
            
            # Add to Faulkner DB
            try:
                result = await add_decision(
                    description=decision_data['description'],
                    rationale=decision_data['rationale'],
                    alternatives=decision_data.get('alternatives', []),
                    related_to=related_ids
                )
                
                decision_id = result.get('decision_id')
                print(f"  ✅ Added: {decision_id}")
                self.decisions_added += 1
                
            except Exception as e:
                print(f"  ❌ Failed to add decision: {e}")
                continue
            
            # Rate limiting (be gentle on APIs)
            await asyncio.sleep(0.5)
    
    async def run_full_ingestion(self):
        """
        Execute complete ingestion across multiple query categories.
        """
        print("="*60)
        print("AGENT GENESIS → FAULKNER DB INGESTION")
        print("="*60)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Define search queries for different decision types
        queries = [
            ("MCP architecture decisions", 50),
            ("database choice Neo4j FalkorDB", 30),
            ("knowledge graph temporal design", 40),
            ("authentication authorization security", 30),
            ("deployment Docker infrastructure", 30),
            ("API design REST GraphQL", 20),
            ("testing strategy pytest validation", 20),
            ("caching Redis performance", 20),
            ("game development Unity patterns", 40),
            ("AI training local cloud", 30),
        ]
        
        for query, limit in queries:
            await self.ingest_from_query(query, limit)
            print(f"\n{'='*60}")
            print(f"PROGRESS: {self.decisions_added} decisions, {self.skipped} skipped")
            print(f"{'='*60}\n")
        
        # Final summary
        print("\n" + "="*60)
        print("✅ AGENT GENESIS INGESTION COMPLETE")
        print("="*60)
        print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nResults:")
        print(f"  Decisions added: {self.decisions_added}")
        print(f"  Patterns added: {self.patterns_added}")
        print(f"  Failures added: {self.failures_added}")
        print(f"  Skipped (no decision): {self.skipped}")
        print(f"  Total nodes: {self.decisions_added + self.patterns_added + self.failures_added}")
        
        # Trigger incremental relationship extraction if new nodes were added
        total_new_nodes = self.decisions_added + self.patterns_added + self.failures_added
        if total_new_nodes > 0:
            print(f"\n🔗 Triggering incremental relationship extraction for {total_new_nodes} new nodes...")
            import subprocess
            try:
                result = subprocess.run(
                    ["./venv/bin/python", "ingestion/relationship_extractor.py", "--incremental"],
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout (may have many nodes)
                )
                if result.returncode == 0:
                    print("✅ Incremental relationship extraction complete")
                else:
                    print(f"⚠️  Relationship extraction failed: {result.stderr}")
            except Exception as e:
                print(f"⚠️  Could not run relationship extraction: {e}")
        
        print()


async def main():
    """Main entry point for Agent Genesis ingestion."""
    importer = AgentGenesisImporter()
    await importer.run_full_ingestion()


if __name__ == "__main__":
    asyncio.run(main())
