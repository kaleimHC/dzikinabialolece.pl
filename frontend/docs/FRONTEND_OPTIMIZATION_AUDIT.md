# Frontend Optimization Audit

**Data:** 2025-01-17
**Audytor:** Claude Code
**Scope:** `frontend/src/` (22 pliki, 3,962 LOC)

---

## 📊 STATYSTYKI

| Metryka | Wartość |
|---------|---------|
| Total Files | 22 |
| Total LOC | 3,962 |
| Components | 14 |
| Custom Hooks | 3 |
| Utilities | 2 |
| Store Hooks | 2 |

### Rozkład komponentów

| Rozmiar | Ilość | Pliki |
|---------|-------|-------|
| Large (>300 LOC) | 2 | MapContainer.jsx (517), ResearchPanel.jsx (830) |
| Medium (100-300 LOC) | 6 | RecalcPanel, ReportSheet, SampleSlider, WeightSliders, Header, FloatingPill |
| Small (<100 LOC) | 6 | CenteredPin, LayerToggles, ModeToggle, ReportFAB, others |

---

## 🗑️ DO USUNIĘCIA

### Console.log (non-error)

| Plik | Linia | Opis | Akcja |
|------|-------|------|-------|
| `MapContainer.jsx` | 486 | `console.log('Refreshing Bayesian layers...')` | Usuń |
| `RecalcPanel.jsx` | 53 | `console.log('Pipeline completed...')` | Usuń |
| `RecalcPanel.jsx` | 88 | `console.log('FAST pipeline result:', data)` | Usuń |
| `RecalcPanel.jsx` | 112 | `console.log('PUB R pipeline started:', data)` | Usuń |
| `SampleSlider.jsx` | 82 | `console.log('Sending POST to...')` | Usuń |
| `SampleSlider.jsx` | 88 | `console.log('Response status:', ...)` | Usuń |
| `SampleSlider.jsx` | 91 | `console.log('Response data:', ...)` | Usuń |

**Status innych kategorii:**
- ✅ Backup files (.bak): 0 znalezionych
- ✅ Unused imports: 0 znalezionych
- ✅ Commented code (>10 lines): 0 znalezionych

---

## ⚡ OPTYMALIZACJE

### P1 - CRITICAL: Duże komponenty do rozbicia

#### MapContainer.jsx (517 LOC)

**Problem:** Wszystko w jednym pliku - inicjalizacja mapy, 20+ warstw, eventy, data sync.

**Rekomendacja:** Rozbić na moduły:
```
MapContainer.jsx (~150 LOC)
├── hooks/useMapInitialization.js (setup warstw)
├── hooks/useMapEvents.js (click/hover handlers)
├── hooks/useMapDataSync.js (aktualizacje danych)
├── hooks/useBayesianLayers.js (logika Bayesian)
└── config/mapLayers.js (definicje warstw)
```

#### ResearchPanel.jsx (830 LOC)

**Problem:** 5 sekcji w jednym komponencie, inline styles, complex state.

**Rekomendacja:** Rozbić na sub-komponenty:
```
ResearchPanel.jsx (~200 LOC)
├── components/ModelSelector.jsx
├── components/ParameterControls.jsx
├── components/DiagnosticsView.jsx
├── components/ResultsTable.jsx
└── styles/researchPanelStyles.js
```

### P2 - Brakujące React.memo()

| Komponent | Trigger re-renderów | Akcja |
|-----------|---------------------|-------|
| `FloatingPill` | Parent layout changes | Wrap z `React.memo()` |
| `LayerToggles` | visibleLayers state | Wrap z `React.memo()` |
| `ResearchPanel` | Parent re-renders | Wrap z `React.memo()` + deps |

### P2 - Brakujące useMemo/useCallback

| Plik | Linia | Problem | Fix |
|------|-------|---------|-----|
| `ResearchPanel.jsx` | 135-139 | Sortowanie results na każdy render | `useMemo([results, sortBy])` |
| `RecalcPanel.jsx` | 127-129 | Progress % na każdy render | `useMemo([computeStatus])` |
| `MapContainer.jsx` | 53-59 | Map config inline | Extract to constant |

### P2 - DRY Violations

#### Layer Fetching Pattern (MapContainer.jsx 358-381)
**Problem:** Identyczny pattern powtórzony 12x

**Fix:**
```javascript
const LAYER_CONFIG = [
  { endpoint: 'buildings', source: 'buildings' },
  { endpoint: 'forests', source: 'forests' },
  // ...12 entries
];
LAYER_CONFIG.forEach(({ endpoint, source }) => fetchLayer(endpoint, source));
```

#### Button Styling
**Problem:** Podobne style w RecalcPanel, WeightSliders, ResearchPanel, SampleSlider

**Fix:** Stworzyć `styles/buttonStyles.js` ze współdzielonymi stylami.

### P3 - Inline Objects in JSX

| Plik | Problem |
|------|---------|
| `Header.jsx` | 3+ inline style objects |
| `MapContainer.jsx` | Map config inline |
| `ResearchPanel.jsx` | Style objects w render |

