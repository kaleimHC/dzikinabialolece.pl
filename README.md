# Dziki na Białołęce

Wild boar risk mapping for Białołęka district, Warsaw.

**Live:** https://dzikinabialolece.pl
**Stack:** Django 5 + PostGIS · React 18 + MapLibre GL · R 4.3 + spatialreg · Docker

## Known limitations

- **sighting_density / eta_score stored columns** = 0 in all RESEARCH rows — pipeline computes density dynamically from geometry; stored columns unused. Cosmetic debt.
- **sightings auto-verified** — every submitted sighting gets `status=VERIFIED` immediately; no moderation layer.
- **pgbouncer bypass** — R scripts connect directly to PostgreSQL (port 5432), not through PgBouncer. Long-running R queries outside the pool.
- **switch_sample_task** — performs `TRUNCATE sightings CASCADE`; safe only in dev. Never trigger on production data.
