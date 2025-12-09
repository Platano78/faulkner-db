# Contributing to Faulkner DB

Thank you for your interest in contributing to Faulkner DB! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

## How to Contribute

### Reporting Bugs

1. **Check existing issues** to avoid duplicates
2. **Use the bug report template** when creating new issues
3. **Include**:
   - Clear description of the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, Docker version)
   - Relevant logs or error messages

### Suggesting Enhancements

1. **Check existing feature requests** first
2. **Use the feature request template**
3. **Provide**:
   - Clear use case description
   - Expected behavior
   - Why this enhancement would be useful
   - Potential implementation approach (optional)

### Pull Requests

1. **Fork the repository** and create a feature branch
2. **Follow the development setup** (see below)
3. **Make your changes**:
   - Write clear, documented code
   - Follow existing code style (PEP 8 for Python)
   - Add tests for new features
   - Update documentation as needed
4. **Ensure all tests pass**:
   ```bash
   pytest tests/ -v
   ```
5. **Commit with clear messages**:
   ```bash
   git commit -m "feat: add temporal query optimization"
   ```
6. **Push and create PR**:
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Fill out the PR template** completely

## Development Setup

### Prerequisites

- Python 3.8+
- Docker and Docker Compose
- Git
- Node.js 16+ (for npm package development)

### Local Development

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/faulkner-db.git
cd faulkner-db

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"  # Install development dependencies

# Start Docker stack
cd docker
cp .env.example .env
# Edit .env to set POSTGRES_PASSWORD
docker-compose up -d

# Run tests
pytest tests/ -v
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_knowledge_types.py -v

# With coverage
pytest tests/ --cov=core --cov=mcp_server --cov-report=html

# Watch mode (requires pytest-watch)
ptw tests/
```

### Code Style

**Python**:
- Follow PEP 8
- Use type hints
- Maximum line length: 120 characters
- Use `black` for formatting: `black core/ mcp_server/ tests/`
- Use `flake8` for linting: `flake8 core/ mcp_server/ tests/`

**JavaScript** (npm package):
- Use ESLint
- Follow Node.js best practices
- Clear error messages

### Commit Message Convention

Use conventional commits format:

```
type(scope): subject

body (optional)

footer (optional)
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements

**Examples**:
```bash
feat(mcp): add timeline query optimization
fix(docker): resolve FalkorDB connection timeout
docs(readme): update installation instructions
test(hybrid-search): add reranking unit tests
```

## Project Structure

```
faulkner-db/
├── core/                    # Core functionality
│   ├── knowledge_types.py   # Decision, Pattern, Failure models
│   ├── graphiti_client.py   # FalkorDB client
│   ├── hybrid_search.py     # Search implementation
│   └── gap_detector.py      # NetworkX analysis
├── mcp_server/              # MCP server
│   ├── server.py            # Main server
│   ├── mcp_tools.py         # Tool implementations
│   └── schemas.py           # Pydantic schemas
├── docker/                  # Docker configuration
├── tests/                   # Test suite
├── npm/                     # NPM configuration package
└── docs/                    # Documentation
```

## Testing Guidelines

### Unit Tests
- Test individual functions and classes
- Mock external dependencies
- Use pytest fixtures for common setups
- Aim for >80% code coverage

### Integration Tests
- Test MCP tool workflows
- Test database operations
- Use Docker containers for dependencies

### Test Naming
```python
def test_<function_name>_<scenario>_<expected_result>():
    # Example:
    def test_add_decision_with_valid_data_succeeds():
        pass
```

## Documentation

### Code Documentation
- Docstrings for all public functions/classes
- Use Google-style docstrings:
  ```python
  def query_decisions(query: str, timeframe: dict) -> list:
      """Search decisions using hybrid search.
      
      Args:
          query: Search query string
          timeframe: Dict with 'start' and 'end' dates
      
      Returns:
          List of matching decision nodes
      
      Raises:
          ValueError: If timeframe is invalid
      """
      pass
  ```

### README Updates
- Update README.md if adding major features
- Include usage examples
- Update architecture diagram if needed

## Release Process

1. **Update version** in `npm/package.json`
2. **Update CHANGELOG.md** with changes
3. **Create release PR** to main branch
4. **After merge**, create GitHub release:
   ```bash
   gh release create v1.1.0 --notes "Release notes here"
   ```
5. **GitHub Actions** will automatically:
   - Run CI tests
   - Publish npm package
   - Build Docker images

## Getting Help

- **GitHub Discussions**: https://github.com/platano78/faulkner-db/discussions
- **Issues**: https://github.com/platano78/faulkner-db/issues
- **Documentation**: https://github.com/platano78/faulkner-db/wiki

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Acknowledged in release notes
- Credited in the README acknowledgments section

Thank you for contributing to Faulkner DB! 🙏
