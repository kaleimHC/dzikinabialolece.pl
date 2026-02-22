# CLAUDE.md — Instructions for Claude Code in /opt/dziki

**At start of every session:** read `docs_internal/state/00_GIT_STATE.md` for current
branch/commit state, and `docs_internal/state/CHECKPOINT_*.md` (latest) for active context.
`docs/PROJECT_STATUS.md` no longer exists — use the state files above.

## Quick context

Portfolio project: wild boar risk mapping for Białołęka district (Warsaw).
- **Live:** https://dzikinabialolece.pl
- **Stack:** Django 5 + PostGIS · React 18 + MapLibre GL · R 4.3 + spatialreg · Docker
- **3 modes:** FAST (Python+SQL square grid) · PUB (R Voronoi) · RESEARCH (8-step R+Python pipeline)
- **Goal:** publish-ready portfolio for technical recruiters
- **Branch:** `main` (refactor/phase-1 + repair/phase-1 + audit/docs-history merged) | **Decisions log:** `docs/DECISIONS.md`

## Working rules

1. Spec → Diff → Apply — never skip Diff
2. Read before Write — show current state before any change
3. Evidence > Confidence — every code claim needs grep/view output
4. Bounded scope — every prompt explicit "fix ONLY X"
5. STOP at uncertainty — return to CEO, never auto-decide

## Navigation

| What | Where |
|------|-------|
| Current state / checkpoints | `docs_internal/state/CHECKPOINT_*.md` |
| Architectural decisions | `docs/DECISIONS.md` |
| Architecture overview | `docs/ARCHITECTURE.md` |
| Database schema | `docs/DATABASE.md` |
| Research pipeline (8-step R) | `docs/RESEARCH_PIPELINE.md` |
| Frontend (React) | `docs/FRONTEND.md` |
| Setup guide | `docs/GETTING_STARTED.md` |
| Infrastructure (Docker/VPS) | `docs/INFRASTRUCTURE.md` |
| Tech stack reference | `docs/STACK.md` |
| REST API reference | `docs/API_REFERENCE.md` |

## What NOT to do

- Don't modify code without explicit CEO approval
- Don't refactor "while you're there" — bounded scope
- Don't make claims about code without grep/view evidence
- Don't auto-decide "reasonable" actions when STOP condition exists
- Don't overwrite files that already exist — ask first
