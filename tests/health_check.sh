#!/bin/bash
# =============================================================================
# Health Check Script - Dziki na Białołęce
# =============================================================================
# Tests all services in the docker-compose stack
# Usage: ./tests/health_check.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo " Dziki na Białołęce - Health Check"
echo "======================================"
echo ""

FAILED=0

# Function to check service
check_service() {
    local name=$1
    local command=$2
    printf "%-20s" "$name..."
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# 1. PostgreSQL
check_service "PostgreSQL" "docker-compose exec -T db pg_isready -U dziki"

# 2. PgBouncer
check_service "PgBouncer" "docker-compose exec -T pgbouncer pg_isready -h 127.0.0.1 -p 6432"

# 3. Redis Broker
check_service "Redis (broker)" "docker-compose exec -T redis-broker redis-cli -a \$REDIS_PASSWORD ping"

# 4. Redis Cache
check_service "Redis (cache)" "docker-compose exec -T redis-cache redis-cli -a \$REDIS_PASSWORD ping"

# 5. Django API
check_service "Django API" "curl -sf http://localhost:8000/api/sightings/"

# 6. Frontend
check_service "Frontend" "curl -sf http://localhost:5173/"

# 7. Celery Worker (check if running)
check_service "Celery Worker" "docker-compose ps worker-py | grep -q 'Up'"

echo ""
echo "======================================"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All services OK!${NC}"
    exit 0
else
    echo -e "${RED}$FAILED service(s) failed${NC}"
    exit 1
fi
