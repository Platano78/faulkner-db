#!/usr/bin/env python3
"""
Markdown Documentation Scanner for Faulkner DB.
Extracts knowledge from markdown files in the project.
"""

import asyncio
import sys
import re
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.mcp_tools import add_decision, add_pattern, add_failure


class MarkdownScanner:
    def __init__(self):
        self.project_dir = Path("/home/platano/project/faulkner-db")
        self.decisions_found = 0
        self.patterns_found = 0
        self.failures_found = 0
        self.files_scanned = 0
        
    def find_markdown_files(self) -> List[Path]:
        """Find all markdown files in the project (excluding venv)."""
        md_files = []
        for md_file in self.project_dir.rglob("*.md"):
            # Skip venv and hidden directories
            if 'venv' not in str(md_file) and not any(p.startswith('.') for p in md_file.parts):
                md_files.append(md_file)
        return md_files
    
    def extract_sections(self, content: str) -> Dict[str, List[str]]:
        """
        Extract different sections from markdown content.
        Looks for headers that indicate decisions, patterns, or failures.
        """
        sections = {
            'decisions': [],
            'patterns': [],
            'failures': []
        }
        
        # Split into sections by headers
        lines = content.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            # Check for section headers
            line_lower = line.lower()
            
            if line.startswith('#'):
                # Save previous section
                if current_section and current_content:
                    text = '\n'.join(current_content).strip()
                    if len(text) > 50:  # Minimum content length
                        sections[current_section].append(text)
                
                # Determine new section type
                if any(kw in line_lower for kw in ['decision', 'chose', 'selected']):
                    current_section = 'decisions'
                    current_content = [line]
                elif any(kw in line_lower for kw in ['pattern', 'approach', 'implementation', 'strategy']):
                    current_section = 'patterns'
                    current_content = [line]
                elif any(kw in line_lower for kw in ['failure', 'issue', 'problem', 'error', 'fix']):
                    current_section = 'failures'
                    current_content = [line]
                else:
                    current_section = None
                    current_content = []
            elif current_section:
                current_content.append(line)
        
        # Save last section
        if current_section and current_content:
            text = '\n'.join(current_content).strip()
            if len(text) > 50:
                sections[current_section].append(text)
        
        return sections
    
    async def process_decision(self, text: str, source_file: str) -> Optional[str]:
        """Process and add a decision from markdown content."""
        # Extract description (first sentence or paragraph)
        lines = [l.strip() for l in text.split('\n') if l.strip() and not l.startswith('#')]
        if not lines:
            return None
        
        description = lines[0][:200]
        rationale = '\n'.join(lines[1:3])[:300] if len(lines) > 1 else description
        
        # Extract any mentioned alternatives
        alternatives = []
        for line in lines:
            if any(marker in line.lower() for marker in ['instead of', 'rather than', 'vs', 'versus', 'alternative']):
                alternatives.append(line[:100])
        
        try:
            result = await add_decision(
                description=f"{description} (from {Path(source_file).name})",
                rationale=rationale,
                alternatives=alternatives[:3],
                related_to=[]
            )
            return result.get('decision_id')
        except Exception as e:
            print(f"  ⚠️  Failed to add decision: {e}")
            return None
    
    async def process_pattern(self, text: str, source_file: str) -> Optional[str]:
        """Process and add a pattern from markdown content."""
        lines = [l.strip() for l in text.split('\n') if l.strip() and not l.startswith('#')]
        if not lines:
            return None
        
        # Extract name from header or first line
        header_match = re.search(r'^#+\s+(.+)$', text, re.MULTILINE)
        name = header_match.group(1)[:80] if header_match else lines[0][:80]
        
        context = '\n'.join(lines[:2])[:300]
        implementation = '\n'.join(lines)[:500]
        use_cases = [lines[0][:100]] if lines else []
        
        try:
            result = await add_pattern(
                name=f"{name} (from {Path(source_file).name})",
                context=context,
                implementation=implementation,
                use_cases=use_cases
            )
            return result.get('pattern_id')
        except Exception as e:
            print(f"  ⚠️  Failed to add pattern: {e}")
            return None
    
    async def process_failure(self, text: str, source_file: str) -> Optional[str]:
        """Process and add a failure from markdown content."""
        lines = [l.strip() for l in text.split('\n') if l.strip() and not l.startswith('#')]
        if not lines:
            return None
        
        attempt = lines[0][:200]
        reason_failed = '\n'.join(lines[1:2])[:300] if len(lines) > 1 else "See documentation"
        
        # Look for lesson learned or solution
        lesson = "See documentation for details"
        alternative = ""
        
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in ['learned', 'lesson', 'solution', 'fix']):
                lesson = line[:300]
                if i + 1 < len(lines):
                    alternative = lines[i + 1][:200]
                break
        
        try:
            result = await add_failure(
                attempt=f"{attempt} (from {Path(source_file).name})",
                reason_failed=reason_failed,
                lesson_learned=lesson,
                alternative_solution=alternative
            )
            return result.get('failure_id')
        except Exception as e:
            print(f"  ⚠️  Failed to add failure: {e}")
            return None
    
    async def scan_file(self, file_path: Path):
        """Scan a single markdown file and extract knowledge."""
        print(f"\n📄 Scanning: {file_path.name}")
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            print(f"  ❌ Error reading file: {e}")
            return
        
        # Extract sections
        sections = self.extract_sections(content)
        
        # Process decisions
        for decision_text in sections['decisions']:
            node_id = await self.process_decision(decision_text, str(file_path))
            if node_id:
                self.decisions_found += 1
                print(f"  ✅ Added decision: {node_id}")
        
        # Process patterns
        for pattern_text in sections['patterns']:
            node_id = await self.process_pattern(pattern_text, str(file_path))
            if node_id:
                self.patterns_found += 1
                print(f"  ✅ Added pattern: {node_id}")
        
        # Process failures
        for failure_text in sections['failures']:
            node_id = await self.process_failure(failure_text, str(file_path))
            if node_id:
                self.failures_found += 1
                print(f"  ✅ Added failure: {node_id}")
        
        self.files_scanned += 1
    
    async def scan_and_ingest(self):
        """Scan all markdown files and ingest knowledge."""
        print("="*60)
        print("MARKDOWN DOCUMENTATION SCANNER")
        print("="*60)
        
        # Find files
        md_files = self.find_markdown_files()
        print(f"\n✅ Found {len(md_files)} markdown files")
        
        if not md_files:
            print("⚠️  No markdown files to process")
            return
        
        # Process each file
        for md_file in md_files:
            await self.scan_file(md_file)
        
        # Summary
        total = self.decisions_found + self.patterns_found + self.failures_found
        print(f"\n{'='*60}")
        print("✅ MARKDOWN SCAN COMPLETE")
        print(f"{'='*60}")
        print(f"\nResults:")
        print(f"  Files scanned: {self.files_scanned}")
        print(f"  Decisions: {self.decisions_found}")
        print(f"  Patterns: {self.patterns_found}")
        print(f"  Failures: {self.failures_found}")
        print(f"  Total nodes: {total}")


async def main():
    scanner = MarkdownScanner()
    await scanner.scan_and_ingest()


if __name__ == "__main__":
    asyncio.run(main())
