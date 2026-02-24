# Changelog

Wszystkie istotne zmiany w frontend sa dokumentowane w tym pliku.

---

## [PRE-FINAL] - 2025-01-17

### Frontend Audit

Przeprowadzono pelny audyt kodu frontendu:

- **17 plikow JS/JSX**, ~3,303 LOC
- **13 komponentow React**
- **17 MapLibre sources**, 27 layers
- **2 custom hooks**, 2 Zustand stores

Szczegoly: [FRONTEND_AUDIT_2025-01-17.md](FRONTEND_AUDIT_2025-01-17.md)

### Mobile UI - KOMPLETNE

- FloatingPill z `position: fixed` i wlasnymi animacjami
- FAST mode: `<LayerToggles bare />` (tylko checkboxy)
- PUB mode: `<ModeToggle embedded />` (pelny accordion)
- FSM hook `useLayoutTransition` koordynujacy Desktop <-> Mobile
- Header crossfade: emoji dzika <-> mini FAB (+)
- Panele animuja sie out przy `isAddMode`

Szczegoly: [MOBILE_UI_STATUS.md](MOBILE_UI_STATUS.md)

### Dokumentacja

- [x] `frontend/README.md` - Quick start, struktura, komponenty
- [x] `docs/FRONTEND_AUDIT_2025-01-17.md` - Ground truth
- [x] `docs/MOBILE_UI_STATUS.md` - Mobile UI status
- [x] `docs/ARCHITECTURE.md` - Architektura i data flow
- [x] `docs/CHANGELOG.md` - Ten plik

### Cleanup

- [x] Usunieto `MapContainer.jsx.bak`

---

## W trakcie

- [ ] Animacje grid crossfade FAST <-> PUB (patrz [GRID_ANIMATION_REPORT.md](GRID_ANIMATION_REPORT.md))

---

## Do naprawy (backlog)

| Issue | Priorytet | Opis |
|-------|-----------|------|
| Lazy loading OSM | Medium | Wszystkie warstwy ladowane na starcie |
| Error boundaries | Medium | Brak ErrorBoundary w App |
| Console.logs cleanup | Low | Usunac przed produkcja |
| Skeleton states | Low | Brak loading skeletons |
| ReportSheet mobile | Low | Za waski na mobile |

---

## Historia (wczesniejsze sesje)

### 2025-01-17 (sesja Mobile UI)

```
f69fba1 UI reorganization: mode selection to RecalcPanel, FloatingPill fixes
6d3efd7 Header animations + OSM attribution to header
0975d77 FSM animation orchestration for Desktop/Mobile layouts
571eb38 Responsive mobile UI with FloatingPills
```

### 2025-01-16 (sesja Research Panel)

- ResearchPanel z MCMC configuration
- Bayesian layer toggle
- Trajectory visualization

### 2025-01-15 (sesja OSM Layers)

- 12 warstw OSM z toggles
- LayerToggles component
- Cluster adaptive sizing

### 2025-01-12 (sesja Bayesian Integration)

- BayesianResult, Trajectory, PriorConfig models
- API endpoints dla Bayesian
- R scripts integration