**Fix:** Extract do module-level constants.

---

## 🐛 PROBLEMY

### P1 - Brak Error Boundaries

**Problem:** Brak `<ErrorBoundary>` w App.jsx. Crash dowolnego komponentu = crash całej apki.

**Fix:**
```javascript
// components/ErrorBoundary.jsx
class ErrorBoundary extends React.Component {
  componentDidCatch(error, errorInfo) {
    console.error('App error:', error);
    this.setState({ hasError: true });
  }
  render() {
    if (this.state?.hasError) {
      return <div className="error-fallback">Błąd aplikacji. Odśwież stronę.</div>;
    }
    return this.props.children;
  }
}

// App.jsx
<ErrorBoundary>
  <MapContainer />
  <Header />
  ...
</ErrorBoundary>
```

### P2 - Brakujące aria-labels

| Komponent | Element | Linia | Fix |
|-----------|---------|-------|-----|
| `Header.jsx` | Risk Map button | 84 | `aria-label="Toggle risk map"` |
| `LayerToggles.jsx` | Layer buttons | 90 | `aria-label="Toggle {layer}"` |
| `WeightSliders.jsx` | Range inputs | 135 | `aria-label="{param} weight"` |
| `ModeToggle.jsx` | Mode buttons | 16-18 | `aria-label="Select {mode} mode"` |

### P2 - Silent Error Catches

| Plik | Linia | Problem |
|------|-------|---------|
| `ReportSheet.jsx` | 18 | `catch {}` - błędy ignorowane |

**Fix:** Dodaj error handling z feedback dla usera.

### P2 - Hardcoded Values

| Plik | Wartość | Rekomendacja |
|------|---------|--------------|
| `MapContainer.jsx:8` | MAP_STYLE path | → `config/mapConfig.js` |
| `MapContainer.jsx:56` | `[20.98, 52.33]` center | → `MAP_CENTER` constant |
| `LayerToggles.jsx:5-78` | LAYERS array | → `config/layers.js` |
| `WeightSliders.jsx:5-11` | WEIGHT_PARAMS | → `config/weights.js` |
| `SampleSlider.jsx:5-10` | SAMPLES | → `config/samples.js` |
| `Header.jsx:48-67` | Colors, gradients | → `config/theme.js` |

### P3 - Brak walidacji inputów

| Plik | Problem |
|------|---------|
| `ReportSheet.jsx:9-17` | Brak walidacji przed submit |
| `WeightSliders.jsx:21-24` | Brak bounds check na weights |

---

## 📋 PRIORYTETYZACJA

### 🔴 IMMEDIATE (P1)

1. **Dodaj Error Boundary** w App.jsx
2. **Fix silent catch** w ReportSheet.jsx
3. **Extract hardcoded constants** do config/

### 🟡 SHORT-TERM (P2)

1. Usuń console.log statements (7 miejsc)
2. Split MapContainer.jsx → 4-5 modułów
3. Split ResearchPanel.jsx → 6 sub-komponentów
4. Dodaj React.memo() do FloatingPill, LayerToggles
5. Dodaj useMemo dla sortowania/kalkulacji
6. Dodaj aria-labels (6-8 miejsc)
7. Create DRY utility dla layer fetching

### 🟢 NICE-TO-HAVE (P3)

1. Extract inline styles do CSS modules
2. Dodaj loading spinners
3. Create shared button styles
4. Rozważ TypeScript
5. Storybook dla dokumentacji komponentów

---

## 📁 PODSUMOWANIE PO PLIKACH

### 🔴 HIGH PRIORITY

| Plik | LOC | Główny problem |
|------|-----|----------------|
| `MapContainer.jsx` | 517 | Za duży, split required |
| `ResearchPanel.jsx` | 830 | Za duży, split required |

### 🟡 MEDIUM PRIORITY

| Plik | LOC | Główny problem |
|------|-----|----------------|
| `RecalcPanel.jsx` | 265 | Console.logs, missing useMemo |
| `Header.jsx` | 181 | Inline styles, missing aria-labels |
| `SampleSlider.jsx` | 239 | Console.logs, potential memory leak |

### 🟢 LOW PRIORITY

| Plik | LOC | Status |
|------|-----|--------|
| `useGridTransition.js` | 229 | ✅ Clean (just refactored) |
| `animateOpacity.js` | 107 | ✅ Clean (just refactored) |
| `FloatingPill.jsx` | 166 | Add React.memo() |
| `LayerToggles.jsx` | 129 | Add React.memo() |

---

## ✅ CO DZIAŁA DOBRZE

- **Cleanup functions** - wszystkie useEffect mają proper cleanup
- **No unused imports** - kod jest czysty
- **No dead code** - brak zakomentowanych bloków
- **Modern React patterns** - hooks, functional components
- **Zustand store** - prosty i efektywny state management
- **Grid animation system** - just implemented, production-ready

---

*Audyt wykonany: 2025-01-17*
*Narzędzie: Claude Code*
