#!/bin/bash
# =============================================================================
# Setup Script - Dziki na Białołęce
# Pierwszy start projektu od zera
# =============================================================================

set -e

echo "========================================"
echo " Dziki na Białołęce - Setup"
echo "========================================"
echo ""

# 1. Sprawdź czy Docker działa
echo "[1/6] Sprawdzam Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker nie jest uruchomiony!"
    echo "Uruchom Docker Desktop i spróbuj ponownie."
    exit 1
fi
echo "OK"

# 2. Skopiuj .env jeśli nie istnieje
echo "[2/6] Sprawdzam plik .env..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "Skopiowano .env.example -> .env"
        echo ""
        echo "UWAGA: Edytuj plik .env i ustaw bezpieczne hasła!"
        echo "       Naciśnij Enter aby kontynuować..."
        read
    else
        echo "WARNING: Brak .env.example - używam domyślnych wartości"
    fi
else
    echo "OK (plik .env istnieje)"
fi

# 3. Buduj obrazy
echo "[3/6] Buduję obrazy Docker..."
docker-compose build

# 4. Start bazy danych
echo "[4/6] Uruchamiam bazę danych..."
docker-compose up -d db redis-broker redis-cache
echo "Czekam 15 sekund na start bazy..."
sleep 15

# 5. Start PgBouncer
echo "[5/6] Uruchamiam PgBouncer..."
docker-compose up -d pgbouncer
sleep 5

# 6. Migracje i start reszty
echo "[6/6] Uruchamiam API i migracje..."
docker-compose up -d api
sleep 10

echo "Uruchamiam migracje..."
docker-compose exec -T api python manage.py migrate --noinput || {
    echo "WARNING: Migracje nie powiodły się. Może to być pierwszy start."
}

# Start pozostałych serwisów
docker-compose up -d

echo ""
echo "========================================"
echo " GOTOWE!"
echo "========================================"
echo ""
echo " Frontend: http://localhost:5173"
echo " API:      http://localhost:8000/api/"
echo " Admin:    http://localhost:8000/admin/"
echo ""
echo " Sprawdź status: make status"
echo " Health check:   make test"
echo ""
