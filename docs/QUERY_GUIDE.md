# Faulkner-DB Query Guide

A practical guide to querying your knowledge graph for decisions, patterns, and failures.

---

## Quick Start

### Python REPL (Recommended)

```bash
cd /home/platano/project/faulkner-db
source venv/bin/activate
python3
```

```python
from core.graphiti_client import GraphitiClient

client = GraphitiClient()
graph = client.db.graph

# Run any Cypher query
result = graph.query("MATCH (n:Decision) RETURN n.description LIMIT 5")
for row in result.result_set:
    print(row)
```

### FalkorDB CLI (Direct)

```bash
docker exec -it faulkner-db-falkordb redis-cli
> GRAPH.QUERY faulkner "MATCH (n) RETURN count(n)"
```

### MCP Tools (Claude Desktop/Code)

```
# Use built-in MCP tools
query_decisions with query="authentication patterns"
find_related with node_id="D-abc12345" depth=2
detect_gaps
```

---

## Graph Structure

### Node Types

| Type | Prefix | Description | Key Fields |
|------|--------|-------------|------------|
| Decision | `D-` | Architectural/development decisions | `description`, `rationale`, `alternatives` |
| Pattern | `P-` | Successful implementation patterns | `name`, `implementation`, `context`, `use_cases` |
| Failure | `F-` | What didn't work and lessons learned | `attempt`, `reason_failed`, `lesson_learned` |

### Edge Types

| Type | Meaning | Example |
|------|---------|---------|
| `SEMANTICALLY_SIMILAR` | Conceptually related (vector similarity > 0.7) | Two decisions about caching |
| `IMPLEMENTS` | Pattern implements a decision | Pattern "Redis Cache" implements Decision "Use distributed caching" |
| `DEPENDS_ON` | One decision depends on another | "Use microservices" depends on "Implement API gateway" |
| `ADDRESSES` | Pattern addresses a failure | Pattern "Circuit breaker" addresses Failure "Cascade failures" |
| `SIMILAR_TO` | Explicitly marked as similar | Manual similarity annotation |
| `REFERENCES` | Direct reference in text | Decision mentions another by ID |

---

## Common Query Patterns

### 1. Basic Statistics

```cypher
// Count nodes by type
MATCH (n)
WHERE n:Decision OR n:Pattern OR n:Failure
RETURN labels(n)[0] as type, count(n) as count

// Count edges by type
MATCH ()-[r]->()
RETURN type(r) as relationship, count(*) as count
ORDER BY count DESC
```

### 2. Find Specific Nodes

```cypher
// Find decisions containing a keyword
MATCH (d:Decision)
WHERE d.description CONTAINS 'authentication'
RETURN d.id, d.description, d.rationale
LIMIT 10

// Find patterns by name
MATCH (p:Pattern)
WHERE p.name CONTAINS 'cache'
RETURN p.id, p.name, p.implementation

// Find recent failures
MATCH (f:Failure)
RETURN f.id, f.attempt, f.lesson_learned
ORDER BY f.timestamp DESC
LIMIT 5
```

### 3. Explore Relationships

```cypher
// Find all connections for a specific node
MATCH (n {id:"D-30cdeec6"})-[r]-(connected)
RETURN n.description, type(r), connected.description
LIMIT 20

// Find nodes with most connections
MATCH (n)-[r]-()
WITH n, count(r) as connections
WHERE connections > 10
RETURN n.id, labels(n)[0] as type, n.description, connections
ORDER BY connections DESC
LIMIT 10
```

### 4. Typed Relationship Queries

```cypher
// Find patterns that implement decisions
MATCH (d:Decision)<-[r:IMPLEMENTS]-(p:Pattern)
RETURN d.description as decision, p.name as pattern, p.implementation

// Find decisions with dependencies
MATCH (d1:Decision)-[r:DEPENDS_ON]->(d2:Decision)
RETURN d1.description as depends, d2.description as on_decision

// Find patterns that address failures
MATCH (f:Failure)<-[r:ADDRESSES]-(p:Pattern)
RETURN f.attempt as failed_approach, f.lesson_learned, p.name as solution
```

### 5. Path Finding

```cypher
// Find shortest path between two nodes
MATCH path = shortestPath(
  (a {id:"D-30cdeec6"})-[*..5]-(b {id:"P-abc12345"})
)
RETURN path

// Find all paths up to 3 hops
MATCH path = (start {id:"D-30cdeec6"})-[*1..3]-(end)
RETURN path
LIMIT 20
```

### 6. Similarity Clusters

