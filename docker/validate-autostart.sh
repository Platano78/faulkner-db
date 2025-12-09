#!/bin/bash
# Faulkner DB Auto-Start Validation Script
# Tests Docker Desktop auto-start functionality

set -e

cd "$(dirname "$0")"

echo "===================================="
echo "Faulkner DB Auto-Start Validation"
echo "===================================="
echo ""

# Check if Docker is running
echo "[1/6] Checking Docker status..."
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running"
    echo "   → Please start Docker Desktop and try again"
    exit 1
fi
echo "✅ Docker is running"
echo ""

# Check if containers exist
echo "[2/6] Checking if containers exist..."
CONTAINER_COUNT=$(docker ps -a --filter "name=faulkner-db" --format "{{.Names}}" | wc -l)
if [ "$CONTAINER_COUNT" -lt 3 ]; then
    echo "⚠️  Only $CONTAINER_COUNT containers found (expected 3)"
    echo "   → Run: docker-compose up -d"
    exit 1
fi
echo "✅ All 3 containers exist"
echo ""

# Check container status
echo "[3/6] Checking container status..."
docker-compose ps
echo ""

# Check health status
echo "[4/6] Checking health status..."
FALKORDB_HEALTH=$(docker inspect faulkner-db-falkordb --format='{{.State.Health.Status}}' 2>/dev/null || echo "no health check")
POSTGRES_HEALTH=$(docker inspect faulkner-db-postgres --format='{{.State.Health.Status}}' 2>/dev/null || echo "no health check")
VIZ_HEALTH=$(docker inspect faulkner-db-visualization --format='{{.State.Health.Status}}' 2>/dev/null || echo "no health check")

echo "  FalkorDB:      $FALKORDB_HEALTH"
echo "  PostgreSQL:    $POSTGRES_HEALTH"
echo "  Visualization: $VIZ_HEALTH"
echo ""

# Check restart policies
echo "[5/6] Checking restart policies..."
FALKORDB_RESTART=$(docker inspect faulkner-db-falkordb --format='{{.HostConfig.RestartPolicy.Name}}' 2>/dev/null || echo "none")
POSTGRES_RESTART=$(docker inspect faulkner-db-postgres --format='{{.HostConfig.RestartPolicy.Name}}' 2>/dev/null || echo "none")
VIZ_RESTART=$(docker inspect faulkner-db-visualization --format='{{.HostConfig.RestartPolicy.Name}}' 2>/dev/null || echo "none")

echo "  FalkorDB:      $FALKORDB_RESTART"
echo "  PostgreSQL:    $POSTGRES_RESTART"
echo "  Visualization: $VIZ_RESTART"

if [ "$FALKORDB_RESTART" != "unless-stopped" ] || [ "$POSTGRES_RESTART" != "unless-stopped" ] || [ "$VIZ_RESTART" != "unless-stopped" ]; then
    echo "⚠️  Not all containers have 'unless-stopped' restart policy"
    echo "   → Check docker-compose.yml configuration"
else
    echo "✅ All containers have correct restart policy"
fi
echo ""

# Test API endpoints
echo "[6/6] Testing API endpoints..."
if curl -s -f http://localhost:8082/health >/dev/null 2>&1; then
    echo "✅ Visualization API is responding"
    STATS=$(curl -s http://localhost:8082/api/stats)
    echo "   Stats: $STATS"
else
    echo "❌ Visualization API is not responding"
    echo "   → Check: docker-compose logs visualization"
fi
echo ""

# Summary
echo "===================================="
echo "Validation Complete"
echo "===================================="
echo ""

if [ "$FALKORDB_HEALTH" = "healthy" ] && [ "$POSTGRES_HEALTH" = "healthy" ] && [ "$VIZ_HEALTH" = "healthy" ]; then
    echo "✅ All systems operational!"
    echo ""
    echo "Auto-start is configured correctly."
    echo "When you quit and restart Docker Desktop,"
    echo "containers will automatically start."
    echo ""
    echo "Access URLs:"
    echo "  Network Graph:  http://localhost:8082/static/index.html"
    echo "  Timeline:       http://localhost:8082/static/timeline.html"
    echo "  Dashboard:      http://localhost:8082/static/dashboard.html"
    echo "  API Health:     http://localhost:8082/health"
    echo "  FalkorDB UI:    http://localhost:8081"
else
    echo "⚠️  Some services are not healthy yet"
    echo "   → Wait 30-60 seconds and run this script again"
    echo "   → Or check logs: docker-compose logs -f"
fi
echo ""
