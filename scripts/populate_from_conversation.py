"""
Populate Faulkner DB with real architectural decisions from current conversation.
Uses the MCP server via stdio JSON-RPC (same as validation test).
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any

class MCPPopulator:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.python_path = self.project_root / "venv" / "bin" / "python3"
        self.server_path = self.project_root / "mcp_server" / "mcp_server.py"
        self.process = None
        self.request_id = 0

    def start_server(self):
        """Start MCP server as subprocess."""
        print("🚀 Starting MCP server...")
        self.process = subprocess.Popen(
            [str(self.python_path), str(self.server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        import time
        time.sleep(2)  # Wait for initialization

        # Initialize
        self.send_jsonrpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "populator", "version": "1.0"}
        })
        print("✅ Server initialized\n")

    def stop_server(self):
        """Stop MCP server."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def send_jsonrpc(self, method: str, params: Dict[str, Any] = None) -> Dict:
        """Send JSON-RPC request and get response."""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }

        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()

        response_line = self.process.stdout.readline()
        if not response_line:
            raise Exception("Server closed stdout")

        return json.loads(response_line)

    def add_decision(self, description: str, rationale: str, alternatives: list, related_to: list = None) -> str:
        """Add decision via MCP."""
        response = self.send_jsonrpc("tools/call", {
            "name": "add_decision",
            "arguments": {
                "description": description,
                "rationale": rationale,
                "alternatives": alternatives,
                "related_to": related_to or []
            }
        })

        text = response["result"]["content"][0]["text"]
        import re
        match = re.search(r'D-[a-f0-9]{8}', text)
        return match.group(0) if match else None

    def add_pattern(self, name: str, context: str, implementation: str, use_cases: list) -> str:
        """Add pattern via MCP."""
        response = self.send_jsonrpc("tools/call", {
            "name": "add_pattern",
            "arguments": {
                "name": name,
                "context": context,
                "implementation": implementation,
                "use_cases": use_cases
            }
        })

        text = response["result"]["content"][0]["text"]
        import re
        match = re.search(r'P-[a-f0-9]{8}', text)
        return match.group(0) if match else None

    def add_failure(self, attempt: str, reason_failed: str, lesson_learned: str, alternative_solution: str = "") -> str:
        """Add failure via MCP."""
        response = self.send_jsonrpc("tools/call", {
            "name": "add_failure",
            "arguments": {
                "attempt": attempt,
                "reason_failed": reason_failed,
                "lesson_learned": lesson_learned,
                "alternative_solution": alternative_solution
            }
        })

        text = response["result"]["content"][0]["text"]
        import re
        match = re.search(r'F-[a-f0-9]{8}', text)
        return match.group(0) if match else None

    def query_decisions(self, query: str) -> str:
        """Query decisions via MCP."""
        response = self.send_jsonrpc("tools/call", {
            "name": "query_decisions",
            "arguments": {"query": query}
        })

        return response["result"]["content"][0]["text"]


