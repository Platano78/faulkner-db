#!/usr/bin/env python3
"""
Relationship Extractor for Faulkner-DB Knowledge Graph

Extracts relationships between existing nodes in FalkorDB using multi-layer detection:
- Layer 1: Explicit references via regex patterns
- Layer 2: Cross-references (IDs, titles)
- Layer 3: FAISS semantic similarity
- Layer 4: Hierarchical relationships

Does NOT re-scan markdown files - operates on existing graph nodes only.
"""

import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.graphiti_client import GraphitiClient
from sentence_transformers import SentenceTransformer
import faiss

# Try to import MKG client for LLM enhancement
try:
    import requests
    MKG_AVAILABLE = True
except ImportError:
    MKG_AVAILABLE = False


class RelationshipExtractor:
    """
    Multi-layer relationship extractor for knowledge graph nodes.
    """
    
    def __init__(self, client: GraphitiClient):
        self.client = client
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Statistics tracking
        self.stats = {
            'explicit_references': 0,
            'cross_references': 0,
            'semantic_similarity': 0,
            'hierarchical': 0,
            'llm_enhanced': 0,
            'total_edges_created': 0,
            'nodes_processed': 0,
            'nodes_with_edges': set(),
        }
        
        # LLM configuration (llamacpp backend - OpenAI-compatible)
        self.llm_base_url = 'http://localhost:8081/v1'  # llamacpp OpenAI-compatible endpoint
        self.mkg_available = self.detect_mkg_availability()
        
        # Node cache for LLM processing
        self.node_cache = {}
        
        # Explicit reference patterns (Layer 1)
        self.explicit_patterns = [
            (r'(?:relates? to|references?)\s+([A-Z][\w\s\-]{2,50})', 'REFERENCES', 1.0),
            (r'(?:depends? on|requires?|needs)\s+([A-Z][\w\s\-]{2,50})', 'DEPENDS_ON', 1.0),
            (r'(?:similar to|like)\s+([A-Z][\w\s\-]{2,50})', 'SIMILAR_TO', 0.9),
            (r'(?:implements?|follows?)\s+([A-Z][\w\s\-]{2,50})', 'IMPLEMENTS', 0.9),
            (r'(?:alternative to|instead of)\s+([A-Z][\w\s\-]{2,50})', 'ALTERNATIVE_TO', 0.9),
            (r'(?:addresses|solves)\s+([A-Z][\w\s\-]{2,50})', 'ADDRESSES', 0.8),
        ]
        
        # Node ID pattern (Layer 2)
        self.node_id_pattern = re.compile(r'\b([DP]-[a-f0-9]{8})\b')
        
    def detect_mkg_availability(self) -> bool:
        """
        Auto-detect if local LLM (llamacpp) is available.

        Returns:
            True if llamacpp is available and has models loaded, False otherwise
        """
        if not MKG_AVAILABLE:
            return False

        try:
            # Try to reach llamacpp models endpoint (OpenAI-compatible)
            response = requests.get(
                f'{self.llm_base_url}/models',
                timeout=3
            )

            if response.status_code == 200:
                models_data = response.json()
                # Check if any models are loaded
                models = models_data.get('models', models_data.get('data', []))
                if models and len(models) > 0:
                    model_name = models[0].get('id', models[0].get('name', 'unknown'))
                    print(f"  📦 Local LLM detected: {model_name}")
                    return True
        except Exception as e:
            print(f"  ⚠️ LLM detection failed: {e}")

        return False
    
    def load_extraction_state(self, state_path: Path) -> Dict:
        """
        Load extraction state from previous run.
        
        Returns:
            State dictionary with last_run_timestamp and nodes_processed
        """
        if not state_path.exists():
            return {
                'last_run_timestamp': None,
                'nodes_processed': [],
                'total_edges': 0,
                'mode': 'full'
            }
        
        try:
            with open(state_path, 'r') as f:
                return json.load(f)
        except:
            return {
                'last_run_timestamp': None,
                'nodes_processed': [],
                'total_edges': 0,
                'mode': 'full'
            }
    
    def save_extraction_state(self, state_path: Path, nodes_processed: List[str], mode: str):
        """
        Save extraction state for future incremental runs.
        """
        state = {
            'last_run_timestamp': datetime.now().isoformat(),
            'nodes_processed': nodes_processed,
            'total_edges': self.stats['total_edges_created'],
            'mode': mode
        }
        
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2)
        
        print(f"\n💾 Extraction state saved to: {state_path}")
    
    def fetch_all_nodes(self) -> List[Dict]:
        """
        Fetch all nodes from FalkorDB with pagination.

        FalkorDB has a 10,000 row limit on RETURN queries, so we paginate
        using ORDER BY n.id to ensure we get all nodes.

        Returns:
            List of node dictionaries with id, type, and text content
        """
        print("📥 Fetching all nodes from FalkorDB...")

        all_nodes = []
        last_id = None
        batch_num = 0
        BATCH_SIZE = 10000

        while True:
            batch_num += 1

            # Build paginated query
            if last_id is None:
                query = """
                MATCH (n)
                WHERE n:Decision OR n:Pattern OR n:Failure
                WITH n ORDER BY n.id
                RETURN n.id AS id,
                       labels(n)[0] AS type,
                       n.description AS description,
                       n.rationale AS rationale,
                       n.name AS name,
                       n.implementation AS implementation,
                       n.context AS context,
                       n.attempt AS attempt,
                       n.reason_failed AS reason_failed,
                       n.lesson_learned AS lesson_learned
                LIMIT 10000
                """
            else:
                query = f"""
                MATCH (n)
                WHERE (n:Decision OR n:Pattern OR n:Failure) AND n.id > "{last_id}"
                WITH n ORDER BY n.id
                RETURN n.id AS id,
                       labels(n)[0] AS type,
                       n.description AS description,
                       n.rationale AS rationale,
                       n.name AS name,
                       n.implementation AS implementation,
                       n.context AS context,
                       n.attempt AS attempt,
                       n.reason_failed AS reason_failed,
                       n.lesson_learned AS lesson_learned
                LIMIT 10000
                """

            result = self.client.db.graph.query(query)

            if not result.result_set:
                break

            batch_nodes = []
            for row in result.result_set:
                node = {
                    'id': row[0],
                    'type': row[1],
                }

                # Extract text content based on node type
                if row[1] == 'Decision':
                    node['text'] = f"{row[2] or ''} {row[3] or ''}".strip()
                elif row[1] == 'Pattern':
                    node['text'] = f"{row[4] or ''} {row[5] or ''} {row[6] or ''}".strip()
                elif row[1] == 'Failure':
                    node['text'] = f"{row[7] or ''} {row[8] or ''} {row[9] or ''}".strip()
                else:
                    node['text'] = ''

                if node['text']:  # Only include nodes with text content
                    batch_nodes.append(node)
                    last_id = row[0]

            all_nodes.extend(batch_nodes)
            print(f"  📦 Batch {batch_num}: {len(batch_nodes)} nodes (total: {len(all_nodes)})")

            # If we got less than BATCH_SIZE, we've reached the end
            if len(result.result_set) < BATCH_SIZE:
                break

        print(f"✅ Fetched {len(all_nodes)} nodes total")
        return all_nodes
    
    def fetch_new_nodes(self, since_timestamp: str) -> List[Dict]:
        """
        Fetch only nodes created after given timestamp (incremental mode).
        
        Args:
            since_timestamp: ISO format timestamp
        
        Returns:
            List of new nodes
        """
        print(f"🔄 Fetching nodes created after {since_timestamp}...")
        
        query = f"""
        MATCH (n)
        WHERE (n:Decision OR n:Pattern OR n:Failure) AND n.timestamp > '{since_timestamp}'
        RETURN n.id AS id, 
               n.type AS type,
               n.description AS description,
               n.rationale AS rationale,
               n.name AS name,
               n.implementation AS implementation,
               n.context AS context,
               n.attempt AS attempt,
               n.reason_failed AS reason_failed,
               n.lesson_learned AS lesson_learned,
               n.timestamp AS timestamp
        """
        
        result = self.client.db.graph.query(query)
        nodes = []
        
        if not result.result_set:
            print("ℹ️  No new nodes found")
            return nodes
        
        for row in result.result_set:
            node = {
                'id': row[0],
                'type': row[1],
            }
            
            # Extract text content based on node type
            if row[1] == 'Decision':
                node['text'] = f"{row[2] or ''} {row[3] or ''}".strip()
            elif row[1] == 'Pattern':
                node['text'] = f"{row[4] or ''} {row[5] or ''} {row[6] or ''}".strip()
            elif row[1] == 'Failure':
                node['text'] = f"{row[7] or ''} {row[8] or ''} {row[9] or ''}".strip()
            else:
                node['text'] = ''
            
            if node['text']:  # Only include nodes with text content
                nodes.append(node)
        
        print(f"✅ Fetched {len(nodes)} new nodes")
        return nodes
    
    def extract_explicit_references(self, nodes: List[Dict]) -> List[Tuple[str, str, str, float]]:
        """
        Layer 1: Extract explicit references using regex patterns.
        
        Returns:
            List of (source_id, target_id, relationship_type, weight) tuples
        """
        print("\n🔍 Layer 1: Detecting explicit references...")
        relationships = []
        
        # Build a lookup map: text_fragment -> node_id
        text_to_id = {}
        for node in nodes:
            # Use first few words as potential reference targets
            words = node['text'].split()[:10]
            for i in range(3, min(len(words) + 1, 10)):
                fragment = ' '.join(words[:i])
                if fragment not in text_to_id:
                    text_to_id[fragment] = node['id']
        
        for source_node in nodes:
            source_id = source_node['id']
            text = source_node['text']
            
            for pattern, rel_type, weight in self.explicit_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                
                for match in matches:
                    referenced_text = match.group(1).strip()
                    
                    # Try to find matching node
                    target_id = text_to_id.get(referenced_text)
                    
                    if target_id and target_id != source_id:
                        relationships.append((source_id, target_id, rel_type, weight))
                        self.stats['explicit_references'] += 1
        
        print(f"  ✅ Found {len(relationships)} explicit references")
        return relationships
    
    def extract_cross_references(self, nodes: List[Dict]) -> List[Tuple[str, str, str, float]]:
        """
        Layer 2: Extract cross-references by detecting node IDs in text.
        
        Returns:
            List of (source_id, target_id, relationship_type, weight) tuples
        """
        print("\n🔗 Layer 2: Detecting cross-references...")
        relationships = []
        
        # Build set of valid node IDs
        valid_ids = {node['id'] for node in nodes}
        
        for source_node in nodes:
            source_id = source_node['id']
            text = source_node['text']
            
            # Find all node IDs mentioned in text
            id_matches = self.node_id_pattern.findall(text)
            
            for target_id in id_matches:
                if target_id in valid_ids and target_id != source_id:
                    relationships.append((source_id, target_id, 'REFERENCES', 0.8))
                    self.stats['cross_references'] += 1
        
        print(f"  ✅ Found {len(relationships)} cross-references")
        return relationships
    
    def extract_semantic_similarity(self, nodes: List[Dict], threshold: float = 0.7) -> List[Tuple[str, str, str, float]]:
        """
        Layer 3: Extract semantic similarity using FAISS and sentence embeddings.
        
        Args:
            nodes: List of nodes with text content
            threshold: Minimum similarity score (0.7+ recommended)
        
        Returns:
            List of (source_id, target_id, relationship_type, weight) tuples
        """
        print(f"\n🧠 Layer 3: Computing semantic similarity (threshold={threshold})...")
        relationships = []
        
        if len(nodes) < 2:
            print("  ⚠️  Not enough nodes for similarity comparison")
            return relationships
        
        # Extract texts and IDs
        texts = [node['text'] for node in nodes]
        node_ids = [node['id'] for node in nodes]
        
        print(f"  📊 Encoding {len(texts)} texts...")
        embeddings = self.embedding_model.encode(texts, batch_size=128, show_progress_bar=True)
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Build FAISS index
        print("  🏗️  Building FAISS index...")
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)  # Inner product = cosine similarity for normalized vectors
        index.add(embeddings.astype('float32'))
        
        # Search for top-50 similar nodes per node
        print("  🔎 Finding similar nodes...")
        k = min(50, len(nodes))  # Top-50 or fewer if less nodes
        similarities, indices = index.search(embeddings.astype('float32'), k)
        
        # Extract relationships above threshold
        for i, (source_id, similar_scores, similar_indices) in enumerate(zip(node_ids, similarities, indices)):
            for score, idx in zip(similar_scores, similar_indices):
                if idx != i and score >= threshold:  # Exclude self and below threshold
                    target_id = node_ids[idx]
                    
                    # Use score as weight (0.7-1.0 range)
                    weight = float(score) * 0.6  # Scale to 0.42-0.6 range
                    
                    relationships.append((source_id, target_id, 'SEMANTICALLY_SIMILAR', weight))
                    self.stats['semantic_similarity'] += 1
        
        print(f"  ✅ Found {len(relationships)} semantic similarities")
        return relationships
    
    def extract_hierarchical_relationships(self, nodes: List[Dict]) -> List[Tuple[str, str, str, float]]:
        """
        Layer 4: Extract hierarchical relationships based on patterns.
        
        For now, this creates IMPLEMENTS relationships between Patterns and Decisions
        based on keyword overlap.
        
        Returns:
            List of (source_id, target_id, relationship_type, weight) tuples
        """
        print("\n🏛️  Layer 4: Detecting hierarchical relationships...")
        relationships = []
        
        # Separate nodes by type
        decisions = [n for n in nodes if n['type'] == 'Decision']
        patterns = [n for n in nodes if n['type'] == 'Pattern']
        
        # Pattern implements Decision if they share significant keywords
        for pattern in patterns:
            pattern_words = set(re.findall(r'\b\w{4,}\b', pattern['text'].lower()))
            
            for decision in decisions:
                decision_words = set(re.findall(r'\b\w{4,}\b', decision['text'].lower()))
                
                # Compute Jaccard similarity
                if decision_words:
                    overlap = len(pattern_words & decision_words)
                    union = len(pattern_words | decision_words)
                    jaccard = overlap / union if union > 0 else 0
                    
                    # If significant overlap (>0.3), create relationship
                    if jaccard > 0.3:
                        weight = min(jaccard, 0.8)  # Cap at 0.8
                        relationships.append((pattern['id'], decision['id'], 'IMPLEMENTS', weight))
                        self.stats['hierarchical'] += 1
        
        print(f"  ✅ Found {len(relationships)} hierarchical relationships")
        return relationships
    
    def enhance_with_llm(self, relationships: List[Tuple[str, str, str, float]], nodes: List[Dict]) -> List[Tuple]:
        """
        Layer 5: Enhance semantic relationships with LLM classification.
        
        Args:
            relationships: List of (source_id, target_id, rel_type, weight) tuples
            nodes: List of all nodes for text lookup
        
        Returns:
            Enhanced relationships with specific types and reasoning metadata
        """
        print(f"\n✨ Layer 5: LLM-enhanced relationship classification...")
        
        if not self.mkg_available:
            print("  ⚠️  MKG not available, skipping LLM enhancement")
            return relationships
        
        # Build node lookup cache
        if not self.node_cache:
            self.node_cache = {node['id']: node for node in nodes}
        
        # Filter only semantic similarity relationships for enhancement
        semantic_rels = [(s, t, rt, w) for s, t, rt, w in relationships if rt == 'SEMANTICALLY_SIMILAR']
        other_rels = [(s, t, rt, w) for s, t, rt, w in relationships if rt != 'SEMANTICALLY_SIMILAR']
        
        if len(semantic_rels) == 0:
            print("  ℹ️  No semantic relationships to enhance")
            return relationships
        
        print(f"  📊 Enhancing {len(semantic_rels)} semantic relationships with MKG local LLM...")
        
        enhanced_rels = []
        batch_size = 10
        total_batches = (len(semantic_rels) + batch_size - 1) // batch_size
        
        for batch_idx in range(0, len(semantic_rels), batch_size):
            batch = semantic_rels[batch_idx:batch_idx + batch_size]
            batch_num = batch_idx // batch_size + 1
            
            print(f"  🔄 Processing batch {batch_num}/{total_batches}...", end='\r')
            
            # Process each relationship in batch
            for source_id, target_id, rel_type, weight in batch:
                source_node = self.node_cache.get(source_id)
                target_node = self.node_cache.get(target_id)
                
                if not source_node or not target_node:
                    enhanced_rels.append((source_id, target_id, rel_type, weight))
                    continue
                
                # Prepare LLM prompt
                prompt = f"""Analyze these two knowledge nodes and classify their relationship.

Node A (ID: {source_id}, Type: {source_node['type']}):
{source_node['text'][:500]}

Node B (ID: {target_id}, Type: {target_node['type']}):
{target_node['text'][:500]}

Choose ONE relationship type:
- IMPLEMENTS: B implements concept from A
- EXTENDS: B extends/builds upon A
- CONTRADICTS: B contradicts A
- DEPENDS_ON: B depends on A
- ALTERNATIVE_TO: B is alternative approach to A
- ADDRESSES: B addresses problem in A
- SEMANTICALLY_SIMILAR: General similarity (default)

Respond ONLY with valid JSON:
{{
  "relationship_type": "...",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation in 1-2 sentences"
}}"""
                
                try:
                    # Query local LLM via OpenAI-compatible endpoint (llamacpp)
                    response = requests.post(
                        f'{self.llm_base_url}/chat/completions',
                        json={
                            'model': 'local',  # llamacpp ignores this, uses loaded model
                            'messages': [
                                {'role': 'system', 'content': 'You are a relationship classifier. Respond only with valid JSON.'},
                                {'role': 'user', 'content': prompt}
                            ],
                            'max_tokens': 200,
                            'temperature': 0.3  # Lower temp for more consistent classification
                        },
                        timeout=30
                    )

                    if response.status_code == 200:
                        result = response.json()
                        # Extract content from OpenAI-compatible response format
                        choices = result.get('choices', [])
                        if choices:
                            llm_response = choices[0].get('message', {}).get('content', '').strip()
                        else:
                            llm_response = ''
                        
                        # Parse JSON response
                        try:
                            # Extract JSON from response (might have markdown code blocks)
                            if '```json' in llm_response:
                                llm_response = llm_response.split('```json')[1].split('```')[0].strip()
                            elif '```' in llm_response:
                                llm_response = llm_response.split('```')[1].split('```')[0].strip()
                            
                            classification = json.loads(llm_response)
                            
                            new_rel_type = classification.get('relationship_type', 'SEMANTICALLY_SIMILAR')
                            llm_confidence = classification.get('confidence', weight)
                            reasoning = classification.get('reasoning', '')
                            
                            # Create enhanced relationship with metadata
                            enhanced_rels.append((
                                source_id,
                                target_id,
                                new_rel_type,
                                llm_confidence,
                                {'reasoning': reasoning, 'llm_classified': True}
                            ))
                            
                            self.stats['llm_enhanced'] += 1
                            
                        except json.JSONDecodeError:
                            # If JSON parsing fails, keep original
                            enhanced_rels.append((source_id, target_id, rel_type, weight))
                    else:
                        # If request fails, keep original
                        enhanced_rels.append((source_id, target_id, rel_type, weight))
                        
                except requests.RequestException:
                    # If request fails, keep original
                    enhanced_rels.append((source_id, target_id, rel_type, weight))
        
        print(f"\n  ✅ Enhanced {self.stats['llm_enhanced']} relationships with LLM classification")
        
        # Combine enhanced semantic rels with other relationship types
        return enhanced_rels + other_rels
    
    def create_edges(self, relationships: List[Tuple], enhanced_metadata: bool = False) -> int:
        """
        Create edges in FalkorDB from relationship tuples.
        
        Args:
            relationships: List of tuples - either (source_id, target_id, rel_type, weight)
                          or (source_id, target_id, rel_type, weight, metadata_dict)
            enhanced_metadata: If True, relationships may include metadata dict
        
        Returns:
            Number of edges successfully created
        """
        print(f"\n💾 Creating {len(relationships)} edges in FalkorDB...")
        
        created = 0
        errors = 0
        
        # Deduplicate relationships (keep highest weight)
        unique_rels = {}
        for rel_tuple in relationships:
            if len(rel_tuple) == 5:
                source_id, target_id, rel_type, weight, metadata = rel_tuple
            else:
                source_id, target_id, rel_type, weight = rel_tuple
                metadata = {}
            
            key = (source_id, target_id, rel_type)
            if key not in unique_rels or unique_rels[key][0] < weight:
                unique_rels[key] = (weight, metadata)
        
        print(f"  📦 Deduplicated to {len(unique_rels)} unique relationships")
        
        for (source_id, target_id, rel_type), (weight, metadata) in unique_rels.items():
            try:
                # Build properties with metadata
                properties = {'weight': weight, 'created_at': datetime.now().isoformat()}
                properties.update(metadata)
                
                self.client.db.create_relationship(
                    from_id=source_id,
                    to_id=target_id,
                    rel_type=rel_type,
                    properties=properties
                )
                created += 1
                self.stats['nodes_with_edges'].add(source_id)
                self.stats['nodes_with_edges'].add(target_id)
                
                if created % 100 == 0:
                    print(f"  ✅ Created {created} edges...", end='\r')
                    
            except Exception as e:
                errors += 1
                if errors <= 5:  # Only print first 5 errors
                    print(f"\n  ⚠️  Error creating edge {source_id} -> {target_id}: {e}")
        
        print(f"\n  ✅ Successfully created {created} edges ({errors} errors)")
        self.stats['total_edges_created'] = created
        return created
    
    def generate_report(self, output_path: Optional[Path] = None) -> Dict:
        """
        Generate extraction statistics report.
        
        Args:
            output_path: Optional path to save JSON report
        
        Returns:
            Report dictionary
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'statistics': {
                'nodes_processed': self.stats['nodes_processed'],
                'nodes_with_edges': len(self.stats['nodes_with_edges']),
                'connectivity_percentage': round(
                    (len(self.stats['nodes_with_edges']) / self.stats['nodes_processed'] * 100) 
                    if self.stats['nodes_processed'] > 0 else 0, 2
                ),
                'total_edges_created': self.stats['total_edges_created'],
            },
            'edges_by_layer': {
                'layer_1_explicit_references': self.stats['explicit_references'],
                'layer_2_cross_references': self.stats['cross_references'],
                'layer_3_semantic_similarity': self.stats['semantic_similarity'],
                'layer_4_hierarchical': self.stats['hierarchical'],
                'layer_5_llm_enhanced': self.stats['llm_enhanced'],
            }
        }
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n📄 Report saved to: {output_path}")
        
        return report
    
    def run(self, semantic_threshold: float = 0.7, output_report: Optional[Path] = None, 
            enhance_with_llm: Optional[bool] = None, incremental: bool = False, 
            last_extraction_state: Optional[Path] = None) -> Dict:
        """
        Run the complete relationship extraction pipeline.
        
        Args:
            semantic_threshold: Minimum similarity score for Layer 3 (default: 0.7)
            output_report: Optional path to save extraction report
        
        Returns:
            Extraction statistics report
        """
        print("\n" + "="*70)
        print("🚀 RELATIONSHIP EXTRACTION PIPELINE")
        print("="*70)
        
        # Auto-detect LLM enhancement if not explicitly set
        if enhance_with_llm is None:
            enhance_with_llm = self.mkg_available
            if enhance_with_llm:
                print("✨ MKG detected - LLM enhancement enabled")
            else:
                print("⚡ MKG not available - running without LLM enhancement")
        elif enhance_with_llm and not self.mkg_available:
            print("⚠️  Warning: --force-llm requested but MKG not available")
            enhance_with_llm = False
        elif not enhance_with_llm:
            print("⚡ LLM enhancement disabled via --no-llm flag")
        
        # Determine extraction mode
        state_path = Path('reports/extraction_state.json')
        extraction_state = self.load_extraction_state(state_path) if incremental else None
        
        # Step 1: Fetch nodes (all or delta)
        if incremental and extraction_state and extraction_state['last_run_timestamp']:
            print(f"\n🔄 INCREMENTAL MODE - processing delta since {extraction_state['last_run_timestamp'][:19]}")
            new_nodes = self.fetch_new_nodes(extraction_state['last_run_timestamp'])
            
            if len(new_nodes) == 0:
                print("\nℹ️  No new nodes to process. Exiting.")
                return self.generate_report(output_report)
            
            # For incremental mode, also fetch ALL nodes for cross-relationships
            print("\n📚 Fetching all existing nodes for cross-relationship detection...")
            all_nodes = self.fetch_all_nodes()
            
            # Build node sets
            new_node_ids = {n['id'] for n in new_nodes}
            existing_nodes = [n for n in all_nodes if n['id'] not in new_node_ids]
            
            print(f"\n📊 Incremental stats: {len(new_nodes)} new nodes, {len(existing_nodes)} existing nodes")
            
            # Process relationships:
            # 1. New ↔ New
            # 2. New ↔ Existing (but not Existing ↔ Existing)
            nodes = all_nodes  # Use all nodes for detection
            self.stats['nodes_processed'] = len(new_nodes)  # Track only new nodes
            mode = 'incremental'
        else:
            print("\n🔄 FULL MODE - processing all nodes")
            nodes = self.fetch_all_nodes()
            self.stats['nodes_processed'] = len(nodes)
            mode = 'full'
        
        if len(nodes) == 0:
            print("\n⚠️  No nodes found in database. Exiting.")
            return self.generate_report(output_report)
        
        # Step 2: Run all extraction layers
        all_relationships = []
        
        all_relationships.extend(self.extract_explicit_references(nodes))
        all_relationships.extend(self.extract_cross_references(nodes))
        all_relationships.extend(self.extract_semantic_similarity(nodes, threshold=semantic_threshold))
        all_relationships.extend(self.extract_hierarchical_relationships(nodes))
        
        # Step 2.5: Enhance with LLM if enabled
        if enhance_with_llm:
            all_relationships = self.enhance_with_llm(all_relationships, nodes)
        
        # Step 3: Create edges
        self.create_edges(all_relationships, enhanced_metadata=enhance_with_llm)
        
        # Step 4: Generate report
        print("\n" + "="*70)
        print("📊 EXTRACTION SUMMARY")
        print("="*70)
        report = self.generate_report(output_report)
        
        print(f"\nNodes processed: {report['statistics']['nodes_processed']}")
        print(f"Nodes with edges: {report['statistics']['nodes_with_edges']} ({report['statistics']['connectivity_percentage']}%)")
        print(f"Total edges created: {report['statistics']['total_edges_created']}")
        print(f"\nEdges by layer:")
        for layer, count in report['edges_by_layer'].items():
            print(f"  - {layer}: {count}")
        
        print("\n" + "="*70)
        print("✅ RELATIONSHIP EXTRACTION COMPLETE")
        print("="*70 + "\n")
        
        # Save extraction state
        if incremental or mode == 'full':
            all_node_ids = [n['id'] for n in nodes]
            self.save_extraction_state(state_path, all_node_ids, mode)
        
        return report


def main():
    """
    Main entry point for relationship extraction.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract relationships between knowledge graph nodes')
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.7,
        help='Semantic similarity threshold (0.0-1.0, default: 0.7)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('reports/relationship_extraction_report.json'),
        help='Output path for extraction report'
    )
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='Disable LLM enhancement even if MKG is available'
    )
    parser.add_argument(
        '--force-llm',
        action='store_true',
        help='Force LLM enhancement (error if MKG not available)'
    )
    parser.add_argument(
        '--incremental',
        action='store_true',
        help='Only process new nodes since last extraction'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Force full re-extraction (ignore incremental state)'
    )
    
    args = parser.parse_args()
    
    # Initialize client
    print("🔌 Connecting to FalkorDB...")
    client = GraphitiClient()
    
    # Determine LLM enhancement mode
    enhance_llm = None
    if args.no_llm:
        enhance_llm = False
    elif args.force_llm:
        enhance_llm = True
    # else: None = auto-detect
    
    # Run extraction
    extractor = RelationshipExtractor(client)
    extractor.run(
        semantic_threshold=args.threshold, 
        output_report=args.output,
        enhance_with_llm=enhance_llm,
        incremental=args.incremental and not args.full
    )


if __name__ == '__main__':
    main()
