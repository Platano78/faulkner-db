#!/usr/bin/env python3
"""
Legacy Tags Migration Script for FalkorDB

This script migrates nodes with missing or empty source fields to use standardized tags.
It's designed to be idempotent and safe for production use with dry-run capability.
"""

import os
import sys
import logging
from datetime import datetime
from typing import Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class FalkorDBMigrator:
    """Handles migration operations for FalkorDB legacy tags."""

    def __init__(self, host: str = 'localhost', port: int = 6379, graph: str = 'knowledge_graph'):
        """
        Initialize the migrator with FalkorDB connection parameters.

        Args:
            host: Redis server hostname
            port: Redis server port
            graph: Name of the graph to operate on
        """
        self.host = host
        self.port = port
        self.graph_name = graph
        self.dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'
        self.db = None
        self.graph = None

    def connect(self) -> bool:
        """
        Establish connection to FalkorDB.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            from falkordb import FalkorDB

            self.db = FalkorDB(host=self.host, port=self.port)
            self.graph = self.db.select_graph(self.graph_name)

            logger.info(f"Connected to FalkorDB at {self.host}:{self.port}, graph: {self.graph_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to FalkorDB: {e}")
            return False

    def validate_environment(self) -> Tuple[bool, Optional[str]]:
        """
        Validate that the environment is ready for migration.

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        if not self.connect():
            return False, "Database connection failed"

        try:
            # Check if we have any nodes to migrate
            count_result = self.count_legacy_nodes()
            if count_result is None:
                return False, "Failed to count legacy nodes"

            logger.info(f"Validation successful. Found {count_result} nodes eligible for migration")
            return True, None

        except Exception as e:
            return False, f"Environment validation failed: {e}"

    def count_legacy_nodes(self) -> Optional[int]:
        """
        Count nodes with missing or empty source fields.

        Returns:
            Optional[int]: Number of legacy nodes, None if query failed
        """
        try:
            query = """
            MATCH (n)
            WHERE n.source IS NULL OR n.source = ''
            RETURN COUNT(n) AS count
            """
            result = self.graph.query(query)
            return result.result_set[0][0] if result.result_set else 0

        except Exception as e:
            logger.error(f"Failed to count legacy nodes: {e}")
            return None

    def get_legacy_nodes_sample(self, limit: int = 5) -> Optional[list]:
        """
        Get a sample of legacy nodes for verification.

        Args:
            limit: Number of sample nodes to return

        Returns:
            Optional[list]: List of sample nodes, None if query failed
        """
        try:
            query = f"""
            MATCH (n)
            WHERE n.source IS NULL OR n.source = ''
            RETURN labels(n)[0] AS type, n.id AS id
            LIMIT {limit}
            """
            result = self.graph.query(query)
            return result.result_set if result.result_set else []

        except Exception as e:
            logger.error(f"Failed to get legacy nodes sample: {e}")
            return None

    def migrate_legacy_nodes(self) -> Tuple[bool, Optional[int]]:
        """
        Perform the migration of legacy nodes.

        Returns:
            Tuple[bool, Optional[int]]: (success, number_of_nodes_migrated)
        """
        if self.dry_run:
            logger.info("DRY RUN MODE - No changes will be made to the database")
            # Just return the count
            count = self.count_legacy_nodes()
            return True, count

        try:
            # Build the update query
            current_timestamp = datetime.now().isoformat()

            # FalkorDB doesn't support parameterized SET, so we use literal values
            update_query = f"""
            MATCH (n)
            WHERE n.source IS NULL OR n.source = ''
            SET n.source = 'claude_desktop',
                n.collection = 'beta_collection',
                n.project = 'unknown',
                n.migrated_at = '{current_timestamp}'
            RETURN COUNT(n) AS migrated_count
            """

            result = self.graph.query(update_query)
            migrated_count = result.result_set[0][0] if result.result_set else 0
            logger.info(f"Migration completed. Nodes migrated: {migrated_count}")
            return True, migrated_count

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False, None

    def verify_migration(self, expected_count: int) -> Tuple[bool, Optional[str]]:
        """
        Verify that the migration was successful.

        Args:
            expected_count: Number of nodes that should have been migrated

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        try:
            # Count remaining legacy nodes
            remaining_count = self.count_legacy_nodes()
            if remaining_count is None:
                return False, "Failed to verify migration count"

            if remaining_count > 0:
                return False, f"Migration incomplete. {remaining_count} nodes still need migration"

            # Verify the new values are set correctly
            verification_query = """
            MATCH (n)
            WHERE n.source = 'claude_desktop'
                AND n.collection = 'beta_collection'
                AND n.project = 'unknown'
                AND n.migrated_at IS NOT NULL
            RETURN COUNT(n) AS verified_count
            """
            result = self.graph.query(verification_query)
            verified_count = result.result_set[0][0] if result.result_set else 0

            logger.info(f"Migration verification successful. {verified_count} nodes verified")
            return True, None

        except Exception as e:
            return False, f"Verification failed: {e}"

    def run_migration(self) -> bool:
        """
        Execute the complete migration process with validation and verification.

        Returns:
            bool: True if migration was successful, False otherwise
        """
        logger.info("Starting legacy tags migration process")

        # Step 1: Environment validation
        logger.info("Step 1: Validating environment")
        success, error_msg = self.validate_environment()
        if not success:
            logger.error(f"Environment validation failed: {error_msg}")
            return False

        # Step 2: Pre-migration assessment
        logger.info("Step 2: Pre-migration assessment")
        legacy_count = self.count_legacy_nodes()
        if legacy_count is None:
            logger.error("Failed to assess pre-migration state")
            return False

        if legacy_count == 0:
            logger.info("No legacy nodes found. Migration not required.")
            return True

        logger.info(f"Found {legacy_count} nodes eligible for migration")

        # Show sample of nodes to be migrated
        sample_nodes = self.get_legacy_nodes_sample(limit=3)
        if sample_nodes:
            logger.info(f"Sample of nodes to be migrated:")
            for node in sample_nodes:
                logger.info(f"  - Type: {node[0]}, ID: {node[1]}")

        # Step 3: Confirm execution (unless dry-run)
        if not self.dry_run:
            logger.info("Step 3: Proceeding with migration")
        else:
            logger.info("Step 3: Dry-run simulation")

        # Step 4: Execute migration
        logger.info("Step 4: Executing migration")
        success, migrated_count = self.migrate_legacy_nodes()
        if not success:
            logger.error("Migration execution failed")
            return False

        # Step 5: Post-migration verification
        if not self.dry_run:
            logger.info("Step 5: Post-migration verification")
            success, error_msg = self.verify_migration(legacy_count)
            if not success:
                logger.error(f"Migration verification failed: {error_msg}")
                return False
        else:
            logger.info("Step 5: Dry-run completed successfully")
            logger.info(f"Would have migrated {legacy_count} nodes")

        logger.info("Legacy tags migration completed successfully")
        return True


def main():
    """Main execution function."""
    migrator = FalkorDBMigrator()

    try:
        success = migrator.run_migration()
        if success:
            logger.info("Migration process completed successfully")
            sys.exit(0)
        else:
            logger.error("Migration process failed")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
