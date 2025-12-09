#!/usr/bin/env python3
"""
Direct JSONL extraction - reads full conversations from Claude Code storage.
Bypasses vector search to get complete conversation content.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Iterator
import uuid
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.graphiti_client import GraphitiClient
from pydantic import BaseModel
from typing import List, Optional

# Pydantic models
class Pattern(BaseModel):
    id: Optional[str] = None
    type: str = "Pattern"
    name: str
    context: str
    implementation: str
    use_cases: List[str]

class Decision(BaseModel):
    id: Optional[str] = None
    type: str = "Decision"
    description: str
    rationale: str
    alternatives: List[str]
    related_to: List[str]

class SystematicFailure(BaseModel):
    id: Optional[str] = None
    type: str = "SystematicFailure"
    attempt: str
    reason_failed: str
    lesson_learned: str
    alternative_solution: str


def find_all_jsonl_files(base_path: str = "~/.claude/projects") -> List[Path]:
    """Find all JSONL conversation files."""
    base = Path(base_path).expanduser()
    return list(base.rglob("*.jsonl"))


def read_conversation(jsonl_file: Path) -> Iterator[Dict]:
    """Read messages from a JSONL conversation file."""
    try:
        with open(jsonl_file, 'r') as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)
    except Exception as e:
        print(f"⚠️  Error reading {jsonl_file.name}: {e}")


def extract_knowledge(messages: List[Dict]) -> List[Pattern]:
    """Extract patterns from conversation messages using simple heuristics."""
    patterns = []

    for msg in messages:
        role = msg.get('role', '')
        content = msg.get('content', '')

        if role != 'assistant' or len(content) < 100:
            continue

        # Extract as generic pattern if message is substantial
        if len(content) > 100:
            # Use first 80 chars as name
            name = content[:80].strip()
            if len(name) > 70:
                name = name[:70] + "..."

            patterns.append(Pattern(
                id=str(uuid.uuid4()),
                name=name,
                context=f"Conversation from {msg.get('timestamp', 'unknown')}",
                implementation=content[:1000],  # First 1000 chars
                use_cases=[]
            ))

    return patterns


def main():
    print("=" * 70)
    print("🚀 DIRECT JSONL EXTRACTION")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Initialize
    graphiti_client = GraphitiClient()

    # Find all JSONL files
    print("📁 Scanning for JSONL conversation files...")
    jsonl_files = find_all_jsonl_files()
    print(f"✅ Found {len(jsonl_files):,} conversation files\n")

    # Process files
    total_patterns = 0
    total_conversations = 0
    errors = 0

    print("📦 Processing conversations...\n")

    for i, jsonl_file in enumerate(jsonl_files, 1):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(jsonl_files)} files | Patterns: {total_patterns:,} | Errors: {errors}")

        try:
            # Read all messages from conversation
            messages = list(read_conversation(jsonl_file))

            if not messages:
                continue

            total_conversations += 1

            # Extract knowledge
            patterns = extract_knowledge(messages)

            # Add to database
            for pattern in patterns:
                try:
                    graphiti_client.add_node(pattern)
                    total_patterns += 1
                except Exception as e:
                    errors += 1
                    if errors <= 10:  # Show first 10 errors
                        print(f"    ⚠️  Failed to add pattern: {str(e)[:100]}")

        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"    ❌ Error processing {jsonl_file.name}: {e}")

    print("\n" + "=" * 70)
    print("✅ EXTRACTION COMPLETE")
    print("=" * 70)
    print(f"\nResults:")
    print(f"  Conversations processed: {total_conversations:,}")
    print(f"  Patterns extracted: {total_patterns:,}")
    print(f"  Errors: {errors}")
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
