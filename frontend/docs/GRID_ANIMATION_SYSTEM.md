# Grid Animation System - Crossfade FAST ↔ PUB

**Status:** ✅ PRODUCTION READY
**Data:** 2025-01-17
**Commit:** d20a446
**Pliki:** `hooks/useGridTransition.js`, `utils/animateOpacity.js`

---

## Architektura

### Pliki

| Plik | LOC | Rola |
|------|-----|------|
| `hooks/useGridTransition.js` | ~180 | Hook React kontrolujący całą logikę przejść |
| `utils/animateOpacity.js` | ~100 | Helpery animacji (rAF, waitForMapIdle, waitForSourceData) |

### Tryby przejścia

| Trigger | Zachowanie | Animacja |
|---------|------------|----------|
| displayMode change (FAST ↔ PUB) | Crossfade | ✅ 300ms fade-out → fetch → 300ms fade-in |
| toggle ON/OFF (showFastGrid/showHeatmap) | Instant | ❌ Natychmiastowe (jeśli mode się nie zmienił) |
| voronoi-refresh event | Instant | ❌ Tylko setData (user oczekuje nowych danych) |
| Pierwszy load | Instant | ❌ Fetch + show |

---

## Sekwencja Crossfade

```
USER CLICK (FAST → PUB)
    │
    ▼
┌─────────────────────────────────────┐
│ EFEKT 1: Sprawdza displayMode       │
│ → modeChanged = true → SKIP         │
│ (crossfade przejmie kontrolę)       │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ EFEKT 2: Crossfade                  │
│                                     │
│ FAZA 1: RÓWNOLEGŁE                  │
│ ├── animateOpacity(0.65 → 0, 300ms) │
│ └── fetch('/api/analytics/voronoi/')│
│                                     │
│ FAZA 2: setData + wait              │
│ ├── source.setData(data)            │
│ └── waitForMapIdle() [>5000 feat]   │
│     lub waitForSourceData() [<5000] │
│                                     │
│ FAZA 3: Fade-in                     │
│ └── animateOpacity(0 → 0.65, 300ms) │
└─────────────────────────────────────┘
```

---

## Kluczowe mechanizmy

### 1. Zapobieganie flash starych danych

**Problem:** EFEKT 1 (instant toggle) odpalał się PRZED EFEKT 2 (crossfade) i ustawiał opacity na stare dane.

**Rozwiązanie:** EFEKT 1 sprawdza `displayMode !== prevDisplayModeRef.current` i robi SKIP jeśli mode się zmienił.

```javascript
// EFEKT 1
const modeChanged = displayMode !== prevDisplayModeRef.current;
if (modeChanged) return; // crossfade will handle
```

### 2. waitForMapIdle vs waitForSourceData

| Funkcja | Kiedy używać | Event MapLibre |
|---------|--------------|----------------|
| `waitForSourceData` | <5000 features | `sourcedata` + `isSourceLoaded` |
| `waitForMapIdle` | ≥5000 features | `idle` (GPU finished) |

**Dlaczego:** Dla 10k kwadratów FAST, `sourcedata` może być emitowane ZANIM GPU skończy przetwarzanie. `idle` czeka na zakończenie WSZYSTKICH operacji renderowania.

### 3. AbortController + Token

```javascript
const myToken = ++transitionTokenRef.current;
if (abortControllerRef.current) abortControllerRef.current.abort();
// ...fetch with signal...
if (myToken !== transitionTokenRef.current) return; // cancelled
```

Zapobiega race conditions przy szybkim klikaniu między trybami.

### 4. Ścieżka "invisible"

Gdy grid był niewidoczny (toggle OFF), crossfade:

1. NIE robi fade-out (opacity już = 0)
2. Fetch + setData
3. waitForMapIdle (dla dużych) lub waitForSourceData
4. Fade-in 300ms (jeśli toggle ON w trybie docelowym)

### 5. Równoległy fetch

Fade-out i fetch wykonują się RÓWNOLEGLE dzięki `Promise.all()`:

```javascript
const results = await Promise.all([...fadeOutPromises, fetchPromise]);
```

To oszczędza ~300ms w każdym przejściu!

---

## Parametry

| Parametr | Wartość | Gdzie |
|----------|---------|-------|
| FADE_DURATION | 300ms | useGridTransition.js |
| FILL_OPACITY | 0.65 | useGridTransition.js |
| OUTLINE_OPACITY | 0.3 | useGridTransition.js |
| Large dataset threshold | 5000 features | useGridTransition.js |
| waitForMapIdle timeout | 2000ms | animateOpacity.js |
| waitForSourceData timeout | 500ms | animateOpacity.js |

---

## API

### useGridTransition(mapRef, mapReady, displayMode, showFastGrid, showHeatmap)

**Input:**
- `mapRef` - React ref do instancji MapLibre
- `mapReady` - boolean, czy mapa jest gotowa
- `displayMode` - `'fast'` | `'publication'`
- `showFastGrid` - boolean, toggle dla FAST mode
- `showHeatmap` - boolean, toggle dla PUB mode

**Output:**
- `{ isAnimating }` - czy animacja jest w toku

### animateOpacity(map, layerId, property, from, to, duration)

Animuje paint property przez `requestAnimationFrame` z easeOutCubic.

```javascript
await animateOpacity(map, 'risk-fill', 'fill-opacity', 0.65, 0, 300);
```

### waitForMapIdle(map, maxWait)

Czeka na event `idle` z timeoutem. Używaj dla dużych datasetów.

```javascript
await waitForMapIdle(map, 2000);
```

### waitForSourceData(map, sourceId, maxWait)

Czeka na event `sourcedata` z `isSourceLoaded: true`. Używaj dla małych datasetów.

```javascript
await waitForSourceData(map, 'risk', 500);
```

---

## Debugging

Jeśli pojawi się flash starych danych:

1. Sprawdź czy EFEKT 1 robi SKIP przy zmianie displayMode
2. Sprawdź czy `waitForMapIdle` jest używane dla >5000 features
3. Zwiększ timeout w `waitForMapIdle` jeśli potrzeba

**Dodaj tymczasowo logi:**

```javascript
// Na początku useGridTransition
const log = (msg, data) => console.log(`[GridTransition] ${msg}`, data);

// Przed każdą operacją
log('EFEKT 1 START', { displayMode, shouldBeVisible });
```

---

## Grid Types

| Tryb | Grid | Endpoint | Typical Features |
|------|------|----------|------------------|
| FAST | SQUARE (100m×100m) | `/api/analytics/grid/` | ~9,875 |
| PUB | VORONOI (dynamic) | `/api/analytics/voronoi/` | ~500 |

---

## Warstwy MapLibre

| Layer ID | Property | Opacity |
|----------|----------|---------|
| `risk-fill` | `fill-opacity` | 0.65 |
| `risk-outline` | `line-opacity` | 0.3 |

---

## Historia

- **2025-01-17** - Implementacja crossfade, debugging, production release
- **Commit:** `d20a446` - feat: grid crossfade animation FAST <-> PUB - production ready
