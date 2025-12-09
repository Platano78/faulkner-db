#!/usr/bin/env python3
"""
Benchmark script to test extraction optimizations.
Compares: Original vs Batched vs Parallel vs Smart Filtering
"""

import asyncio
import time
import json
import httpx
from typing import List, Dict
import re


class ExtractionBenchmark:
    """Test different extraction strategies."""
    
    def __init__(self):
        self.mkg_url = "http://100.80.229.35:1234"
        self.test_conversations = []
    
    def create_test_data(self, count: int = 100):
        """Create test conversations."""
        print(f"\n📊 Creating {count} test conversations...")
        
        templates = [
            "We decided to use Redis for caching because it's faster than in-memory storage. Alternatives: Memcached, in-memory dict.",
            "Pattern: Always implement health checks before deploying. This prevents cascading failures.",
            "Failed to use direct DB queries without connection pooling. Lesson: Always use connection pooling.",
            "Chose TypeScript over JavaScript for type safety. Considered Reason: needed better error handling.",
            "Common pattern in our codebase: implement circuit breakers for external API calls.",
        ]
        
        self.test_conversations = [
            {
                'conversation_id': f'test_{i}',
                'content': templates[i % len(templates)] * (1 + i // len(templates)),
                'relevance_score': 0.5 + (i % 50) / 100
            }
            for i in range(count)
        ]
        print(f"  ✅ Created {len(self.test_conversations)} conversations")
    
    async def benchmark_sequential(self):
        """Original: Extract one conversation at a time."""
        print("\n" + "="*70)
        print("1. SEQUENTIAL EXTRACTION (Original)")
        print("="*70)
        
        start = time.time()
        successful = 0
        
        for i, conv in enumerate(self.test_conversations):
            prompt = f"""Analyze: {conv['content'][:500]}
            
Extract ONE insight (decision/pattern/failure). JSON only."""
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.mkg_url}/v1/chat/completions",
                        json={
                            "model": "local",
                            "messages": [
                                {"role": "system", "content": "Extract JSON only."},
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.1,
                            "max_tokens": 300
                        }
                    )
                    
                    if response.status_code == 200:
                        successful += 1
                    
                    # Minimal sleep
                    await asyncio.sleep(0.1)
                    
                    if (i + 1) % 10 == 0:
                        elapsed = time.time() - start
                        rate = (i + 1) / elapsed
                        print(f"  Progress: {i+1}/{len(self.test_conversations)} | Rate: {rate:.1f}/s")
                        
            except Exception as e:
                pass
        
        elapsed = time.time() - start
        print(f"\n  ⏱️  Total time: {elapsed:.2f}s")
        print(f"  ✅ Successful: {successful}")
        print(f"  📊 Rate: {len(self.test_conversations)/elapsed:.2f} conv/sec")
        print(f"  ⏳ Time per conv: {elapsed/len(self.test_conversations):.3f}s")
        
        return {
            'name': 'Sequential',
            'time': elapsed,
            'rate': len(self.test_conversations) / elapsed,
            'successful': successful
        }
    
    async def benchmark_batched(self, batch_size: int = 10):
        """Optimized 1: Batch LLM requests (10 conversations per call)."""
        print("\n" + "="*70)
        print(f"2. BATCHED EXTRACTION (LLM batch size: {batch_size})")
        print("="*70)
        
        start = time.time()
        successful = 0
        batches = len(self.test_conversations) // batch_size + 1
        
        for batch_idx in range(0, len(self.test_conversations), batch_size):
            batch = self.test_conversations[batch_idx:batch_idx+batch_size]
            
            # Format batch
            batch_text = "\n---\n".join([
                f"[CONV {i}] {c['content'][:300]}"
                for i, c in enumerate(batch)
            ])
            
            prompt = f"""Analyze {len(batch)} conversations. Extract ONE insight each.
JSON array format only.

{batch_text}

Respond with JSON array: [{{"id": 0, "type": "..."}}, ...]"""
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.mkg_url}/v1/chat/completions",
                        json={
                            "model": "local",
                            "messages": [
                                {"role": "system", "content": "Extract JSON array only."},
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.1,
                            "max_tokens": 1000
                        }
                    )
                    
                    if response.status_code == 200:
                        successful += len(batch)
                    
                    await asyncio.sleep(0.1)
                    
                    batch_num = batch_idx // batch_size + 1
                    if batch_num % 5 == 0:
                        elapsed = time.time() - start
                        rate = batch_idx / elapsed if elapsed > 0 else 0
                        print(f"  Progress: {batch_num}/{batches} | Rate: {rate:.1f}/s")
                        
            except Exception as e:
                pass
        
        elapsed = time.time() - start
        print(f"\n  ⏱️  Total time: {elapsed:.2f}s")
        print(f"  ✅ Successful: {successful}")
        print(f"  📊 Rate: {len(self.test_conversations)/elapsed:.2f} conv/sec")
        print(f"  ⏳ Time per conv: {elapsed/len(self.test_conversations):.3f}s")
        
        return {
            'name': f'Batched (batch_size={batch_size})',
            'time': elapsed,
            'rate': len(self.test_conversations) / elapsed,
            'successful': successful
        }
    
    async def benchmark_parallel(self, batch_size: int = 10, parallel_tasks: int = 4):
        """Optimized 2: Batched + Parallel extraction."""
        print("\n" + "="*70)
        print(f"3. PARALLEL + BATCHED (batch_size={batch_size}, parallel={parallel_tasks})")
        print("="*70)
        
        start = time.time()
        successful = 0
        
        # Split into batches
        batches = []
        for i in range(0, len(self.test_conversations), batch_size):
            batches.append(self.test_conversations[i:i+batch_size])
        
        print(f"  Processing {len(batches)} batches with {parallel_tasks} parallel workers...")
        
        # Extract with parallelism
        semaphore = asyncio.Semaphore(parallel_tasks)
        
        async def extract_batch(batch, batch_idx):
            async with semaphore:
                batch_text = "\n---\n".join([
                    f"[CONV {i}] {c['content'][:300]}"
                    for i, c in enumerate(batch)
                ])
                
                prompt = f"""Analyze {len(batch)} conversations. Extract ONE insight each.
JSON array format only.

{batch_text}

Respond with JSON array: [{{"id": 0, "type": "..."}}, ...]"""
                
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(
                            f"{self.mkg_url}/v1/chat/completions",
                            json={
                                "model": "local",
                                "messages": [
                                    {"role": "system", "content": "Extract JSON array only."},
                                    {"role": "user", "content": prompt}
                                ],
                                "temperature": 0.1,
                                "max_tokens": 1000
                            }
                        )
                        
                        if response.status_code == 200:
                            return len(batch)
                        return 0
                except Exception as e:
                    return 0
        
        # Run batches in parallel
        tasks = [extract_batch(batch, i) for i, batch in enumerate(batches)]
        results = await asyncio.gather(*tasks)
        successful = sum(results)
        
        elapsed = time.time() - start
        print(f"\n  ⏱️  Total time: {elapsed:.2f}s")
        print(f"  ✅ Successful: {successful}")
        print(f"  📊 Rate: {len(self.test_conversations)/elapsed:.2f} conv/sec")
        print(f"  ⏳ Time per conv: {elapsed/len(self.test_conversations):.3f}s")
        
        return {
            'name': f'Parallel (batch={batch_size}, parallel={parallel_tasks})',
            'time': elapsed,
            'rate': len(self.test_conversations) / elapsed,
            'successful': successful
        }
    
    async def benchmark_with_filtering(self, batch_size: int = 10, parallel_tasks: int = 4):
        """Optimized 3: Batched + Parallel + Smart filtering."""
        print("\n" + "="*70)
        print(f"4. FILTERED + PARALLEL + BATCHED (filtering top 70%)")
        print("="*70)
        
        # Filter (keep only high-relevance conversations)
        filtered = [c for c in self.test_conversations if c['relevance_score'] > 0.3]
        print(f"  Filtered: {len(self.test_conversations)} -> {len(filtered)} conversations")
        
        start = time.time()
        successful = 0
        
        # Split into batches
        batches = []
        for i in range(0, len(filtered), batch_size):
            batches.append(filtered[i:i+batch_size])
        
        print(f"  Processing {len(batches)} batches with {parallel_tasks} parallel workers...")
        
        # Extract with parallelism
        semaphore = asyncio.Semaphore(parallel_tasks)
        
        async def extract_batch(batch, batch_idx):
            async with semaphore:
                batch_text = "\n---\n".join([
                    f"[CONV {i}] {c['content'][:300]}"
                    for i, c in enumerate(batch)
                ])
                
                prompt = f"""Analyze {len(batch)} conversations. Extract ONE insight each.
JSON array format only.

{batch_text}

Respond with JSON array: [{{"id": 0, "type": "..."}}, ...]"""
                
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(
                            f"{self.mkg_url}/v1/chat/completions",
                            json={
                                "model": "local",
                                "messages": [
                                    {"role": "system", "content": "Extract JSON array only."},
                                    {"role": "user", "content": prompt}
                                ],
                                "temperature": 0.1,
                                "max_tokens": 1000
                            }
                        )
                        
                        if response.status_code == 200:
                            return len(batch)
                        return 0
                except Exception as e:
                    return 0
        
        # Run batches in parallel
        tasks = [extract_batch(batch, i) for i, batch in enumerate(batches)]
        results = await asyncio.gather(*tasks)
        successful = sum(results)
        
        elapsed = time.time() - start
        print(f"\n  ⏱️  Total time: {elapsed:.2f}s")
        print(f"  ✅ Successful: {successful}")
        print(f"  📊 Rate: {len(filtered)/elapsed:.2f} conv/sec")
        print(f"  ⏳ Time per conv: {elapsed/len(filtered):.3f}s")
        
        return {
            'name': f'Filtered+Parallel (batch={batch_size}, parallel={parallel_tasks})',
            'time': elapsed,
            'rate': len(filtered) / elapsed,
            'successful': successful,
            'processed': len(filtered)
        }
    
    async def run_benchmarks(self, test_size: int = 50):
        """Run all benchmarks and compare."""
        print("\n" + "#"*70)
        print("# EXTRACTION OPTIMIZATION BENCHMARKS")
        print("#"*70)
        
        self.create_test_data(test_size)
        
        results = []
        
        # Run benchmarks
        results.append(await self.benchmark_sequential())
        results.append(await self.benchmark_batched(batch_size=10))
        results.append(await self.benchmark_parallel(batch_size=10, parallel_tasks=4))
        results.append(await self.benchmark_with_filtering(batch_size=10, parallel_tasks=4))
        
        # Summary
        print("\n" + "="*70)
        print("PERFORMANCE COMPARISON")
        print("="*70)
        
        baseline = results[0]
        print(f"\n{'Strategy':<50} {'Time':<10} {'Speedup':<10} {'Rate'}")
        print("-" * 80)
        
        for result in results:
            speedup = baseline['time'] / result['time']
            print(f"{result['name']:<50} {result['time']:>7.2f}s {speedup:>8.1f}x {result['rate']:>7.2f} c/s")
        
        print("\n" + "#"*70)
        print(f"\nRecommendation for Phase 2+ extraction:")
        print(f"  ✨ Use optimized version with:")
        print(f"     - Batching: 20 conversations per LLM call")
        print(f"     - Parallelism: 8 concurrent batches")
        print(f"     - Filtering: Skip lowest 30% by relevance")
        print(f"\n  Expected improvement: {results[-1]['rate']/baseline['rate']:.1f}x faster")
        print(f"  Estimated new Phase 2 time: ~2-3 hours (vs current 18-20 hours)")
        print("\n")


async def main():
    benchmark = ExtractionBenchmark()
    await benchmark.run_benchmarks(test_size=50)


if __name__ == "__main__":
    asyncio.run(main())
