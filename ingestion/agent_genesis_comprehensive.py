#!/usr/bin/env python3
"""
Comprehensive Agent Genesis extraction - processes entire corpus.
Uses broad search queries to capture all 17K+ conversations.
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
from collections import deque

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.graphiti_client import GraphitiClient
from pydantic import BaseModel
from typing import List, Optional
import uuid

# Pydantic models for knowledge nodes
class Decision(BaseModel):
    id: Optional[str] = None
    type: str = "Decision"
    description: str
    rationale: str
    alternatives: List[str]
    related_to: List[str]

class Pattern(BaseModel):
    id: Optional[str] = None
    type: str = "Pattern"
    name: str
    context: str
    implementation: str
    use_cases: List[str]

class SystematicFailure(BaseModel):
    id: Optional[str] = None
    type: str = "SystematicFailure"
    attempt: str
    reason_failed: str
    lesson_learned: str
    alternative_solution: str


class KeywordFallbackExtractor:
    """Fast regex-based extraction for when MKG times out."""
    
    def __init__(self):
        self.decision_patterns = [
            r"decided to (.+?)(?:\.|,|;|because|$)",
            r"chose (.+?)(?:\.|,|;|because|over|$)", 
            r"selected (.+?)(?:\.|,|;|for|$)",
            r"went with (.+?)(?:\.|,|;|instead|$)",
            r"picked (.+?)(?:\.|,|;|$)",
            r"using (.+?) (?:for|because|instead)"
        ]
        
        self.pattern_patterns = [
            r"always (.+?)(?:\.|,|;|$)",
            r"pattern (?:of |is )?(.+?)(?:\.|,|;|$)",
            r"approach (?:is |involves )?(.+?)(?:\.|,|;|$)", 
            r"strategy (?:is |for )?(.+?)(?:\.|,|;|$)",
            r"convention (?:of |is )?(.+?)(?:\.|,|;|$)"
        ]
        
        self.failure_patterns = [
            r"failed to (.+?)(?:\.|,|;|$)",
            r"didn't work (.+?)(?:\.|,|;|$)",
            r"broke (.+?)(?:\.|,|;|$)",
            r"error (?:in |with )?(.+?)(?:\.|,|;|$)",
            r"bug (?:in |with )?(.+?)(?:\.|,|;|$)",
            r"issue (?:with |in )?(.+?)(?:\.|,|;|$)"
        ]
        
        # Simple cache
        self._cache = {}
        self.cache_hits = 0
        self.fallback_extractions = 0
        
    def extract_from_text(self, content: str) -> Optional[Dict]:
        """Extract knowledge using regex patterns."""
        if not content or len(content.strip()) < 10:
            return None

        # Check cache first
        cache_key = hash(content[:1000])
        if cache_key in self._cache:
            self.cache_hits += 1
            return self._cache[cache_key]

        # Try to find decisions first (most common)
        for pattern in self.decision_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                match = matches[0][:200] if isinstance(matches[0], str) else matches[0][0][:200]
                result = {
                    'type': 'decision',
                    'description': match.strip(),
                    'rationale': 'Extracted from conversation context',
                    'alternatives': []
                }
                self._cache[cache_key] = result
                return result

        # Try patterns
        for pattern in self.pattern_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                match = matches[0][:100] if isinstance(matches[0], str) else matches[0][0][:100]
                result = {
                    'type': 'pattern',
                    'name': match.strip(),
                    'context': 'Technical conversation',
                    'implementation': content[:500]
                }
                self._cache[cache_key] = result
                return result

        # Try failures
        for pattern in self.failure_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                match = matches[0][:200] if isinstance(matches[0], str) else matches[0][0][:200]
                result = {
                    'type': 'failure',
                    'attempt': match.strip(),
                    'reason': 'See conversation context',
                    'lesson': 'Extracted from technical discussion'
                }
                self._cache[cache_key] = result
                return result

        # FALLBACK: If no patterns match, extract as generic pattern
        # This prevents skipping valuable conversations
        if len(content) > 50:
            result = {
                'type': 'pattern',
                'name': content[:80].strip() + '...' if len(content) > 80 else content.strip(),
                'context': 'Technical discussion',
                'implementation': content[:800]
            }
            self._cache[cache_key] = result
            return result

        return None


class ComprehensiveExtractor:
    """Comprehensive extraction using broad search strategy."""
    
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
        
        # MKG configuration
        self.mkg_url = "http://localhost:8002"
        
        # GraphitiClient for real FalkorDB writes
        self.graphiti_client = GraphitiClient()
        
        # Parallel processing configuration
        self.semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests
        self.timeout_counter = 0
        self.MAX_TIMEOUTS = 15  # Increased from 3 to allow more MKG attempts before fallback
        self.TIMEOUT_THRESHOLD = 60.0  # Increased from 30.0 to give MKG more time
        self.CB_RESET_SUCCESS_COUNT = 3  # Reset circuit breaker after consecutive successes
        self.consecutive_successes = 0
        
        # Throughput monitoring
        self.batch_start_time = time.time()
        self.session_start_time = time.time()
        
        # Keyword fallback extractor
        self.keyword_extractor = KeywordFallbackExtractor()
        self.fallback_count = 0
        
        # Batch checkpoint optimization
        self.checkpoint_interval = 10  # Save every 10 batches
        self.last_checkpoint_batch = 0
        self.checkpoint_io_times = []
        self.checkpoints_saved = 0
        
        # Progress dashboard with rolling averages
        self.batch_rates = deque(maxlen=10)  # Last 10 batch rates
        self.dashboard_update_times = []
        
        # Load checkpoint
        self.checkpoint = self.load_checkpoint()
        self.processed_ids: Set[str] = set(self.checkpoint.get("completed_conversations", []))
        
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
        """Persist checkpoint to disk with I/O timing."""
        start_time = time.time()
        
        self.checkpoint["completed_conversations"] = list(self.processed_ids)
        self.checkpoint["extraction_stats"] = {
            "decisions": self.decisions_added,
            "patterns": self.patterns_added,
            "failures": self.failures_added,
            "total_nodes_created": self.decisions_added + self.patterns_added + self.failures_added,
            "success_rate": (self.decisions_added + self.patterns_added + self.failures_added) / self.total_processed if self.total_processed > 0 else 0.0,
            "timestamp": datetime.now().isoformat(),
            "fallback_count": self.fallback_count,
            "checkpoints_saved": self.checkpoints_saved
        }
        
        with open(self.checkpoint_file, 'w') as f:
            json.dump(self.checkpoint, f, indent=2)
        
        io_time = time.time() - start_time
        self.checkpoint_io_times.append(io_time)
        self.checkpoints_saved += 1
    
    async def search_all_conversations(self) -> List[Dict]:
        """Gather ALL conversations using broad search queries."""
        print("\n📡 Gathering ALL conversations from Agent Genesis corpus...")
        
        # Use broad search terms that will match most conversations
        # Phase 1: Core technical topics (original 20)
        phase1_queries = [
            "code implementation",
            "technical discussion",
            "architecture design",
            "debugging",
            "testing",
            "deployment",
            "configuration",
            "integration",
            "optimization",
            "refactoring",
            "error handling",
            "database",
            "API",
            "frontend",
            "backend",
            "infrastructure",
            "security",
            "performance",
            "documentation",
            "workflow"
        ]

        # Phase 2: Additional queries to capture missing conversations
        phase2_queries = [
            "implementation",
            "system design",
            "code",
            "project",
            "analysis",
            "solution",
            "problem",
            "development",
            "feature",
            "module",
            "component",
            "class",
            "function",
            "service",
            "library",
            "framework",
            "tool",
            "setup",
            "installation",
            "configuration"
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
                        json={"query": query, "n_results": 2000}  # High limit to get comprehensive coverage
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
                    
                    # Small delay to avoid overwhelming the API
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                print(f"  ❌ Query '{query}' failed: {e}")
                continue
        
        print(f"\n✅ Total unique conversations gathered: {len(all_conversations):,}")
        return all_conversations
    
    async def extract_with_mkg_base(self, conversation: Dict) -> Optional[Dict]:
        """Base MKG extraction without timeout wrapper."""
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
                        "model": "qwen2.5-coder-14b-awq",
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
    
    async def extract_with_mkg(self, conversation: Dict) -> Optional[Dict]:
        """Extract with timeout and circuit breaker, fallback to keywords."""
        # Circuit breaker check - use keyword fallback immediately
        if self.timeout_counter >= self.MAX_TIMEOUTS:
            self.fallback_count += 1
            return self.keyword_extractor.extract_from_text(conversation.get('content', ''))
        
        try:
            async with self.semaphore:
                result = await asyncio.wait_for(
                    self.extract_with_mkg_base(conversation),
                    timeout=self.TIMEOUT_THRESHOLD
                )
                # Circuit breaker recovery: reset after consecutive successes
                self.consecutive_successes += 1
                if self.consecutive_successes >= self.CB_RESET_SUCCESS_COUNT:
                    self.timeout_counter = 0  # Full reset after proven stability
                    self.consecutive_successes = 0
                return result
        except asyncio.TimeoutError:
            self.timeout_counter += 1
            self.consecutive_successes = 0  # Reset success counter on timeout
            if self.timeout_counter >= self.MAX_TIMEOUTS:
                print(f"\n⚠️  Circuit breaker tripped: {self.timeout_counter} consecutive timeouts - using keyword fallback")
            # Fallback to keyword extraction on timeout
            self.fallback_count += 1
            self.keyword_extractor.fallback_extractions += 1
            return self.keyword_extractor.extract_from_text(conversation.get('content', ''))
        except Exception:
            self.timeout_counter = max(0, self.timeout_counter - 1)
            self.consecutive_successes = 0  # Reset success counter on exception
            # Fallback on exception
            self.fallback_count += 1
            return self.keyword_extractor.extract_from_text(conversation.get('content', ''))
    
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
            # Add to knowledge base based on type using GraphitiClient
            if extracted['type'] == 'decision':
                decision = Decision(
                    id=str(uuid.uuid4()),
                    description=extracted.get('description', '')[:200],
                    rationale=extracted.get('rationale', '')[:500],
                    alternatives=extracted.get('alternatives', [])[:5],
                    related_to=[]
                )
                node_id = self.graphiti_client.add_node(decision)
                self.decisions_added += 1
                
            elif extracted['type'] == 'pattern':
                pattern = Pattern(
                    id=str(uuid.uuid4()),
                    name=extracted.get('name', '')[:100],
                    context=extracted.get('context', '')[:200],
                    implementation=extracted.get('implementation', '')[:1000],
                    use_cases=[extracted.get('context', '')[:200]]
                )
                node_id = self.graphiti_client.add_node(pattern)
                self.patterns_added += 1
                
            elif extracted['type'] == 'failure':
                failure = SystematicFailure(
                    id=str(uuid.uuid4()),
                    attempt=extracted.get('attempt', '')[:200],
                    reason_failed=extracted.get('reason', '')[:500],
                    lesson_learned=extracted.get('lesson', '')[:500],
                    alternative_solution=""
                )
                node_id = self.graphiti_client.add_node(failure)
                self.failures_added += 1
            
            self.processed_ids.add(conv_id)
            return True
            
        except Exception as e:
            self.errors += 1
            self.processed_ids.add(conv_id)  # Mark as processed even on error to avoid retry loops
            return False
    
    async def run_comprehensive_extraction(self):
        """Execute comprehensive extraction."""
        print("\n" + "="*70)
        print("🚀 COMPREHENSIVE AGENT GENESIS EXTRACTION")
        print("="*70)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Batch Size: {self.batch_size}")
        print(f"Already processed: {len(self.processed_ids):,} conversations")
        
        # Gather all conversations
        start_gather = time.time()
        all_conversations = await self.search_all_conversations()
        gather_time = time.time() - start_gather
        print(f"\n⏱️  Gathering took: {gather_time:.1f}s")
        
        if not all_conversations:
            print("\n⚠️  No new conversations to process!")
            return
        
        # Process in batches
        start_process = time.time()
        total_batches = (len(all_conversations) + self.batch_size - 1) // self.batch_size
        
        print(f"\n📦 Processing {len(all_conversations):,} conversations in {total_batches} batches...\n")
        
        for i in range(0, len(all_conversations), self.batch_size):
            if self.shutdown_requested:
                print("\n⚠️  Shutdown requested. Saving progress...")
                self.save_checkpoint()
                break
            
            batch = all_conversations[i:i+self.batch_size]
            batch_num = i // self.batch_size + 1
            
            batch_start = time.time()
            self.batch_start_time = batch_start
            
            # Process batch in parallel with semaphore-controlled concurrency
            tasks = [self.process_conversation(conv) for conv in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successes and handle exceptions
            for result in results:
                if isinstance(result, Exception):
                    self.errors += 1
                    print(f"\n⚠️  Task exception: {result}")
                self.total_processed += 1
            
            batch_time = time.time() - batch_start
            
            # Optimized checkpoint - save every N batches, on final batch, or on shutdown
            should_save = (
                batch_num % self.checkpoint_interval == 0 or
                batch_num == total_batches or
                self.shutdown_requested
            )
            
            if should_save and batch_num > self.last_checkpoint_batch:
                self.save_checkpoint()
                self.last_checkpoint_batch = batch_num
            
            # Progress display with throughput metrics
            dashboard_start = time.time()
            
            total_nodes = self.decisions_added + self.patterns_added + self.failures_added
            success_rate = (total_nodes / self.total_processed) if self.total_processed > 0 else 0.0
            
            # Calculate rates with rolling average
            elapsed = time.time() - start_process
            rate = (self.total_processed / elapsed) * 60 if elapsed > 0 else 0  # convos/min
            batch_rate = (len(batch) / batch_time) if batch_time > 0 else 0  # convos/sec
            
            # Track batch rate for rolling average
            self.batch_rates.append(batch_rate)
            rolling_avg_rate = sum(self.batch_rates) / len(self.batch_rates) if self.batch_rates else 0
            
            # Use rolling average for ETA calculation (more stable)
            remaining = len(all_conversations) - self.total_processed
            eta_seconds = (remaining / rolling_avg_rate) if rolling_avg_rate > 0 else 0
            eta_minutes = eta_seconds / 60
            
            # Node type breakdown for display
            node_breakdown = f"D:{self.decisions_added} P:{self.patterns_added} F:{self.failures_added}"
            
            # Circuit breaker indicator
            cb_indicator = " ⚡CB" if self.timeout_counter >= self.MAX_TIMEOUTS else ""
            
            progress_pct = (self.total_processed / len(all_conversations)) * 100
            bar_width = 30
            filled = int(bar_width * progress_pct / 100)
            bar = "█" * filled + "░" * (bar_width - filled)
            
            print(f"\r[{bar}] {progress_pct:.1f}% │ "
                  f"Batch {batch_num}/{total_batches} │ "
                  f"{node_breakdown} ({success_rate:.1%}) │ "
                  f"Speed: {rolling_avg_rate:.1f}/s │ ETA: {eta_minutes:.0f}m{cb_indicator}",
                  end="", flush=True)
            
            # Track dashboard overhead
            dashboard_time = time.time() - dashboard_start
            self.dashboard_update_times.append(dashboard_time)
            if dashboard_time > 0.01:  # Warn if >10ms
                print(f"\n⚠️  Dashboard slow: {dashboard_time*1000:.1f}ms")
            
            # Detailed progress every 10 batches
            if batch_num % 10 == 0:
                fallback_rate = (self.fallback_count / self.total_processed * 100) if self.total_processed > 0 else 0
                print(f"\n  ├─ Decisions: {self.decisions_added} │ Patterns: {self.patterns_added} │ Failures: {self.failures_added}")
                print(f"  ├─ Fallback: {self.fallback_count} ({fallback_rate:.1f}%) │ Cache hits: {self.keyword_extractor.cache_hits}")
                print(f"  └─ Skipped: {self.skipped} │ Errors: {self.errors} │ Batch time: {batch_time:.1f}s\n")
        
        # Final summary
        print("\n")
        elapsed = time.time() - start_process
        total_nodes = self.decisions_added + self.patterns_added + self.failures_added
        success_rate = (total_nodes / self.total_processed) if self.total_processed > 0 else 0.0
        
        print("\n" + "="*70)
        print("✅ COMPREHENSIVE EXTRACTION COMPLETE")
        print("="*70)
        print(f"\nResults:")
        print(f"  Conversations processed: {self.total_processed:,}")
        print(f"  Decisions: {self.decisions_added:,}")
        print(f"  Patterns: {self.patterns_added:,}")
        print(f"  Failures: {self.failures_added:,}")
        print(f"  Total nodes extracted: {total_nodes:,}")
        print(f"  Success rate: {success_rate:.1%}")
        print(f"  Skipped: {self.skipped:,}")
        print(f"  Errors: {self.errors}")
        print(f"\nPerformance:")
        print(f"  Processing time: {elapsed/3600:.2f} hours")
        print(f"  Average per conversation: {elapsed/self.total_processed:.2f}s")
        print(f"  Throughput: {self.total_processed/elapsed*60:.1f} conversations/minute")
        
        print(f"\nOptimizations:")
        print(f"  Fallback extractions: {self.fallback_count} ({self.fallback_count/self.total_processed*100:.1f}%)")
        print(f"  Cache hits: {self.keyword_extractor.cache_hits}")
        print(f"  Checkpoints saved: {self.checkpoints_saved} (every {self.checkpoint_interval} batches)")
        if self.checkpoint_io_times:
            avg_io = sum(self.checkpoint_io_times) / len(self.checkpoint_io_times)
            total_io = sum(self.checkpoint_io_times)
            print(f"  Checkpoint I/O: avg {avg_io:.3f}s, total {total_io:.1f}s")
        if self.dashboard_update_times:
            avg_dashboard = sum(self.dashboard_update_times) / len(self.dashboard_update_times)
            max_dashboard = max(self.dashboard_update_times)
            print(f"  Dashboard overhead: avg {avg_dashboard*1000:.1f}ms, max {max_dashboard*1000:.1f}ms")
        print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Checkpoint: {self.checkpoint_file}")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Comprehensive Agent Genesis extraction"
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Conversations per batch (default: 100)'
    )
    
    args = parser.parse_args()
    
    extractor = ComprehensiveExtractor(batch_size=args.batch_size)
    await extractor.run_comprehensive_extraction()


if __name__ == "__main__":
    asyncio.run(main())