def populate_real_decisions():
    """Add real decisions from Nov 8, 2025 conversation."""

    print("=" * 60)
    print("POPULATING FAULKNER DB WITH REAL DECISIONS")
    print("=" * 60)

    populator = MCPPopulator()

    try:
        populator.start_server()

        decisions = []
        patterns = []
        failures = []

        # Decision 1: FalkorDB Choice
        print("\n[1/10] Adding FalkorDB decision...")
        d1 = populator.add_decision(
            description="Chose FalkorDB as the graph database for Faulkner DB knowledge graph system",
            rationale="FalkorDB is CPU-only (preserves GPU for gaming), uses GraphBLAS for performance, supports OpenCypher queries, runs in Docker with easy stop/start, and is production-ready. Gaming-friendly architecture was critical constraint.",
            alternatives=[
                "Neo4j - requires paid license for production, more resource-intensive, competes with gaming GPU usage",
                "ArangoDB - multi-model complexity not needed, less mature graph features",
                "NetworkX only - no persistence, loses data on restart, not production-ready",
                "Custom graph implementation - would be over-engineering, reinventing tested solutions"
            ],
            related_to=[]
        )
        decisions.append(d1)
        print(f"   ✅ {d1}")

        # Decision 2: Graphiti Framework
        print("\n[2/10] Adding Graphiti framework decision...")
        d2 = populator.add_decision(
            description="Use Graphiti framework as the temporal knowledge graph layer on top of FalkorDB",
            rationale="Graphiti provides production-ready entity extraction, relationship management, and temporal edge tracking. Extends FalkorDB with semantic capabilities without reimplementing graph algorithms. Maintained by Zep AI with active development.",
            alternatives=[
                "Build custom graph abstraction - over-engineering, would recreate Graphiti features",
                "LangChain GraphQA - less specialized, not designed for temporal knowledge",
                "Direct FalkorDB queries only - loses semantic abstraction, harder to maintain"
            ],
            related_to=[d1]
        )
        decisions.append(d2)
        print(f"   ✅ {d2}")

        # Decision 3: Production RAG Pipeline
        print("\n[3/10] Adding production RAG pipeline decision...")
        d3 = populator.add_decision(
            description="Implement hybrid search with multi-query generation + CrossEncoder reranking for Faulkner DB queries",
            rationale="Production RAG analysis showed 87% accuracy with hybrid approach vs 62% graph-only and 58% vector-only. Multi-query generation (4 variants) with parallel execution and Reciprocal Rank Fusion merging captures different query interpretations. CrossEncoder reranking (50→15 candidates) provides highest ROI improvement. All components are CPU-compatible for gaming-friendly operation.",
            alternatives=[
                "Simple vector search only - 58% accuracy, misses graph relationships",
                "Graph traversal only - 62% accuracy, misses semantic similarity",
                "Query expansion instead of multi-query - less effective than parallel queries",
                "Larger reranking window - diminishing returns beyond 15 results"
            ],
            related_to=[d2]
        )
        decisions.append(d3)
        print(f"   ✅ {d3}")

        # Decision 4: DevOracle Local Training
        print("\n[4/10] Adding DevOracle local training decision...")
        d4 = populator.add_decision(
            description="Train DevOracle locally on RTX 5080 16GB using nanochat framework instead of cloud training",
            rationale="Local training eliminates ongoing API costs, provides gaming-friendly pause/resume capabilities, uses existing RTX 5080 hardware efficiently, and allows experimentation without per-token charges. Depth 8 validation (4 hours) proves viability before depth 16 production (32 hours). Training data comes from Faulkner DB knowledge graph exports.",
            alternatives=[
                "Cloud training on Runpod/Lambda Labs - ongoing costs, no pause for gaming",
                "Use only retrieval systems without training - misses opportunity to bake knowledge into weights",
                "Fine-tune existing models - less specialized than training from scratch on domain knowledge"
            ],
            related_to=[d2]
        )
        decisions.append(d4)
        print(f"   ✅ {d4}")

        # Decision 5: Agent Genesis for Conversation Retrieval
        print("\n[5/10] Adding Agent Genesis decision...")
        d5 = populator.add_decision(
            description="Use Agent Genesis (PostgreSQL + pgvector) for conversation retrieval, separate from Faulkner DB knowledge understanding",
            rationale="Separation of concerns: Agent Genesis handles 'what conversations mentioned X' (17K+ conversations, semantic search), while Faulkner DB handles 'what is X, how does it relate to Y, how has understanding changed' (knowledge graph with temporal edges). Different problems require different tools.",
            alternatives=[
                "Use single system for both - conflates conversation history with knowledge understanding",
                "Store conversations in graph database - loses vector search efficiency",
                "Rebuild conversation search in Faulkner DB - unnecessary duplication of working system"
            ],
            related_to=[]
        )
        decisions.append(d5)
        print(f"   ✅ {d5}")

        # Pattern 1: Gaming-Friendly Infrastructure
        print("\n[6/10] Adding gaming-friendly pattern...")
        p1 = populator.add_pattern(
            name="Gaming-Friendly Development Infrastructure",
            context="Development infrastructure must not compete with gaming GPU/VRAM usage. RTX 5080 16GB needs to be available for gaming without stopping development services.",
            implementation="All services run in Docker with: (1) CPU-only components where possible (FalkorDB, embeddings, reranking), (2) Easy stop: docker-compose down, (3) Easy start: docker-compose up -d, (4) GPU services (like DevOracle training) use Ctrl+Z pause or checkpoint-based resumption, (5) Training jobs save frequent checkpoints (every 500 iterations)",
            use_cases=[
                "When designing new development infrastructure",
                "When selecting between cloud and local solutions",
                "When evaluating ML frameworks for local training",
                "When building tools for developer-gamers"
            ]
        )
        patterns.append(p1)
        print(f"   ✅ {p1}")

        # Pattern 2: MCP Tool Categorization
        print("\n[7/10] Adding MCP tool categorization pattern...")
        p2 = populator.add_pattern(
            name="MCP Tool Categorization Pattern",
            context="All MCP servers should organize tools into Query, Ingest, and Discovery categories for clear separation of concerns and better Claude orchestration",
            implementation="Tools are categorized as: Query (read-only: query_decisions, find_related, get_timeline), Ingest (write: add_decision, add_pattern, add_failure), Discovery (analysis: detect_gaps). This pattern appears in Agent Genesis, Development-Context, Faulkner DB.",
            use_cases=[
                "When designing new MCP servers",
                "When documenting existing MCP tool capabilities",
                "When teaching Claude how to use multi-tool orchestration"
            ]
        )
        patterns.append(p2)
        print(f"   ✅ {p2}")

        # Pattern 3: SDAD Methodology
        print("\n[8/10] Adding SDAD methodology pattern...")
        p3 = populator.add_pattern(
            name="SDAD Methodology for MCP Development",
            context="Systematic approach to building MCP servers: Specification → Development → Analysis → Documentation. Prevents scope creep while supporting completist infrastructure.",
            implementation="(1) Specification: Define exact tools, inputs/outputs, success criteria. (2) Development: Build with working code examples. (3) Analysis: Test with real data, validate protocol. (4) Documentation: Create usage guides, deployment docs. Anti-over-engineering but completist on infrastructure.",
            use_cases=[
                "When starting new MCP server projects",
                "When evaluating whether to build vs extend existing tools",
                "When scoping development work to prevent feature creep"
            ]
        )
        patterns.append(p3)
        print(f"   ✅ {p3}")

        # Failure 1: MemGPT Evaluation
        print("\n[9/10] Adding MemGPT failure...")
        f1 = populator.add_failure(
            attempt="Evaluated MemGPT as knowledge graph framework for Faulkner DB",
            reason_failed="MemGPT architecture is over-engineered for knowledge graph use case. Requires complex multi-agent setup, external memory tiers, and abstractions we don't need. The 'personification' of memory (treating it as a chatbot) doesn't align with structured knowledge graph queries. Would add unnecessary complexity without clear benefits over Graphiti.",
            lesson_learned="For domain-specific knowledge graphs, prefer frameworks explicitly designed for that purpose (Graphiti) over general agent frameworks repurposed for knowledge management. Agent frameworks optimize for conversation continuity, not structured knowledge retrieval.",
            alternative_solution="Used Graphiti framework which provides temporal knowledge graphs without agent abstraction overhead"
        )
        failures.append(f1)
        print(f"   ✅ {f1}")

        # Failure 2: Python Function Testing Instead of MCP Protocol
        print("\n[10/10] Adding MCP protocol testing failure...")
        f2 = populator.add_failure(
            attempt="Validated MCP server by calling Python functions directly (comprehensive_mcp_test.py)",
            reason_failed="Testing Python function implementations (handle_request) doesn't validate the actual MCP protocol that Claude Code uses. The stdio JSON-RPC communication layer wasn't tested, so we couldn't confirm the server works with real Claude Code integration.",
            lesson_learned="Always test the actual integration protocol, not just the underlying implementation. For MCP servers, this means testing stdio JSON-RPC communication via subprocess, not direct Python function calls.",
            alternative_solution="Created test_mcp_stdio.py that spawns server as subprocess and sends real JSON-RPC messages via stdin/stdout"
        )
        failures.append(f2)
        print(f"   ✅ {f2}")

        # Summary
        print("\n" + "=" * 60)
        print("✅ POPULATION COMPLETE")
        print("=" * 60)
        print(f"\nAdded to Faulkner DB:")
        print(f"  - Decisions: {len(decisions)}")
        print(f"  - Patterns: {len(patterns)}")
        print(f"  - Failures: {len(failures)}")
        print(f"  - Total nodes: {len(decisions) + len(patterns) + len(failures)}")

        # Test query
        print("\n" + "=" * 60)
        print("TESTING QUERY WITH NEW DATA")
        print("=" * 60)
        print("\nQuerying: 'Why did we choose FalkorDB?'")

        results_text = populator.query_decisions(query="Why did we choose FalkorDB?")
        print(f"\n✅ Query results:")
        print(results_text[:300] + "...")

        return {
            'decisions': decisions,
            'patterns': patterns,
            'failures': failures
        }

    finally:
        populator.stop_server()


if __name__ == "__main__":
    populate_real_decisions()
