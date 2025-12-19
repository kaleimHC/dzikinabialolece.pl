# Dziki na Białołęce

Mapa ryzyka spotkania z dzikami w dzielnicy Białołęka (Warszawa).

**Live:** https://dzikinabialolece.pl
**Stack:** Django 5 + PostGIS · React 18 + MapLibre GL · R 4.3 + spatialreg · Docker

## Znane ograniczenia

- **Tryb PUB** — `ensemble_risk` = PERCENTILE_RANK(1/area_proportion); trzy składniki ważonej sumy sprowadzają się do tego samego sygnału (zmierzone corr=1.000, patrz DECISIONS.md D-11).
- **Automatyczna weryfikacja zgłoszeń** - każde nowe zgłoszenie otrzymuje `status=VERIFIED` natychmiast; brak warstwy moderacji.
- **Bypass PgBouncer** - skrypty R łączą się bezpośrednio z PostgreSQL (port 5432), omijając PgBouncer. Długie zapytania R poza pulą połączeń.
- **switch_sample_task** - wykonuje `TRUNCATE sightings CASCADE`; bezpieczne wyłącznie w środowisku deweloperskim. Nigdy nie uruchamiać na danych produkcyjnych.
