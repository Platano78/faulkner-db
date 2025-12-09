#!/usr/bin/env python3
"""
Phase 2: Agent Genesis extraction - targeted queries for remaining 6K conversations.
Uses specialized domain and alternative phrasing queries to capture missed conversations.
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
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.mcp_tools import add_decision, add_pattern, add_failure


class Phase2Extractor:
    """Phase 2 extraction using specialized and alternative queries."""

    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.checkpoint_file = Path("ingestion/comprehensive_checkpoint.json")

        # Statistics
        self.decisions_added = 0
        self.patterns_added = 0
        self.failures_added = 0
        self.total_processed = 0
        self.skipped = 0
        self.errors = 0
        self.new_conversations = 0

        # MKG configuration
        self.mkg_url = "http://100.80.229.35:1234"

        # Load checkpoint from Phase 1
        self.checkpoint = self.load_checkpoint()
        self.processed_ids: Set[str] = set(self.checkpoint.get("completed_conversations", []))
        self.phase1_count = len(self.processed_ids)

        # Graceful shutdown
        self.shutdown_requested = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully."""
        print("\n\n⚠️  Shutdown signal received. Saving checkpoint...")
        self.shutdown_requested = True

    def load_checkpoint(self) -> Dict:
        """Load checkpoint from Phase 1."""
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

    async def search_phase2_conversations(self) -> List[Dict]:
        """Gather remaining conversations using specialized queries."""
        print("\n📡 Phase 2: Searching for additional conversations...")
        print(f"   Already processed (Phase 1): {self.phase1_count:,} conversations\n")

        # Specialized domain queries
        domain_queries = [
            "machine learning",
            "data science",
            "artificial intelligence",
            "neural network",
            "web development",
            "mobile development",
            "cloud computing",
            "devops",
            "kubernetes",
            "docker",
            "microservices",
            "game development",
            "graphics",
            "rendering",
            "systems programming"
        ]

        # Alternative phrasing queries
        alternative_queries = [
            "learning",
            "tutorial",
            "example code",
            "bug fix",
            "solution",
            "design pattern",
            "best practice",
            "principle",
            "framework comparison",
            "library evaluation",
            "tradeoff",
            "decision making",
            "choice",
            "consideration",
            "evaluation"
        ]

        # Wildcard/catch-all queries
        wildcard_queries = [
            "work",
            "help",
            "idea",
            "note",
            "task",
            "milestone",
            "release",
            "discuss",
            "question",
            "answer"
        ]

        all_queries = domain_queries + alternative_queries + wildcard_queries

        all_conversations = []
        seen_ids = self.processed_ids.copy()

        # Search with high limit per query
        for i, query in enumerate(all_queries, 1):
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

                    print(f"  [{i:2d}/40] '{query:25s}': +{new_count:4d} new (total new: {len(all_conversations):,})")

                    # Small delay to avoid overwhelming the API
                    await asyncio.sleep(0.5)

            except Exception as e:
                print(f"  ❌ Query '{query}' failed: {e}")
                continue

        self.new_conversations = len(all_conversations)
        print(f"\n✅ NEW conversations found in Phase 2: {self.new_conversations:,}")
        print(f"   Total processed after Phase 2: {self.phase1_count + self.new_conversations:,}\n")
        return all_conversations

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
                cleaned = answer
                cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
                cleaned = re.sub(r'```json\s*', '', cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r'```\s*', '', cleaned)
                cleaned = re.sub(r'`+', '', cleaned)
                cleaned = re.sub(r'^[^{\[]*', '', cleaned)
                cleaned = re.sub(r'[^}\]]*$', '', cleaned)
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
                json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', answer, re.DOTALL)
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
            self.processed_ids.add(conv_id)
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

            self.processed_ids.add(conv_id)
            return True

        except Exception as e:
            self.errors += 1
            self.processed_ids.add(conv_id)
            return False

    async def run_phase2_extraction(self):
        """Execute Phase 2 extraction."""
        print("\n" + "="*70)
        print("🚀 PHASE 2: AGENT GENESIS EXTRACTION")
        print("="*70)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Batch Size: {self.batch_size}")
        print(f"Already processed (Phase 1): {self.phase1_count:,} conversations")

        # Gather new conversations
        start_gather = time.time()
        all_conversations = await self.search_phase2_conversations()
        gather_time = time.time() - start_gather
        print(f"⏱️  Gathering took: {gather_time:.1f}s")

        if not all_conversations:
            print("\n⚠️  No new conversations found in Phase 2!")
            print("This indicates Phase 1 captured most semantically relevant conversations.")
            return

        # Process in batches
        start_process = time.time()
        total_batches = (len(all_conversations) + self.batch_size - 1) // self.batch_size

        print(f"\n📦 Processing {len(all_conversations):,} new conversations in {total_batches} batches...\n")

        for i in range(0, len(all_conversations), self.batch_size):
            if self.shutdown_requested:
                print("\n⚠️  Shutdown requested. Saving progress...")
                self.save_checkpoint()
                break

            batch = all_conversations[i:i+self.batch_size]
            batch_num = i // self.batch_size + 1

            batch_start = time.time()

            # Process batch
            for conv in batch:
                success = await self.process_conversation(conv)
                self.total_processed += 1

                if success:
                    await asyncio.sleep(0.3)  # Rate limiting

            batch_time = time.time() - batch_start

            # Update checkpoint every batch
            self.save_checkpoint()

            # Progress display
            total_nodes = self.decisions_added + self.patterns_added + self.failures_added
            success_rate = (total_nodes / self.total_processed) if self.total_processed > 0 else 0.0
            rate = self.total_processed / (time.time() - start_process) * 60  # convos/min
            remaining = len(all_conversations) - self.total_processed
            eta_minutes = (remaining / rate) if rate > 0 else 0

            progress_pct = (self.total_processed / len(all_conversations)) * 100
            bar_width = 30
            filled = int(bar_width * progress_pct / 100)
            bar = "█" * filled + "░" * (bar_width - filled)

            print(f"\r[{bar}] {progress_pct:.1f}% │ "
                  f"Batch {batch_num}/{total_batches} │ "
                  f"New Nodes: {total_nodes} ({success_rate:.1%}) │ "
                  f"Rate: {rate:.1f}/min │ "
                  f"ETA: {eta_minutes:.0f}m",
                  end="", flush=True)

            # Detailed progress every 10 batches
            if batch_num % 10 == 0:
                print(f"\n  ├─ Decisions: {self.decisions_added} │ Patterns: {self.patterns_added} │ Failures: {self.failures_added}")
                print(f"  └─ Skipped: {self.skipped} │ Errors: {self.errors} │ Batch time: {batch_time:.1f}s\n")

        # Final summary
        print("\n")
        elapsed = time.time() - start_process
        total_nodes = self.decisions_added + self.patterns_added + self.failures_added
        success_rate = (total_nodes / self.total_processed) if self.total_processed > 0 else 0.0

        print("\n" + "="*70)
        print("✅ PHASE 2 EXTRACTION COMPLETE")
        print("="*70)
        print(f"\nPhase 2 Results:")
        print(f"  New conversations processed: {self.total_processed:,}")
        print(f"  New decisions: {self.decisions_added:,}")
        print(f"  New patterns: {self.patterns_added:,}")
        print(f"  New failures: {self.failures_added:,}")
        print(f"  New nodes extracted: {total_nodes:,}")
        print(f"  Success rate: {success_rate:.1%}")
        print(f"  Skipped: {self.skipped:,}")
        print(f"  Errors: {self.errors}")
        print(f"\nCumulative Results (Phase 1 + Phase 2):")
        print(f"  Total conversations processed: {self.phase1_count + self.total_processed:,}")
        print(f"  Total knowledge nodes: ~{int(self.checkpoint['extraction_stats']['decisions'] + self.decisions_added + self.checkpoint['extraction_stats']['patterns'] + self.patterns_added + self.checkpoint['extraction_stats']['failures'] + self.failures_added):,}")
        print(f"\nPerformance:")
        print(f"  Phase 2 processing time: {elapsed/3600:.2f} hours")
        print(f"  Average per conversation: {elapsed/self.total_processed:.2f}s")
        print(f"  Throughput: {self.total_processed/elapsed*60:.1f} conversations/minute")
        print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Checkpoint: {self.checkpoint_file}")


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 2 Agent Genesis extraction"
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Conversations per batch (default: 100)'
    )

    args = parser.parse_args()

    extractor = Phase2Extractor(batch_size=args.batch_size)
    await extractor.run_phase2_extraction()


if __name__ == "__main__":
    asyncio.run(main())
