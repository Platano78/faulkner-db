# ~/project/faulkner-db/core/graphiti_client.py
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
try:
    from knowledge_types import Decision, Pattern, Failure
except ImportError:
    from core.knowledge_types import Decision, Pattern, Failure


class MetricsCollector:
    """Collects operational metrics"""
    def __init__(self):
        self.nodes_created = 0
        self.queries_executed = 0
        self.validation_errors = 0
        self.query_times = []

    def record_query(self, duration: float):
        self.queries_executed += 1
        self.query_times.append(duration)

    def record_node_creation(self):
        self.nodes_created += 1

    def record_validation_error(self):
        self.validation_errors += 1


class FalkorDBAdapter:
    """Real FalkorDB adapter using official falkordb library"""
    def __init__(self, host='localhost', port=6379, graph_name='knowledge_graph', pool_size=10):
        from falkordb import FalkorDB
        
        self.db = FalkorDB(host=host, port=port)
        self.graph = self.db.select_graph(graph_name)
        
    def create_node(self, node_data: Dict[str, Any]) -> str:
        """Create a node in FalkorDB graph using literal values"""
        import json
        
        # Extract node properties
        props = node_data.copy()
        node_id = props.get('id')
        node_type = props.get('type')
        
        if not node_id or not node_type:
            raise ValueError("Node must have 'id' and 'type' fields")
        
        def escape_cypher_string(s: str) -> str:
            """Escape string for Cypher query"""
            # Escape backslashes first, then quotes
            return s.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')
        
        # Build property string with literal values
        prop_strings = []
        for key, value in props.items():
            if value is None:
                continue
            elif isinstance(value, str):
                escaped = escape_cypher_string(value)
                prop_strings.append(f"{key}: '{escaped}'")
            elif isinstance(value, bool):
                prop_strings.append(f"{key}: {str(value).lower()}")
            elif isinstance(value, (int, float)):
                prop_strings.append(f"{key}: {value}")
            elif isinstance(value, (list, dict)):
                # Convert to JSON string and escape
                json_str = json.dumps(value)
                escaped = escape_cypher_string(json_str)
                prop_strings.append(f"{key}: '{escaped}'")
        
        prop_string = ', '.join(prop_strings)
            
        # Create node using literal Cypher CREATE
        query = f'CREATE (n:{node_type} {{{prop_string}}})'
        self.graph.query(query)
        return node_id
        
    def query_nodes(self, query: Dict[str, Any]) -> List[Dict]:
        """Query nodes by properties"""
        # Build WHERE clause from query conditions
        where_conditions = []
        for key, value in query.items():
            if isinstance(value, str):
                escaped_value = value.replace('"', '\\\\"')
                where_conditions.append(f'n.{key} = "{escaped_value}"')
            else:
                where_conditions.append(f'n.{key} = {value}')
                
        where_clause = ' AND '.join(where_conditions)
        if where_clause:
            where_clause = 'WHERE ' + where_clause
            
        # Execute query
        cypher_query = f'MATCH (n) {where_clause} RETURN n'
        result = self.graph.query(cypher_query)
        
        # Convert results to list of dictionaries
        nodes = []
        if result.result_set:
            for record in result.result_set:
                node = record[0]  # The node object
                node_dict = {}
                
                # Add node ID if available
                if hasattr(node, 'id'):
                    node_dict['node_internal_id'] = node.id
                    
                # Add all properties
                if hasattr(node, 'properties'):
                    for prop_name, prop_value in node.properties.items():
                        node_dict[prop_name] = prop_value
                        
                # Add labels (taking first label as type)
                if hasattr(node, 'labels') and node.labels:
                    node_dict['type'] = node.labels[0]
                    
                nodes.append(node_dict)
                
        return nodes
        
    def create_relationship(self, from_id: str, to_id: str, rel_type: str, properties: Dict = None):
        """Create a relationship between two nodes"""
        # Build property string for relationship
        prop_string = ''
        if properties:
            prop_strings = []
            for key, value in properties.items():
                if isinstance(value, str):
                    escaped_value = value.replace('"', '\\\\"')
                    prop_strings.append(f'{key}:"{escaped_value}"')
                else:
                    prop_strings.append(f'{key}:{value}')
            prop_string = ' {' + ', '.join(prop_strings) + '}'
            
        # Create relationship between nodes
        query = f'MATCH (a {{id:"{from_id}"}}), (b {{id:"{to_id}"}}) CREATE (a)-[:{rel_type}{prop_string}]->(b)'
        self.graph.query(query)
    
    def query_relationships(self, node_id: str) -> List[Dict]:
        """Query all relationships for a given node (both incoming and outgoing).
        
        Args:
            node_id: The ID of the node to query relationships for
            
        Returns:
            List of dictionaries containing relationship information:
            - 'to': ID of the connected node
            - 'type': Relationship type
            - 'properties': Dictionary of relationship properties
        """
        if not node_id:
            raise ValueError("node_id cannot be empty")
        
        # Check if node exists first
        node_check_query = f'MATCH (n {{id:"{node_id}"}}) RETURN count(n) > 0 AS exists'
        try:
            node_exists_result = self.graph.query(node_check_query)
            if not node_exists_result.result_set or not node_exists_result.result_set[0][0]:
                return []  # Node doesn't exist, return empty list
        except Exception:
            return []  # If check fails, assume node doesn't exist
        
        # Single bidirectional query for all relationships
        query = f'''
        MATCH (n {{id:"{node_id}"}})-[r]-(b) 
        RETURN b.id AS to, type(r) AS type, properties(r) AS properties
        ORDER BY type(r), b.id
        '''
        
        try:
            result = self.graph.query(query)
            
            relationships = []
            for record in result.result_set:
                to_id, rel_type, rel_properties = record
                
                # Normalize properties - ensure it's always a dict
                normalized_properties = {}
                if rel_properties and isinstance(rel_properties, dict):
                    normalized_properties = rel_properties
                elif rel_properties:
                    # Handle case where FalkorDB might return different formats
                    try:
                        normalized_properties = dict(rel_properties)
                    except (TypeError, ValueError):
                        normalized_properties = {}
                
                relationships.append({
                    'to': to_id,
                    'type': rel_type,
                    'properties': normalized_properties
                })
            
            return relationships
            
        except Exception as e:
            raise Exception(f"Failed to query relationships for node {node_id}: {str(e)}")


