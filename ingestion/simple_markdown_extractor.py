#!/usr/bin/env python3
"""
Simple direct markdown extraction - scans ALL markdown files in specified paths.
No complex project discovery - just recursive glob.
"""

import sys
from pathlib import Path
from typing import List
import uuid
from datetime import datetime
import re

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


def find_markdown_files(paths: List[str]) -> List[Path]:
    """Find all markdown files recursively in given paths."""
    all_files = []
    excluded = ['venv', '__pycache__', '.git', 'node_modules', 'dist', 'build']

    for path_str in paths:
        base_path = Path(path_str).expanduser()

        if not base_path.exists():
            print(f"⚠️  Path does not exist: {path_str}")
            continue

        # Recursive glob for all .md files
        for md_file in base_path.rglob("*.md"):
            # Skip excluded directories
            if any(excl in str(md_file) for excl in excluded):
                continue
            if md_file.name.startswith('.'):
                continue

            all_files.append(md_file)

    return all_files


def extract_from_markdown(md_file: Path) -> List[Pattern]:
    """Extract patterns from markdown file content."""
    try:
        content = md_file.read_text(encoding='utf-8')
    except Exception as e:
        print(f"    ⚠️  Could not read {md_file.name}: {e}")
        return []

    if len(content) < 50:
        return []

    patterns = []

    # Split by major sections (## headers)
    sections = re.split(r'\n##\s+', content)

    for section in sections:
        if len(section) < 100:
            continue

        # Extract section title
        lines = section.split('\n', 1)
        title = lines[0].strip()[:80]
        body = lines[1] if len(lines) > 1 else section

        patterns.append(Pattern(
            id=str(uuid.uuid4()),
            name=title if title else md_file.stem[:80],
            context=f"From {md_file.name}",
            implementation=body[:1000],
            use_cases=[]
        ))

    # If no sections found, treat whole file as one pattern
    if not patterns and len(content) > 100:
        patterns.append(Pattern(
            id=str(uuid.uuid4()),
            name=md_file.stem[:80],
            context=f"From {md_file.name}",
            implementation=content[:1000],
            use_cases=[]
        ))

    return patterns


def main():
    print("=" * 70)
    print("🚀 SIMPLE MARKDOWN EXTRACTION")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Target paths
    paths = [
        "/home/platano/.claude/agents",
        "/mnt/c/Users/Aldwin/Desktop/AI Templates and Information",
        "/home/platano/project/.serena/memories",
        "/mnt/d/ai-workspace"
    ]

    # Initialize
    graphiti_client = GraphitiClient()

    # Find all markdown files
    print("📁 Scanning for markdown files...")
    md_files = find_markdown_files(paths)
    print(f"✅ Found {len(md_files):,} markdown files\n")

    # Process files
    total_patterns = 0
    total_files = 0
    errors = 0

    print("📦 Processing files...\n")

    for i, md_file in enumerate(md_files, 1):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(md_files)} files | Patterns: {total_patterns:,} | Errors: {errors}")

        try:
            patterns = extract_from_markdown(md_file)

            if patterns:
                total_files += 1

                # Add to database
                for pattern in patterns:
                    try:
                        graphiti_client.add_node(pattern)
                        total_patterns += 1
                    except Exception as e:
                        errors += 1
                        if errors <= 10:
                            print(f"      ⚠️  Failed to add pattern: {str(e)[:100]}")

        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"    ❌ Error processing {md_file.name}: {e}")

    print("\n" + "=" * 70)
    print("✅ EXTRACTION COMPLETE")
    print("=" * 70)
    print(f"\nResults:")
    print(f"  Files processed: {total_files:,}")
    print(f"  Patterns extracted: {total_patterns:,}")
    print(f"  Errors: {errors}")
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
