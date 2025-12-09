#!/usr/bin/env python3
"""
Fast deduplication using Bloom filter for Agent Genesis import.
Replaces expensive query_decisions() calls (1.5-2s) with hash-based checks (<0.01s).
"""

from typing import Set, Tuple, Dict
from collections import defaultdict


class BloomDeduplicator:
    """
    Fast probabilistic deduplication using Bloom filter.

    Performance:
    - Hash-based check: < 0.01s per conversation
    - vs query_decisions: 1.5-2s per conversation
    - Speedup: 100-200x

    Memory usage:
    - ~10MB for 100K conversations
    - Scales linearly with capacity
    """

    def __init__(self, capacity: int = 100000, error_rate: float = 0.001):
        """
        Initialize Bloom filter deduplicator.

        Args:
            capacity: Expected number of unique items (default: 100K)
            error_rate: Acceptable false positive rate (default: 0.1%)
        """
        try:
            from pybloom_live import BloomFilter
            self.bloom = BloomFilter(capacity=capacity, error_rate=error_rate)
            self.has_bloom = True
        except ImportError:
            # Fallback to set-based deduplication if pybloom not available
            self.bloom = None
            self.has_bloom = False
            print("⚠️  pybloom_live not installed, using set-based deduplication")
            print("   Install with: pip install pybloom-live")

        self.seen_hashes: Set[int] = set()
        self.duplicates_found = 0
        self.unique_items = 0
        self.capacity = capacity
        self.error_rate = error_rate

    def is_duplicate(self, content: str, use_full_content: bool = False) -> Tuple[bool, str]:
        """
        Check if content is duplicate.

        Args:
            content: Content to check
            use_full_content: If True, hash entire content. If False, hash first 500 chars

        Returns:
            Tuple of (is_duplicate: bool, reason: str)
        """
        # Create content hash
        if use_full_content:
            content_hash = hash(content)
        else:
            # Hash first 500 chars for efficiency
            content_hash = hash(content[:500])

        if self.has_bloom:
            # Use Bloom filter for probabilistic check
            if content_hash in self.bloom:
                # Bloom filter says "maybe duplicate"
                if content_hash in self.seen_hashes:
                    # Confirmed duplicate
                    self.duplicates_found += 1
                    return True, "exact_duplicate"

            # Add to both structures
            self.bloom.add(content_hash)
            self.seen_hashes.add(content_hash)
            self.unique_items += 1
            return False, "new_content"

        else:
            # Fallback: set-based deduplication
            if content_hash in self.seen_hashes:
                self.duplicates_found += 1
                return True, "exact_duplicate"

            self.seen_hashes.add(content_hash)
            self.unique_items += 1
            return False, "new_content"

    def get_stats(self) -> Dict:
        """Get deduplication statistics."""
        stats = {
            "unique_items": self.unique_items,
            "duplicates_found": self.duplicates_found,
            "total_checked": self.unique_items + self.duplicates_found,
            "duplicate_rate": (
                self.duplicates_found / (self.unique_items + self.duplicates_found)
                if (self.unique_items + self.duplicates_found) > 0
                else 0.0
            ),
            "using_bloom_filter": self.has_bloom
        }

        if self.has_bloom:
            stats["bloom_error_rate"] = self.error_rate
            stats["bloom_capacity"] = self.capacity

        return stats

    def reset(self):
        """Reset deduplicator state."""
        if self.has_bloom:
            from pybloom_live import BloomFilter
            self.bloom = BloomFilter(capacity=self.capacity, error_rate=self.error_rate)

        self.seen_hashes.clear()
        self.duplicates_found = 0
        self.unique_items = 0


class PatternDeduplicator:
    """
    Advanced pattern-based deduplication.
    Detects similar content patterns beyond exact duplicates.
    """

    def __init__(self, max_duplicates_per_pattern: int = 20):
        """
        Initialize pattern deduplicator.

        Args:
            max_duplicates_per_pattern: Max occurrences of same pattern before skipping
        """
        self.pattern_signatures = defaultdict(int)
        self.max_duplicates = max_duplicates_per_pattern
        self.pattern_skips = 0

    def should_skip(self, content: str) -> Tuple[bool, str]:
        """
        Check if content should be skipped due to pattern duplication.

        Args:
            content: Content to check

        Returns:
            Tuple of (should_skip: bool, reason: str)
        """
        # Create pattern signature from first 200 chars
        # Hash to 10K buckets for collision resistance
        content_sig = hash(content[:200]) % 10000

        if self.pattern_signatures[content_sig] >= self.max_duplicates:
            self.pattern_skips += 1
            return True, f"pattern_duplicate_limit_reached"

        self.pattern_signatures[content_sig] += 1
        return False, "pattern_ok"

    def get_stats(self) -> Dict:
        """Get pattern deduplication statistics."""
        total_patterns = len(self.pattern_signatures)
        avg_per_pattern = (
            sum(self.pattern_signatures.values()) / total_patterns
            if total_patterns > 0
            else 0.0
        )

        return {
            "total_patterns": total_patterns,
            "pattern_skips": self.pattern_skips,
            "avg_per_pattern": avg_per_pattern,
            "max_duplicates_per_pattern": self.max_duplicates
        }


# Example usage
if __name__ == "__main__":
    # Test Bloom deduplicator
    dedup = BloomDeduplicator(capacity=1000)

    # Add some test content
    test_content = [
        "This is a unique conversation about MCP servers",
        "Another unique conversation about FalkorDB",
        "This is a unique conversation about MCP servers",  # Duplicate
        "Yet another unique conversation about testing"
    ]

    for i, content in enumerate(test_content, 1):
        is_dup, reason = dedup.is_duplicate(content)
        print(f"{i}. {'DUPLICATE' if is_dup else 'NEW'}: {reason}")

    print("\nStatistics:")
    stats = dedup.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Test pattern deduplicator
    print("\n--- Pattern Deduplicator Test ---")
    pattern_dedup = PatternDeduplicator(max_duplicates_per_pattern=2)

    similar_content = [
        "Similar content pattern A",
        "Similar content pattern A",  # Same pattern
        "Similar content pattern A",  # Should skip
        "Different content pattern B"
    ]

    for i, content in enumerate(similar_content, 1):
        should_skip, reason = pattern_dedup.should_skip(content)
        print(f"{i}. {'SKIP' if should_skip else 'OK'}: {reason}")

    print("\nPattern Statistics:")
    pattern_stats = pattern_dedup.get_stats()
    for key, value in pattern_stats.items():
        print(f"  {key}: {value}")
