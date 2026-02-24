# Dziki na Bialolece — Frontend

**Status:** PRE-FINAL
**LOC:** ~3,300 w 17 plikach
**Tech:** React 18 + MapLibre GL + Framer Motion + Zustand + Tailwind CSS

---

## 🔴 PRODUKCJA - KRYTYCZNE!

**Frontend działa w trybie DEV na VPS!**

```bash
# Aktualnie uruchomiony (ŹLE!):
npm run dev  # Node process PID 29

# WYMAGANE - build produkcyjny:
npm run build
# Potem zmień nginx aby serwował /app/dist/
```

Pełna instrukcja: [DZIKI_TODO_NEXT_SESSION.md](../DZIKI_TODO_NEXT_SESSION.md)

---

## Quick Start

```bash
# Z Docker (zalecane)
docker-compose up frontend

# Lub lokalnie
cd frontend
npm install
npm run dev
```

Aplikacja dostepna na: http://localhost:5173

## Struktura

```
frontend/src/
├── main.jsx                    # Entry point (Vite)
├── App.jsx                     # Root component (135 LOC)
├── components/
│   ├── MapContainer.jsx        # Glowna mapa (556 LOC)
│   ├── Header.jsx              # Naglowek + toggles (181 LOC)
│   ├── RecalcPanel.jsx         # Panel obliczen (264 LOC)
│   ├── ResearchPanel.jsx       # Panel badawczy MCMC (830 LOC)
│   ├── SampleSlider.jsx        # Slider proby (238 LOC)
│   ├── ModeToggle.jsx          # Kontener warstw (52 LOC)
│   ├── LayerToggles.jsx        # Grid 12 warstw OSM (183 LOC)
│   ├── WeightSliders.jsx       # Slidery wag srodowiskowych (223 LOC)
│   ├── FloatingPill.jsx        # Mobile floating panel (99 LOC)
│   ├── ReportSheet.jsx         # Formularz zgloszenia (128 LOC)
│   ├── ReportFAB.jsx           # Floating Action Button (21 LOC)
│   └── CenteredPin.jsx         # Pin przy dodawaniu (42 LOC)
├── hooks/
│   ├── useLayoutTransition.js  # FSM Desktop<->Mobile (41 LOC)
│   └── useMediaQuery.js        # Media queries (46 LOC)
├── stores/
│   └── sightingsStore.js       # Zustand store (210 LOC)
├── config/
│   └── layoutAnimations.js     # Framer Motion variants (107 LOC)
├── utils/
│   └── clusterConfig.js        # Adaptive circle sizing (303 LOC)
└── styles/
    └── globals.css             # Tailwind + custom styles
```

## Komponenty

| Komponent | LOC | Odpowiedzialnosc |
|-----------|-----|------------------|
| MapContainer | 556 | Glowna mapa MapLibre, 17 zrodel, 27 warstw |
| ResearchPanel | 830 | Panel badawczy MCMC, diagnostyka, wyniki |
| RecalcPanel | 264 | Panel obliczen, slider proby, mode selection |
| SampleSlider | 238 | Slider wielkosci proby (100-3500) |
| WeightSliders | 223 | Slidery 5 wag srodowiskowych |
| LayerToggles | 183 | Grid 12 warstw OSM |
| Header | 181 | Naglowek, toggle mapy ryzyka, tryb badawczy |
| App | 135 | Orkiestracja layoutow Desktop/Mobile |
| ReportSheet | 128 | Bottom sheet do zglaszania obserwacji |
| FloatingPill | 99 | Mobile floating panel z animacja |
| ModeToggle | 52 | Kontener dla LayerToggles + WeightSliders |
| CenteredPin | 42 | Pin SVG przy dodawaniu obserwacji |
| ReportFAB | 21 | Floating Action Button (desktop) |

## Mapa

- **17 zrodel GeoJSON** — OSM layers, risk grid, bayesian, trajectories, sightings
- **27 warstw** — fill, line, circle, symbol
- **Risk grid:** SQUARE (fast) lub VORONOI (publication)
- **Clustering:** encounters + ryjowisko z adaptive sizing

## Tryby analityczne

| Tryb | Grid | Cells | Endpoint |
|------|------|-------|----------|
| **fastPython** | SQUARE (100m x 100m) | ~9,875 (stale) | `/api/analytics/grid/` |
| **spatialWarsaw** | VORONOI | dynamicznie* | `/api/analytics/voronoi/` |

*Liczba komorek Voronoi zalezy od wielkosci proby (100/500/1500/3500)

## Mobile vs Desktop

| Aspekt | Desktop (>=768px) | Mobile (<768px) |
|--------|-------------------|-----------------|
| RecalcPanel | Fixed bottom-left | FloatingPill left |
| ModeToggle | Fixed top-right | FloatingPill right (PUB) |
| LayerToggles | W ModeToggle | FloatingPill right (FAST) |
| ReportFAB | Fixed bottom-right | Header mini FAB |
| ResearchPanel | Side panel | Hidden |
| Animacje | Slide left/right | Slide up |

## Tech Stack

| Technologia | Wersja | Rola |
|-------------|--------|------|
| React | 18.x | UI framework |
| Vite | 5.x | Build tool |
| MapLibre GL JS | 4.x | Map rendering |
| Framer Motion | 11.x | Animations |
| Zustand | 4.x | State management |
| Tailwind CSS | 3.x | Styling |

## Dokumentacja szczegolowa

- [FRONTEND_AUDIT_2025-01-17.md](docs/FRONTEND_AUDIT_2025-01-17.md) — pelny audyt kodu
- [MOBILE_UI_STATUS.md](docs/MOBILE_UI_STATUS.md) — status Mobile UI
- [GRID_ANIMATION_REPORT.md](docs/GRID_ANIMATION_REPORT.md) — raport o animacjach grid
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — architektura i data flow
- [CHANGELOG.md](docs/CHANGELOG.md) — historia zmian

## Event System

Komponenty komunikuja sie przez CustomEvents:

| Event | Emitter | Listener | Opis |
|-------|---------|----------|------|
| `voronoi-refresh` | RecalcPanel | MapContainer | Odswiez risk grid |
| `bayesian-refresh` | ResearchPanel | MapContainer | Odswiez dane Bayesian |
| `bayesian-layer-toggle` | ResearchPanel | MapContainer | Toggle warstw Bayesian |

## Development

```bash
# Uruchom dev server
npm run dev

# Build produkcyjny
npm run build

# Preview buildu
npm run preview
```

## Known Issues

- [ ] Brak animacji przy przelaczaniu FAST <-> PUB (instant switch)
- [ ] OSM layers ladowane na starcie (mozliwy lazy loading)
- [ ] Brak ErrorBoundary
- [ ] Console.logs do usuniecia przed produkcja
