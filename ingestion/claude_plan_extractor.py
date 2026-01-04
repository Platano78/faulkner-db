#!/usr/bin/env python3
"""
Claude Plan Extractor - Extracts knowledge from Claude Code plan files.
Maps structured plan sections to faulkner-db node types with deduplication.
"""

import asyncio
import re
import sys
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.mcp_tools import add_decision, add_pattern, add_failure
from ingestion.file_tracker import FileTracker


class ClaudePlanExtractor:
    """Extract and ingest knowledge from Claude Code plan files"""

    # Section patterns in Claude plans
    SECTION_PATTERNS = {
        'problem': r'^#+\s*(problem\s*summary|problem|issue|challenge)',
        'root_cause': r'^#+\s*(root\s*cause|cause|reason)',
        'proposed_changes': r'^#+\s*(proposed\s*changes?|solution|approach|changes?)',
        'implementation': r'^#+\s*(implementation\s*steps?|steps|how\s*to|procedure)',
        'files_to_modify': r'^#+\s*(files?\s*to\s*modify|files?\s*changed?|affected\s*files?)',
        'expected_outcome': r'^#+\s*(expected\s*outcome|outcome|result|impact)',
        'rationale': r'^#+\s*(rationale|reasoning|why|justification)',
        'alternatives': r'^#+\s*(alternatives?|other\s*options?|considered)',
        'risks': r'^#+\s*(risks?|concerns?|caveats?|warnings?)',
        'dependencies': r'^#+\s*(dependencies|requirements|prerequisites)',
    }

    def __init__(self, tracker: FileTracker):
        self.tracker = tracker
        self.stats = {
            'files_processed': 0,
            'decisions_created': 0,
            'patterns_created': 0,
            'failures_created': 0,
            'duplicates_skipped': 0
        }

    def parse_plan_file(self, content: str) -> Dict[str, str]:
        """Parse a Claude plan file into sections"""
        sections = {}
        lines = content.split('\n')

        current_section = None
        current_content = []

        for line in lines:
            line_lower = line.lower().strip()

            # Check if this line is a section header
            matched_section = None
            for section_name, pattern in self.SECTION_PATTERNS.items():
                if re.match(pattern, line_lower, re.IGNORECASE):
                    matched_section = section_name
                    break

            if matched_section:
                # Save previous section
                if current_section and current_content:
                    text = '\n'.join(current_content).strip()
                    if text and len(text) > 20:
                        sections[current_section] = text

                current_section = matched_section
                current_content = []
            elif current_section:
                current_content.append(line)

        # Save last section
        if current_section and current_content:
            text = '\n'.join(current_content).strip()
            if text and len(text) > 20:
                sections[current_section] = text

        # Also extract title (first H1)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            sections['title'] = title_match.group(1).strip()

        return sections

    def extract_file_paths(self, content: str) -> List[str]:
        """Extract file paths mentioned in the plan"""
        paths = []

        # Common path patterns
        path_patterns = [
            r'`([/\w.-]+\.\w+)`',  # Backtick-wrapped paths
            r'\*\*File\*\*:\s*`?([/\w.-]+\.\w+)`?',  # **File**: path
            r'([/\w.-]+/[/\w.-]+\.\w+)',  # Unix-style paths
        ]

        for pattern in path_patterns:
            matches = re.findall(pattern, content)
            paths.extend(matches)

        # Deduplicate while preserving order
        seen = set()
        unique_paths = []
        for p in paths:
            if p not in seen and len(p) > 5:
                seen.add(p)
                unique_paths.append(p)

        return unique_paths[:20]  # Limit to 20 paths

    def compute_content_hash(self, text: str) -> str:
        """Compute hash for deduplication"""
        # Normalize whitespace for better deduplication
        normalized = ' '.join(text.split()).lower()
        return hashlib.md5(normalized.encode()).hexdigest()

    async def create_decision_from_plan(
        self,
        sections: Dict[str, str],
        source_file: str,
        file_id: int
    ) -> Optional[str]:
        """Create a decision node from plan sections"""

        # Build description from problem + title
        title = sections.get('title', 'Untitled Plan')
        problem = sections.get('problem', '')
        root_cause = sections.get('root_cause', '')

        description = f"{title}"
        if problem:
            description += f": {problem[:200]}"

        # Build rationale from root cause + proposed changes
        rationale_parts = []
        if root_cause:
            rationale_parts.append(f"Root Cause: {root_cause[:300]}")
        if sections.get('rationale'):
            rationale_parts.append(sections['rationale'][:300])
        if sections.get('proposed_changes'):
            rationale_parts.append(f"Solution: {sections['proposed_changes'][:300]}")

        rationale = '\n\n'.join(rationale_parts) if rationale_parts else description

        # Extract alternatives
        alternatives = []
        if sections.get('alternatives'):
            alt_text = sections['alternatives']
            # Try to extract bullet points
            alt_matches = re.findall(r'^[-*]\s+(.+)$', alt_text, re.MULTILINE)
            alternatives = [a[:100] for a in alt_matches[:5]]

        # Check for duplicate
        content_hash = self.compute_content_hash(description + rationale)
        existing = self.tracker.check_duplicate_content(content_hash, 'decision')

        if existing:
            self.stats['duplicates_skipped'] += 1
            # Update source files list
            self.tracker.register_content(content_hash, 'decision', existing['node_id'], source_file)
            return existing['node_id']

        try:
            result = await add_decision(
                description=description[:500],
                rationale=rationale[:1000],
                alternatives=alternatives,
                related_to=self.extract_file_paths(sections.get('files_to_modify', ''))[:5]
            )

            node_id = result.get('decision_id')
            if node_id:
                self.tracker.register_content(content_hash, 'decision', node_id, source_file)
                self.tracker.record_extraction(file_id, 'decision', node_id, content_hash)
                self.stats['decisions_created'] += 1

            return node_id

        except Exception as e:
            print(f"  Warning: Failed to create decision: {e}")
            return None

    async def create_pattern_from_plan(
        self,
        sections: Dict[str, str],
        source_file: str,
        file_id: int
    ) -> Optional[str]:
        """Create a pattern node from implementation details"""

        implementation = sections.get('implementation', '')
        proposed = sections.get('proposed_changes', '')

        if not implementation and not proposed:
            return None

        title = sections.get('title', 'Implementation Pattern')
        name = f"{title} - Implementation"

        # Context from problem/rationale
        context_parts = []
        if sections.get('problem'):
            context_parts.append(f"Problem: {sections['problem'][:200]}")
        if sections.get('rationale'):
            context_parts.append(sections['rationale'][:200])

        context = '\n'.join(context_parts) if context_parts else "See plan for context"

        # Implementation details
        impl_text = implementation if implementation else proposed

        # Extract use cases from expected outcome
        use_cases = []
        if sections.get('expected_outcome'):
            use_cases.append(sections['expected_outcome'][:150])

        # File paths as additional use cases
        file_paths = self.extract_file_paths(sections.get('files_to_modify', ''))
        use_cases.extend([f"Applies to: {p}" for p in file_paths[:3]])

        # Check for duplicate
        content_hash = self.compute_content_hash(name + impl_text)
        existing = self.tracker.check_duplicate_content(content_hash, 'pattern')

        if existing:
            self.stats['duplicates_skipped'] += 1
            self.tracker.register_content(content_hash, 'pattern', existing['node_id'], source_file)
            return existing['node_id']

        try:
            result = await add_pattern(
                name=name[:200],
                context=context[:500],
                implementation=impl_text[:2000],
                use_cases=use_cases[:5]
            )

            node_id = result.get('pattern_id')
            if node_id:
                self.tracker.register_content(content_hash, 'pattern', node_id, source_file)
                self.tracker.record_extraction(file_id, 'pattern', node_id, content_hash)
                self.stats['patterns_created'] += 1

            return node_id

        except Exception as e:
            print(f"  Warning: Failed to create pattern: {e}")
            return None

    async def create_failure_from_risks(
        self,
        sections: Dict[str, str],
        source_file: str,
        file_id: int
    ) -> Optional[str]:
        """Create failure nodes from risks/concerns sections"""

        risks = sections.get('risks', '')
        if not risks or len(risks) < 50:
            return None

        title = sections.get('title', 'Risk Assessment')

        # Parse risk items
        risk_items = re.findall(r'^[-*]\s+(.+)$', risks, re.MULTILINE)
        if not risk_items:
            risk_items = [risks[:300]]

        attempt = f"Planning: {title}"
        reason = f"Identified risks: {'; '.join(risk_items[:3])}"
        lesson = "Risks documented during planning phase - monitor during implementation"

        # Alternative from proposed changes
        alternative = sections.get('proposed_changes', '')[:200] if sections.get('proposed_changes') else ""

        # Check for duplicate
        content_hash = self.compute_content_hash(attempt + reason)
        existing = self.tracker.check_duplicate_content(content_hash, 'failure')

        if existing:
            self.stats['duplicates_skipped'] += 1
            return existing['node_id']

        try:
            result = await add_failure(
                attempt=attempt[:300],
                reason_failed=reason[:500],
                lesson_learned=lesson[:300],
                alternative_solution=alternative
            )

            node_id = result.get('failure_id')
            if node_id:
                self.tracker.register_content(content_hash, 'failure', node_id, source_file)
                self.tracker.record_extraction(file_id, 'failure', node_id, content_hash)
                self.stats['failures_created'] += 1

            return node_id

        except Exception as e:
            print(f"  Warning: Failed to create failure record: {e}")
            return None

    async def process_plan_file(self, file_path: Path, project_id: str = "claude-plans") -> Dict[str, Any]:
        """Process a single Claude plan file"""

        result = {
            'file': str(file_path),
            'sections_found': [],
            'nodes_created': []
        }

        # Check if needs processing
        if not self.tracker.needs_processing(file_path):
            return {'file': str(file_path), 'skipped': True, 'reason': 'unchanged'}

        # Record file
        file_id = self.tracker.record_file(file_path, project_id)

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            self.tracker.mark_file_failed(file_id, str(e))
            return {'file': str(file_path), 'error': str(e)}

        # Parse sections
        sections = self.parse_plan_file(content)
        result['sections_found'] = list(sections.keys())

        if not sections:
            self.tracker.mark_file_completed(file_id)
            return result

        # Create decision from problem/solution
        if any(k in sections for k in ['problem', 'root_cause', 'proposed_changes']):
            node_id = await self.create_decision_from_plan(sections, str(file_path), file_id)
            if node_id:
                result['nodes_created'].append(('decision', node_id))

        # Create pattern from implementation
        if any(k in sections for k in ['implementation', 'proposed_changes']):
            node_id = await self.create_pattern_from_plan(sections, str(file_path), file_id)
            if node_id:
                result['nodes_created'].append(('pattern', node_id))

        # Create failure record from risks
        if 'risks' in sections:
            node_id = await self.create_failure_from_risks(sections, str(file_path), file_id)
            if node_id:
                result['nodes_created'].append(('failure', node_id))

        self.tracker.mark_file_completed(file_id)
        self.stats['files_processed'] += 1

        return result

    async def scan_plans_directory(self, plans_dir: Path) -> Dict[str, Any]:
        """Scan all plan files in directory"""

        print(f"\n{'='*60}")
        print("CLAUDE PLAN EXTRACTOR")
        print(f"{'='*60}")
        print(f"\nScanning: {plans_dir}")

        if not plans_dir.exists():
            print(f"Directory not found: {plans_dir}")
            return {'error': 'directory_not_found'}

        plan_files = list(plans_dir.glob("*.md"))
        print(f"Found {len(plan_files)} plan files\n")

        results = []
        for plan_file in plan_files:
            print(f"Processing: {plan_file.name}...", end=" ")
            result = await self.process_plan_file(plan_file)

            if result.get('skipped'):
                print("(skipped - unchanged)")
            elif result.get('error'):
                print(f"(error: {result['error']})")
            else:
                nodes = len(result.get('nodes_created', []))
                print(f"({nodes} nodes)")

            results.append(result)

        # Summary
        print(f"\n{'='*60}")
        print("EXTRACTION COMPLETE")
        print(f"{'='*60}")
        print(f"\nStatistics:")
        print(f"  Files processed: {self.stats['files_processed']}")
        print(f"  Decisions created: {self.stats['decisions_created']}")
        print(f"  Patterns created: {self.stats['patterns_created']}")
        print(f"  Failures created: {self.stats['failures_created']}")
        print(f"  Duplicates skipped: {self.stats['duplicates_skipped']}")

        return {
            'stats': self.stats,
            'results': results
        }


async def main():
    """Entry point for standalone execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Extract knowledge from Claude Code plan files")
    parser.add_argument('--plans-dir', default=str(Path.home() / '.claude' / 'plans'),
                        help='Directory containing Claude plan files')
    parser.add_argument('--db-path', default='/home/platano/project/faulkner-db/data/scanner_tracking.db',
                        help='Path to file tracker database')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be processed without making changes')

    args = parser.parse_args()

    plans_dir = Path(args.plans_dir)
    db_path = Path(args.db_path)

    if args.dry_run:
        print(f"DRY RUN - Would scan: {plans_dir}")
        plan_files = list(plans_dir.glob("*.md"))
        print(f"Found {len(plan_files)} plan files")
        for f in plan_files[:10]:
            print(f"  - {f.name}")
        if len(plan_files) > 10:
            print(f"  ... and {len(plan_files) - 10} more")
        return

    tracker = FileTracker(db_path)
    extractor = ClaudePlanExtractor(tracker)

    await extractor.scan_plans_directory(plans_dir)


if __name__ == "__main__":
    asyncio.run(main())
