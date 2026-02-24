# Frontend Architecture

**Data:** 2025-01-17
**Status:** PRE-FINAL

---

## Tech Stack

| Technologia | Wersja | Rola |
|-------------|--------|------|
| React | 18.x | UI framework |
| Vite | 5.x | Build tool / dev server |
| MapLibre GL JS | 4.x | Map rendering (WebGL) |
| Framer Motion | 11.x | Animations |
| Zustand | 4.x | State management |
| Tailwind CSS | 3.x | Utility-first CSS |

---

## High-Level Architecture

```
+-----------------------------------------------------------------------+
|                              Browser                                   |
+-----------------------------------------------------------------------+
|                                                                       |
|  +-------------------------------------------------------------+      |
|  |                         App.jsx                              |      |
|  |                     (Root Controller)                        |      |
|  +-------------------------------------------------------------+      |
|       |              |                |              |                |
|       v              v                v              v                |
|  +--------+   +------------+   +------------+   +----------+          |
|  | Header |   | MapContainer|   |  Panels   |   | Overlays |          |
|  +--------+   +------------+   +------------+   +----------+          |
|       |              |                |              |                |
|       |              |                |              |                |
|  +-------------------------------------------------------------+      |
|  |                    Zustand Store                             |      |
|  |  (sightings, displayMode, visibleLayers, isAddMode, ...)    |      |
|  +-------------------------------------------------------------+      |
|                              |                                        |
|                              v                                        |
|  +-------------------------------------------------------------+      |
|  |                    Backend API                               |      |
|  |  /api/sightings/, /api/analytics/grid/, /api/analytics/...  |      |
|  +-------------------------------------------------------------+      |
|                                                                       |
+-----------------------------------------------------------------------+
```

---

## Component Hierarchy

```
App.jsx
|
+-- MapContainer.jsx (fullscreen, z=0)
|   +-- MapLibre GL instance
|   +-- 17 GeoJSON sources
|   +-- 27 map layers
|
+-- Header.jsx (fixed top, z=10)
|   +-- Logo / Mini FAB (mobile)
|   +-- "Mapa ryzyka" toggle
|   +-- "Tryb badawczy" toggle (desktop only)
|   +-- OfflineIndicator
|
+-- AnimatePresence mode="wait"
|   |
|   +-- [Desktop] motion.div
|   |   +-- RecalcPanel.jsx
|   |   |   +-- SampleSlider.jsx
|   |   |   +-- Mode buttons (FAST/PUB)
|   |   |   +-- Compute button
|   |   |
|   |   +-- ModeToggle.jsx
|   |   |   +-- LayerToggles.jsx
|   |   |   +-- WeightSliders.jsx (PUB only)
|   |   |
|   |   +-- ReportFAB.jsx
|   |
|   +-- [Mobile] motion.div
|       +-- FloatingPill (left)
|       |   +-- RecalcPanel embedded
|       |
|       +-- FloatingPill (right)
|           +-- LayerToggles bare (FAST)
|           +-- ModeToggle embedded (PUB)
|
+-- CenteredPin.jsx (gdy isAddMode)
+-- ReportSheet.jsx (gdy isAddMode)
+-- ResearchPanel.jsx (gdy showResearchPanel, desktop only)
```

---

## State Management (Zustand)

### Main Store: `sightingsStore.js`

```javascript
useSightingsStore = {
  // Data
  sightings: Feature[],
  selectedSighting: object | null,
  isLoading: boolean,
  error: string | null,

  // Map state (transient - no re-render)
  mapCenter: [lng, lat],
  mapZoom: number,

  // Add mode
  isAddMode: boolean,
  pendingLocation: { lat, lng } | null,

  // Grid visibility
  showFastGrid: boolean,     // FAST mode
  showHeatmap: boolean,      // PUB mode

  // OSM layers (12 toggles)
  visibleLayers: {
    forests, scrub, meadows, parks,
    water, waterways, farmland, allotments,
    buildings, barriers, roads, railway
  },

  // Display mode
  displayMode: 'fast' | 'publication',

  // Research panel
  showResearchPanel: boolean,

  // Actions
  fetchSightings(),
  submitSighting(data),
  enterAddMode(),
  exitAddMode(),
  toggleLayer(key),
  setDisplayMode(mode),
  ...
}
```

### Offline Store: `useOfflineQueue`

```javascript
useOfflineQueue = {
  queue: [],
  addToQueue(sighting),
  processQueue(),
  loadFromStorage()
}
```

---

## Data Flow

### 1. Sightings Flow

```
User adds sighting
       |
       v
+----------------+     +----------------+     +----------------+
| CenteredPin    | --> | ReportSheet    | --> | submitSighting |
| (shows pin)    |     | (type select)  |     | (POST /api/)   |
+----------------+     +----------------+     +----------------+
                                                     |
                                                     v
                                              +----------------+
                                              | fetchSightings |
                                              | (refresh list) |
                                              +----------------+
                                                     |
                                                     v
                                              +----------------+
                                              | MapContainer   |
                                              | (update points)|
                                              +----------------+
```

### 2. Grid Computation Flow

```
User clicks "Oblicz"
       |
       v
+----------------+     +----------------+     +----------------+
| RecalcPanel    | --> | POST /api/     | --> | Backend        |
| handleCompute  |     | pipeline/ or   |     | computation    |
+----------------+     | recalculate/   |     +----------------+
                       +----------------+            |
                                                     v
                                              +----------------+
                                              | CustomEvent    |
                                              | voronoi-refresh|
                                              +----------------+
                                                     |
                                                     v
                                              +----------------+
                                              | MapContainer   |
                                              | fetch grid     |
                                              +----------------+
```

