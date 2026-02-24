# Frontend Audit - Ground Truth

**Data:** 2025-01-17
**Status:** PRE-FINAL
**Zrodlo:** Automatyczny audyt Claude Code

> Ten plik jest ZRODLEM PRAWDY dla dokumentacji. Inne pliki docs powinny byc spojne z tym audytem.

---

## CZESC A: STRUKTURA PROJEKTU

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

**Lacznie:** ~3,303 LOC w 17 plikach JS/JSX

---

## CZESC B: ANALIZA KOMPONENTOW

### B.1 App.jsx (135 LOC) - Root Component

| Aspekt | Opis |
|--------|------|
| **Odpowiedzialnosc** | Orkiestracja layoutow Desktop/Mobile, zarzadzanie pill'ami |
| **Zaleznosci** | Framer Motion, wszystkie komponenty, Zustand store, hooki |
| **Kluczowe stany** | `openPill` (null\|'left'\|'right'), `layout` z hooka |

**Struktura renderowania:**
```
App
├── MapContainer (fullscreen, z=0)
├── Header (fixed top, z=10)
├── CenteredPin (tylko gdy isAddMode)
├── ReportSheet (bottom sheet, z=200)
├── AnimatePresence mode="wait"
│   ├── [Desktop] motion.div key="desktop-layout"
│   │   ├── RecalcPanel (bottom-left)
│   │   ├── ModeToggle (top-right)
│   │   └── ReportFAB (bottom-right)
│   └── [Mobile] motion.div key="mobile-layout"
│       ├── FloatingPill side="left" -> RecalcPanel embedded
│       └── FloatingPill side="right" -> LayerToggles bare | ModeToggle embedded
└── ResearchPanel (side panel, z=20)
```

**Warunkowe renderowanie Mobile:**
```javascript
{displayMode === 'fast' ? (
  <LayerToggles bare />  // Tylko checkboxy
) : (
  <ModeToggle embedded /> // Pelny accordion
)}
```

---

### B.2 MapContainer.jsx (556 LOC) - GLOWNA MAPA

| Aspekt | Opis |
|--------|------|
| **Biblioteka** | MapLibre GL JS |
| **Style** | `/styles/dark-wildlife.json` (custom dark theme) |
| **Center** | [20.98, 52.33] (Bialoleka) |

**ZRODLA (17 total):**

| Source | Typ | Endpoint | Cluster |
|--------|-----|----------|---------|
| `boundaries` | geojson | `/api/analytics/boundaries/` | - |
| `forests` | geojson | `/api/analytics/forests/` | - |
| `water` | geojson | `/api/analytics/water/` | - |
| `waterways` | geojson | `/api/analytics/waterways/` | - |
| `buildings` | geojson | `/api/analytics/buildings/` | - |
| `roads` | geojson | `/api/analytics/roads/` | - |
| `barriers` | geojson | `/api/analytics/barriers/` | - |
| `allotments` | geojson | `/api/analytics/allotments/` | - |
| `meadows` | geojson | `/api/analytics/meadows/` | - |
| `farmland` | geojson | `/api/analytics/farmland/` | - |
| `parks` | geojson | `/api/analytics/parks/` | - |
| `scrub` | geojson | `/api/analytics/scrub/` | - |
| `railway` | geojson | `/api/analytics/railway/` | - |
| `risk` | geojson | `/api/analytics/grid/` lub `/voronoi/` | - |
| `bayesian-results` | geojson | `/api/analytics/bayesian/` | - |
| `trajectories` | geojson | `/api/analytics/trajectories/` | - |
| `encounters` | geojson | sightings (filtered) | maxZoom=14, radius=50 |
| `ryjowisko` | geojson | sightings (filtered) | maxZoom=14, radius=50 |

**WARSTWY (27 total):**

