#!/bin/bash
# Wrapper for systemd timer that runs scripts/health_check.py.
#
# Reads credentials from $FAULKNER_HEALTH_ENV_FILE (default
# ~/.config/faulkner-health/env) instead of docker/.env so the
# scheduler does not depend on docker-compose internal hostnames or
# whatever password rotation has happened in the docker stack.
#
# Required env vars (set in the env file):
#   FALKORDB_HOST       e.g. 192.168.1.79
#   FALKORDB_PORT       e.g. 6380
#   FALKORDB_PASSWORD   the FalkorDB auth password
#
# To create the env file once:
#   mkdir -p ~/.config/faulkner-health
#   cat > ~/.config/faulkner-health/env <<EOF
#   FALKORDB_HOST=192.168.1.79
#   FALKORDB_PORT=6380
#   FALKORDB_PASSWORD=YOUR_PASSWORD_HERE
#   EOF
#   chmod 600 ~/.config/faulkner-health/env
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${FAULKNER_HEALTH_ENV_FILE:-$HOME/.config/faulkner-health/env}"

if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
else
    echo "ERROR: $ENV_FILE not found. See header of this script for setup." >&2
    exit 64
fi

: "${FALKORDB_HOST:?FALKORDB_HOST not set in $ENV_FILE}"
: "${FALKORDB_PORT:?FALKORDB_PORT not set in $ENV_FILE}"
: "${FALKORDB_PASSWORD:?FALKORDB_PASSWORD not set in $ENV_FILE}"

exec "$PROJECT_ROOT/venv/bin/python" "$PROJECT_ROOT/scripts/health_check.py" "$@"
