"""Configuration loader for Faulkner-DB with fallback hierarchy.

Priority order:
1. Environment variables (FALKORDB_*)
2. Config file (config/graphiti_config.yaml)
3. Hardcoded defaults (will fail auth if server requires password)
"""

import os
import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import redis


@dataclass
class FalkorDBConfig:
    """FalkorDB connection configuration."""
    host: str
    port: int
    password: Optional[str]
    graph_name: str = 'knowledge_graph'


_CONFIG_FILE = Path(__file__).parent.parent / 'config' / 'graphiti_config.yaml'


def load_config() -> FalkorDBConfig:
    """Load FalkorDB configuration with fallback hierarchy.

    Priority:
    1. Environment variables (FALKORDB_HOST, FALKORDB_PORT, FALKORDB_PASSWORD)
    2. Config file (config/graphiti_config.yaml)
    3. Hardcoded defaults
    """
    # 1. Environment variables (highest priority)
    if os.environ.get('FALKORDB_HOST') or os.environ.get('FALKORDB_PASSWORD'):
        return FalkorDBConfig(
            host=os.environ.get('FALKORDB_HOST', 'localhost'),
            port=int(os.environ.get('FALKORDB_PORT', 6380)),
            password=os.environ.get('FALKORDB_PASSWORD'),
            graph_name=os.environ.get('FALKORDB_GRAPH', 'knowledge_graph')
        )

    # 2. Config file (fallback)
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE) as f:
                yaml_config = yaml.safe_load(f)
                fdb = yaml_config.get('falkordb', {})
                graph = yaml_config.get('graph', {})

                return FalkorDBConfig(
                    host=fdb.get('host', 'localhost'),
                    port=fdb.get('port', 6380),
                    password=fdb.get('password'),
                    graph_name=graph.get('default_graph_name', 'knowledge_graph')
                )
        except Exception as e:
            raise ValueError(f"Failed to parse config file {_CONFIG_FILE}: {e}")

    # 3. Hardcoded defaults
    return FalkorDBConfig(host='localhost', port=6380, password=None)


def validate_connection(config: FalkorDBConfig) -> None:
    """Validate FalkorDB connection. Raises on failure with actionable message."""
    try:
        client = redis.Redis(
            host=config.host,
            port=config.port,
            password=config.password,
            decode_responses=True,
            socket_connect_timeout=5
        )
        client.ping()
        client.close()

    except redis.AuthenticationError as e:
        raise RuntimeError(
            f"\n"
            f"  FAULKNER-DB AUTHENTICATION FAILED\n"
            f"\n"
            f"  FalkorDB at {config.host}:{config.port} requires a password.\n"
            f"  Password provided: {'YES' if config.password else 'NO'}\n"
            f"\n"
            f"  Fix by setting the password in ONE of:\n"
            f"  1. Environment variable: export FALKORDB_PASSWORD='...'\n"
            f"  2. Config file: {_CONFIG_FILE}\n"
            f"     Set falkordb.password to the correct value\n"
            f"  3. MCP config: ~/.claude/mcp_servers.json\n"
            f"     Add FALKORDB_PASSWORD to faulkner-db env section\n"
        ) from e

    except redis.ConnectionError as e:
        raise ConnectionError(
            f"\n"
            f"  FAULKNER-DB CONNECTION FAILED\n"
            f"\n"
            f"  Could not connect to FalkorDB at {config.host}:{config.port}\n"
            f"\n"
            f"  Ensure the container is running:\n"
            f"    docker ps | grep faulkner-db-falkordb\n"
            f"  If not running:\n"
            f"    cd /home/platano/project/faulkner-db/docker && docker-compose up -d falkordb\n"
        ) from e
