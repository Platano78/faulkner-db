# Faulkner DB User Guide

Welcome to Faulkner DB - your temporal knowledge graph system for capturing architectural decisions, implementation patterns, and failure learnings with full context preservation.

## Table of Contents

- [Quick Start](#quick-start)
- [Daily Workflow](#daily-workflow)
- [MCP Tools Reference](#mcp-tools-reference)
- [Visualization Guide](#visualization-guide)
- [Best Practices](#best-practices)
- [Tips & Tricks](#tips--tricks)

---

## Quick Start

### First Time Setup

1. **Ensure Docker Desktop is running**
   - Windows/Mac: Launch Docker Desktop application
   - Linux: `sudo systemctl start docker`

2. **Navigate to project**
   ```bash
   cd ~/projects/faulkner-db
   ```

3. **Start all services**
   ```bash
   cd docker
   docker-compose up -d
   ```

4. **Wait for health checks** (~30 seconds)
   ```bash
   ./validate-autostart.sh
   ```

5. **Open visualizations**
   - Browser: http://localhost:8082/static/index.html

---

## Daily Workflow

### 1. Start System

**Method A: Automatic (Configured)**
- Launch Docker Desktop
- Wait 60 seconds
- Services start automatically

**Method B: Manual**
```bash
cd ~/projects/faulkner-db/docker
docker-compose up -d
```

**Verify startup:**
```bash
./validate-autostart.sh
```

Expected output:
```
✅ Docker is running
✅ All 3 containers exist
✅ All containers healthy
✅ APIs responding
```

### 2. Add Decisions

**Via Claude Desktop (MCP):**
```
Use add_decision to record that we chose FalkorDB over Neo4j because:
- CPU-only operation (gaming-friendly)
- Redis compatibility
- Lower memory footprint
- Cypher query support
```

**What gets stored:**
- Decision content with timestamp
- Context and reasoning
- Relationships to other decisions
- Embeddings for semantic search

### 3. Query Knowledge

**Simple search:**
```
Use query_decisions to find all decisions about "database selection"
```

**Advanced search:**
```
Use query_decisions with filters:
- Category: "Infrastructure"
- Date range: 2024-01-01 to 2024-12-31
- Keywords: "performance, scaling"
```

**How it works:**
- Hybrid search: graph traversal + vector embeddings
- CrossEncoder reranking for 90%+ accuracy
- Results sorted by relevance score

### 4. Explore Visualizations

**Network Graph**
- URL: http://localhost:8082/static/index.html
- Interactive force-directed layout
- Click nodes to see details
- Drag to reposition

**Timeline View**
- URL: http://localhost:8082/static/timeline.html
- Chronological decision history
- Filter by category/date
- Zoom to specific periods

**Dashboard**
- URL: http://localhost:8082/static/dashboard.html
- Key metrics overview
- Decision trends
- Category distribution

**Gap Analysis**
- URL: http://localhost:8082/static/gaps.html
- Identify undocumented areas
- Structural holes in knowledge
- Recommended next decisions

### 5. Stop System

**Graceful shutdown:**
```bash
cd ~/projects/faulkner-db/docker
docker-compose down
```

**Emergency stop:**
```bash
docker-compose kill
```

**Note:** Data persists in Docker volumes, safe to stop anytime.

---

## MCP Tools Reference

### 1. add_decision

**Purpose:** Record architectural decisions with full context.

**Usage:**
```
Use add_decision to document:
Title: "API Gateway Selection"
Decision: "Chose Kong over AWS API Gateway"
Context: "Need on-premise solution for data sovereignty"
Alternatives: "AWS API Gateway, Apigee, Tyk"
Consequences: "Increased maintenance, better control"
```

**Parameters:**
- `title` (required): Short decision name
- `content` (required): Full decision description
- `category` (optional): Infrastructure, Architecture, etc.
- `status` (optional): Proposed, Accepted, Deprecated
- `tags` (optional): Searchable keywords

**Example Output:**
```
Decision added successfully!
ID: DEC-2024-001
Embedding generated (384 dimensions)
Related decisions found: 3
```

### 2. query_decisions

**Purpose:** Search knowledge base with hybrid semantic+graph search.

**Usage:**
```
Use query_decisions to find decisions about "caching strategy"
```

**Advanced filtering:**
```
Query decisions where:
- Keyword: "Redis"
- Category: "Infrastructure"
- Status: "Accepted"
- Limit: 10
```

**Search modes:**
- **Semantic**: Uses embeddings for conceptual matches
- **Keyword**: Exact text matching
- **Graph**: Traverse relationships
- **Hybrid** (default): Combines all three with reranking

**Example Output:**
```
Found 5 relevant decisions (95% confidence):

1. [DEC-2024-015] Redis Caching Implementation (Score: 0.94)
   "Implemented Redis for session caching..."
   Related: DEC-2024-008, DEC-2024-012

2. [DEC-2024-008] Cache Invalidation Strategy (Score: 0.89)
   "Using event-driven cache invalidation..."
```

### 3. add_pattern

**Purpose:** Document implementation patterns and their context.

**Usage:**
```
Use add_pattern to record:
Pattern: "Event Sourcing"
Context: "Order Management System"
Benefits: "Audit trail, temporal queries, event replay"
Tradeoffs: "Increased storage, eventual consistency"
Implementation: "Using Kafka for event store"
```

**When to use:**
- Documenting design patterns applied
- Recording pattern variations
- Noting implementation specifics
- Capturing lessons learned

### 4. add_failure

**Purpose:** Record system failures for organizational learning.

**Usage:**
```
Use add_failure to document:
Incident: "Payment Gateway Timeout - 2024-03-15"
Root Cause: "Third-party API rate limiting"
Impact: "15 minutes downtime, 200 failed transactions"
Resolution: "Implemented circuit breaker pattern"
Prevention: "Added retry logic with exponential backoff"
```

**Best practices:**
- Document within 24 hours of incident
- Include metrics/logs
- Link to related decisions
- Note prevention measures

### 5. find_related

**Purpose:** Discover connections between decisions, patterns, failures.

**Usage:**
```
Use find_related for decision DEC-2024-015
```

**Output shows:**
- Direct dependencies
- Influenced decisions
- Related patterns
- Connected failures
- Temporal proximity

**Use cases:**
- Impact analysis before changes
- Understanding decision context
- Finding similar past problems
- Identifying pattern usage

### 6. detect_gaps

**Purpose:** Identify undocumented architectural areas using NetworkX analysis.

**Usage:**
```
Use detect_gaps to analyze coverage for:
Component: "Authentication System"
Required areas: OAuth, JWT, MFA, Session Management
```

**Gap types detected:**
- **Structural holes**: Missing connections between clusters
- **Undocumented components**: Known areas without decisions
- **Orphan decisions**: Isolated without relationships
- **Time gaps**: Periods without decisions

**Example Output:**
```
Gaps detected in Authentication System:

1. Missing Documentation
   - MFA implementation (no decisions found)
   - Session timeout policies (no decisions found)

2. Structural Holes
   - OAuth integration ↔ API Gateway (no link)
   - JWT validation ↔ User service (weak connection)

3. Recommendations
   - Document MFA selection criteria
   - Link OAuth decision to API Gateway decision
```

### 7. get_timeline

**Purpose:** View chronological decision history with temporal analysis.

**Usage:**
```
Use get_timeline from 2024-01-01 to 2024-12-31
```

**Filters:**
- Date range
- Category
- Team/person
- Status

**Output formats:**
- Visual timeline (web UI)
- JSON data export
- Markdown summary

**Example:**
```
2024 Decision Timeline

Jan ██████ 6 decisions (Infrastructure focus)
Feb ████ 4 decisions (Architecture patterns)
Mar ████████ 8 decisions (Security hardening)
Apr ██ 2 decisions
May ██████████ 10 decisions (Performance optimization)

Key milestones:
- Jan 15: Migration to microservices decided
- Mar 10: Security audit triggered 8 decisions
- May 20: Performance crisis led to optimization wave
```

---

## Visualization Guide

### Network Graph

**Features:**
- Force-directed layout
- Node colors by type:
  - 🔵 Blue: Decisions
  - 🟢 Green: Patterns
  - 🔴 Red: Failures
- Edge thickness = relationship strength
- Hover for details
- Click for full content

**Navigation:**
- **Scroll**: Zoom in/out
- **Drag background**: Pan view
- **Drag node**: Reposition
- **Click node**: Show details panel
- **Double-click**: Center on node

**Use cases:**
- Understand decision dependencies
- Find clusters of related work
- Identify central/important decisions
- Visualize knowledge spread

### Timeline View

**Layout:**
- Horizontal time axis
- Vertical swim lanes by category
- Markers for decisions/events

**Interactions:**
- **Zoom**: Mouse wheel or pinch
- **Pan**: Click and drag
- **Filter**: Category checkboxes
- **Search**: Text filter box

**Use cases:**
- Track decision evolution
- Identify busy periods
- Correlate with project phases
- Plan future decisions

### Dashboard

**Metrics displayed:**
- Total decisions documented
- Decisions by category (pie chart)
- Decisions over time (line graph)
- Pattern adoption rate
- Failure frequency trends
- Knowledge coverage %

**Refresh rate:** Real-time

**Export:** CSV, JSON, PNG

### Gaps Analysis

**Heatmap view:**
- Rows: Components/areas
- Columns: Documentation aspects
- Color intensity: Coverage level
  - 🟢 Green: Well documented (80-100%)
  - 🟡 Yellow: Partial (50-79%)
  - 🔴 Red: Gaps (0-49%)

**Recommendations:**
- Prioritized list of areas to document
- Suggested decision templates
- Related existing decisions

---

## Best Practices

### Decision Documentation Standards

**✅ DO:**
- Write in present tense ("We choose X")
- Include context and constraints
- List alternatives considered
- State consequences (good and bad)
- Link to related decisions
- Add relevant tags for searchability
- Update status as implementation progresses

**❌ DON'T:**
- Skip the "why" - always explain reasoning
- Document implementation details (use code comments)
- Create orphan decisions without relationships
- Use jargon without definitions
- Forget to timestamp decisions

**Template:**
```
Title: [Short, descriptive name]

Context:
[What situation led to this decision?]

Decision:
[What did we decide?]

Alternatives Considered:
1. Option A - rejected because...
2. Option B - rejected because...

Consequences:
+ Positive impact 1
+ Positive impact 2
- Negative impact 1
- Mitigation for negative impact

Related Decisions:
- DEC-2024-XXX
- DEC-2024-YYY
```

### Pattern vs Decision

**Use `add_pattern` when:**
- Documenting a reusable design pattern
- Recording implementation approach
- Noting pattern variations used
- Capturing pattern-specific learnings

**Use `add_decision` when:**
- Making a one-time architectural choice
- Selecting between alternatives
- Documenting project-specific decisions
- Recording "what" was decided

**Example:**
- **Pattern**: "We use Repository Pattern for data access"
- **Decision**: "We chose PostgreSQL over MongoDB for user data"

### Failure Documentation

**Document immediately:**
- While context is fresh
- Include logs/metrics
- Note time to detect (TTD)
- Note time to resolve (TTR)

**Root cause analysis:**
- Use 5 Whys technique
- Include contributing factors
- Distinguish proximate vs root cause

**Prevention:**
- Link to follow-up decisions
- Document process changes
- Add monitoring/alerting updates

### Temporal Relationship Guidelines

**Types of relationships:**
- **Supersedes**: New decision replaces old
- **Depends on**: Requires prior decision
- **Influences**: Informed by prior decision
- **Conflicts with**: Contradicts earlier decision (requires resolution)
- **Implements**: Puts pattern into practice

**Maintaining relationships:**
- Review quarterly for accuracy
- Update when decisions change
- Remove obsolete connections
- Add new connections as discovered

---

## Tips & Tricks

### Search Optimization

**Better search queries:**
- Use specific technical terms
- Combine keywords: "Redis caching performance"
- Use category filters to narrow results
- Try semantic variations ("database" vs "data store")

**Leverage hybrid search:**
- Semantic search finds conceptually similar decisions
- Even if exact keywords don't match
- Example: "authentication" finds "login", "authorization", "identity"

### Batch Operations

**Importing multiple decisions:**
```python
# Script example (future feature)
for decision in legacy_decisions:
    mcp.add_decision(
        title=decision['title'],
        content=decision['content'],
        category=decision['category']
    )
```

### Backup & Export

**Backup FalkorDB:**
```bash
docker-compose exec falkordb redis-cli SAVE
docker cp faulkner-db-falkordb:/data/dump.rdb ./backup/
```

**Export PostgreSQL:**
```bash
docker-compose exec postgres pg_dump -U faulkner faulkner_db > backup.sql
```

**Export knowledge map:**
```bash
curl http://localhost:8082/api/export > knowledge_graph.json
```

### Performance Tips

**Large graphs (1000+ nodes):**
- Use category filters in searches
- Enable pagination in visualizations
- Consider archiving old decisions

**Slow queries:**
- Add more specific search terms
- Use date range filters
- Increase Docker memory allocation

### Integration Examples

**GitHub Actions:**
```yaml
- name: Document deployment decision
  run: |
    claude-mcp add_decision \
      --title "Production Deploy $(date)" \
      --content "Deployed v$VERSION to production"
```

**VS Code Task:**
```json
{
  "label": "Document Decision",
  "type": "shell",
  "command": "echo 'Use add_decision in Claude Desktop'"
}
```

---

## Getting Help

**Documentation:**
- [System Status](SYSTEM_STATUS.md)
- [Tech Stack](TECH_STACK.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Roadmap](ROADMAP.md)

**Quick validation:**
```bash
cd ~/projects/faulkner-db/docker
./validate-autostart.sh
```

**View logs:**
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f falkordb
docker-compose logs -f visualization
```

**Check system health:**
```bash
curl http://localhost:8082/health
```

---

**Last Updated:** 2025-11-08  
**Version:** 1.0.0