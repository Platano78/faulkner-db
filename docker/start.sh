#!/bin/bash
echo "Starting Faulkner DB stack..."
docker-compose up -d
echo "Stack started. Use './test.sh' to validate setup."
