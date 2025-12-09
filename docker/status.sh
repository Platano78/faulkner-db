#!/bin/bash
echo "=== Faulkner DB Status ==="
echo
docker-compose ps
echo
echo "=== Health Checks ==="
echo -n "FalkorDB: "
docker inspect faulkner-db-falkordb --format='{{.State.Health.Status}}' 2>/dev/null || echo "not running"
echo -n "PostgreSQL: "
docker inspect faulkner-db-postgres --format='{{.State.Health.Status}}' 2>/dev/null || echo "not running"
echo -n "Visualization: "
docker inspect faulkner-db-visualization --format='{{.State.Health.Status}}' 2>/dev/null || echo "not running"
echo
echo "=== Access URLs ==="
echo "Network Graph:  http://localhost:8082/static/index.html"
echo "Timeline:       http://localhost:8082/static/timeline.html"
echo "Dashboard:      http://localhost:8082/static/dashboard.html"
echo "Gaps:          http://localhost:8082/static/gaps.html"
echo "API Health:    http://localhost:8082/health"
echo "FalkorDB UI:   http://localhost:8081"
