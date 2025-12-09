# faulkner-db-config

> Configure Claude Desktop/Code to use Faulkner DB MCP server

This CLI tool automatically configures your Claude installation to use Faulkner DB for temporal knowledge graph management and architectural decision tracking.

## Installation

```bash
npx faulkner-db-config setup
```

Or install globally:

```bash
npm install -g faulkner-db-config
faulkner-db-config setup
```

## What it does

1. Detects your Claude configuration file location (macOS/Windows/Linux/WSL)
2. Adds Faulkner DB MCP server to your Claude configuration
3. Provides next steps for starting the Docker stack
4. Verifies Docker availability

## Commands

### Setup (default)

Configure Claude to use Faulkner DB:

```bash
npx faulkner-db-config setup
```

### Status

Check current configuration status:

```bash
npx faulkner-db-config status
```

### Remove

Remove Faulkner DB from Claude configuration:

```bash
npx faulkner-db-config remove
```

## Prerequisites

- **Node.js** 16+
- **Python** 3.8+
- **Docker** (for running Faulkner DB)

## Full Setup

For the complete Faulkner DB installation:

```bash
# 1. Clone the repository
git clone https://github.com/platano78/faulkner-db.git
cd faulkner-db

# 2. Configure Claude (if not done by setup script)
npx faulkner-db-config setup

# 3. Start the Docker stack
cd docker
docker-compose up -d

# 4. Restart Claude Desktop/Code

# 5. Verify the setup
npx faulkner-db-config status
```

## Configuration File Locations

| Platform | Path |
|----------|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |
| WSL | Uses Windows path automatically |

## Troubleshooting

### Docker not found
Faulkner DB requires Docker to run. Install Docker from https://docs.docker.com/get-docker/

### Python not found
Ensure Python 3.8+ is installed and available in your PATH.

### Configuration not applied
After running setup, restart Claude Desktop/Code for changes to take effect.

### MCP server not starting
1. Verify Docker stack is running: `docker-compose ps`
2. Check Faulkner DB logs: `docker-compose logs -f`
3. Ensure FalkorDB is accessible on port 6379

## About Faulkner DB

Faulkner DB is a temporal knowledge graph system that helps teams:
- Track architectural decisions over time
- Document implementation patterns and failures
- Query historical knowledge with hybrid search
- Detect knowledge gaps using graph analysis

Learn more: https://github.com/platano78/faulkner-db

## License

MIT
