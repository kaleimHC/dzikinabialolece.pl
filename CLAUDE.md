# CLAUDE.md — Instructions for Claude Code in /opt/dziki

**Always read `docs/PROJECT_STATUS.md` FIRST at start of every session.**
That file is the source of truth for project state, working patterns, 
and anti-patterns to avoid.

## Quick context

Portfolio project: wild boar risk mapping for Białołęka district (Warsaw).
- **Live:** https://dzikinabialolece.pl
- **Stack:** Django 5 + PostGIS · React 18 + MapLibre GL · R 4.3 + spatialreg · Docker
- **3 modes:** FAST (Python+SQL square grid) · PUB (R Voronoi) · RESEARCH (8-step R+Python pipeline)
- **Goal:** publish-ready portfolio for technical recruiters

## Working rules (full list in PROJECT_STATUS.md)

1. Spec → Diff → Apply — never skip Diff
2. Read before Write — show current state before any change
3. Evidence > Confidence — every code claim needs grep/view output
4. Bounded scope — every prompt explicit "fix ONLY X"
5. STOP at uncertainty — return to CEO, never auto-decide

## Navigation

| What | Where |
|------|-------|
| Current state, milestones, backlog | `docs/PROJECT_STATUS.md` |
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
- Full anti-patterns list: see PROJECT_STATUS.md "Anti-patterns" section
