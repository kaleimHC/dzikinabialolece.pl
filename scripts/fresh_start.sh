#!/bin/bash
# =============================================================================
# FRESH START - Dziki na Białołęce
# Pełne odtworzenie projektu od zera
# Wersja: 1.8 (2026-01-12)
# 12 kroków: Docker → Migrations → Boundaries → OSM → Grids → Sightings → Admin
# =============================================================================

set -e

echo "=========================================="
echo "  FRESH START - Dziki na Białołęce"
echo "  $(date)"
echo "=========================================="

cd "$(dirname "$0")/.."
PROJECT_DIR=$(pwd)

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

success() { echo -e "${GREEN}✓ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
error() { echo -e "${RED}✗ $1${NC}"; exit 1; }

# =============================================================================
# [1/12] Sprawdź Docker
# =============================================================================
echo ""
echo "[1/12] Sprawdzam Docker..."
docker info > /dev/null 2>&1 || error "Docker nie jest uruchomiony!"
success "Docker działa"

# =============================================================================
# [2/12] Uruchom kontenery
# =============================================================================
echo ""
echo "[2/12] Uruchamiam kontenery..."
docker-compose up -d db redis-broker redis-cache
sleep 10
docker-compose up -d pgbouncer
sleep 5
docker-compose up -d api worker-py celery-beat frontend
sleep 10
success "Kontenery uruchomione"

# =============================================================================
# [3/12] Sprawdź zdrowie kontenerów
# =============================================================================
echo ""
echo "[3/12] Sprawdzam zdrowie kontenerów..."
docker ps --format "table {{.Names}}\t{{.Status}}" | grep dziki

# =============================================================================
# [4/12] Migracje Django
# =============================================================================
echo ""
echo "[4/12] Uruchamiam migracje Django..."
docker exec dziki-api python manage.py migrate --noinput
success "Migracje zakończone"

# =============================================================================
# [5/12] Import granicy Białołęki
# =============================================================================
echo ""
echo "[5/12] Importuję granicę Białołęki..."
if [ -f "data/boundaries_bialoleka.sql" ]; then
    docker exec -i dziki-db psql -U dziki -d dziki_db < data/boundaries_bialoleka.sql 2>/dev/null || true
    success "Granica zaimportowana"
else
    warning "Brak pliku data/boundaries_bialoleka.sql - używam fixtures"
    docker exec -i dziki-db psql -U dziki -d dziki_db < fixtures/sql/01_boundaries.sql 2>/dev/null || true
fi

# Weryfikacja granicy
BOUNDARY_COUNT=$(docker exec dziki-db psql -U dziki -d dziki_db -t -c "SELECT COUNT(*) FROM boundaries WHERE name='bialoleka';" | tr -d ' ')
if [ "$BOUNDARY_COUNT" -eq "1" ]; then
    success "Granica zweryfikowana (1 poligon)"
else
    error "Problem z granicą! Znaleziono: $BOUNDARY_COUNT"
fi

# =============================================================================
# [6/12] Import danych OSM
# =============================================================================
echo ""
echo "[6/12] Importuję dane OSM..."

# Metoda 1: Użyj fix_osm_import.py (preferowana - pobiera świeże dane)
if [ -f "scripts/fix_osm_import.py" ]; then
    echo "    Uruchamiam fix_osm_import.py (może potrwać kilka minut)..."
    docker cp scripts/fix_osm_import.py dziki-api:/tmp/
    docker exec dziki-api python /tmp/fix_osm_import.py 2>&1 | tail -20
    success "Dane OSM zaimportowane (fresh)"
# Metoda 2: Użyj SQL backupów
elif [ -f "fixtures/sql/05_osm_buildings.sql" ]; then
    echo "    Importuję z SQL backupów..."
    docker exec -i dziki-db psql -U dziki -d dziki_db < fixtures/sql/02_osm_forests.sql 2>/dev/null
    docker exec -i dziki-db psql -U dziki -d dziki_db < fixtures/sql/03_osm_water.sql 2>/dev/null
    docker exec -i dziki-db psql -U dziki -d dziki_db < fixtures/sql/04_osm_roads.sql 2>/dev/null
    docker exec -i dziki-db psql -U dziki -d dziki_db < fixtures/sql/05_osm_buildings.sql 2>/dev/null
    docker exec -i dziki-db psql -U dziki -d dziki_db < fixtures/sql/06_osm_barriers.sql 2>/dev/null
    success "Dane OSM zaimportowane (z backupu)"
else
    warning "Brak danych OSM - uruchom ręcznie: docker exec dziki-api python /tmp/fix_osm_import.py"
fi

# =============================================================================
# [7/12] Generuj siatkę FAST (square grid)
# =============================================================================
echo ""
echo "[7/12] Generuję siatkę FAST (100x100m)..."
docker exec dziki-api python manage.py init_grids --generate-square 2>&1 | tail -5
SQUARE_COUNT=$(docker exec dziki-db psql -U dziki -d dziki_db -t -c "SELECT COUNT(*) FROM sightings_gridcell_square;" | tr -d ' ')
success "Siatka FAST: $SQUARE_COUNT komórek"

# =============================================================================
# [8/12] Generuj siatkę Voronoi (PUB)
# =============================================================================
echo ""
echo "[8/12] Generuję siatkę Voronoi (PUB)..."
echo "    UWAGA: Na Windows użyj: MSYS_NO_PATHCONV=1 przed komendą"

# Próba uruchomienia R workera
if docker-compose run --rm worker-r Rscript /app/r_scripts/01_generate_voronoi.R 2>&1 | tail -10; then
    VORONOI_COUNT=$(docker exec dziki-db psql -U dziki -d dziki_db -t -c "SELECT COUNT(*) FROM sightings_gridcell_voronoi;" | tr -d ' ')
    success "Siatka Voronoi: $VORONOI_COUNT komórek"
else
    warning "Voronoi nie wygenerowany - uruchom ręcznie:"
    echo "    MSYS_NO_PATHCONV=1 docker-compose run --rm worker-r Rscript /app/r_scripts/01_generate_voronoi.R"
fi

# =============================================================================
# [9/12] Załaduj próbki obserwacji
# =============================================================================
echo ""
echo "[9/12] Ładuję próbki obserwacji..."
if [ -f "fixtures/sightings.json" ]; then
    docker exec dziki-api python manage.py loaddata fixtures/sightings.json 2>/dev/null || true
    SIGHTING_COUNT=$(docker exec dziki-db psql -U dziki -d dziki_db -t -c "SELECT COUNT(*) FROM sightings_sighting;" | tr -d ' ')
    success "Załadowano $SIGHTING_COUNT obserwacji"
else
    warning "Brak fixtures/sightings.json"
fi

# =============================================================================
# [10/12] Superuser (admin panel)
# =============================================================================
echo ""
echo "[10/12] Tworzę superusera..."
docker exec dziki-api python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@dziki.pl', 'admin123')
    print('Created admin/admin123')
else:
    print('Superuser already exists')
"
success "Superuser gotowy (admin/admin123)"

# =============================================================================
# [11/12] Kolumna distance_to_forest (wymagana przez API)
# =============================================================================
echo ""
echo "[11/12] Sprawdzam kolumnę distance_to_forest..."
docker exec dziki-db psql -U dziki -d dziki_db -c "
ALTER TABLE sightings_gridcell_voronoi ADD COLUMN IF NOT EXISTS distance_to_forest DOUBLE PRECISION DEFAULT 0;
" 2>/dev/null
success "Kolumna distance_to_forest OK"

# =============================================================================
# [12/12] Weryfikacja końcowa
# =============================================================================
echo ""
echo "[12/12] Weryfikacja końcowa..."
echo ""
docker exec dziki-db psql -U dziki -d dziki_db -c "
SELECT 'boundaries' as tabela, COUNT(*) as rekordy FROM boundaries
UNION ALL SELECT 'sightings', COUNT(*) FROM sightings_sighting
UNION ALL SELECT 'square_grid (FAST)', COUNT(*) FROM sightings_gridcell_square
UNION ALL SELECT 'voronoi (PUB)', COUNT(*) FROM sightings_gridcell_voronoi
UNION ALL SELECT 'osm_buildings', COUNT(*) FROM osm_buildings
UNION ALL SELECT 'osm_forests', COUNT(*) FROM osm_forests
UNION ALL SELECT 'osm_water', COUNT(*) FROM osm_water
UNION ALL SELECT 'osm_barriers', COUNT(*) FROM osm_barriers
UNION ALL SELECT 'osm_roads', COUNT(*) FROM osm_roads
ORDER BY 1;"

# Test API
echo ""
echo "Testuję API..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/analytics/grid/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    success "API działa (HTTP $HTTP_CODE)"
else
    warning "API nie odpowiada (HTTP $HTTP_CODE) - poczekaj chwilę"
fi

echo ""
echo "=========================================="
echo "  FRESH START ZAKOŃCZONY!"
echo "=========================================="
echo ""
echo "  Frontend: http://localhost:5173"
echo "  API:      http://localhost:8000/api/"
echo "  Admin:    http://localhost:8000/admin/ (admin/admin123)"
echo ""
echo "  TRYBY ANALITYCZNE:"
echo "  ├─ FAST (SQUARE grid)  - instant, kliknij 'Oblicz mapę ryzyka'"
echo "  └─ PUB  (VORONOI grid) - 5 R scripts, ~2-5 min"
echo ""
echo "  JEŚLI VORONOI NIE WYGENEROWAŁ SIĘ:"
echo "  MSYS_NO_PATHCONV=1 docker-compose run --rm worker-r Rscript /app/r_scripts/01_generate_voronoi.R"
echo ""
echo "  PEŁNY R PIPELINE (opcjonalnie):"
echo "  curl -X POST http://localhost:8000/api/analytics/recalculate/?mode=full"
echo ""
