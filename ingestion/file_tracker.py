#!/usr/bin/env python3
"""
File Tracker - SQLite-based persistent tracking for multi-project markdown scanner.
Handles cross-platform path normalization (WSL/Windows) and incremental scanning.
"""

import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import json


class FileTracker:
    """SQLite-based file tracking with cross-platform path normalization"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            # Main file tracking table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scanned_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    normalized_path TEXT UNIQUE NOT NULL,
                    original_path TEXT NOT NULL,
                    filesystem_id TEXT NOT NULL,
                    file_size INTEGER,
                    last_modified REAL,
                    content_hash TEXT,
                    last_scanned REAL,
                    project_id TEXT,
                    scan_status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Scan session tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scan_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    end_time DATETIME,
                    total_files INTEGER DEFAULT 0,
                    processed_files INTEGER DEFAULT 0,
                    skipped_files INTEGER DEFAULT 0,
                    failed_files INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running'
                )
            ''')
            
            # Extraction results linking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS extraction_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER REFERENCES scanned_files(id),
                    node_type TEXT NOT NULL,
                    node_id TEXT,
                    content_hash TEXT,
                    extracted_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Content deduplication tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS content_deduplication (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT UNIQUE NOT NULL,
                    node_type TEXT NOT NULL,
                    canonical_node_id TEXT,
                    source_files TEXT,
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_normalized_path ON scanned_files(normalized_path)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON scanned_files(content_hash)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_project_id ON scanned_files(project_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_dedup_hash ON content_deduplication(content_hash)')
            
            conn.commit()
    
    def normalize_path(self, file_path: Path) -> str:
        """Convert path to cross-platform normalized form"""
        path_str = str(file_path)
        
        # Handle WSL Windows mount points: /mnt/d/ -> d:/
        if path_str.startswith('/mnt/'):
            parts = path_str.split('/')
            if len(parts) >= 3:
                drive_letter = parts[2]
                rest_path = '/'.join(parts[3:])
                return f"{drive_letter}:/{rest_path}".lower()
        
        # Standard Linux path normalization
        return str(file_path.resolve()).lower()
    
    def get_filesystem_id(self, file_path: Path) -> str:
        """Generate unique filesystem identifier for path"""
        try:
            stat = file_path.stat()
            # Use device + inode for unique identification
            return f"{stat.st_dev}:{stat.st_ino}"
        except (OSError, AttributeError):
            # Fallback for filesystems without inodes
            return hashlib.md5(self.normalize_path(file_path).encode()).hexdigest()
    
    def compute_content_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of file content"""
        hasher = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""
    
    def compute_text_hash(self, text: str) -> str:
        """Compute MD5 hash of text content (for deduplication)"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def record_file(self, file_path: Path, project_id: str) -> int:
        """Record file in database, return file_id"""
        normalized = self.normalize_path(file_path)
        fs_id = self.get_filesystem_id(file_path)
        content_hash = self.compute_content_hash(file_path)
        
        try:
            stat = file_path.stat()
            file_size = stat.st_size
            last_modified = stat.st_mtime
        except OSError:
            file_size = 0
            last_modified = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT OR REPLACE INTO scanned_files 
                (normalized_path, original_path, filesystem_id, file_size, 
                 last_modified, content_hash, project_id, last_scanned, scan_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'processing')
            ''', (
                normalized, str(file_path), fs_id, file_size,
                last_modified, content_hash, project_id, datetime.now().timestamp()
            ))
            
            # Get the ID of inserted/updated row
            cursor.execute('SELECT id FROM scanned_files WHERE normalized_path = ?', (normalized,))
            result = cursor.fetchone()
            return result[0] if result else cursor.lastrowid
    
    def needs_processing(self, file_path: Path) -> bool:
        """Check if file needs processing (new or modified)"""
        normalized = self.normalize_path(file_path)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT file_size, last_modified, content_hash, scan_status
                FROM scanned_files 
                WHERE normalized_path = ?
            ''', (normalized,))
            
            result = cursor.fetchone()
            if not result:
                return True  # New file
            
            old_size, old_mtime, old_hash, status = result
            
            # Skip if currently processing (avoid race conditions)
            if status == 'processing':
                return False
            
            try:
                current_stat = file_path.stat()
                
                # Check if file has changed
                if current_stat.st_size != old_size or current_stat.st_mtime != old_mtime:
                    return True
                
                # Optional: content hash verification for extra safety
                if old_hash:
                    current_hash = self.compute_content_hash(file_path)
                    return current_hash != old_hash
                
            except OSError:
                return False  # File no longer accessible
            
            return False
    
    def mark_file_completed(self, file_id: int):
        """Mark file as successfully processed"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE scanned_files 
                SET scan_status = 'completed', error_message = NULL
                WHERE id = ?
            ''', (file_id,))
            conn.commit()
    
    def mark_file_failed(self, file_id: int, error: str):
        """Mark file as failed with error message"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE scanned_files 
                SET scan_status = 'failed', error_message = ?
                WHERE id = ?
            ''', (error, file_id))
            conn.commit()
    
    def record_extraction(self, file_id: int, node_type: str, node_id: str, content_hash: str):
        """Record an extracted node from a file"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO extraction_results (file_id, node_type, node_id, content_hash)
                VALUES (?, ?, ?, ?)
            ''', (file_id, node_type, node_id, content_hash))
            conn.commit()
    
    def check_duplicate_content(self, content_hash: str, node_type: str) -> Optional[Dict[str, Any]]:
        """Check if content hash already exists (for deduplication)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT canonical_node_id, source_files
                FROM content_deduplication
                WHERE content_hash = ? AND node_type = ?
            ''', (content_hash, node_type))
            
            result = cursor.fetchone()
            if result:
                return {
                    'node_id': result[0],
                    'source_files': json.loads(result[1]) if result[1] else []
                }
            return None
    
    def register_content(self, content_hash: str, node_type: str, node_id: str, source_file: str):
        """Register content for deduplication tracking"""
        with sqlite3.connect(self.db_path) as conn:
            # Try to update existing entry
            cursor = conn.execute('''
                SELECT source_files FROM content_deduplication
                WHERE content_hash = ? AND node_type = ?
            ''', (content_hash, node_type))
            
            result = cursor.fetchone()
            
            if result:
                # Update existing: add source file to list
                source_files = json.loads(result[0]) if result[0] else []
                if source_file not in source_files:
                    source_files.append(source_file)
                
                conn.execute('''
                    UPDATE content_deduplication
                    SET source_files = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE content_hash = ? AND node_type = ?
                ''', (json.dumps(source_files), content_hash, node_type))
            else:
                # Insert new entry
                conn.execute('''
                    INSERT INTO content_deduplication 
                    (content_hash, node_type, canonical_node_id, source_files)
                    VALUES (?, ?, ?, ?)
                ''', (content_hash, node_type, node_id, json.dumps([source_file])))
            
            conn.commit()
    
    def start_scan_session(self) -> int:
        """Start a new scan session, return session_id"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('INSERT INTO scan_sessions DEFAULT VALUES')
            conn.commit()
            return cursor.lastrowid
    
    def update_scan_session(self, session_id: int, stats: Dict[str, int]):
        """Update scan session statistics"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE scan_sessions
                SET total_files = ?, processed_files = ?, 
                    skipped_files = ?, failed_files = ?
                WHERE id = ?
            ''', (
                stats.get('total', 0),
                stats.get('processed', 0),
                stats.get('skipped', 0),
                stats.get('failed', 0),
                session_id
            ))
            conn.commit()
    
    def complete_scan_session(self, session_id: int):
        """Mark scan session as completed"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE scan_sessions
                SET end_time = CURRENT_TIMESTAMP, status = 'completed'
                WHERE id = ?
            ''', (session_id,))
            conn.commit()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall scanning statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total_files,
                    SUM(CASE WHEN scan_status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN scan_status = 'failed' THEN 1 ELSE 0 END) as failed,
                    COUNT(DISTINCT project_id) as projects
                FROM scanned_files
            ''')
            
            row = cursor.fetchone()
            
            return {
                'total_files': row[0] or 0,
                'completed': row[1] or 0,
                'failed': row[2] or 0,
                'projects': row[3] or 0
            }
