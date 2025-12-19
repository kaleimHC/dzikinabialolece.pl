# Dziki na Białołęce

Mapa ryzyka spotkania z dzikami w warszawskiej Białołęce - aplikacja webowa łącząca
crowdsourcing zgłoszeń z przestrzenną ekonometrią. Trzy niezależne tryby liczenia
ryzyka: od szybkiej heurystyki SQL, przez teselację Voronoi, po model SAR/SEM w R.

**Live:** https://dzikinabialolece.pl

**Stack:** Django 5 + PostGIS · React 18 + MapLibre GL · R 4.3 + spatialreg · Docker

> **Demo portfolio** na danych syntetycznych - publiczna piaskownica prezentująca
> metodologię, nie produkcyjny rejestr realnych zgłoszeń. Akcje obliczeniowe
> (przeliczanie ryzyka, przełączanie próbek) są celowo otwarte dla anonimowych
> użytkowników; przełączenie próbki nadpisuje zbiór demo i jest zamierzone.

## Co to robi

Użytkownicy zgłaszają obserwacje dzików na interaktywnej mapie (PWA, MapLibre GL).
Backend agreguje zgłoszenia do siatki przestrzennej i liczy ryzyko spotkania w trzech
niezależnych trybach, które można przełączać i przeliczać na żywo. Wynik to warstwa
choropleth ryzyka plus, w trybie RESEARCH, pełna diagnostyka modelu przestrzennego.

## Trzy tryby liczenia ryzyka

| Tryb | Silnik | Geometria | Metoda |
|------|--------|-----------|--------|
| **FAST** | Python + SQL | siatka kwadratowa 100 m | heurystyka CASE na gęstości zgłoszeń (Celery, bez R) |
| **PUB** | R | teselacja Voronoi | `ensemble_risk` = area-rank = `PERCENTILE_RANK(1/pole)`, modulowane proximity |
| **RESEARCH** | R + spatialreg | siatka 500 m / Voronoi | SAR/SEM, Y = intensywność zgłoszeń na powierzchnię; diagnostyka (Moran I, LM, VIF, impacts) |

Dlaczego trzy tryby: FAST daje natychmiastowy podgląd, PUB pokazuje czysto geometryczny
sygnał gęstości (mniejszy kafel Voronoi = gęstszy klaster zgłoszeń), a RESEARCH stawia
model przestrzenny (SAR/SEM) z predyktorami środowiskowymi OSM i diagnostyką.

## Stack

- **Backend:** Django 5 + PostGIS, Django REST Framework, Celery + Redis, Channels (WebSocket progress)
- **Frontend:** React 18 + Vite, MapLibre GL, Zustand, PWA (offline-capable)
- **Analityka:** R 4.3 (`spatialreg`, `sf`, `spdep`) - reimplementacja metodologii spatialWarsaw (SAR/SEM, macierze W, diagnostyka)
- **Infra:** Docker Compose (9 usług), Nginx, PgBouncer (dual-pool), GitHub Actions CI (lint, migrate-from-zero, pytest, build)

## Architektura

```
UI (React/MapLibre)
  -> REST / Celery
    -> mode_router (FAST, PUB)  |  ResearchOrchestrator (RESEARCH, 8 kroków)
      -> SQL (Python)  |  R via Docker (Rscript, env RESEARCH_TARGET_TABLE)
        -> tabele grid (sightings_gridcell_*, research_grid_500m)
          -> endpoint GeoJSON -> warstwa ryzyka na mapie
```

Tryb RESEARCH przechodzi przez R-pipeline: populacja GUS -> cechy OSM -> zmienna Y ->
macierz W -> model SAR/SEM -> diagnostyka -> zapis ryzyka. Postęp transmitowany przez
WebSocket. Wybór modelu (SAR vs SEM) po AIC; macierz W domyślnie z k-NN po AIC (knn_aic).

## Setup / pierwszy standup

Tabele OSM (`osm_*`) są `managed=False` - nie tworzą ich migracje Django, więc świeży
klon wymaga bootstrapu danych OSM przed pierwszym uruchomieniem pipeline'u PUB/RESEARCH:

1. `docker compose up -d` - PostGIS init: `config/postgres/01-init.sql` + `02-fix-hba.sh`
2. `python manage.py migrate`
3. Bootstrap OSM (oba kroki - rozłączne zbiory tabel):
   - `python scripts/fix_osm_import.py` - tworzy i zapełnia `osm_forests, osm_water,
     osm_roads, osm_allotments, osm_meadow, osm_farmland, osm_parks, osm_scrub, osm_railway`
   - `Rscript r_scripts/00_import_osm_features.R` - zapełnia `osm_buildings, osm_barriers`
     (jedyne źródło `osm_barriers`)
4. `python manage.py init_grids`, następnie pipeline (FAST / PUB / RESEARCH).

## Decyzje projektowe i ograniczenia

- **Automatyczna weryfikacja zgłoszeń:** każde nowe zgłoszenie dostaje `status=VERIFIED`
  natychmiast; brak warstwy moderacji (świadome uproszczenie demo).
- **Bypass PgBouncer:** skrypty R łączą się bezpośrednio z PostgreSQL (port 5432),
  omijając PgBouncer - długie zapytania R poza pulą połączeń.

## Licencja

GPL-3.0 - patrz LICENSE.
