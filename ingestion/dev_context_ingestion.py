#!/usr/bin/env python3
"""
Development Context MCP Ingestion Script
Ingests decisions and breakthroughs from Development Context MCP into Faulkner DB.
"""

import asyncio
import sys
import json
import httpx
from pathlib import Path
from typing import List, Dict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.mcp_tools import add_decision, add_pattern, add_failure


class DevContextIngester:
    """Ingest Development Context MCP data into Faulkner DB."""
    
    def __init__(self):
        self.decisions_added = 0
        self.patterns_added = 0
        self.failures_added = 0
        self.breakthroughs_converted = 0
        self.errors = 0
        
    async def fetch_all_context(self) -> List[Dict]:
        """Fetch all development context entries using MCP tool directly."""
        print("  🔍 Fetching development context...")
        
        try:
            # Import the MCP tool
            from mcp_tools import mcp__development_context_mcp__search_development_context
            
            # Call the MCP tool directly
            result = await mcp__development_context_mcp__search_development_context(
                query="*",
                limit=100
            )
            
            # Parse the text result
            text = result.get('result', '')
            entries = self._parse_context_text(text)
            
            print(f"    ✅ Found {len(entries)} context entries")
            return entries
                
        except Exception as e:
            print(f"    ❌ Failed to fetch: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _parse_context_text(self, text: str) -> List[Dict]:
        """Parse the text output from Development Context MCP."""
        entries = []
        current_entry = {}
        
        for line in text.split('\n'):
            line = line.strip()
            
            if line.startswith('## '):
                if current_entry:
                    entries.append(current_entry)
                current_entry = {}
            elif line.startswith('**ID:**'):
                current_entry['id'] = line.replace('**ID:**', '').strip()
            elif line.startswith('**Decision:**'):
                current_entry['type'] = 'decision'
                current_entry['description'] = line.replace('**Decision:**', '').strip()[:200]
            elif line.startswith('**Breakthrough:**'):
                current_entry['type'] = 'breakthrough'
                current_entry['description'] = line.replace('**Breakthrough:**', '').strip()[:200]
            elif line.startswith('**Context:**'):
                current_entry['context'] = line.replace('**Context:**', '').strip()[:500]
            elif line.startswith('**Technical Details:**'):
                current_entry['technical_details'] = line.replace('**Technical Details:**', '').strip()[:1000]
            elif line.startswith('**Tags:**'):
                tags_str = line.replace('**Tags:**', '').strip()
                current_entry['tags'] = [t.strip() for t in tags_str.split(',')]
            elif line.startswith('**Priority:**'):
                current_entry['priority'] = line.replace('**Priority:**', '').strip()
            elif line.startswith('**Difficulty:**'):
                current_entry['difficulty'] = line.replace('**Difficulty:**', '').strip()
        
        if current_entry:
            entries.append(current_entry)
        
        return entries
    
    async def ingest_decision(self, entry: Dict) -> bool:
        """Ingest a decision entry."""
        try:
            description = entry.get('description', 'Unknown decision')[:200]
            context = entry.get('context', '')[:500]
            tags = entry.get('tags', [])
            
            # Extract alternatives from context/tags if available
            alternatives = []
            if 'typescript' in str(tags).lower():
                alternatives = ['Continue with errors', 'Systematic fix approach']
            
            result = await add_decision(
                description=description,
                rationale=context,
                alternatives=alternatives,
                related_to=[]
            )
            
            self.decisions_added += 1
            node_id = result['decision_id']
            print(f"    ✅ Added decision: {node_id[:12]}...")
            return True
            
        except Exception as e:
            print(f"    ❌ Failed to add decision: {e}")
            self.errors += 1
            return False
    
    async def ingest_breakthrough(self, entry: Dict) -> bool:
        """Ingest a breakthrough as a pattern."""
        try:
            description = entry.get('description', 'Unknown breakthrough')[:200]
            technical_details = entry.get('technical_details', '')[:1000]
            difficulty = entry.get('difficulty', 'medium')
            
            # Convert breakthrough to pattern
            result = await add_pattern(
                name=description[:100],
                context=f"Breakthrough difficulty: {difficulty}",
                implementation=technical_details,
                use_cases=[description[:200]]
            )
            
            self.patterns_added += 1
            self.breakthroughs_converted += 1
            node_id = result['pattern_id']
            print(f"    ✅ Added breakthrough as pattern: {node_id[:12]}...")
            return True
            
        except Exception as e:
            print(f"    ❌ Failed to add breakthrough: {e}")
            self.errors += 1
            return False
    
    async def run_ingestion(self):
        """Execute full ingestion from Development Context MCP."""
        print("="*60)
        print("DEVELOPMENT CONTEXT MCP INGESTION")
        print("="*60)
        print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Fetch all context
        entries = await self.fetch_all_context()
        
        if not entries:
            print("\n⚠️  No entries found")
            return
        
        print(f"\n📊 Processing {len(entries)} entries...\n")
        
        # Process each entry
        for i, entry in enumerate(entries, 1):
            entry_type = entry.get('type', 'unknown')
            print(f"[{i}/{len(entries)}] {entry_type.upper()}: ", end='')
            
            if entry_type == 'decision':
                await self.ingest_decision(entry)
            elif entry_type == 'breakthrough':
                await self.ingest_breakthrough(entry)
            else:
                print(f"⚠️  Unknown type: {entry_type}")
            
            # Rate limiting
            await asyncio.sleep(0.5)
        
        # Summary
        total = self.decisions_added + self.patterns_added
        print("\n" + "="*60)
        print("✅ INGESTION COMPLETE")
        print("="*60)
        print(f"\nResults:")
        print(f"  Decisions: {self.decisions_added}")
        print(f"  Patterns: {self.patterns_added} (from breakthroughs: {self.breakthroughs_converted})")
        print(f"  Total nodes: {total}")
        print(f"  Errors: {self.errors}")
        print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def main():
    ingester = DevContextIngester()
    await ingester.run_ingestion()


if __name__ == "__main__":
    asyncio.run(main())