class GraphitiClient:
    """Graphiti client with FalkorDB backend adapter"""
    
    def __init__(self):
        self.db = FalkorDBAdapter()
        self.metrics = MetricsCollector()

    def add_node(self, model: BaseModel) -> str:
        """Add a knowledge node to the graph"""
        start_time = time.time()
        try:
            data = model.dict()
            # Add type field based on model class name
            if 'type' not in data:
                data['type'] = model.__class__.__name__
            # Convert datetime objects to ISO8601 strings
            if 'timestamp' in data and isinstance(data['timestamp'], datetime):
                data['timestamp'] = data['timestamp'].isoformat()
            node_id = self.db.create_node(data)
            self.metrics.record_node_creation()
            return node_id
        except Exception as e:
            self.metrics.record_validation_error()
            raise e
        finally:
            self.metrics.record_query(time.time() - start_time)

    def query_temporal(
        self, 
        entity_type: str, 
        entity_id: str, 
        start_time: datetime, 
        end_time: datetime
    ) -> List[Dict]:
        """Query nodes by temporal constraints"""
        start_time_perf = time.time()
        try:
            query = {
                "type": entity_type,
                "id": entity_id
            }
            results = self.db.query_nodes(query)
            # Filter by temporal constraints
            filtered = [
                r for r in results
                if start_time <= datetime.fromisoformat(r['timestamp'][:-1]) <= end_time
            ]
            return filtered
        finally:
            self.metrics.record_query(time.time() - start_time_perf)

    def find_relationships(self, node_id: str) -> List[Dict]:
        """Find relationships for a given node"""
        start_time = time.time()
        try:
            return self.db.query_relationships(node_id)
        finally:
            self.metrics.record_query(time.time() - start_time)

    def connect_decisions(self, decision_a_id: str, decision_b_id: str, relationship: str):
        """Create relationship between two decisions"""
        start_time = time.time()
        try:
            self.db.create_relationship(decision_a_id, decision_b_id, relationship)
        finally:
            self.metrics.record_query(time.time() - start_time)
    
    def update_node_source_files(self, node_id: str, source_file: str):
        """Add a source file to an existing node's source_files array"""
        start_time = time.time()
        try:
            import json
            
            # Query existing source_files
            query = f'MATCH (n {{id:"{node_id}"}}) RETURN n.source_files AS source_files'
            result = self.db.graph.query(query)
            
            existing_sources = []
            if result.result_set and result.result_set[0][0]:
                # Parse JSON array
                try:
                    existing_sources = json.loads(result.result_set[0][0])
                except (json.JSONDecodeError, TypeError):
                    existing_sources = []
            
            # Add new source if not already present
            if source_file not in existing_sources:
                existing_sources.append(source_file)
                
                # Update node with new source_files array
                sources_json = json.dumps(existing_sources)
                escaped_json = sources_json.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')
                update_query = f"MATCH (n {{id:\"{node_id}\"}}) SET n.source_files = '{escaped_json}'"
                self.db.graph.query(update_query)
        
        finally:
            self.metrics.record_query(time.time() - start_time)