| Layer | Type | Source | Z-Order |
|-------|------|--------|---------|
| `forests-fill` | fill | forests | 1 |
| `water-fill` | fill | water | 2 |
| `waterways-line` | line | waterways | 3 |
| `buildings-fill` | fill | buildings | 4 |
| `roads-line` | line | roads | 5 |
| `barriers-line` | line | barriers | 6 |
| `allotments-fill` | fill | allotments | 7 |
| `meadows-fill` | fill | meadows | 8 |
| `farmland-fill` | fill | farmland | 9 |
| `parks-fill` | fill | parks | 10 |
| `scrub-fill` | fill | scrub | 11 |
| `railway-line` | line | railway | 12 |
| `risk-fill` | fill | risk | 13 |
| `risk-outline` | line | risk | 14 |
| `bayesian-heatmap` | fill | bayesian-results | 15 (hidden) |
| `trajectory-lines` | line | trajectories | 16 (hidden) |
| `encounters-clusters` | circle | encounters | 17 |
| `encounters-cluster-count` | symbol | encounters | 18 |
| `encounters-point` | circle | encounters | 19 |
| `encounters-hover-ring` | circle | encounters | 20 |
| `ryjowisko-clusters` | circle | ryjowisko | 21 |
| `ryjowisko-cluster-count` | symbol | ryjowisko | 22 |
| `ryjowisko-point` | circle | ryjowisko | 23 |
| `ryjowisko-hover-ring` | circle | ryjowisko | 24 |
| `bialoleka-outline` | line | boundaries | 25 (TOP) |
| `wisla-line` | line | boundaries | 26 (TOP) |

**Risk Grid Color Scale:**
```javascript
["interpolate", ["linear"], ["get", "risk"],
  0.0, "#1e3a2f",   // dark green
  0.1, "#22c55e",   // green
  0.25, "#84cc16",  // lime
  0.4, "#eab308",   // yellow
  0.55, "#f97316",  // orange
  0.7, "#ef4444",   // red
  0.85, "#dc2626",  // dark red
  1.0, "#991b1b"    // very dark red
]
```

**Event Listeners:**
- `voronoi-refresh` -> refetch risk grid
- `bayesian-layer-toggle` -> toggle Bayesian/trajectories visibility
- `bayesian-refresh` -> refetch Bayesian data

---

### B.3 Header.jsx (181 LOC)

| Element | Desktop | Mobile |
|---------|---------|--------|
| Logo/FAB | emoji dzika | + button (mini FAB) |
| "Mapa ryzyka" | tak | tak |
| "Tryb badawczy" | tak | nie (hidden) |
| OfflineIndicator | tak | tak |

**Logika toggle mapy ryzyka:**
```javascript
const isFastMode = displayMode === 'fast';
const isMapVisible = isFastMode ? showFastGrid : showHeatmap;
const toggleMap = isFastMode ? toggleFastGrid : toggleHeatmap;
```

---

### B.4 RecalcPanel.jsx (264 LOC)

| Sekcja | Opis |
|--------|------|
| SampleSlider | Accordion z sliderem 100/500/1500/3500 |
| Mode Selection | Przyciski FAST / spatialWarsaw |
| Compute Button | "Oblicz mape ryzyka" |
| Progress | Pasek postepu (tylko PUB mode) |

**API Calls:**
- FAST mode: `POST /api/analytics/pipeline/` -> sync
- PUB mode: `POST /api/analytics/recalculate/?mode=full` -> async + polling

---

### B.5 ResearchPanel.jsx (830 LOC) - Najwiekszy komponent

| Sekcja | Funkcja |
|--------|---------|
| ModelSelector | 4 presety: quick_preview, conservative, aggressive, publication |
| ParameterControls | MCMC params (iterations, warmup, chains, rho, delta, kappa) |
| Run Pipeline | Uruchom Bayesian Pipeline |
| Layer Toggles | bayesianHeatmap, trajectories, highRiskOnly |
| Diagnostics | R-hat, ESS, konwergencja |
| Ensemble Weights | RF/GWR/ETA procentowo |
| ResultsTable | Sortowalna tabela wynikow |
| Legenda | Gradient ryzyka + korytarze migracji |

---

### B.6 Pozostale komponenty

| Komponent | LOC | Odpowiedzialnosc |
|-----------|-----|------------------|
| SampleSlider | 238 | Slider proby + async switch |
| ModeToggle | 52 | Kontener LayerToggles + WeightSliders |
| LayerToggles | 183 | Grid 12 warstw OSM (2 kolumny) |
| WeightSliders | 223 | 5 wag srodowiskowych + "Przelicz cechy" |
| FloatingPill | 99 | Mobile floating panel z animacja |
| ReportSheet | 128 | Bottom sheet do zglaszania |
| ReportFAB | 21 | Przycisk "+" (desktop) |
| CenteredPin | 42 | Pin SVG z emoji dzika |

---

## CZESC C: HOOKI

### C.1 useMediaQuery.js (46 LOC)

```javascript
// Uzycie React 18 useSyncExternalStore dla bezpieczenstwa
export function useMediaQuery(query) { ... }
export function useIsMobile() { return !useMediaQuery('(min-width: 768px)'); }
export function useIsDesktop() { return useMediaQuery('(min-width: 768px)'); }
```

**Breakpoint:** 768px (md w Tailwind)

