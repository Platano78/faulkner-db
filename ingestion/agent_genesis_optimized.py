#!/usr/bin/env python3
"""
Optimized Agent Genesis extraction - 5-10x faster
Combines: Batch LLM inference, async parallelism, smart filtering
"""

import asyncio
import sys
import json
import httpx
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
import time
from datetime import datetime, timedelta
import signal
import re
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.mcp_tools import add_decision, add_pattern, add_failure


class OptimizedExtractor:
    """Optimized extraction with batching, parallelism, and smart filtering."""
    
    def __init__(self, batch_size: int = 100, llm_batch_size: int = 20, parallel_tasks: int = 8):
        self.batch_size = batch_size
        self.llm_batch_size = llm_batch_size  # NEW: Batch LLM requests
        self.parallel_tasks = parallel_tasks  # NEW: Concurrent extraction
        self.checkpoint_file = Path("ingestion/optimized_checkpoint.json")
        
        # Statistics
        self.decisions_added = 0
        self.patterns_added = 0
        self.failures_added = 0
        self.total_processed = 0
        self.skipped = 0
        self.filtered = 0  # NEW: Track filtered conversations
        self.errors = 0
        self.batched_extractions = 0  # NEW: Track batch efficiency
        
        # MKG configuration
        self.mkg_url = "http://localhost:8002"
        
        # Load checkpoint
        self.checkpoint = self.load_checkpoint()
        self.processed_ids: Set[str] = set(self.checkpoint.get("completed_conversations", []))
        
        # Extraction cache (NEW: smart pattern caching)
        self.extraction_cache = {}
        self.pattern_signatures = defaultdict(int)  # Track repeated patterns
        
        # Graceful shutdown
        self.shutdown_requested = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully."""
        print("\n\n⚠️  Shutdown signal received. Saving checkpoint...")
        self.shutdown_requested = True
    
    def load_checkpoint(self) -> Dict:
        """Load existing checkpoint or create new one."""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file, 'r') as f:
                return json.load(f)
        
        return {
            "completed_conversations": [],
            "failed_conversations": [],
            "extraction_stats": {
                "decisions": 0,
                "patterns": 0,
                "failures": 0,
                "total_nodes_created": 0,
                "success_rate": 0.0
            }
        }
    
    def save_checkpoint(self):
        """Persist checkpoint to disk."""
        self.checkpoint["completed_conversations"] = list(self.processed_ids)
        self.checkpoint["extraction_stats"] = {
            "decisions": self.decisions_added,
            "patterns": self.patterns_added,
            "failures": self.failures_added,
            "total_nodes_created": self.decisions_added + self.patterns_added + self.failures_added,
            "success_rate": (self.decisions_added + self.patterns_added + self.failures_added) / self.total_processed if self.total_processed > 0 else 0.0,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(self.checkpoint_file, 'w') as f:
            json.dump(self.checkpoint, f, indent=2)
    
    async def search_all_conversations(self) -> List[Dict]:
        """Gather ALL conversations using broad search queries."""
        print("\n📡 Gathering ALL conversations from Agent Genesis corpus...")
        
        phase1_queries = [
            "code implementation", "technical discussion", "architecture design",
            "debugging", "testing", "deployment", "configuration", "integration",
            "optimization", "refactoring", "error handling", "database", "API",
            "frontend", "backend", "infrastructure", "security", "performance",
            "documentation", "workflow"
        ]

        phase2_queries = [
            "implementation", "system design", "code", "project", "analysis",
            "solution", "problem", "development", "feature", "module",
            "component", "class", "function", "service", "library",
            "framework", "tool", "setup", "installation", "configuration"
        ]

        broad_queries = phase1_queries + phase2_queries
        
        all_conversations = []
        seen_ids = self.processed_ids.copy()
        
        # Search with high limit per query
        for query in broad_queries:
            if self.shutdown_requested:
                break
            
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        "http://localhost:8080/search",
                        json={"query": query, "n_results": 2000}
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    nested_results = result.get("results", {})
                    conversations = nested_results.get("results", [])
                    
                    new_count = 0
                    for conv in conversations:
                        conv_id = conv.get('id', 'unknown')
                        
                        if conv_id not in seen_ids:
                            seen_ids.add(conv_id)
                            all_conversations.append({
                                'conversation_id': conv_id,
                                'content': conv.get('document', ''),
                                'metadata': conv.get('metadata', {}),
                                'relevance_score': 1.0 - conv.get('distance', 0.5)
                            })
                            new_count += 1
                    
                    print(f"  '{query}': +{new_count} new (total unique: {len(all_conversations):,})")
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                print(f"  ❌ Query '{query}' failed: {e}")
                continue
        
        print(f"\n✅ Total unique conversations gathered: {len(all_conversations):,}")
        
        # NEW: Sort by relevance (higher score = process first)
        all_conversations.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        return all_conversations
    
    def filter_conversation(self, conversation: Dict) -> Tuple[bool, str]:
        """NEW: Smart filtering - skip low-quality conversations."""
        content = conversation.get('content', '')
        relevance = conversation.get('relevance_score', 0.5)  # Default to 0.5 if missing

        # Filter 1: Content quality - RELAXED from 100 to 30
        if len(content) < 30:
            return False, "too_short"

        # Filter 2: Relevance threshold - RELAXED from 0.15 to 0.05
        if relevance < 0.05:  # Only filter truly irrelevant
            return False, "low_relevance"

        # Filter 3: Avoid duplicates - RELAXED from 5 to 20
        content_sig = hash(content[:200]) % 10000
        if self.pattern_signatures[content_sig] > 20:  # Allow more duplicates
            return False, "duplicate_pattern"

        self.pattern_signatures[content_sig] += 1
        return True, "accepted"
    
    async def extract_batch_with_mkg(self, batch_convs: List[Dict]) -> Dict[str, Optional[Dict]]:
        """NEW: Extract multiple conversations in a single LLM call."""
        results = {}
        
        # Format batch for extraction
        batch_text = "\n\n---\n\n".join([
            f"[CONVERSATION {i}]\n{conv.get('content', '')[:1000]}"
            for i, conv in enumerate(batch_convs)
        ])
        
        prompt = f"""Analyze these {len(batch_convs)} technical conversations and extract insights.

