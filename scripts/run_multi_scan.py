#!/usr/bin/env python3
"""
CLI Entry Point for Multi-Project Markdown Scanner

Usage:
    python run_multi_scan.py                    # Full incremental scan
    python run_multi_scan.py --dry-run          # Show what would be scanned
    python run_multi_scan.py --project PROJECT  # Scan specific project
    python run_multi_scan.py --full             # Force full rescan
    python run_multi_scan.py --stats            # Show statistics only
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.multi_project_scanner import MultiProjectScanner
from ingestion.file_tracker import FileTracker
import logging

logger = logging.getLogger(__name__)


def show_statistics(config_path: Path):
    """Show current scanning statistics"""
    scanner = MultiProjectScanner(config_path)
    stats = scanner.tracker.get_statistics()
    
    print("\n" + "="*60)
    print("SCANNER STATISTICS")
    print("="*60)
    for key, value in stats.items():
        print(f"  {key.replace('_', ' ').title()}: {value}")
    print("="*60 + "\n")


async def run_full_scan(config_path: Path):
    """Run full scan (clear database first)"""
    scanner = MultiProjectScanner(config_path)
    
    print("\nWARNING: Full scan will clear existing database!")
    response = input("Continue? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Aborted.")
        return
    
    # Clear database
    scanner.tracker.db_path.unlink(missing_ok=True)
    scanner.tracker._init_database()
    
    # Run scan
    results = await scanner.run_scan()
    return results


async def run_project_scan(config_path: Path, project_filter: str):
    """Run scan for specific project only"""
    scanner = MultiProjectScanner(config_path)
    projects = scanner.registry.discover_projects()
    
    # Filter projects
    matching_projects = {
        pid: path for pid, path in projects.items()
        if project_filter.lower() in pid.lower()
    }
    
    if not matching_projects:
        print(f"\nNo projects matching '{project_filter}' found.")
        print(f"Available projects: {', '.join(projects.keys())}")
        return
    
    print(f"\nScanning {len(matching_projects)} project(s): {', '.join(matching_projects.keys())}")
    
    scanner.reporter.print_header("Project-Specific Scan")
    scanner.reporter.start()
    
    try:
        results = {}
        for project_id, project_path in matching_projects.items():
            processed = await scanner.scanner.scan_project(project_id, project_path)
            results[project_id] = processed
        
        return results
    
    finally:
        scanner.reporter.stop()
        scanner.reporter.print_summary()


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Multi-Project Markdown Scanner for Faulkner DB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_multi_scan.py                      # Incremental scan (default)
  python run_multi_scan.py --dry-run            # Show scan plan
  python run_multi_scan.py --full               # Full rescan
  python run_multi_scan.py --project faulkner   # Scan specific project
  python run_multi_scan.py --stats              # Show statistics
  python run_multi_scan.py --config custom.yaml # Use custom config
        """
    )
    
    parser.add_argument(
        '--config',
        default='ingestion/scanner_config.yaml',
        help='Configuration file path (default: ingestion/scanner_config.yaml)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be scanned without executing'
    )
    
    parser.add_argument(
        '--full',
        action='store_true',
        help='Force full rescan (clears database)'
    )
    
    parser.add_argument(
        '--project',
        type=str,
        help='Scan specific project only (partial name match)'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only (no scanning)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Resolve config path
    config_path = Path(args.config)
    if not config_path.is_absolute():
        # Relative to script directory
        config_path = Path(__file__).parent.parent / config_path
    
    if not config_path.exists():
        print(f"\nERROR: Config file not found: {config_path}")
        print("\nCreate a config file or use --config to specify location.")
        sys.exit(1)
    
    try:
        # Handle different modes
        if args.stats:
            show_statistics(config_path)
        
        elif args.full:
            results = asyncio.run(run_full_scan(config_path))
            if results:
                print(f"\nFull scan completed. Processed {sum(results.values())} files across {len(results)} projects.")
        
        elif args.project:
            results = asyncio.run(run_project_scan(config_path, args.project))
            if results:
                print(f"\nProject scan completed. Processed {sum(results.values())} files.")
        
        elif args.dry_run:
            scanner = MultiProjectScanner(config_path)
            plan = scanner.dry_run()
            
            print("\n" + "="*60)
            print("DRY RUN - Scan Plan")
            print("="*60)
            
            total_files = 0
            for project_id, files in plan.items():
                total_files += len(files)
                print(f"\n{project_id}: {len(files)} files to process")
                
                # Show sample files
                for f in files[:5]:
                    print(f"  - {f.name}")
                
                if len(files) > 5:
                    print(f"  ... and {len(files) - 5} more files")
            
            print(f"\n{'='*60}")
            print(f"Total: {total_files} files across {len(plan)} projects")
            print(f"{'='*60}\n")
        
        else:
            # Default: incremental scan
            scanner = MultiProjectScanner(config_path)
            results = asyncio.run(scanner.run_scan())
            
            if results:
                total_processed = sum(results.values())
                print(f"\nIncremental scan completed. Processed {total_processed} files across {len(results)} projects.")
    
    except KeyboardInterrupt:
        print("\n\nScan interrupted by user.")
        sys.exit(130)
    
    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
