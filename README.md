# Dziki na Białołęce

Mapa ryzyka spotkania z dzikami w dzielnicy Białołęka (Warszawa).

**Live:** https://dzikinabialolece.pl
**Stack:** Django 5 + PostGIS · React 18 + MapLibre GL · R 4.3 + spatialreg · Docker

## Setup / pierwszy standup

Tabele OSM (`osm_*`) są `managed=False` — nie tworzą ich migracje Django, więc świeży
klon wymaga bootstrapu danych OSM przed pierwszym uruchomieniem pipeline'u PUB/RESEARCH:

1. `docker compose up -d` — PostGIS init: `config/postgres/01-init.sql` + `02-fix-hba.sh`
2. `python manage.py migrate`
3. Bootstrap OSM (oba kroki — rozłączne zbiory tabel):
   - `python scripts/fix_osm_import.py` — tworzy i zapełnia `osm_forests, osm_water,
     osm_roads, osm_allotments, osm_meadow, osm_farmland, osm_parks, osm_scrub, osm_railway`
   - `Rscript r_scripts/00_import_osm_features.R` — zapełnia `osm_buildings, osm_barriers`
     (jedyne źródło `osm_barriers`)
4. `python manage.py init_grids`, następnie pipeline (FAST / PUB / RESEARCH).

## Znane ograniczenia

- **Tryb PUB** — `ensemble_risk` = PERCENTILE_RANK(1/area_proportion); trzy składniki ważonej sumy sprowadzają się do tego samego sygnału (zmierzone corr=1.000, patrz DECISIONS.md D-11).
- **Automatyczna weryfikacja zgłoszeń** - każde nowe zgłoszenie otrzymuje `status=VERIFIED` natychmiast; brak warstwy moderacji.
- **Bypass PgBouncer** - skrypty R łączą się bezpośrednio z PostgreSQL (port 5432), omijając PgBouncer. Długie zapytania R poza pulą połączeń.
- **switch_sample_task** - wykonuje `TRUNCATE sightings CASCADE`; bezpieczne wyłącznie w środowisku deweloperskim. Nigdy nie uruchamiać na danych produkcyjnych.
