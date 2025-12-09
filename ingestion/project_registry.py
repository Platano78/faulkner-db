#!/usr/bin/env python3
"""
Project Registry - Multi-project discovery and management for markdown scanner.
Handles automatic project detection across multiple root directories.
"""

from pathlib import Path
from typing import Dict, List, Set, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ProjectRegistry:
    """Manage multiple project directories with cross-platform support"""
    
    # Files/directories that indicate a project root
    PROJECT_MARKERS = [
        '.git',
        'README.md',
        'pyproject.toml',
        'package.json',
        'Cargo.toml',
        'go.mod',
        'pom.xml',
        'build.gradle',
        'CMakeLists.txt',
        '.project',
        'setup.py',
        'composer.json'
    ]
    
    def __init__(self, project_paths: List[Path]):
        self.project_paths = [Path(p) for p in project_paths]
        self._project_cache: Dict[str, Path] = {}
        self._discovered = False
    
    def discover_projects(self, force_refresh: bool = False) -> Dict[str, Path]:
        """Discover all projects in configured paths"""
        if self._discovered and not force_refresh:
            return self._project_cache
        
        projects = {}
        
        for base_path in self.project_paths:
            if not base_path.exists():
                logger.warning(f"Project path does not exist: {base_path}")
                continue
            
            logger.info(f"Scanning for projects in: {base_path}")
            
            # Immediate children as potential projects
            try:
                for item in base_path.iterdir():
                    if item.is_dir() and not self._should_skip(item):
                        # Check if it's a project
                        if self._is_project_root(item):
                            project_id = self._generate_project_id(item)
                            projects[project_id] = item
                            logger.debug(f"Found project: {project_id} at {item}")
            except PermissionError:
                logger.warning(f"Permission denied accessing: {base_path}")
                continue
        
        self._project_cache = projects
        self._discovered = True
        logger.info(f"Discovered {len(projects)} projects")
        
        return projects
    
    def _is_project_root(self, directory: Path) -> bool:
        """Check if directory is a project root by looking for marker files"""
        for marker in self.PROJECT_MARKERS:
            marker_path = directory / marker
            if marker_path.exists():
                return True
        return False
    
    def _should_skip(self, directory: Path) -> bool:
        """Check if directory should be skipped during discovery"""
        name = directory.name
        
        # Skip hidden directories
        if name.startswith('.'):
            return True
        
        # Skip common non-project directories
        skip_names = {
            'venv', '__pycache__', 'node_modules', 'dist', 'build',
            'target', '.pytest_cache', '.mypy_cache', 'logs', 'tmp', 'temp'
        }
        
        return name.lower() in skip_names
    
    def _generate_project_id(self, project_path: Path) -> str:
        """Generate unique project identifier from path"""
        # Use parent + project name for uniqueness
        parts = project_path.parts
        
        if len(parts) >= 2:
            # Format: parent_projectname
            return f"{parts[-2]}_{parts[-1]}"
        
        return parts[-1] if parts else "unknown"
    
    def get_project_path(self, project_id: str) -> Optional[Path]:
        """Get path for a specific project ID"""
        if not self._discovered:
            self.discover_projects()
        
        return self._project_cache.get(project_id)
    
    def get_all_project_ids(self) -> List[str]:
        """Get list of all discovered project IDs"""
        if not self._discovered:
            self.discover_projects()
        
        return list(self._project_cache.keys())
    
    def find_markdown_files(
        self,
        directory: Path,
        excluded_patterns: List[str],
        max_age_days: Optional[int] = None
    ) -> List[Path]:
        """Find all markdown files in directory with filtering"""
        md_files = []
        
        try:
            for md_path in directory.rglob("*.md"):
                # Check exclusion patterns
                if self._matches_exclusion(md_path, excluded_patterns):
                    continue
                
                # Check file age if specified
                if max_age_days is not None:
                    try:
                        from datetime import datetime
                        file_age = datetime.now().timestamp() - md_path.stat().st_mtime
                        max_age_seconds = max_age_days * 24 * 60 * 60
                        if file_age > max_age_seconds:
                            continue
                    except OSError:
                        continue
                
                md_files.append(md_path)
        
        except PermissionError:
            logger.warning(f"Permission denied accessing: {directory}")
        
        return md_files
    
    def _matches_exclusion(self, file_path: Path, patterns: List[str]) -> bool:
        """Check if file path matches any exclusion pattern"""
        path_str = str(file_path)
        
        for pattern in patterns:
            # Handle glob-style patterns
            if '*' in pattern or '?' in pattern:
                if file_path.match(pattern):
                    return True
            # Simple substring matching
            elif pattern in path_str:
                return True
        
        return False
    
    def get_project_files(
        self,
        project_id: str,
        excluded_patterns: List[str],
        max_age_days: Optional[int] = None
    ) -> List[Path]:
        """Get all markdown files for a specific project"""
        project_path = self.get_project_path(project_id)
        if not project_path:
            logger.warning(f"Project not found: {project_id}")
            return []
        
        return self.find_markdown_files(
            project_path,
            excluded_patterns,
            max_age_days
        )
    
    def get_project_statistics(self) -> Dict[str, Any]:
        """Get statistics about discovered projects"""
        
        if not self._discovered:
            self.discover_projects()
        
        stats = {
            'total_projects': len(self._project_cache),
            'projects_by_root': {}
        }
        
        # Group projects by root path
        for project_id, project_path in self._project_cache.items():
            for root in self.project_paths:
                if root in project_path.parents or root == project_path:
                    root_str = str(root)
                    if root_str not in stats['projects_by_root']:
                        stats['projects_by_root'][root_str] = []
                    stats['projects_by_root'][root_str].append(project_id)
                    break
        
        return stats
