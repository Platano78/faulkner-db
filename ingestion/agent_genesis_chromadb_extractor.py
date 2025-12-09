#!/usr/bin/env python3
"""
Agent Genesis ChromaDB Conversation Extractor

Extracts full conversation content from Agent Genesis ChromaDB and imports into FalkorDB.
Agent Genesis has already indexed 35,627 messages - we extract them directly from ChromaDB
instead of re-parsing JSONL files.

Features:
- Direct ChromaDB connection for full message content (not 42-char snippets)
- Batch extraction with progress tracking
- Knowledge pattern identification (decisions, patterns, failures)
- FalkorDB integration with proper node types
- Error handling and logging
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime
import json
import uuid
import re
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    print("ERROR: chromadb package not installed")
    print("Install with: pip install chromadb")
    sys.exit(1)

try:
    from falkordb import FalkorDB
except ImportError:
    print("ERROR: falkordb package not installed")
    print("Install with: pip install falkordb")
    sys.exit(1)

from core.knowledge_types import Decision, Pattern, Failure
from core.graphiti_client import GraphitiClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chromadb_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AgentGenesisExtractor:
    """Extract conversations from Agent Genesis ChromaDB and insert into FalkorDB"""

    def __init__(
        self,
        chromadb_path: str = "/home/platano/project/agent-genesis/docker-knowledge/",
        collection_name: str = "alpha_claude_code",
        falkordb_host: str = "localhost",
        falkordb_port: int = 6379,
        graph_name: str = "knowledge_graph",
        additive: bool = False
    ):
        """
        Initialize extractor

        Args:
            chromadb_path: Path to Agent Genesis ChromaDB storage
            collection_name: ChromaDB collection name (alpha_claude_code or beta_claude_desktop)
            falkordb_host: FalkorDB host
            falkordb_port: FalkorDB port
            graph_name: FalkorDB graph name
        """
        self.chromadb_path = chromadb_path
        self.collection_name = collection_name
        self.falkordb_host = falkordb_host
        self.falkordb_port = falkordb_port
        self.graph_name = graph_name
        self.additive = additive

        # Determine source/collection tags based on collection name
        self.source_tag = "claude_code" if "alpha" in collection_name else "claude_desktop"
        self.collection_tag = "alpha" if "alpha" in collection_name else "beta"

        # Statistics
        self.stats = {
            'messages_extracted': 0,
            'conversations_found': 0,
            'decisions_created': 0,
            'patterns_created': 0,
            'failures_created': 0,
            'errors': 0
        }

        # Initialize clients
        self.chroma_client = None
        self.collection = None
        self.graphiti_client = None

    def connect_chromadb(self) -> bool:
        """Connect to Agent Genesis ChromaDB"""
        try:
            logger.info(f"Connecting to ChromaDB at {self.chromadb_path}")

            self.chroma_client = chromadb.PersistentClient(
                path=self.chromadb_path,
                settings=Settings(anonymized_telemetry=False)
            )

            # Get collection (alpha = Claude Code JSONL, beta = Claude Desktop LevelDB)
            self.collection = self.chroma_client.get_collection(self.collection_name)

            count = self.collection.count()
            logger.info(f"Connected to collection '{self.collection_name}' with {count:,} documents")

            return True

        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
            return False

    def connect_falkordb(self) -> bool:
        """Connect to FalkorDB"""
        try:
            logger.info(f"Connecting to FalkorDB at {self.falkordb_host}:{self.falkordb_port}")

            self.graphiti_client = GraphitiClient()

            logger.info(f"Connected to FalkorDB graph '{self.graph_name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to FalkorDB: {e}")
            return False

    def extract_all_messages(self, batch_size: int = 1000) -> List[Tuple[str, Dict]]:
        """
        Extract all messages from ChromaDB with full content

        Args:
            batch_size: Number of messages to fetch per batch

        Returns:
            List of (document, metadata) tuples
        """
        logger.info("Stage 1: Extracting messages from ChromaDB...")

        all_messages = []
        total_count = self.collection.count()
        offset = 0

        while offset < total_count:
            try:
                # Fetch batch with full documents and metadata
                batch = self.collection.get(
                    limit=batch_size,
                    offset=offset,
                    include=["documents", "metadatas"]
                )

                # Check if we got results
                if not batch['ids']:
                    break

                # Combine documents and metadata
                batch_messages = list(zip(batch['documents'], batch['metadatas']))
                all_messages.extend(batch_messages)

                offset += len(batch['ids'])
                self.stats['messages_extracted'] = len(all_messages)

                # Progress update
                if offset % 5000 == 0 or offset >= total_count:
                    logger.info(f"Progress: {offset:,}/{total_count:,} messages extracted")

            except Exception as e:
                logger.error(f"Error extracting batch at offset {offset}: {e}")
                self.stats['errors'] += 1
                break

        logger.info(f"Extraction complete: {len(all_messages):,} messages extracted")
        return all_messages

    def group_by_conversation(self, messages: List[Tuple[str, Dict]]) -> Dict[str, List[Dict]]:
        """
        Group messages by conversation_id

        Args:
            messages: List of (document, metadata) tuples

        Returns:
            Dictionary mapping conversation_id to list of message dicts
        """
        logger.info("Stage 2: Grouping messages by conversation...")

        conversations = defaultdict(list)

        for document, metadata in messages:
            conv_id = metadata.get('conversation_id', 'unknown')

            conversations[conv_id].append({
                'content': document,
                'role': metadata.get('role', 'unknown'),
                'timestamp': metadata.get('timestamp', ''),
                'project': metadata.get('project', 'unknown'),
                'source': metadata.get('source', 'unknown'),
                'cwd': metadata.get('cwd', ''),
                'git_branch': metadata.get('git_branch', '')
            })

        self.stats['conversations_found'] = len(conversations)
        logger.info(f"Found {len(conversations):,} conversations from {len(messages):,} messages")

        return dict(conversations)

    def extract_knowledge_from_conversation(self, messages: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Analyze conversation messages to extract knowledge patterns

        Args:
            messages: List of message dicts for a conversation

        Returns:
            Dict with 'decisions', 'patterns', 'failures' keys
        """
        knowledge = {
            'decisions': [],
            'patterns': [],
            'failures': []
        }

        # Combine all assistant messages for analysis
        assistant_content = []
        for msg in messages:
            if msg['role'] == 'assistant' and msg['content']:
                assistant_content.append(msg['content'])

        full_text = '\n'.join(assistant_content)

        # Extract decisions
        decision_indicators = [
            r'decided to\s+(.{10,200})',
            r'chose to\s+(.{10,200})',
            r'selected\s+(.{10,200})',
            r'went with\s+(.{10,200})',
            r'decision was to\s+(.{10,200})',
            r'architecture is to\s+(.{10,200})'
        ]

        for pattern in decision_indicators:
            matches = re.finditer(pattern, full_text, re.IGNORECASE)
            for match in matches:
                description = match.group(1).strip()[:1000]
                if len(description) >= 10:
                    # Try to find rationale in surrounding context
                    start = max(0, match.start() - 200)
                    end = min(len(full_text), match.end() + 300)
                    context = full_text[start:end]

                    knowledge['decisions'].append({
                        'description': description,
                        'rationale': context[:2000],
                        'timestamp': messages[0].get('timestamp', ''),
                        'project': messages[0].get('project', 'unknown')
                    })

        # Extract patterns
        pattern_indicators = [
            r'pattern is\s+(.{10,200})',
            r'approach is\s+(.{10,200})',
            r'strategy for\s+(.{10,200})',
            r'always\s+(.{10,200})',
            r'consistently\s+(.{10,200})',
            r'best practice\s+(.{10,200})'
        ]

        for pattern in pattern_indicators:
            matches = re.finditer(pattern, full_text, re.IGNORECASE)
            for match in matches:
                name = match.group(1).strip()[:100]
                if len(name) >= 10:
                    # Extract implementation context
                    start = max(0, match.start() - 100)
                    end = min(len(full_text), match.end() + 500)
                    implementation = full_text[start:end]

                    # Use implementation text as context (ensuring min length)
                    context_text = implementation[:1000]
                    if len(context_text) < 10:
                        context_text = f"Pattern found in {messages[0].get('project', 'unknown')} project: {name}"

                    knowledge['patterns'].append({
                        'name': name,
                        'implementation': implementation[:3000],
                        'context': context_text,
                        'timestamp': messages[0].get('timestamp', '')
                    })

        # Extract failures
        failure_indicators = [
            r'failed\s+(.{10,200})',
            r'broke\s+(.{10,200})',
            r'error\s+(.{10,200})',
            r'bug\s+(.{10,200})',
            r'lesson learned\s+(.{10,200})',
            r"don't\s+(.{10,200})",
            r'avoid\s+(.{10,200})'
        ]

        for pattern in failure_indicators:
            matches = re.finditer(pattern, full_text, re.IGNORECASE)
            for match in matches:
                attempt = match.group(1).strip()[:1000]
                if len(attempt) >= 10:
                    # Extract reason and lesson
                    start = max(0, match.start() - 200)
                    end = min(len(full_text), match.end() + 400)
                    context = full_text[start:end]

                    knowledge['failures'].append({
                        'attempt': attempt,
                        'reason_failed': context[:2000],
                        'lesson_learned': f"Learned from: {attempt[:200]}",
                        'timestamp': messages[0].get('timestamp', ''),
                        'project': messages[0].get('project', 'unknown')
                    })

        return knowledge

    def create_decision_node(self, decision_data: Dict) -> Optional[str]:
        """Create Decision node in FalkorDB"""
        try:
            decision = Decision(
                id=f"D-{uuid.uuid4().hex[:8]}",
                description=decision_data['description'][:1000],
                rationale=decision_data['rationale'][:2000],
                alternatives=[],  # Could extract from context
                related_to=[],
                source_files=[f"agent-genesis:{decision_data.get('project', 'unknown')}"],
                source=self.source_tag,
                collection=self.collection_tag,
                project=decision_data.get('project', 'unknown')
            )

            node_id = self.graphiti_client.add_node(decision)
            self.stats['decisions_created'] += 1
            return node_id

        except Exception as e:
            logger.error(f"Failed to create Decision node: {e}")
            self.stats['errors'] += 1
            return None

    def create_pattern_node(self, pattern_data: Dict) -> Optional[str]:
        """Create Pattern node in FalkorDB"""
        try:
            # Ensure context meets minimum length requirement
            context = pattern_data.get('context', '')
            if len(context) < 10:
                context = f"Pattern from {pattern_data.get('project', 'unknown')}: {pattern_data['name'][:100]}"

            pattern = Pattern(
                id=f"P-{uuid.uuid4().hex[:8]}",
                name=pattern_data['name'][:100],
                implementation=pattern_data['implementation'][:3000],
                context=context[:1000],
                use_cases=[],  # Could extract from context
                source_files=[f"agent-genesis:{pattern_data.get('project', 'unknown')}"],
                source=self.source_tag,
                collection=self.collection_tag,
                project=pattern_data.get('project', 'unknown')
            )

            node_id = self.graphiti_client.add_node(pattern)
            self.stats['patterns_created'] += 1
            return node_id

        except Exception as e:
            logger.error(f"Failed to create Pattern node: {e}")
            self.stats['errors'] += 1
            return None

    def create_failure_node(self, failure_data: Dict) -> Optional[str]:
        """Create Failure node in FalkorDB"""
        try:
            failure = Failure(
                id=f"F-{uuid.uuid4().hex[:8]}",
                attempt=failure_data['attempt'][:1000],
                reason_failed=failure_data['reason_failed'][:2000],
                lesson_learned=failure_data['lesson_learned'][:2000],
                alternative_solution=None,  # Could extract from context
                source_files=[f"agent-genesis:{failure_data.get('project', 'unknown')}"],
                source=self.source_tag,
                collection=self.collection_tag,
                project=failure_data.get('project', 'unknown')
            )

            node_id = self.graphiti_client.add_node(failure)
            self.stats['failures_created'] += 1
            return node_id

        except Exception as e:
            logger.error(f"Failed to create Failure node: {e}")
            self.stats['errors'] += 1
            return None

    def process_conversations(self, conversations: Dict[str, List[Dict]]):
        """Process all conversations and create FalkorDB nodes"""
        logger.info(f"Stage 3: Analyzing {len(conversations):,} conversations for knowledge patterns...")

        conversation_count = 0

        for conv_id, messages in conversations.items():
            try:
                # Extract knowledge from conversation
                knowledge = self.extract_knowledge_from_conversation(messages)

                # Create nodes for each knowledge type
                for decision in knowledge['decisions']:
                    self.create_decision_node(decision)

                for pattern in knowledge['patterns']:
                    self.create_pattern_node(pattern)

                for failure in knowledge['failures']:
                    self.create_failure_node(failure)

                conversation_count += 1

                # Progress update
                if conversation_count % 100 == 0:
                    logger.info(
                        f"Progress: {conversation_count:,}/{len(conversations):,} | "
                        f"Nodes: {self.stats['decisions_created'] + self.stats['patterns_created'] + self.stats['failures_created']:,} | "
                        f"Decisions: {self.stats['decisions_created']:,} | "
                        f"Patterns: {self.stats['patterns_created']:,} | "
                        f"Failures: {self.stats['failures_created']:,}"
                    )

            except Exception as e:
                logger.error(f"Error processing conversation {conv_id}: {e}")
                self.stats['errors'] += 1

    def print_summary(self):
        """Print extraction summary"""
        print("\n" + "="*80)
        print("EXTRACTION COMPLETE")
        print("="*80)
        print(f"Total messages extracted:     {self.stats['messages_extracted']:,}")
        print(f"Conversations processed:      {self.stats['conversations_found']:,}")
        print(f"Decisions created:            {self.stats['decisions_created']:,}")
        print(f"Patterns created:             {self.stats['patterns_created']:,}")
        print(f"Failures created:             {self.stats['failures_created']:,}")
        print(f"Total nodes created:          {self.stats['decisions_created'] + self.stats['patterns_created'] + self.stats['failures_created']:,}")
        print(f"Errors encountered:           {self.stats['errors']:,}")
        print("="*80)

    def run(self):
        """Main extraction workflow"""
        print("="*80)
        print("AGENT GENESIS CHROMADB EXTRACTOR")
        print("="*80)
        print(f"Mode: {'ADDITIVE (keeping existing nodes)' if self.additive else 'REPLACE (clearing graph first)'}")
        print(f"Source: {self.chromadb_path}")
        print(f"Collection: {self.collection_name}")
        print(f"Tags: source={self.source_tag}, collection={self.collection_tag}")
        print("="*80)

        # Connect to databases
        if not self.connect_chromadb():
            logger.error("Failed to connect to ChromaDB. Exiting.")
            return False

        if not self.connect_falkordb():
            logger.error("Failed to connect to FalkorDB. Exiting.")
            return False

        # Clear graph if not in additive mode
        if not self.additive:
            logger.info("Clearing existing knowledge graph...")
            try:
                self.graphiti_client.clear_graph()
                logger.info("Graph cleared successfully")
            except Exception as e:
                logger.error(f"Failed to clear graph: {e}")
                return False
        else:
            logger.info("Additive mode: keeping existing nodes")

        # Extract messages
        messages = self.extract_all_messages()
        if not messages:
            logger.error("No messages extracted. Exiting.")
            return False

        # Group by conversation
        conversations = self.group_by_conversation(messages)
        if not conversations:
            logger.error("No conversations found. Exiting.")
            return False

        # Process conversations and create nodes
        self.process_conversations(conversations)

        # Print summary
        self.print_summary()

        return True


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract Agent Genesis conversations from ChromaDB to FalkorDB"
    )
    parser.add_argument(
        '--chromadb-path',
        default="/home/platano/project/agent-genesis/docker-knowledge/",
        help="Path to Agent Genesis ChromaDB storage (default: Docker copy with 52K+ messages)"
    )
    parser.add_argument(
        '--collection',
        default="alpha_claude_code",
        choices=["alpha_claude_code", "beta_claude_desktop"],
        help="ChromaDB collection name (default: alpha_claude_code with 52K+ messages)"
    )
    parser.add_argument(
        '--additive',
        action='store_true',
        help="Add to existing graph instead of clearing first (for combining alpha + beta)"
    )
    parser.add_argument(
        '--falkordb-host',
        default="localhost",
        help="FalkorDB host"
    )
    parser.add_argument(
        '--falkordb-port',
        type=int,
        default=6379,
        help="FalkorDB port"
    )
    parser.add_argument(
        '--graph-name',
        default="knowledge_graph",
        help="FalkorDB graph name"
    )

    args = parser.parse_args()

    # Create and run extractor
    extractor = AgentGenesisExtractor(
        chromadb_path=args.chromadb_path,
        collection_name=args.collection,
        falkordb_host=args.falkordb_host,
        falkordb_port=args.falkordb_port,
        graph_name=args.graph_name,
        additive=args.additive
    )

    success = extractor.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
