# =============================================================================
# FRESH START - Dziki na Białołęce (PowerShell)
# Pełne odtworzenie projektu od zera
# Wersja: 1.7 (2026-01-11)
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  FRESH START - Dziki na Białołęce" -ForegroundColor Cyan
Write-Host "  $(Get-Date)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Przejdź do katalogu projektu
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path -Parent $ScriptDir)

function Write-Success { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warning { param($msg) Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Error { param($msg) Write-Host "[X] $msg" -ForegroundColor Red; exit 1 }

# =============================================================================
# [1/10] Sprawdź Docker
# =============================================================================
Write-Host "`n[1/10] Sprawdzam Docker..." -ForegroundColor White
try {
    docker info | Out-Null
    Write-Success "Docker działa"
} catch {
    Write-Error "Docker nie jest uruchomiony!"
}

# =============================================================================
# [2/10] Uruchom kontenery
# =============================================================================
Write-Host "`n[2/10] Uruchamiam kontenery..." -ForegroundColor White
docker-compose up -d db redis-broker redis-cache
Start-Sleep -Seconds 10
docker-compose up -d pgbouncer
Start-Sleep -Seconds 5
docker-compose up -d api worker-py celery-beat frontend
Start-Sleep -Seconds 10
Write-Success "Kontenery uruchomione"

# =============================================================================
# [3/10] Sprawdź zdrowie kontenerów
# =============================================================================
Write-Host "`n[3/10] Sprawdzam zdrowie kontenerów..." -ForegroundColor White
docker ps --format "table {{.Names}}`t{{.Status}}" | Select-String "dziki"

# =============================================================================
# [4/10] Migracje Django
# =============================================================================
Write-Host "`n[4/10] Uruchamiam migracje Django..." -ForegroundColor White
docker exec dziki-api python manage.py migrate --noinput
Write-Success "Migracje zakończone"

# =============================================================================
# [5/10] Import granicy Białołęki
# =============================================================================
Write-Host "`n[5/10] Importuję granicę Białołęki..." -ForegroundColor White
if (Test-Path "data/boundaries_bialoleka.sql") {
    Get-Content "data/boundaries_bialoleka.sql" | docker exec -i dziki-db psql -U dziki -d dziki_db 2>$null
    Write-Success "Granica zaimportowana"
} elseif (Test-Path "fixtures/sql/01_boundaries.sql") {
    Get-Content "fixtures/sql/01_boundaries.sql" | docker exec -i dziki-db psql -U dziki -d dziki_db 2>$null
    Write-Success "Granica zaimportowana (z fixtures)"
} else {
    Write-Warning "Brak pliku granicy!"
}

# Weryfikacja
$boundaryCount = docker exec dziki-db psql -U dziki -d dziki_db -t -c "SELECT COUNT(*) FROM boundaries WHERE name='bialoleka';"
$boundaryCount = $boundaryCount.Trim()
if ($boundaryCount -eq "1") {
    Write-Success "Granica zweryfikowana (1 poligon)"
} else {
    Write-Warning "Problem z granicą! Znaleziono: $boundaryCount"
}

# =============================================================================
# [6/10] Import danych OSM
# =============================================================================
Write-Host "`n[6/10] Importuję dane OSM..." -ForegroundColor White

if (Test-Path "scripts/fix_osm_import.py") {
    Write-Host "    Uruchamiam fix_osm_import.py (może potrwać kilka minut)..." -ForegroundColor Gray
    docker cp scripts/fix_osm_import.py dziki-api:/tmp/
    docker exec dziki-api python /tmp/fix_osm_import.py 2>&1 | Select-Object -Last 20
    Write-Success "Dane OSM zaimportowane (fresh)"
} elseif (Test-Path "fixtures/sql/05_osm_buildings.sql") {
    Write-Host "    Importuję z SQL backupów..." -ForegroundColor Gray
    Get-Content "fixtures/sql/02_osm_forests.sql" | docker exec -i dziki-db psql -U dziki -d dziki_db 2>$null
    Get-Content "fixtures/sql/03_osm_water.sql" | docker exec -i dziki-db psql -U dziki -d dziki_db 2>$null
    Get-Content "fixtures/sql/04_osm_roads.sql" | docker exec -i dziki-db psql -U dziki -d dziki_db 2>$null
    Get-Content "fixtures/sql/05_osm_buildings.sql" | docker exec -i dziki-db psql -U dziki -d dziki_db 2>$null
    Get-Content "fixtures/sql/06_osm_barriers.sql" | docker exec -i dziki-db psql -U dziki -d dziki_db 2>$null
    Write-Success "Dane OSM zaimportowane (z backupu)"
} else {
    Write-Warning "Brak danych OSM"
}

# =============================================================================
# [7/10] Generuj siatkę FAST
# =============================================================================
Write-Host "`n[7/10] Generuję siatkę FAST (100x100m)..." -ForegroundColor White
docker exec dziki-api python manage.py init_grids --generate-square 2>&1 | Select-Object -Last 5
$squareCount = docker exec dziki-db psql -U dziki -d dziki_db -t -c "SELECT COUNT(*) FROM sightings_gridcell_square;"
Write-Success "Siatka FAST: $($squareCount.Trim()) komórek"

# =============================================================================
# [8/10] Generuj siatkę Voronoi (PUB)
# =============================================================================
Write-Host "`n[8/10] Generuję siatkę Voronoi (PUB)..." -ForegroundColor White
Write-Host "    UWAGA: Używam MSYS_NO_PATHCONV=1 automatycznie" -ForegroundColor Gray

$env:MSYS_NO_PATHCONV = "1"
try {
    docker-compose run --rm worker-r Rscript /app/r_scripts/01_generate_voronoi.R 2>&1 | Select-Object -Last 10
    $voronoiCount = docker exec dziki-db psql -U dziki -d dziki_db -t -c "SELECT COUNT(*) FROM sightings_gridcell_voronoi;"
    Write-Success "Siatka Voronoi: $($voronoiCount.Trim()) komórek"
} catch {
    Write-Warning "Voronoi nie wygenerowany - uruchom ręcznie:"
    Write-Host "    `$env:MSYS_NO_PATHCONV='1'; docker-compose run --rm worker-r Rscript /app/r_scripts/01_generate_voronoi.R" -ForegroundColor Yellow
}

# =============================================================================
# [9/10] Załaduj próbki obserwacji
# =============================================================================
Write-Host "`n[9/10] Ładuję próbki obserwacji..." -ForegroundColor White
if (Test-Path "fixtures/sightings.json") {
    docker exec dziki-api python manage.py loaddata fixtures/sightings.json 2>$null
    $sightingCount = docker exec dziki-db psql -U dziki -d dziki_db -t -c "SELECT COUNT(*) FROM sightings_sighting;"
    Write-Success "Załadowano $($sightingCount.Trim()) obserwacji"
} else {
    Write-Warning "Brak fixtures/sightings.json"
}

# =============================================================================
# [10/10] Weryfikacja końcowa
# =============================================================================
Write-Host "`n[10/10] Weryfikacja końcowa..." -ForegroundColor White
docker exec dziki-db psql -U dziki -d dziki_db -c @"
SELECT 'boundaries' as tabela, COUNT(*) as rekordy FROM boundaries
UNION ALL SELECT 'sightings', COUNT(*) FROM sightings_sighting
UNION ALL SELECT 'square_grid (FAST)', COUNT(*) FROM sightings_gridcell_square
UNION ALL SELECT 'voronoi (PUB)', COUNT(*) FROM sightings_gridcell_voronoi
UNION ALL SELECT 'osm_buildings', COUNT(*) FROM osm_buildings
UNION ALL SELECT 'osm_forests', COUNT(*) FROM osm_forests
UNION ALL SELECT 'osm_water', COUNT(*) FROM osm_water
UNION ALL SELECT 'osm_barriers', COUNT(*) FROM osm_barriers
UNION ALL SELECT 'osm_roads', COUNT(*) FROM osm_roads
ORDER BY 1;
"@

# Test API
Write-Host "`nTestuję API..." -ForegroundColor White
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/analytics/grid/" -UseBasicParsing -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Success "API działa (HTTP 200)"
    }
} catch {
    Write-Warning "API nie odpowiada - poczekaj chwilę"
}

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "  FRESH START ZAKOŃCZONY!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  API:      http://localhost:8000/api/" -ForegroundColor White
Write-Host ""
Write-Host "  Następne kroki:" -ForegroundColor White
Write-Host "  1. Otwórz http://localhost:5173" -ForegroundColor Gray
Write-Host "  2. Wybierz tryb FAST lub PUB" -ForegroundColor Gray
Write-Host "  3. Kliknij 'Przelicz FAST' aby zobaczyć heatmapę" -ForegroundColor Gray
Write-Host ""