```cypher
// Find clusters of similar decisions
MATCH (d1:Decision)-[r:SEMANTICALLY_SIMILAR]-(d2:Decision)
WHERE r.weight > 0.8
RETURN d1.description, d2.description, r.weight
ORDER BY r.weight DESC
LIMIT 20

// Find the most connected semantic cluster
MATCH (n)-[r:SEMANTICALLY_SIMILAR]-()
WITH n, count(r) as similar_count
WHERE similar_count > 5
RETURN n.id, labels(n)[0], n.description, similar_count
ORDER BY similar_count DESC
LIMIT 10
```

---

## Use Cases

### Use Case 1: "What decisions relate to my current problem?"

**Scenario**: You're implementing user authentication and want to find relevant past decisions.

```python
from core.graphiti_client import GraphitiClient

client = GraphitiClient()
graph = client.db.graph

# Search for authentication-related decisions
result = graph.query("""
MATCH (d:Decision)
WHERE d.description CONTAINS 'auth' OR d.description CONTAINS 'login'
   OR d.description CONTAINS 'session' OR d.description CONTAINS 'token'
RETURN d.id, d.description, d.rationale
LIMIT 10
""")

for row in result.result_set:
    print(f"[{row[0]}] {row[1][:80]}...")
    if row[2]:
        print(f"  Rationale: {row[2][:100]}...")
    print()
```

### Use Case 2: "What patterns can help with this failure?"

**Scenario**: You experienced a cascade failure and want to find patterns that address similar issues.

```python
# Find failures about cascade/timeout issues
result = graph.query("""
MATCH (f:Failure)
WHERE f.attempt CONTAINS 'cascade' OR f.attempt CONTAINS 'timeout'
   OR f.reason_failed CONTAINS 'cascade'
OPTIONAL MATCH (f)<-[r:ADDRESSES]-(p:Pattern)
RETURN f.attempt, f.lesson_learned, collect(p.name) as solutions
LIMIT 5
""")

for row in result.result_set:
    print(f"Failed: {row[0][:60]}...")
    print(f"Lesson: {row[1][:80]}...")
    if row[2]:
        print(f"Solutions: {row[2]}")
    print()
```

### Use Case 3: "What's the context around this decision?"

**Scenario**: You found a decision and want to understand its full context - what it depends on, what implements it, and related concepts.

```python
decision_id = "D-30cdeec6"  # Replace with actual ID

# Get decision details and all relationships
result = graph.query(f"""
MATCH (d {{id: "{decision_id}"}})
OPTIONAL MATCH (d)-[r]-(connected)
RETURN d.description, d.rationale,
       collect(DISTINCT {{type: type(r), node: connected.description}}) as connections
""")

if result.result_set:
    row = result.result_set[0]
    print(f"Decision: {row[0]}")
    print(f"Rationale: {row[1]}")
    print(f"\nConnections:")
    for conn in row[2]:
        print(f"  --[{conn['type']}]--> {conn['node'][:60]}...")
```

### Use Case 4: "Find knowledge gaps"

**Scenario**: Identify areas where knowledge is incomplete or isolated.

```python
# Find isolated nodes (no connections)
result = graph.query("""
MATCH (n)
WHERE (n:Decision OR n:Pattern OR n:Failure)
  AND NOT (n)--()
RETURN labels(n)[0] as type, n.id, n.description
LIMIT 20
""")

print("Isolated nodes (potential knowledge gaps):")
for row in result.result_set:
    print(f"  [{row[0]}] {row[1]}: {row[2][:50]}...")

# Find decisions without patterns
result = graph.query("""
MATCH (d:Decision)
WHERE NOT (d)<-[:IMPLEMENTS]-(:Pattern)
RETURN d.id, d.description
LIMIT 10
""")

print("\nDecisions without implementation patterns:")
for row in result.result_set:
    print(f"  {row[0]}: {row[1][:60]}...")
```

### Use Case 5: "What have we learned from failures?"

**Scenario**: Review lessons learned to avoid repeating mistakes.

```python
# Get all failures with their lessons and any addressing patterns
result = graph.query("""
MATCH (f:Failure)
OPTIONAL MATCH (f)<-[:ADDRESSES]-(p:Pattern)
RETURN f.attempt, f.reason_failed, f.lesson_learned,
       collect(p.name) as addressing_patterns
ORDER BY f.timestamp DESC
LIMIT 10
""")

for row in result.result_set:
    print(f"Attempted: {row[0][:60]}...")
    print(f"Failed because: {row[1][:80]}...")
    print(f"Lesson: {row[2][:80]}...")
    if row[3] and row[3][0]:
        print(f"Patterns that help: {row[3]}")
    print("-" * 60)
```

### Use Case 6: "Trace decision dependencies"

**Scenario**: Understand the dependency chain for a major decision.