### C.2 useLayoutTransition.js (41 LOC)

```javascript
export function useLayoutTransition(isMobile) {
  const layout = isMobile ? 'mobile' : 'desktop';
  const [isTransitioning, setIsTransitioning] = useState(false);
  return { layout, onExitComplete, isTransitioning };
}
```

**Cel:** Koordynacja AnimatePresence mode="wait"

---

## CZESC D: STORE (Zustand)

### sightingsStore.js (210 LOC)

| Slice | Keys |
|-------|------|
| **Data** | sightings, selectedSighting, isLoading, error |
| **Map** | mapCenter, mapZoom (transient - nie rerenderuje) |
| **Add Mode** | isAddMode, pendingLocation |
| **Grid Visibility** | showFastGrid, showHeatmap |
| **OSM Layers** | visibleLayers (12 boolean flags) |
| **Display Mode** | displayMode ('fast' \| 'publication') |
| **Research** | showResearchPanel |

**Async Actions:**
- `fetchSightings()` -> `GET /api/sightings/`
- `submitSighting(data)` -> `POST /api/sightings/`

**Offline Queue (useOfflineQueue):**
- IndexedDB storage dla PWA
- Auto-sync przy `online` event

---

## CZESC E: KONFIGURACJA

### layoutAnimations.js (107 LOC)

| Variant | Animacja |
|---------|----------|
| `containerVariants` | opacity 0->1, beforeChildren/afterChildren |
| `desktopChildVariants.left` | x: -50->0 (RecalcPanel) |
| `desktopChildVariants.right` | x: 50->0 (ModeToggle) |
| `desktopChildVariants.fab` | scale: 0.8->1 (FAB) |
| `mobileChildVariants` | y: 30->0 |

**Stale:**
- `ANIMATION_DURATION = 0.3s`
- `ANIMATION_EASE = 'easeOut'`

---

## CZESC F: MAPCONTAINER SZCZEGOLY

### F.1 Lifecycle

```
1. useEffect (mount) -> new maplibregl.Map()
2. map.on("load") -> addSource/addLayer x 27
3. setMapReady(true)
4. useEffect [mapReady] -> fetch boundaries, OSM layers
5. useEffect [displayMode] -> fetch risk grid
6. useEffect [sightings] -> update encounters/ryjowisko
7. useEffect [visibleLayers] -> toggle OSM visibility
8. useEffect [showFastGrid, showHeatmap] -> toggle risk visibility
```

### F.2 Grid Switching (BRAK ANIMACJI)

```javascript
// Linia 351-383 - NATYCHMIASTOWA PODMIANA
const url = displayMode === 'fast'
  ? '/api/analytics/grid/'      // SQUARE cells (~9,875)
  : '/api/analytics/voronoi/';  // VORONOI cells (dynamicznie)

fetch(url).then(data => {
  mapRef.current?.getSource("risk").setData(data);  // INSTANT
});
```

**UWAGA:** Brak crossfade miedzy gridami (patrz GRID_ANIMATION_REPORT.md)

### F.3 Cluster Configuration

```javascript
// clusterConfig.js - adaptive sizing
getPointRadius(n, zoom)  // K / log10(n+10) * zoomFactor
getRadiusExpression(n)   // MapLibre interpolate expression
```

---

## CZESC G: MOBILE vs DESKTOP

| Aspekt | Desktop (>=768px) | Mobile (<768px) |
|--------|-------------------|-----------------|
| **RecalcPanel** | Fixed bottom-left, panel | FloatingPill left, embedded |
| **ModeToggle** | Fixed top-right, panel | FloatingPill right (PUB) |
| **LayerToggles** | W ModeToggle (accordion) | FloatingPill right (bare) - FAST |
| **ReportFAB** | Fixed bottom-right | Header mini FAB |
| **ResearchPanel** | Side panel | Hidden |
| **Transitions** | Slide left/right | Slide up |

**Pill Content Logic:**
- FAST mode -> `<LayerToggles bare />` (tylko checkboxy)
- PUB mode -> `<ModeToggle embedded />` (accordion z WeightSliders)

---

## CZESC H: TRYBY ANALITYCZNE

### H.1 FAST Mode (fastPython)

| Parametr | Wartosc |
|----------|---------|
| Grid | SQUARE (100m x 100m) |
| Cells | ~9,875 (stale) |
| Endpoint | `/api/analytics/grid/` |
| Pipeline | `/api/analytics/pipeline/` (sync) |
| Czas | ~2-5 sekund |

### H.2 PUB Mode (spatialWarsaw)

