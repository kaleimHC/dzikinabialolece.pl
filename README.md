# Dziki na Białołęce

Mapa ryzyka spotkania z dzikami w dzielnicy Białołęka (Warszawa).

**Live:** https://dzikinabialolece.pl
**Stack:** Django 5 + PostGIS · React 18 + MapLibre GL · R 4.3 + spatialreg · Docker

## Znane ograniczenia

- **Kolumny sighting_density / eta_score** = 0 we wszystkich wierszach RESEARCH — pipeline liczy gęstość dynamicznie z geometrii; kolumny przechowywane nieużywane. Dług kosmetyczny.
- **Automatyczna weryfikacja zgłoszeń** — każde nowe zgłoszenie otrzymuje `status=VERIFIED` natychmiast; brak warstwy moderacji.
- **Bypass PgBouncer** — skrypty R łączą się bezpośrednio z PostgreSQL (port 5432), z pominięciem PgBouncer. Długie zapytania R poza pulą połączeń.
- **switch_sample_task** — wykonuje `TRUNCATE sightings CASCADE`; bezpieczne wyłącznie w środowisku deweloperskim. Nigdy nie uruchamiać na danych produkcyjnych.