```python
# Find all decisions in a dependency chain
result = graph.query("""
MATCH path = (d:Decision)-[:DEPENDS_ON*1..3]->(dep:Decision)
WHERE d.id = "D-30cdeec6"
RETURN d.description,
       [n in nodes(path) | n.description] as dependency_chain
""")

if result.result_set:
    for row in result.result_set:
        print(f"Starting from: {row[0][:50]}...")
        print("Dependency chain:")
        for i, dep in enumerate(row[1]):
            print(f"  {'  ' * i}-> {dep[:50]}...")
```

### Use Case 7: "Find cross-cutting patterns"

**Scenario**: Identify patterns that appear across multiple contexts.

```python
# Find patterns connected to the most diverse set of decisions
result = graph.query("""
MATCH (p:Pattern)-[r]-(d:Decision)
WITH p, count(DISTINCT d) as decision_count, collect(d.description) as decisions
WHERE decision_count > 2
RETURN p.name, p.implementation, decision_count, decisions[0..3] as sample_decisions
ORDER BY decision_count DESC
LIMIT 10
""")

for row in result.result_set:
    print(f"Pattern: {row[0]}")
    print(f"Implementation: {row[1][:80]}...")
    print(f"Connected to {row[2]} decisions")
    print(f"Examples: {[d[:40] for d in row[3]]}")
    print()
```

---

## Performance Tips

1. **Use LIMIT**: Always add `LIMIT` to exploratory queries to avoid returning massive result sets.

2. **Index usage**: The graph indexes nodes by `id`. Use `{id: "xxx"}` for fast lookups.

3. **Avoid full scans**: Instead of `MATCH (n) WHERE n.description CONTAINS 'x'`, consider using the MCP `query_decisions` tool which uses vector search.

4. **Batch operations**: For multiple lookups, use `IN` clauses:
   ```cypher
   MATCH (n) WHERE n.id IN ["D-abc", "P-xyz", "F-123"]
   RETURN n
   ```

5. **Profile queries**: Use `GRAPH.PROFILE` in redis-cli to analyze query performance:
   ```
   GRAPH.PROFILE faulkner "MATCH (n)-[r]-(m) RETURN count(*)"
   ```

---

## MCP Tool Integration

Your Faulkner-DB MCP server exposes these high-level tools:

| Tool | Use For | Example |
|------|---------|---------|
| `query_decisions` | Semantic search with vector + graph hybrid | "find authentication patterns" |
| `find_related` | Graph traversal from a node | Start at decision, explore 2 hops |
| `detect_gaps` | NetworkX structural analysis | Find isolated clusters, missing connections |
| `get_timeline` | Temporal knowledge evolution | How decisions evolved over time |
| `add_decision` | Add new decision | Capture current decision with context |
| `add_pattern` | Add new pattern | Document successful implementation |
| `add_failure` | Add new failure | Record what didn't work |

### Example MCP Usage in Claude

```
User: What do we know about caching strategies?

Claude: Let me search your knowledge graph.
[Uses query_decisions with query="caching strategies"]

Found 5 relevant items:
1. Decision: Use Redis for session caching
2. Pattern: Cache-aside pattern implementation
3. Failure: Attempted in-memory caching (failed due to scaling)
...
```

---

## Appendix: Full Schema Reference

### Decision Node
```
{
  id: "D-xxxxxxxx",
  type: "Decision",
  description: "What was decided",
  rationale: "Why this decision was made",
  alternatives: ["Option A", "Option B"],
  related_to: ["D-other-id"],
  timestamp: "2025-01-15T10:30:00Z",
  source: "claude_code",
  project: "project-name"
}
```

### Pattern Node
```
{
  id: "P-xxxxxxxx",
  type: "Pattern",
  name: "Pattern Name",
  implementation: "How to implement this",
  context: "When to use this pattern",
  use_cases: ["Use case 1", "Use case 2"],
  timestamp: "2025-01-15T10:30:00Z",
  source: "claude_code",
  project: "project-name"
}
```

### Failure Node
```
{
  id: "F-xxxxxxxx",
  type: "Failure",
  attempt: "What was attempted",
  reason_failed: "Why it failed",
  lesson_learned: "What we learned",
  alternative_solution: "What worked instead",
  timestamp: "2025-01-15T10:30:00Z",
  source: "claude_code",
  project: "project-name"
}
```

### Relationship Properties
```
{
  weight: 0.85,              // Similarity/confidence score (0-1)
  llm_classified: true,      // Whether LLM enhanced this edge
  reasoning: "Explanation",  // LLM's reasoning (if classified)
  created_at: "2025-01-15"   // When relationship was created
}
```