| Parametr | Wartosc |
|----------|---------|
| Grid | VORONOI (centroidy obserwacji) |
| Cells | **Dynamicznie** (zalezne od sample size) |
| Endpoint | `/api/analytics/voronoi/` |
| Pipeline | `/api/analytics/recalculate/?mode=full` (async) |
| Czas | ~2-5 minut (5 R scripts) |

**UWAGA:** Liczba komorek Voronoi zalezy od wielkosci proby (100/500/1500/3500).

### H.3 Bayesian Mode (Research)

| Parametr | Wartosc |
|----------|---------|
| Presets | quick_preview, conservative, aggressive, publication |
| MCMC | iterations, warmup, chains |
| Params | rho (persistence), delta (diffusion), kappa |
| Diagnostics | R-hat, ESS, convergence |

---

## CZESC I: ANIMACJE (Framer Motion)

| Komponent | Typ animacji | Czas |
|-----------|--------------|------|
| App layouts | AnimatePresence mode="wait" | 0.3s |
| Desktop panels | x slide (+/-50px) | 0.3s |
| Mobile pills | y slide (30px) | 0.3s |
| FloatingPill panel | height auto | 0.3s |
| Header FAB crossfade | scale + opacity | 0.2s |
| ReportSheet | y slide (80px) | 0.5s |
| CenteredPin | spring (y: -30->0) | spring |
| Accordion content | height + opacity | 0.5s |
| ResearchPanel | x slide (80px) | 0.5s |
| Progress bars | width % | motion |

---

## CZESC J: PROBLEMY / DO NAPRAWY

### J.1 Potencjalne problemy

| Problem | Lokalizacja | Sugestia |
|---------|-------------|----------|
| Brak animacji grid switch | MapContainer:351-383 | Implementacja crossfade |
| OSM layers fetch ALL on mount | MapContainer:387-413 | Lazy loading przy toggle |
| No error boundaries | App.jsx | Dodac ErrorBoundary |
| No skeleton states | Components | Dodac loading skeletons |
| No debounce na slider | WeightSliders | Dodac debounce |
| Console.logs | MapContainer | Usunac w production |

### J.2 Duplikacja logiki

| Duplikacja | Gdzie |
|------------|-------|
| Fetch + setData pattern | MapContainer (x12 razy) |
| Accordion animation | SampleSlider, LayerToggles, WeightSliders |
| Button styling | RecalcPanel, SampleSlider, WeightSliders |

---

## CZESC K: PODSUMOWANIE

### K.1 Statystyki

| Metryka | Wartosc |
|---------|---------|
| Pliki JS/JSX | 17 |
| Laczny LOC | ~3,303 |
| Komponenty | 13 |
| Hooki custom | 2 |
| Stores | 2 (main + offline) |
| MapLibre sources | 17 |
| MapLibre layers | 27 |
| API endpoints | ~20 |

### K.2 Architektura

```
+-------------------------------------------------------------+
|                         App.jsx                              |
|  +----------------------------------------------------------+|
|  |                   Zustand Store                          ||
|  |  displayMode, sightings, visibleLayers, isAddMode...    ||
|  +----------------------------------------------------------+|
|                              |                               |
|    +-------------------------+-------------------------+     |
|    |                         |                         |     |
|    v                         v                         v     |
| +------------+    +------------------+    +------------+     |
| |   Header   |    |   MapContainer   |    |  Panels    |     |
| |  (toggles) |    |   (MapLibre)     |    |  (UI)      |     |
| +------------+    +------------------+    +------------+     |
|                              |                               |
|                   +----------+-----------+                   |
|                   |    CustomEvents      |                   |
|                   |  voronoi-refresh     |                   |
|                   |  bayesian-refresh    |                   |
|                   |  bayesian-layer-toggle                   |
|                   +----------------------+                   |
+-------------------------------------------------------------+
```

### K.3 Mocne strony

1. **Czysta separacja** - komponenty maja jasna odpowiedzialnosc
2. **Responsive design** - dobrze zaimplementowane Desktop/Mobile
3. **Animacje** - plynne przejscia z Framer Motion
4. **Store** - centralne zarzadzanie stanem (Zustand)
5. **Offline support** - IndexedDB queue
6. **Adaptive sizing** - dynamiczne rozmiary punktow na mapie

### K.4 Do poprawy

1. **Grid animation** - brak plynnego przejscia FAST<->PUB
2. **Lazy loading OSM** - wszystkie warstwy laduja sie na starcie
3. **Error handling** - brak ErrorBoundary, slabe error states
4. **Code duplication** - accordion/button/fetch patterns
