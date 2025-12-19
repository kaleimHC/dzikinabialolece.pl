# =============================================================================
# Makefile - Dziki na Białołęce
# Wersja: 1.7 (2026-01-11)
# =============================================================================
# Typowe operacje dla projektu
# Usage: make <target>

.PHONY: up down restart logs test migrate shell clean help fresh-start osm-fix status verify

# Default target
help:
	@echo "Dostępne komendy:"
	@echo ""
	@echo "  PODSTAWOWE:"
	@echo "    make up           - Uruchom wszystkie serwisy"
	@echo "    make down         - Zatrzymaj wszystkie serwisy"
	@echo "    make restart      - Zrestartuj wszystkie serwisy"
	@echo "    make status       - Pokaż status kontenerów"
	@echo "    make logs         - Pokaż logi (follow mode)"
	@echo ""
	@echo "  SETUP:"
	@echo "    make fresh-start  - Pełny reset i setup od zera"
	@echo "    make migrate      - Uruchom migracje Django"
	@echo "    make osm-fix      - Napraw/odśwież dane OSM"
	@echo "    make init-grids   - Generuj siatki FAST + Voronoi"
	@echo ""
	@echo "  DEVELOPMENT:"
	@echo "    make shell        - Otwórz shell Django"
	@echo "    make db-shell     - Otwórz shell PostgreSQL"
	@echo "    make test         - Uruchom health check"
	@echo "    make verify       - Sprawdź stan bazy danych"
	@echo ""
	@echo "  CZYSZCZENIE:"
	@echo "    make clean        - Usuń cache i zbędne pliki"
	@echo "    make clean-all    - Usuń wszystko (włącznie z volumes)"

# =============================================================================
# PODSTAWOWE
# =============================================================================

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

status:
	docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "dziki|NAMES"

logs:
	docker-compose logs -f

# =============================================================================
# SETUP
# =============================================================================

fresh-start:
	@echo "Uruchamiam pełny fresh start..."
	bash scripts/fresh_start.sh

migrate:
	docker exec dziki-api python manage.py migrate

osm-fix:
	@echo "Naprawiam dane OSM..."
	docker cp scripts/fix_osm_import.py dziki-api:/tmp/
	docker exec dziki-api python /tmp/fix_osm_import.py

init-grids:
	@echo "Generuję siatkę FAST..."
	docker exec dziki-api python manage.py init_grids --generate-square
	@echo ""
	@echo "Generuję siatkę Voronoi..."
	@echo "UWAGA: Na Windows użyj: MSYS_NO_PATHCONV=1 make voronoi"
	docker-compose run --rm worker-r Rscript /app/r_scripts/01_generate_voronoi.R

voronoi:
	docker-compose run --rm worker-r Rscript /app/r_scripts/01_generate_voronoi.R

fast-grid:
	docker exec dziki-api python manage.py init_grids --generate-square

# =============================================================================
# DEVELOPMENT
# =============================================================================

test:
	@echo "Health check..."
	@curl -s http://localhost:8000/api/health/ || echo "API nie odpowiada"
	@echo ""
	bash tests/health_check.sh 2>/dev/null || true

shell:
	docker exec -it dziki-api python manage.py shell

db-shell:
	docker exec -it dziki-db psql -U dziki -d dziki_db

verify:
	@echo "Stan bazy danych:"
	@docker exec dziki-db psql -U dziki -d dziki_db -c "\
		SELECT 'boundaries' as tabela, COUNT(*) as rekordy FROM boundaries \
		UNION ALL SELECT 'sightings', COUNT(*) FROM sightings_sighting \
		UNION ALL SELECT 'square_grid', COUNT(*) FROM sightings_gridcell_square \
		UNION ALL SELECT 'voronoi', COUNT(*) FROM sightings_gridcell_voronoi \
		UNION ALL SELECT 'osm_buildings', COUNT(*) FROM osm_buildings \
		UNION ALL SELECT 'osm_forests', COUNT(*) FROM osm_forests \
		UNION ALL SELECT 'osm_water', COUNT(*) FROM osm_water \
		UNION ALL SELECT 'osm_barriers', COUNT(*) FROM osm_barriers \
		UNION ALL SELECT 'osm_roads', COUNT(*) FROM osm_roads \
		ORDER BY 1;"

# =============================================================================
# LOGI SZCZEGÓŁOWE
# =============================================================================

api-logs:
	docker logs dziki-api --tail 100 -f

worker-logs:
	docker logs dziki-worker-py --tail 100 -f

frontend-logs:
	docker logs dziki-frontend --tail 100 -f

r-logs:
	docker-compose logs worker-r

# =============================================================================
# CZYSZCZENIE
# =============================================================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".DS_Store" -delete 2>/dev/null || true

clean-all: clean
	docker-compose down -v --remove-orphans
	@echo "UWAGA: Wszystkie dane zostały usunięte!"

# =============================================================================
# CACHE
# =============================================================================

flush-cache:
	docker exec dziki-redis-cache redis-cli FLUSHALL
	@echo "Cache wyczyszczony"

# =============================================================================
# FRONTEND
# =============================================================================

frontend-build:
	cd frontend && npm run build

frontend-restart:
	docker-compose restart frontend

frontend-rebuild: frontend-build frontend-restart
	@echo "Frontend przebudowany i zrestartowany"

# =============================================================================
# BACKUP
# =============================================================================

backup-db:
	@echo "Tworzę backup bazy..."
	docker exec dziki-db pg_dump -U dziki -d dziki_db > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup utworzony"

# =============================================================================
# RECALCULATE
# =============================================================================

recalc-fast:
	@echo "Przeliczam FAST..."
	curl -X POST http://localhost:8000/api/analytics/recalculate/?mode=fast
	@echo ""

recalc-full:
	@echo "Uruchamiam pełny pipeline R..."
	curl -X POST http://localhost:8000/api/analytics/recalculate/?mode=full
	@echo ""
