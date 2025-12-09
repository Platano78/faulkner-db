#!/usr/bin/env python3
"""
Deduplication Engine - Smart content deduplication for knowledge graph ingestion.
Handles exact and fuzzy matching to merge duplicate decisions/patterns/failures.
"""

import hashlib
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class DeduplicationEngine:
    """Smart content deduplication with fuzzy matching support"""
    
    def __init__(self, file_tracker, similarity_threshold: float = 0.85):
        """
        Args:
            file_tracker: FileTracker instance for database access
            similarity_threshold: Minimum similarity score (0.0-1.0) for fuzzy matching
        """
        self.tracker = file_tracker
        self.similarity_threshold = similarity_threshold
    
    def compute_content_hash(self, text: str) -> str:
        """Compute MD5 hash of normalized text content"""
        # Normalize: lowercase, strip whitespace
        normalized = ' '.join(text.lower().split())
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    def check_duplicate(
        self,
        content: str,
        node_type: str,
        source_file: str
    ) -> Optional[Dict[str, any]]:
        """
        Check if content is a duplicate.
        
        Returns:
            None if not a duplicate
            Dict with 'node_id' and 'source_files' if duplicate found
        """
        content_hash = self.compute_content_hash(content)
        
        # Check exact match first
        existing = self.tracker.check_duplicate_content(content_hash, node_type)
        
        if existing:
            logger.info(
                f"Found exact duplicate {node_type}: {existing['node_id']} "
                f"(already in {len(existing['source_files'])} file(s))"
            )
            return existing
        
        return None
    
    def register_content(
        self,
        content: str,
        node_type: str,
        node_id: str,
        source_file: str
    ):
        """Register content in deduplication system"""
        content_hash = self.compute_content_hash(content)
        self.tracker.register_content(content_hash, node_type, node_id, source_file)
        logger.debug(f"Registered {node_type} {node_id} from {Path(source_file).name}")
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity score between two texts using Levenshtein ratio"""
        # Simple implementation using difflib for now
        # For production, consider python-Levenshtein package for performance
        from difflib import SequenceMatcher
        
        # Normalize texts
        norm1 = ' '.join(text1.lower().split())
        norm2 = ' '.join(text2.lower().split())
        
        # Calculate similarity ratio
        matcher = SequenceMatcher(None, norm1, norm2)
        return matcher.ratio()
    
    def find_similar_content(
        self,
        content: str,
        node_type: str,
        existing_contents: List[Tuple[str, str]]
    ) -> Optional[Tuple[str, float]]:
        """
        Find similar content in existing items using fuzzy matching.
        
        Args:
            content: Text to check
            node_type: Type of node (decision/pattern/failure)
            existing_contents: List of (node_id, content) tuples to compare against
        
        Returns:
            Tuple of (node_id, similarity_score) if similar content found, else None
        """
        best_match = None
        best_score = 0.0
        
        for node_id, existing_content in existing_contents:
            score = self.calculate_similarity(content, existing_content)
            
            if score > best_score and score >= self.similarity_threshold:
                best_match = node_id
                best_score = score
        
        if best_match:
            logger.info(
                f"Found fuzzy match for {node_type}: {best_match} "
                f"(similarity: {best_score:.2%})"
            )
            return (best_match, best_score)
        
        return None
    
    def merge_strategy(
        self,
        existing_node_id: str,
        new_source_file: str,
        similarity_score: float = 1.0
    ) -> Dict[str, any]:
        """
        Determine merge strategy for duplicate content.
        
        Returns:
            Dict with 'action' (skip/merge) and 'node_id'
        """
        if similarity_score >= 1.0:
            # Exact duplicate - just add source reference
            return {
                'action': 'skip',
                'node_id': existing_node_id,
                'reason': 'exact_duplicate'
            }
        elif similarity_score >= self.similarity_threshold:
            # Similar content - merge with note
            return {
                'action': 'merge',
                'node_id': existing_node_id,
                'reason': 'similar_content',
                'similarity': similarity_score
            }
        else:
            # Not similar enough - create new node
            return {
                'action': 'create',
                'node_id': None,
                'reason': 'unique_content'
            }
    
    def get_deduplication_stats(self) -> Dict[str, int]:
        """Get statistics about deduplication"""
        # Query database for dedup statistics
        # This is a placeholder - implement based on tracker database schema
        return {
            'total_unique': 0,
            'total_duplicates': 0,
            'exact_matches': 0,
            'fuzzy_matches': 0
        }


class SmartDeduplicator:
    """High-level deduplication coordinator for scanner"""
    
    def __init__(self, engine: DeduplicationEngine, graphiti_client=None):
        self.engine = engine
        self.graphiti_client = graphiti_client
        self.stats = {
            'unique': 0,
            'duplicates': 0,
            'merged': 0
        }
    
    async def process_content(
        self,
        content: str,
        node_type: str,
        source_file: str,
        create_node_func
    ) -> Optional[str]:
        """
        Process content with deduplication logic.
        
        Args:
            content: Text content to process
            node_type: Type (decision/pattern/failure)
            source_file: Source file path
            create_node_func: Async function to create node if not duplicate
        
        Returns:
            node_id of created or existing node, or None if skipped
        """
        # Check for duplicates
        duplicate = self.engine.check_duplicate(content, node_type, source_file)
        
        if duplicate:
            # Duplicate found - register additional source
            node_id = duplicate['node_id']
            self.engine.register_content(content, node_type, node_id, source_file)
            
            # Update the node in the graph to add the new source file
            if self.graphiti_client:
                try:
                    self.graphiti_client.update_node_source_files(node_id, source_file)
                    logger.info(
                        f"Updated {node_type} {node_id} with additional source: {Path(source_file).name}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to update node source_files in graph: {e}")
            
            self.stats['duplicates'] += 1
            
            logger.info(
                f"Skipped duplicate {node_type} (using existing {node_id}), "
                f"added {Path(source_file).name} to sources"
            )
            
            return node_id
        
        # Not a duplicate - create new node
        try:
            node_id = await create_node_func()
            
            if node_id:
                # Register in deduplication system
                self.engine.register_content(content, node_type, node_id, source_file)
                self.stats['unique'] += 1
                logger.debug(f"Created unique {node_type}: {node_id}")
            
            return node_id
        
        except Exception as e:
            logger.error(f"Failed to create {node_type}: {e}")
            return None
    
    def get_statistics(self) -> Dict[str, int]:
        """Get deduplication statistics for this session"""
        return self.stats.copy()
