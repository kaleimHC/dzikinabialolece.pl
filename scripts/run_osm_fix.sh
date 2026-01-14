#!/bin/bash
# =============================================================================
# RUN OSM FIX - Uruchom pełną naprawę OSM z Docker
# =============================================================================

set -e

echo "=============================================="
echo "OSM FIX - Pełna naprawa danych OSM"
echo "=============================================="

# Sprawdź czy kontenery działają
echo ""
echo "[1] Sprawdzanie kontenerów..."
if ! docker ps | grep -q dziki-db; then
    echo "BŁĄD: Kontener dziki-db nie działa!"
    echo "Uruchom: docker-compose up -d"
    exit 1
fi

if ! docker ps | grep -q dziki-api; then
    echo "BŁĄD: Kontener dziki-api nie działa!"
    echo "Uruchom: docker-compose up -d"
    exit 1
fi

echo "  Kontenery OK"

# Krok 1: Import OSM
echo ""
echo "[2] Uruchamianie fix_osm_import.py..."
docker exec dziki-api python /app/scripts/fix_osm_import.py

# Krok 2: Przelicz cechy
echo ""
echo "[3] Uruchamianie recalculate_features.py..."
docker exec dziki-api python /app/scripts/recalculate_features.py

# Krok 3: Przelicz ensemble (R)
echo ""
echo "[4] Uruchamianie R ensemble prediction..."
docker-compose run --rm worker-r Rscript /app/r_scripts/05_ensemble_prediction.R

echo ""
echo "=============================================="
echo "ZAKOŃCZONO!"
echo "=============================================="
echo ""
echo "Odśwież przeglądarkę żeby zobaczyć zmiany."
