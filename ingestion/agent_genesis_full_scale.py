#!/usr/bin/env python3
"""
Full-scale Agent Genesis extraction with checkpointing and progress monitoring.
Processes entire 17K conversation corpus with resilience and monitoring.
"""

import asyncio
import sys
import json
import httpx
from pathlib import Path
from typing import List, Dict, Optional, Set
import time
from datetime import datetime, timedelta
import signal

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.mcp_tools import add_decision, add_pattern, add_failure


class CheckpointManager:
    """Manages extraction checkpoints for resume capability."""
    
    def __init__(self, checkpoint_file: str = "ingestion/extraction_checkpoint.json"):
        self.checkpoint_file = Path(checkpoint_file)
        self.data = self.load()
    
    def load(self) -> Dict:
        """Load existing checkpoint or create new one."""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file, 'r') as f:
                return json.load(f)
        
        return {
            "last_processed_batch": 0,
            "completed_conversations": [],
            "failed_conversations": [],
            "extraction_stats": {
                "total_nodes_created": 0,
                "decisions": 0,
                "patterns": 0,
                "failures": 0,
                "success_rate": 0.0,
                "processing_timestamp": None
            },
            "batch_metadata": {
                "batch_size": 50,
                "start_time": None,
                "estimated_completion": None
            }
        }
    
    def save(self):
        """Persist checkpoint to disk."""
        with open(self.checkpoint_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def update_stats(self, decisions: int, patterns: int, failures: int, total_processed: int):
        """Update extraction statistics."""
        stats = self.data["extraction_stats"]
        stats["decisions"] = decisions
        stats["patterns"] = patterns
        stats["failures"] = failures
        stats["total_nodes_created"] = decisions + patterns + failures
        stats["success_rate"] = (stats["total_nodes_created"] / total_processed) if total_processed > 0 else 0.0
        stats["processing_timestamp"] = datetime.now().isoformat()
        self.save()
    
    def mark_conversation_completed(self, conv_id: str):
        """Mark a conversation as successfully processed."""
        if conv_id not in self.data["completed_conversations"]:
            self.data["completed_conversations"].append(conv_id)
    
    def mark_conversation_failed(self, conv_id: str):
        """Mark a conversation as failed."""
        if conv_id not in self.data["failed_conversations"]:
            self.data["failed_conversations"].append(conv_id)
    
    def is_completed(self, conv_id: str) -> bool:
        """Check if conversation already processed."""
        return conv_id in self.data["completed_conversations"]
    
    def get_completed_count(self) -> int:
        """Get number of completed conversations."""
        return len(self.data["completed_conversations"])


class ProgressMonitor:
    """Real-time progress monitoring with ETA calculation."""
    
    def __init__(self, total_conversations: int):
        self.total = total_conversations
        self.start_time = time.time()
        self.last_update = self.start_time
        self.recent_rates = []  # Rolling window for rate calculation
    
    def display(self, processed: int, nodes: int, current_batch: int, total_batches: int, 
                workers_active: int, recent_success_rate: float):
        """Display progress dashboard."""
        elapsed = time.time() - self.start_time
        rate = processed / elapsed if elapsed > 0 else 0
        
        # Store recent rate
        self.recent_rates.append(rate)
        if len(self.recent_rates) > 10:
            self.recent_rates.pop(0)
        
        # Calculate ETA
        avg_rate = sum(self.recent_rates) / len(self.recent_rates) if self.recent_rates else rate
        remaining = self.total - processed
        eta_seconds = remaining / avg_rate if avg_rate > 0 else 0
        eta = timedelta(seconds=int(eta_seconds))
        
        # Progress percentage
        progress_pct = (processed / self.total) * 100 if self.total > 0 else 0
        
        # Progress bar
        bar_width = 30
        filled = int(bar_width * progress_pct / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        # Display
        print(f"\n{'='*70}")
        print(f"📊 EXTRACTION PROGRESS")
        print(f"{'='*70}")
        print(f"Overall: {processed:,}/{self.total:,} ({progress_pct:.1f}%) │ ETA: {eta}")
        print(f"Rate: {rate:.1f} convos/min │ Nodes: {nodes:,} │ Success: {recent_success_rate:.1%}")
        print(f"Batch: {current_batch}/{total_batches} │ Workers: {workers_active} active")
        print(f"\n[{bar}] {progress_pct:.1f}%")
        print(f"{'='*70}")


class FullScaleExtractor:
    """Full-scale extraction with checkpointing and monitoring."""
    
    def __init__(self, batch_size: int = 50, queries_file: str = "ingestion/agent_genesis_queries.txt"):
        self.batch_size = batch_size
        self.queries_file = Path(queries_file)
        
        # Checkpoint manager
        self.checkpoint = CheckpointManager()
        
        # Statistics
        self.decisions_added = self.checkpoint.data["extraction_stats"]["decisions"]
        self.patterns_added = self.checkpoint.data["extraction_stats"]["patterns"]
        self.failures_added = self.checkpoint.data["extraction_stats"]["failures"]
        self.total_processed = self.checkpoint.get_completed_count()
        self.skipped = 0
        self.errors = 0
        
        # MKG configuration
        self.mkg_url = "http://100.80.229.35:1234"
        
        # Graceful shutdown
        self.shutdown_requested = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully."""
        print("\n\n⚠️  Shutdown signal received. Saving checkpoint...")
        self.shutdown_requested = True
    
    def load_queries(self) -> List[str]:
        """Load search queries from file."""
        queries = []
        with open(self.queries_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    queries.append(line)
        return queries
    
    async def search_all_conversations(self, query: str, limit: int = 1000) -> List[Dict]:
        """Search Agent Genesis for conversations (high limit for comprehensive coverage)."""
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
                
                # Transform to expected format
                transformed = []
                for conv in conversations:
                    conv_id = conv.get('id', 'unknown')
                    
                    # Skip if already processed
                    if self.checkpoint.is_completed(conv_id):
                        continue
                    
                    transformed.append({
                        'conversation_id': conv_id,
                        'content': conv.get('document', ''),
                        'metadata': conv.get('metadata', {}),
                        'relevance_score': 1.0 - conv.get('distance', 0.5)
                    })
                
                return transformed
                
        except Exception as e:
            print(f"    ❌ Search failed: {e}")
            return []
    
    async def extract_with_mkg(self, conversation: Dict) -> Optional[Dict]:
        """Extract knowledge using MKG semantic analysis."""
        content = conversation.get('content', '')
        
        if len(content) < 100:
            return None
        
        prompt = f"""Analyze this technical conversation and extract EXACTLY ONE insight:

TYPE 1 - TECHNICAL DECISION: Deliberate choice between alternatives
Examples: "Chose Redis over MongoDB", "Decided TypeScript over JavaScript"
Format: {{"type": "decision", "description": "brief summary", "rationale": "why", "alternatives": ["opt1", "opt2"]}}

TYPE 2 - RECURRING PATTERN: Repeated solution approach
Examples: "Always implement health checks", "Use dependency injection"
Format: {{"type": "pattern", "name": "pattern name", "context": "when", "implementation": "how"}}

TYPE 3 - SYSTEMATIC FAILURE: Consistent problem/anti-pattern
Examples: "Timeouts during cache invalidation", "Memory leaks in handlers"
Format: {{"type": "failure", "attempt": "what tried", "reason": "why failed", "lesson": "learned"}}

Conversation:
{content[:2000]}

Respond with ONLY valid JSON. If none match, return {{"type": "none"}}.
No markdown, no explanation, just JSON."""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.mkg_url}/v1/chat/completions",
                    json={
                        "model": "local",
                        "messages": [
                            {"role": "system", "content": "You are a JSON extraction assistant. Respond with ONLY valid JSON, no markdown, no explanation."},
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
                choices = result.get('choices', [])
                if not choices:
                    return None
                
                answer = choices[0].get('message', {}).get('content', '').strip()
                
                # Robust JSON cleaning
                import re
                cleaned = answer
                cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
                cleaned = re.sub(r'```json\\s*', '', cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r'```\\s*', '', cleaned)
                cleaned = re.sub(r'`+', '', cleaned)
                cleaned = re.sub(r'^[^{\\[]*', '', cleaned)
                cleaned = re.sub(r'[^}\\]]*$', '', cleaned)
                cleaned = cleaned.strip()
                
                try:
                    extracted = json.loads(cleaned)
                    if extracted.get('type') in ['decision', 'pattern', 'failure']:
                        return extracted
                    if extracted.get('type') == 'none':
                        return None
                except json.JSONDecodeError:
                    pass
                
                # Fallback: find JSON objects
                json_matches = re.findall(r'\\{[^{}]*(?:\\{[^{}]*\\}[^{}]*)*\\}', answer, re.DOTALL)
                for json_str in reversed(json_matches):
                    try:
                        extracted = json.loads(json_str)
                        if extracted.get('type') in ['decision', 'pattern', 'failure']:
                            return extracted
                    except json.JSONDecodeError:
                        continue
                
                return None
                
        except Exception as e:
            return None
    
    async def process_conversation(self, conversation: Dict) -> bool:
        """Process a single conversation and add to knowledge base."""
        conv_id = conversation.get('conversation_id', 'unknown')
        
        # Extract knowledge
        extracted = await self.extract_with_mkg(conversation)
        
        if not extracted or extracted.get('type') == 'none':
            self.skipped += 1
            self.checkpoint.mark_conversation_completed(conv_id)
            return False
        
        try:
            # Add to knowledge base based on type
            if extracted['type'] == 'decision':
                result = await add_decision(
                    description=extracted.get('description', '')[:200],
                    rationale=extracted.get('rationale', '')[:500],
                    alternatives=extracted.get('alternatives', [])[:5],
                    related_to=[]
                )
                self.decisions_added += 1
                
            elif extracted['type'] == 'pattern':
                result = await add_pattern(
                    name=extracted.get('name', '')[:100],
                    context=extracted.get('context', '')[:200],
                    implementation=extracted.get('implementation', '')[:1000],
                    use_cases=[extracted.get('context', '')[:200]]
                )
                self.patterns_added += 1
                
            elif extracted['type'] == 'failure':
                result = await add_failure(
                    attempt=extracted.get('attempt', '')[:200],
                    reason_failed=extracted.get('reason', '')[:500],
                    lesson_learned=extracted.get('lesson', '')[:500],
                    alternative_solution=""
                )
                self.failures_added += 1
            
            self.checkpoint.mark_conversation_completed(conv_id)
            return True
            
        except Exception as e:
            self.errors += 1
            self.checkpoint.mark_conversation_failed(conv_id)
            return False
    
    async def run_full_extraction(self):
        """Execute full-scale extraction with monitoring."""
        print("\n" + "="*70)
        print("🚀 FULL-SCALE AGENT GENESIS EXTRACTION")
        print("="*70)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Batch Size: {self.batch_size}")
        print(f"Resuming from: {self.checkpoint.get_completed_count()} completed conversations")
        
        # Load queries
        queries = self.load_queries()
        print(f"Queries: {len(queries)}")
        
        # Collect all unique conversations
        all_conversations = []
        seen_ids = set()
        
        print("\n📡 Gathering conversations from Agent Genesis...")
        for query in queries:
            conversations = await self.search_all_conversations(query, limit=1000)
            for conv in conversations:
                conv_id = conv['conversation_id']
                if conv_id not in seen_ids:
                    seen_ids.add(conv_id)
                    all_conversations.append(conv)
            print(f"  Query: '{query[:50]}...' → {len(conversations)} new conversations")
        
        print(f"\n✅ Total unique conversations to process: {len(all_conversations):,}")
        
        # Progress monitor
        monitor = ProgressMonitor(len(all_conversations))
        
        # Process in batches
        start_time = time.time()
        total_batches = (len(all_conversations) + self.batch_size - 1) // self.batch_size
        
        for i in range(0, len(all_conversations), self.batch_size):
            if self.shutdown_requested:
                print("\n⚠️  Shutdown requested. Saving progress...")
                self.checkpoint.update_stats(
                    self.decisions_added, self.patterns_added, 
                    self.failures_added, self.total_processed
                )
                break
            
            batch = all_conversations[i:i+self.batch_size]
            batch_num = i // self.batch_size + 1
            
            # Process batch
            for conv in batch:
                success = await self.process_conversation(conv)
                self.total_processed += 1
                
                if success:
                    await asyncio.sleep(0.5)  # Rate limiting
            
            # Update checkpoint every batch
            self.checkpoint.update_stats(
                self.decisions_added, self.patterns_added,
                self.failures_added, self.total_processed
            )
            
            # Display progress every 5 batches
            if batch_num % 5 == 0 or batch_num == total_batches:
                total_nodes = self.decisions_added + self.patterns_added + self.failures_added
                success_rate = (total_nodes / self.total_processed) if self.total_processed > 0 else 0.0
                monitor.display(
                    self.total_processed, total_nodes, batch_num, 
                    total_batches, 1, success_rate
                )
        
        # Final summary
        elapsed = time.time() - start_time
        total_nodes = self.decisions_added + self.patterns_added + self.failures_added
        success_rate = (total_nodes / self.total_processed) if self.total_processed > 0 else 0.0
        
        print("\n" + "="*70)
        print("✅ FULL-SCALE EXTRACTION COMPLETE")
        print("="*70)
        print(f"\nResults:")
        print(f"  Conversations processed: {self.total_processed:,}")
        print(f"  Decisions: {self.decisions_added:,}")
        print(f"  Patterns: {self.patterns_added:,}")
        print(f"  Failures: {self.failures_added:,}")
        print(f"  Total nodes: {total_nodes:,}")
        print(f"  Success rate: {success_rate:.1%}")
        print(f"  Skipped: {self.skipped:,}")
        print(f"  Errors: {self.errors}")
        print(f"\nTime: {elapsed/3600:.1f} hours")
        print(f"Avg per conversation: {elapsed/self.total_processed:.1f}s")
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nCheckpoint saved: {self.checkpoint.checkpoint_file}")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Full-scale Agent Genesis extraction"
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Conversations per batch (default: 50)'
    )
    parser.add_argument(
        '--queries-file',
        default='ingestion/agent_genesis_queries.txt',
        help='Search queries file'
    )
    
    args = parser.parse_args()
    
    extractor = FullScaleExtractor(
        batch_size=args.batch_size,
        queries_file=args.queries_file
    )
    
    await extractor.run_full_extraction()


if __name__ == "__main__":
    asyncio.run(main())