### 3. Layer Toggle Flow

```
User toggles layer
       |
       v
+----------------+     +----------------+     +----------------+
| LayerToggles   | --> | toggleLayer    | --> | visibleLayers  |
| onClick        |     | (store action) |     | (state update) |
+----------------+     +----------------+     +----------------+
                                                     |
                                                     v
                                              +----------------+
                                              | MapContainer   |
                                              | useEffect      |
                                              | setLayoutProp  |
                                              +----------------+
```

---

## Event System

Komponenty komunikuja sie przez `window` CustomEvents:

| Event | Emitter | Listener | Payload |
|-------|---------|----------|---------|
| `voronoi-refresh` | RecalcPanel, SampleSlider | MapContainer | none |
| `bayesian-refresh` | ResearchPanel | MapContainer | none |
| `bayesian-layer-toggle` | ResearchPanel | MapContainer | `{ layer, visible }` |

### Przyklad:

```javascript
// Emitter (RecalcPanel.jsx)
window.dispatchEvent(new CustomEvent('voronoi-refresh'));

// Listener (MapContainer.jsx)
useEffect(() => {
  const handleRefresh = () => fetchRiskGrid();
  window.addEventListener('voronoi-refresh', handleRefresh);
  return () => window.removeEventListener('voronoi-refresh', handleRefresh);
}, []);
```

---

## MapLibre Architecture

### Sources (17)

| Source | Type | Data Origin |
|--------|------|-------------|
| boundaries | geojson | /api/analytics/boundaries/ |
| forests | geojson | /api/analytics/forests/ |
| water | geojson | /api/analytics/water/ |
| waterways | geojson | /api/analytics/waterways/ |
| buildings | geojson | /api/analytics/buildings/ |
| roads | geojson | /api/analytics/roads/ |
| barriers | geojson | /api/analytics/barriers/ |
| allotments | geojson | /api/analytics/allotments/ |
| meadows | geojson | /api/analytics/meadows/ |
| farmland | geojson | /api/analytics/farmland/ |
| parks | geojson | /api/analytics/parks/ |
| scrub | geojson | /api/analytics/scrub/ |
| railway | geojson | /api/analytics/railway/ |
| risk | geojson | /api/analytics/grid/ or /voronoi/ |
| bayesian-results | geojson | /api/analytics/bayesian/ |
| trajectories | geojson | /api/analytics/trajectories/ |
| encounters | geojson + cluster | filtered sightings |
| ryjowisko | geojson + cluster | filtered sightings |

### Layer Ordering (bottom to top)

```
[BOTTOM - base map tiles]
     |
     v
OSM layers (forests, water, buildings, roads...)
     |
     v
risk-fill, risk-outline (grid/voronoi)
     |
     v
bayesian-heatmap, trajectory-lines (research)
     |
     v
encounters, ryjowisko (clusters + points)
     |
     v
boundaries (bialoleka-outline, wisla-line)
     |
[TOP]
```

---

## Responsive Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Mobile | < 768px | FloatingPills, mini FAB in Header |
| Desktop | >= 768px | Fixed panels, FAB bottom-right |

### Hook: `useIsMobile()`

```javascript
export function useIsMobile() {
  return !useMediaQuery('(min-width: 768px)');
}
```

---

## Animation System

### Framer Motion Variants

```javascript
// layoutAnimations.js
containerVariants: { opacity transitions, beforeChildren/afterChildren }
desktopChildVariants.left: { x: -50 -> 0 }
desktopChildVariants.right: { x: 50 -> 0 }
desktopChildVariants.fab: { scale: 0.8 -> 1 }
mobileChildVariants: { y: 30 -> 0 }
```

### Animation Timing

| Element | Duration | Easing |
|---------|----------|--------|
| Layout transitions | 0.3s | easeOut |
| Panel open/close | 0.3s | easeOut |
| Accordion expand | 0.5s | easeOut |
| FAB crossfade | 0.2s | default |
| CenteredPin | spring | stiffness=300, damping=20 |

---

## API Endpoints

### Sightings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/sightings/ | List all sightings |
| POST | /api/sightings/ | Create sighting |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/analytics/grid/ | FAST grid (SQUARE) |
| GET | /api/analytics/voronoi/ | PUB grid (VORONOI) |
| POST | /api/analytics/pipeline/ | Run FAST pipeline |
| POST | /api/analytics/recalculate/ | Run PUB pipeline |
| GET | /api/analytics/boundaries/ | District + river boundaries |
| GET | /api/analytics/{layer}/ | OSM layers (12 endpoints) |
| GET | /api/analytics/bayesian/ | Bayesian results |
| GET | /api/analytics/trajectories/ | Migration corridors |
| GET | /api/analytics/samples/current/ | Current sample info |
| POST | /api/analytics/samples/switch/ | Switch sample size |

---

## File Structure Summary

```
frontend/
├── src/
│   ├── main.jsx              # Entry point
│   ├── App.jsx               # Root controller
│   ├── components/           # 13 components
│   ├── hooks/                # 2 custom hooks
│   ├── stores/               # Zustand store
│   ├── config/               # Animation variants
│   ├── utils/                # Cluster config
│   └── styles/               # Global CSS
├── docs/
│   ├── FRONTEND_AUDIT_2025-01-17.md
│   ├── MOBILE_UI_STATUS.md
│   ├── GRID_ANIMATION_REPORT.md
│   ├── ARCHITECTURE.md       # This file
│   └── CHANGELOG.md
├── public/
│   └── styles/
│       └── dark-wildlife.json
├── package.json
├── vite.config.js
└── README.md
```
