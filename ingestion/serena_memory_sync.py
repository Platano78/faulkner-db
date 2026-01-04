#!/usr/bin/env python3
"""
Serena Memory Sync - Syncs extracted knowledge from Claude plans to Serena memories.
Provides project-specific context retrieval from ingested plan files.
"""

import asyncio
import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import re

# Auto-detect paths - no configuration needed
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
DEFAULT_DB_PATH = DATA_DIR / 'scanner_tracking.db'
DEFAULT_PLANS_DIR = Path.home() / '.claude' / 'plans'
# Projects directory can be overridden via environment variable
PROJECTS_DIR = Path(os.environ.get('FAULKNER_PROJECTS_DIR', PROJECT_ROOT.parent))

sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.file_tracker import FileTracker


class SerenaMemorySync:
    """Sync extracted knowledge to Serena memories"""

    def __init__(self, tracker: FileTracker):
        self.tracker = tracker
        self.stats = {
            'memories_created': 0,
            'memories_updated': 0,
            'errors': 0
        }

    def _call_serena_mcp(self, tool_name: str, args: Dict[str, Any]) -> Optional[Dict]:
        """Call Serena MCP tool via Claude Code's MCP connection"""
        # Note: In production, this would use the actual MCP client
        # For now, we'll write memory files directly to .serena/memories
        return None

    def _write_memory_file(self, project_path: Path, memory_name: str, content: str) -> bool:
        """Write a memory file directly to project's .serena/memories directory"""
        serena_dir = project_path / '.serena' / 'memories'

        try:
            serena_dir.mkdir(parents=True, exist_ok=True)
            memory_file = serena_dir / f"{memory_name}.md"

            memory_file.write_text(content, encoding='utf-8')
            return True
        except Exception as e:
            print(f"  Error writing memory: {e}")
            self.stats['errors'] += 1
            return False

    def _read_memory_file(self, project_path: Path, memory_name: str) -> Optional[str]:
        """Read existing memory file content"""
        memory_file = project_path / '.serena' / 'memories' / f"{memory_name}.md"
        if memory_file.exists():
            try:
                return memory_file.read_text(encoding='utf-8')
            except Exception:
                pass
        return None

    def extract_project_from_plan(self, plan_content: str) -> Optional[str]:
        """Try to identify the project from plan content"""
        # Look for project paths in the content - generic patterns
        project_patterns = [
            r'/home/[^/]+/project/([^/\s]+)',  # Linux home paths
            r'/Users/[^/]+/project/([^/\s]+)',  # macOS paths
            r'/mnt/[cd]/[^/]+/([^/\s]+)',      # WSL mount paths
            r'project[:\s]+([a-zA-Z0-9_-]+)',   # Generic project label
        ]

        for pattern in project_patterns:
            match = re.search(pattern, plan_content, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def generate_plan_summary(self, sections: Dict[str, str], plan_file: str) -> str:
        """Generate a concise summary of a plan for Serena memory"""
        lines = []

        # Title
        title = sections.get('title', Path(plan_file).stem)
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"**Source**: `{Path(plan_file).name}`")
        lines.append(f"**Extracted**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        # Problem/Context
        if sections.get('problem'):
            lines.append("## Problem")
            lines.append(sections['problem'][:500])
            lines.append("")

        # Root Cause
        if sections.get('root_cause'):
            lines.append("## Root Cause")
            lines.append(sections['root_cause'][:300])
            lines.append("")

        # Solution/Changes
        if sections.get('proposed_changes'):
            lines.append("## Solution")
            lines.append(sections['proposed_changes'][:500])
            lines.append("")

        # Implementation
        if sections.get('implementation'):
            lines.append("## Implementation Steps")
            lines.append(sections['implementation'][:500])
            lines.append("")

        # Files
        if sections.get('files_to_modify'):
            lines.append("## Files Modified")
            lines.append(sections['files_to_modify'][:300])
            lines.append("")

        return '\n'.join(lines)

    def aggregate_plans_for_project(
        self,
        project_name: str,
        plans: List[Dict[str, Any]]
    ) -> str:
        """Aggregate multiple plan summaries for a project"""
        lines = []
        lines.append(f"# Claude Plans for {project_name}")
        lines.append("")
        lines.append(f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**Plans Count**: {len(plans)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for i, plan in enumerate(plans, 1):
            lines.append(f"## {i}. {plan.get('title', 'Untitled')}")
            lines.append("")

            if plan.get('problem'):
                lines.append(f"**Problem**: {plan['problem'][:200]}...")
                lines.append("")

            if plan.get('solution'):
                lines.append(f"**Solution**: {plan['solution'][:200]}...")
                lines.append("")

            if plan.get('files'):
                lines.append(f"**Files**: {', '.join(plan['files'][:5])}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return '\n'.join(lines)

    async def sync_plan_to_serena(
        self,
        plan_file: Path,
        sections: Dict[str, str],
        project_path: Optional[Path] = None
    ) -> bool:
        """Sync a single plan to Serena memory"""

        # Try to identify project from content
        if not project_path:
            content = plan_file.read_text(encoding='utf-8', errors='ignore')
            project_name = self.extract_project_from_plan(content)
            if project_name:
                project_path = PROJECTS_DIR / project_name

        if not project_path or not project_path.exists():
            # Use a default location for unassociated plans
            project_path = PROJECT_ROOT

        # Generate memory name from plan file
        memory_name = f"plan-{plan_file.stem}"

        # Generate summary content
        summary = self.generate_plan_summary(sections, str(plan_file))

        # Check if memory exists and needs update
        existing = self._read_memory_file(project_path, memory_name)
        if existing and existing.strip() == summary.strip():
            return True  # No update needed

        # Write memory
        if self._write_memory_file(project_path, memory_name, summary):
            if existing:
                self.stats['memories_updated'] += 1
            else:
                self.stats['memories_created'] += 1
            return True

        return False

    async def sync_all_plans(
        self,
        plans_dir: Path,
        target_project: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Sync all plans to Serena memories, grouped by project"""

        print(f"\n{'='*60}")
        print("SERENA MEMORY SYNC")
        print(f"{'='*60}")
        print(f"\nScanning: {plans_dir}")

        # Import the plan extractor to parse files
        from ingestion.claude_plan_extractor import ClaudePlanExtractor
        extractor = ClaudePlanExtractor(self.tracker)

        plan_files = list(plans_dir.glob("*.md"))
        print(f"Found {len(plan_files)} plan files\n")

        # Group plans by detected project
        project_plans: Dict[str, List[Dict]] = {}

        for plan_file in plan_files:
            try:
                content = plan_file.read_text(encoding='utf-8', errors='ignore')
                sections = extractor.parse_plan_file(content)

                if not sections:
                    continue

                # Identify project
                project_name = self.extract_project_from_plan(content)
                if not project_name:
                    project_name = 'general'

                if project_name not in project_plans:
                    project_plans[project_name] = []

                project_plans[project_name].append({
                    'file': str(plan_file),
                    'title': sections.get('title', plan_file.stem),
                    'problem': sections.get('problem', ''),
                    'solution': sections.get('proposed_changes', ''),
                    'files': extractor.extract_file_paths(
                        sections.get('files_to_modify', '')
                    )
                })

                print(f"  {plan_file.name} -> {project_name}")

            except Exception as e:
                print(f"  Error processing {plan_file.name}: {e}")
                self.stats['errors'] += 1

        # Write aggregated memories per project
        print(f"\nWriting aggregated memories...")

        for project_name, plans in project_plans.items():
            project_path = PROJECTS_DIR / project_name
            if not project_path.exists():
                project_path = PROJECT_ROOT

            # Create aggregated memory
            aggregated = self.aggregate_plans_for_project(project_name, plans)
            memory_name = f"claude-plans-{project_name}"

            if self._write_memory_file(project_path, memory_name, aggregated):
                print(f"  Created: {project_path}/.serena/memories/{memory_name}.md ({len(plans)} plans)")
                self.stats['memories_created'] += 1

        # Summary
        print(f"\n{'='*60}")
        print("SYNC COMPLETE")
        print(f"{'='*60}")
        print(f"\nStatistics:")
        print(f"  Memories created: {self.stats['memories_created']}")
        print(f"  Memories updated: {self.stats['memories_updated']}")
        print(f"  Errors: {self.stats['errors']}")
        print(f"  Projects with plans: {len(project_plans)}")

        return {
            'stats': self.stats,
            'projects': list(project_plans.keys()),
            'plans_per_project': {k: len(v) for k, v in project_plans.items()}
        }


async def main():
    """Entry point for standalone execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Sync Claude plans to Serena memories")
    parser.add_argument('--plans-dir', default=str(DEFAULT_PLANS_DIR),
                        help='Directory containing Claude plan files (default: ~/.claude/plans)')
    parser.add_argument('--db-path', default=str(DEFAULT_DB_PATH),
                        help='Path to file tracker database (default: auto-detected)')
    parser.add_argument('--project', help='Target project path (optional)')

    args = parser.parse_args()

    plans_dir = Path(args.plans_dir)
    db_path = Path(args.db_path)
    target_project = Path(args.project) if args.project else None

    tracker = FileTracker(db_path)
    syncer = SerenaMemorySync(tracker)

    await syncer.sync_all_plans(plans_dir, target_project)


if __name__ == "__main__":
    asyncio.run(main())
