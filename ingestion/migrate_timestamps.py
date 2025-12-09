from falkordb import FalkorDB
from datetime import datetime, timezone
import math
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_timestamps(batch_size=500, graph_name='knowledge_graph'):
    """
    Migrates nodes by adding timestamp property with current UTC time
    """
    # Connect to database
    db = FalkorDB()
    graph = db.select_graph(graph_name)
    
    # Get total count of nodes without timestamp
    count_query = "MATCH (n) WHERE n.timestamp IS NULL RETURN count(n)"
    result = graph.query(count_query)
    total_nodes = result.result_set[0][0] if result.result_set else 0
    
    if total_nodes == 0:
        logger.info("No nodes require timestamp migration")
        return {'status': 'completed', 'migrated': 0, 'total': 0}
    
    # Calculate batches
    total_batches = math.ceil(total_nodes / batch_size)
    logger.info(f"Starting migration for {total_nodes} nodes in {total_batches} batches")
    
    # Get default timestamp
    default_timestamp = datetime.now(timezone.utc).isoformat()
    
    # Process all nodes in one go (FalkorDB doesn't support SKIP/LIMIT in SET)
    migrated_count = 0
    for batch_num in range(total_batches):
        # Process one batch at a time
        update_query = f"""
        MATCH (n) 
        WHERE n.timestamp IS NULL 
        WITH n LIMIT {batch_size}
        SET n.timestamp = '{default_timestamp}'
        RETURN count(n)
        """
        
        result = graph.query(update_query)
        batch_count = result.result_set[0][0] if result.result_set else 0
        migrated_count += batch_count
        
        logger.info(f"Batch {batch_num+1}/{total_batches}: Migrated {batch_count} nodes (Total: {migrated_count}/{total_nodes})")
        
        if batch_count == 0:
            break
    
    logger.info(f"Timestamp migration completed: {migrated_count} nodes migrated")
    return {'status': 'completed', 'migrated': migrated_count, 'total': total_nodes}

if __name__ == "__main__":
    result = migrate_timestamps()
    print(f"Migration result: {result}")
