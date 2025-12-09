#!/usr/bin/env python3
"""
Multi-Project Markdown Scanner - Extends markdown_scanner.py for multiple projects.
"""

import asyncio
import sys
import logging
from pathlib import Path
from typing import Dict, List
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.file_tracker import FileTracker
from ingestion.project_registry import ProjectRegistry
from ingestion.deduplication import DeduplicationEngine, SmartDeduplicator
from ingestion.markdown_scanner import MarkdownScanner
from core.graphiti_client import GraphitiClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MultiProjectScanner:
    """Scan markdown files across multiple projects with deduplication"""
    
    def __init__(self, config_path: Path):
        # Load config
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        self.config = config
        self.tracker = FileTracker(Path(config.get('database_path', 'scanner_tracking.db')))
        self.registry = ProjectRegistry([Path(p) for p in config.get('project_paths', [])])
        self.graphiti_client = GraphitiClient()
        
        # Setup deduplication
        self.dedup_engine = DeduplicationEngine(
            self.tracker,
            config.get('deduplication', {}).get('similarity_threshold', 0.85)
        )
        self.deduplicator = SmartDeduplicator(self.dedup_engine, self.graphiti_client)
    
    async def run_scan(self) -> Dict[str, int]:
        """Run scan across all projects"""
        print("\n" + "="*60)
        print("MULTI-PROJECT MARKDOWN SCANNER")
        print("="*60 + "\n")
        
        projects = self.registry.discover_projects()
        print(f"Found {len(projects)} projects\n")
        
        results = {}
        for project_id, project_path in projects.items():
            print(f"Scanning: {project_id}...")
            count = await self.scan_project(project_id, project_path)
            results[project_id] = count
            print(f"  Processed {count} files\n")
        
        print("="*60)
        print(f"COMPLETED: {sum(results.values())} files across {len(results)} projects")
        print("="*60 + "\n")
        
        return results
    
    async def scan_project(self, project_id: str, project_path: Path) -> int:
        """Scan single project using markdown_scanner logic"""
        # Get markdown files
        md_files = list(project_path.rglob("*.md"))
        
        # Filter by exclusions
        excluded = self.config.get('excluded_patterns', [])
        md_files = [f for f in md_files if not any(p in str(f) for p in excluded)]
        
        processed = 0
        for md_file in md_files:
            # Check if needs processing (incremental)
            if not self.tracker.needs_processing(md_file):
                continue
            
            # Record file
            file_id = self.tracker.record_file(md_file, project_id)
            
            try:
                # Use existing markdown scanner extraction
                scanner = MarkdownScanner()
                scanner.project_dir = project_path
                
                # Process file
                await scanner.scan_file(md_file)
                
                self.tracker.mark_file_completed(file_id)
                processed += 1
            
            except Exception as e:
                logger.error(f"Error processing {md_file}: {e}")
                self.tracker.mark_file_failed(file_id, str(e))
        
        return processed


async def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='ingestion/scanner_config.yaml')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path(__file__).parent.parent / config_path
    
    scanner = MultiProjectScanner(config_path)
    
    if args.dry_run:
        projects = scanner.registry.discover_projects()
        print(f"\nWould scan {len(projects)} projects:")
        for pid in projects:
            print(f"  - {pid}")
    else:
        await scanner.run_scan()


if __name__ == "__main__":
    asyncio.run(main())