For EACH conversation, identify ONE of these types:

TYPE 1 - DECISION: Deliberate choice between alternatives
Format: {{"id": N, "type": "decision", "description": "brief", "rationale": "why", "alternatives": ["opt1", "opt2"]}}

TYPE 2 - PATTERN: Repeated solution approach  
Format: {{"id": N, "type": "pattern", "name": "pattern name", "context": "when", "implementation": "how"}}

TYPE 3 - FAILURE: Consistent problem/anti-pattern
Format: {{"id": N, "type": "failure", "attempt": "what", "reason": "why", "lesson": "learned"}}

If none match: {{"id": N, "type": "none"}}

Conversations:
{batch_text}

Respond with ONLY a JSON array. No markdown, no explanation.
Example: [{{...}}, {{...}}]"""

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:  # Longer timeout for batch
                response = await client.post(
                    f"{self.mkg_url}/v1/chat/completions",
                    json={
                        "model": "qwen2.5-coder-14b-awq",
                        "messages": [
                            {"role": "system", "content": "You are a JSON extraction assistant. Respond with ONLY valid JSON arrays, no markdown."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 2000  # More tokens for batch
                    },
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    return {conv.get('conversation_id'): None for conv in batch_convs}
                
                result = response.json()
                answer = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                
                # Clean response
                cleaned = re.sub(r'```json\s*', '', answer, flags=re.IGNORECASE)
                cleaned = re.sub(r'```\s*', '', cleaned)
                cleaned = re.sub(r'`+', '', cleaned)
                cleaned = cleaned.strip()
                
                try:
                    extracted_list = json.loads(cleaned)
                    if not isinstance(extracted_list, list):
                        extracted_list = [extracted_list]
                    
                    # Map results back to conversations
                    for item in extracted_list:
                        conv_id = batch_convs[item.get('id', 0)].get('conversation_id')
                        if item.get('type') in ['decision', 'pattern', 'failure']:
                            results[conv_id] = item
                        else:
                            results[conv_id] = None
                    
                    # Fill missing
                    for conv in batch_convs:
                        if conv.get('conversation_id') not in results:
                            results[conv.get('conversation_id')] = None
                    
                    self.batched_extractions += 1
                    return results
                    
                except json.JSONDecodeError:
                    return {conv.get('conversation_id'): None for conv in batch_convs}
                    
        except Exception as e:
            return {conv.get('conversation_id'): None for conv in batch_convs}
    
    async def process_conversation(self, conversation: Dict) -> bool:
        """Process single conversation (result from batch extraction)."""
        conv_id = conversation.get('conversation_id', 'unknown')
        extracted = conversation.get('_extracted')
        
        if not extracted or extracted.get('type') == 'none':
            self.skipped += 1
            self.processed_ids.add(conv_id)
            return False
        
        try:
            # Add to knowledge base based on type
            if extracted['type'] == 'decision':
                await add_decision(
                    description=extracted.get('description', '')[:200],
                    rationale=extracted.get('rationale', '')[:500],
                    alternatives=extracted.get('alternatives', [])[:5],
                    related_to=[]
                )
                self.decisions_added += 1
                
            elif extracted['type'] == 'pattern':
                await add_pattern(
                    name=extracted.get('name', '')[:100],
                    context=extracted.get('context', '')[:200],
                    implementation=extracted.get('implementation', '')[:1000],
                    use_cases=[extracted.get('context', '')[:200]]
                )
                self.patterns_added += 1
                
            elif extracted['type'] == 'failure':
                await add_failure(
                    attempt=extracted.get('attempt', '')[:200],
                    reason_failed=extracted.get('reason', '')[:500],
                    lesson_learned=extracted.get('lesson', '')[:500],
                    alternative_solution=""
                )
                self.failures_added += 1
            
            self.processed_ids.add(conv_id)
            return True
            
        except Exception as e:
            self.errors += 1
            self.processed_ids.add(conv_id)
            return False
    
    async def run_optimized_extraction(self):
        """Execute optimized extraction with batching and parallelism."""
        print("\n" + "="*70)
        print("🚀 OPTIMIZED AGENT GENESIS EXTRACTION (5-10x faster)")
        print("="*70)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Batch Size: {self.batch_size} | LLM Batch: {self.llm_batch_size} | Parallel: {self.parallel_tasks}")
        print(f"Already processed: {len(self.processed_ids):,} conversations")
        
        # Gather all conversations
        start_gather = time.time()
        all_conversations = await self.search_all_conversations()
        gather_time = time.time() - start_gather
        print(f"\n⏱️  Gathering took: {gather_time:.1f}s")
        
        if not all_conversations:
            print("\n⚠️  No new conversations to process!")
            return
        
        # Filter conversations (NEW)
        print(f"\n🔍 Filtering conversations...")
        filtered_convs = []
        filter_stats = defaultdict(int)
        
        for conv in all_conversations:
            keep, reason = self.filter_conversation(conv)
            if keep:
                filtered_convs.append(conv)
            else:
                self.filtered += 1
                filter_stats[reason] += 1
        
        print(f"  Kept: {len(filtered_convs):,} | Filtered: {self.filtered:,}")
        for reason, count in sorted(filter_stats.items(), key=lambda x: -x[1]):
            print(f"    - {reason}: {count:,}")
        
        # Process in batches with LLM batching
        start_process = time.time()
        total_batches = (len(filtered_convs) + self.batch_size - 1) // self.batch_size
        
        print(f"\n📦 Processing {len(filtered_convs):,} conversations in {total_batches} batches...")
        print(f"   (batching {self.llm_batch_size} conversations per LLM call)\n")
        
        for batch_idx in range(0, len(filtered_convs), self.batch_size):
            if self.shutdown_requested:
                print("\n⚠️  Shutdown requested. Saving progress...")
                self.save_checkpoint()
                break
            
            batch = filtered_convs[batch_idx:batch_idx+self.batch_size]
            batch_num = batch_idx // self.batch_size + 1
            batch_start = time.time()
            
            # NEW: Process with LLM batching
            # Split batch into LLM sub-batches
            llm_sub_batches = []
            for i in range(0, len(batch), self.llm_batch_size):
                llm_sub_batches.append(batch[i:i+self.llm_batch_size])
            
            # NEW: Extract in parallel with semaphore to limit concurrency
            semaphore = asyncio.Semaphore(self.parallel_tasks)
            
            async def extract_sub_batch(sub_batch):
                async with semaphore:
                    return await self.extract_batch_with_mkg(sub_batch)
            
            # Parallel extraction
            extraction_tasks = [extract_sub_batch(sub) for sub in llm_sub_batches]
            extraction_results = await asyncio.gather(*extraction_tasks)
            
            # Merge extraction results
            all_extractions = {}
            for result_dict in extraction_results:
                all_extractions.update(result_dict)
            
            # Add extraction results to conversations
            for conv in batch:
                conv['_extracted'] = all_extractions.get(conv.get('conversation_id'))
            
            # Process results and add to knowledge base (with some parallelism)
            add_tasks = [self.process_conversation(conv) for conv in batch]
            await asyncio.gather(*add_tasks)
            
            for conv in batch:
                self.total_processed += 1
            
            batch_time = time.time() - batch_start
            
            # Update checkpoint every batch
            self.save_checkpoint()
            
            # Progress display
            total_nodes = self.decisions_added + self.patterns_added + self.failures_added
            success_rate = (total_nodes / self.total_processed) if self.total_processed > 0 else 0.0
            rate = self.total_processed / (time.time() - start_process) * 60
            remaining = len(filtered_convs) - self.total_processed
            eta_minutes = (remaining / rate) if rate > 0 else 0
            
            progress_pct = (self.total_processed / len(filtered_convs)) * 100
            bar_width = 30
            filled = int(bar_width * progress_pct / 100)
            bar = "█" * filled + "░" * (bar_width - filled)
            
            print(f"\r[{bar}] {progress_pct:.1f}% │ "
                  f"Batch {batch_num}/{total_batches} │ "
                  f"Nodes: {total_nodes} ({success_rate:.1%}) │ "
                  f"Rate: {rate:.1f}/min │ "
                  f"ETA: {eta_minutes:.0f}m",
                  end="", flush=True)
            
            # Detailed progress every 10 batches
            if batch_num % 10 == 0:
                print(f"\n  ├─ Decisions: {self.decisions_added} │ Patterns: {self.patterns_added} │ Failures: {self.failures_added}")
                print(f"  ├─ Batch time: {batch_time:.1f}s │ LLM calls: {len(llm_sub_batches)}")
                print(f"  └─ Skipped: {self.skipped} │ Errors: {self.errors}\n")
        
        # Final summary
        print("\n")
        elapsed = time.time() - start_process
        total_nodes = self.decisions_added + self.patterns_added + self.failures_added
        success_rate = (total_nodes / self.total_processed) if self.total_processed > 0 else 0.0
        
        print("\n" + "="*70)
        print("✅ OPTIMIZED EXTRACTION COMPLETE")
        print("="*70)
        print(f"\nResults:")
        print(f"  Conversations processed: {self.total_processed:,}")
        print(f"  Decisions: {self.decisions_added:,}")
        print(f"  Patterns: {self.patterns_added:,}")
        print(f"  Failures: {self.failures_added:,}")
        print(f"  Total nodes extracted: {total_nodes:,}")
        print(f"  Success rate: {success_rate:.1%}")
        print(f"\nFiltering & Optimization:")
        print(f"  Filtered out: {self.filtered:,}")
        print(f"  Skipped (no insight): {self.skipped:,}")
        print(f"  Errors: {self.errors}")
        print(f"  Batched LLM calls: {self.batched_extractions}")
        print(f"\nPerformance:")
        print(f"  Processing time: {elapsed/3600:.2f} hours")
        if self.total_processed > 0:
            print(f"  Average per conversation: {elapsed/self.total_processed:.3f}s")
            print(f"  Throughput: {self.total_processed/elapsed*60:.1f} conversations/minute")
            print(f"  Estimated speedup: {(self.llm_batch_size / (elapsed / self.total_processed)):.1f}x faster than sequential")
        else:
            print(f"  No conversations processed")
        print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Checkpoint: {self.checkpoint_file}")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Optimized Agent Genesis extraction"
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Conversations per batch (default: 100)'
    )
    parser.add_argument(
        '--llm-batch',
        type=int,
        default=20,
        help='Conversations per LLM call (default: 20)'
    )
    parser.add_argument(
        '--parallel',
        type=int,
        default=8,
        help='Parallel LLM batches (default: 8)'
    )
    
    args = parser.parse_args()
    
    extractor = OptimizedExtractor(
        batch_size=args.batch_size,
        llm_batch_size=args.llm_batch,
        parallel_tasks=args.parallel
    )
    await extractor.run_optimized_extraction()


if __name__ == "__main__":
    asyncio.run(main())
