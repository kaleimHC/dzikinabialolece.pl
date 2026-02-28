# CLAUDE.md — Instructions for Claude Code in /opt/dziki

**At start of every session:** read `/opt/dziki_docs/docs_internal/state/00_GIT_STATE.md` for current
branch/commit state, and `/opt/dziki_docs/docs_internal/state/CHECKPOINT_*.md` (latest) for active context.

## Quick context

Portfolio project: wild boar risk mapping for Białołęka district (Warsaw).
- **Live:** https://dzikinabialolece.pl
- **Stack:** Django 5 + PostGIS · React 18 + MapLibre GL · R 4.3 + spatialreg · Docker
- **3 modes:** FAST (Python+SQL square grid) · PUB (R Voronoi) · RESEARCH (8-step R+Python pipeline)
- **Goal:** publish-ready portfolio for technical recruiters
- **Branch:** `main` | **Decisions log:** `/opt/dziki_docs/DECISIONS.md`

## Working rules

1. Spec → Diff → Apply — never skip Diff
2. Read before Write — show current state before any change
3. Evidence > Confidence — every code claim needs grep/view output
4. Bounded scope — every prompt explicit "fix ONLY X"
5. STOP at uncertainty — return to CEO, never auto-decide

## Lokalizacja zasobów poza repozytorium

Repozytorium zawiera WYŁĄCZNIE kod funkcyjny. Pozostałe zasoby:

| Co | Gdzie na dysku |
|----|----------------|
| Dokumentacja (ARCHITECTURE, API, DB…) | `/opt/dziki_docs/docs/` |
| Checkpointy / stan sesji | `/opt/dziki_docs/docs_internal/` |
| Decisions log | `/opt/dziki_docs/DECISIONS.md` |
| Dane GUS (shapefile 500m/1000m) | `/opt/dziki_data/data/gus/` |
| Fixtures SQL / JSON | `/opt/dziki_data/fixtures/` |
| Backup z 2026-05-21 | `/root/dziki_backup_20260521/` |
| Manifesty CEO / Notebook | `/opt/dziki_docs/manifestClaudeCEO.txt` |

## Navigation (kod)

| What | Where in repo |
|------|-------|
| Django app | `src/` |
| React frontend | `frontend/` |
| R pipeline scripts | `r_scripts/` |
| spatialWarsaw package | `spatialModel/` |
| Docker orchestration | `docker-compose.yml`, `Dockerfile.*` |
| Config (nginx/postgres) | `config/` |

## What NOT to do

- Don't modify code without explicit CEO approval
- Don't refactor "while you're there" — bounded scope
- Don't make claims about code without grep/view evidence
- Don't auto-decide "reasonable" actions when STOP condition exists
- Don't overwrite files that already exist — ask first
