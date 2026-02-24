# Raport: Animacja przejścia między trybami FAST ↔ PUB na mapie

**Data:** 2025-01-17
**Cel:** Analiza możliwości implementacji płynnej animacji przejścia między siatkami gridów przy zmianie trybu fastPython ↔ spatialWarsaw
**Ocena trudności:** 🔴 BARDZO TRUDNE

---

## 1. AKTUALNY STAN

### 1.1 Struktura gridów

| Tryb | Endpoint | Typ siatki | Liczba komórek | Geometria |
|------|----------|------------|----------------|-----------|
| **fastPython** | `/api/analytics/grid/` | SQUARE | ~9,875 | Regularna siatka kwadratów |
| **spatialWarsaw** | `/api/analytics/voronoi/` | VORONOI | ~500 | Nieregularna teselacja Voronoi |

### 1.2 Kluczowe pliki

```
frontend/src/
├── components/
│   └── MapContainer.jsx          # Główny komponent mapy (556 linii)
├── stores/
│   └── sightingsStore.js         # Zustand store z displayMode
└── config/
    └── layoutAnimations.js       # Variants dla UI (nie mapy)
```

### 1.3 Obecna implementacja (MapContainer.jsx)

```javascript
// Linia 351-383: Fetch grid przy zmianie displayMode
useEffect(() => {
  const url = displayMode === 'fast'
    ? '/api/analytics/grid/'
    : '/api/analytics/voronoi/';

  fetch(url)
    .then(r => r.json())
    .then(data => {
      const src = mapRef.current?.getSource("risk");
      if (src) src.setData(data);  // ← NATYCHMIASTOWA PODMIANA
    });
}, [mapReady, displayMode]);
```

**Problem:** `setData()` podmienia dane natychmiast bez żadnej animacji.

### 1.4 Warstwy mapy (kolejność renderowania)

```
[BOTTOM]
├── OSM layers (forests, water, buildings, roads...)
├── risk-fill          ← GRID/VORONOI (to chcemy animować)
├── risk-outline
├── bayesian-heatmap
├── trajectory-lines
├── encounters (clusters + points)
├── ryjowisko (clusters + points)
└── boundaries (bialoleka-outline, wisla-line)
[TOP]
```

---

## 2. DLACZEGO TO TRUDNE

### 2.1 Fundamentalne ograniczenia MapLibre GL

| Ograniczenie | Opis |
|--------------|------|
| **Brak natywnych animacji warstw** | MapLibre nie ma wbudowanego API do animowania przejść między źródłami danych |
| **setData() jest atomowe** | Nie ma opcji "fade" czy "transition" przy podmianie danych |
| **Różne geometrie** | SQUARE (9875 kwadratów) vs VORONOI (500 nieregularnych wielokątów) - nie da się morfować |
| **Brak paint-opacity-transition dla fill** | Chociaż MapLibre ma transitions, nie działają one przy całkowitej podmianie source |

### 2.2 Różnice geometryczne

```
FAST (SQUARE):                    PUB (VORONOI):
┌───┬───┬───┬───┐                 ┌─────────┐
│   │   │   │   │                 │    ╱    │
├───┼───┼───┼───┤                 │   ╱  ╲  │
│   │   │   │   │                 │  ╱    ╲ │
├───┼───┼───┼───┤       →         ├─╱──────╲┤
│   │   │   │   │                 │╱   ╲    │
├───┼───┼───┼───┤                 │     ╲   │
│   │   │   │   │                 └──────╲──┘
└───┴───┴───┴───┘

Różna liczba komórek, różne kształty, różne centroidy
```

### 2.3 Problemy z centroidami

- FAST: Centroidy w środku każdego kwadratu (regularne)
- PUB: Centroidy w punktach obserwacji dzików (nieregularne)
- Nie ma mapowania 1:1 między centroidami

---

## 3. MOŻLIWE PODEJŚCIA

### 3.1 Podejście A: Crossfade dwóch warstw (REKOMENDOWANE)

**Koncepcja:** Dwie osobne warstwy, animacja opacity między nimi.

```javascript
// Struktura:
map.addSource("risk-fast", { type: "geojson", data: fastGrid });
map.addSource("risk-voronoi", { type: "geojson", data: voronoiGrid });

map.addLayer({ id: "risk-fast-fill", source: "risk-fast", paint: { "fill-opacity": 1 } });
map.addLayer({ id: "risk-voronoi-fill", source: "risk-voronoi", paint: { "fill-opacity": 0 } });

// Przy zmianie trybu:
function animateTransition(toMode) {
  const fromLayer = toMode === 'fast' ? 'risk-voronoi-fill' : 'risk-fast-fill';
  const toLayer = toMode === 'fast' ? 'risk-fast-fill' : 'risk-voronoi-fill';

  // Animacja przez requestAnimationFrame
  let progress = 0;
  const animate = () => {
    progress += 0.02;  // ~50 klatek @ 60fps = 0.8s

    map.setPaintProperty(fromLayer, 'fill-opacity', 0.65 * (1 - progress));
    map.setPaintProperty(toLayer, 'fill-opacity', 0.65 * progress);

    if (progress < 1) requestAnimationFrame(animate);
  };
  animate();
}
```

**Zalety:**
- Prosty koncept
- Pełna kontrola nad czasem animacji
- Nie wymaga modyfikacji backendu

**Wady:**
- Podwójne zużycie pamięci (dwa gridy w pamięci)
- Trzeba pre-loadować oba gridy

**Ocena:** ⭐⭐⭐⭐ (4/5)

---

### 3.2 Podejście B: Canvas snapshot + overlay

**Koncepcja:** Zrzut ekranu mapy → animowany overlay → nowe dane.

```javascript
function captureAndTransition(toMode) {
  // 1. Zrzut aktualnego stanu
  const canvas = map.getCanvas();
  const snapshot = canvas.toDataURL();

  // 2. Overlay div z zrzutem
  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position: absolute; inset: 0;
    background: url(${snapshot});
    transition: opacity 0.5s;
  `;
  containerRef.current.appendChild(overlay);

  // 3. Załaduj nowe dane
  fetch(newUrl).then(data => {
    source.setData(data);

    // 4. Fade out overlay
    overlay.style.opacity = 0;
    setTimeout(() => overlay.remove(), 500);
  });
}
```

**Zalety:**
- Działa z każdą różnicą geometrii
- Nie wymaga podwójnego gridu

**Wady:**
- Widoczny "freeze" podczas ładowania
- Overlay przykrywa całą mapę (pan/zoom zablokowane)
- Może być glitchy na słabszych urządzeniach

**Ocena:** ⭐⭐⭐ (3/5)

---

### 3.3 Podejście C: WebGL dissolve shader

**Koncepcja:** Custom shader łączący dwie tekstury gridu.

```glsl
// Fragment shader
uniform sampler2D gridA;
uniform sampler2D gridB;
uniform float mixFactor;

void main() {
  vec4 colorA = texture2D(gridA, vUv);
  vec4 colorB = texture2D(gridB, vUv);
  gl_FragColor = mix(colorA, colorB, mixFactor);
}
```

**Zalety:**
- Najlepszy efekt wizualny
- Możliwe zaawansowane efekty (dissolve, wipe, pixelate)

**Wady:**
- Wymaga znacznej refaktoryzacji
- MapLibre custom layers są skomplikowane
- Debugowanie nightmare

**Ocena:** ⭐⭐ (2/5) - overengineering

---

### 3.4 Podejście D: Sekwencyjna animacja komórek

**Koncepcja:** Animacja pojedynczych komórek (stagger effect).

```javascript
// Fade out komórki jedna po drugiej
features.forEach((feature, i) => {
  setTimeout(() => {
    feature.properties.opacity = 0;
    source.setData(geojson);
  }, i * 10);  // 10ms między komórkami
});
```

**Zalety:**
- Efektowne vizualnie (ripple effect)

**Wady:**
- 9875 setTimeout-ów = performance disaster
- setData() przy każdej komórce = ~10,000 operacji

**Ocena:** ⭐ (1/5) - niewykonalne dla dużych gridów

---

## 4. REKOMENDACJA

### Podejście A (Crossfade) z modyfikacjami

```
Faza 1: Pre-load
├── Przy starcie aplikacji załaduj OBA gridy
├── risk-fast-fill (opacity: 1 gdy fast mode)
└── risk-voronoi-fill (opacity: 0 gdy fast mode)

Faza 2: Transition
├── Użytkownik zmienia tryb
├── requestAnimationFrame loop (~800ms)
├── Interpoluj opacity obu warstw
└── Po zakończeniu ukryj nieaktywną warstwę (visibility: none)

Faza 3: Optymalizacja
├── Lazy-load drugiego gridu przy pierwszej zmianie trybu
├── Cache gridów w pamięci
└── Debounce przy szybkim przełączaniu
```

### Estymowany nakład pracy

| Etap | Czas | Opis |
|------|------|------|
| Refactor źródeł | 2h | Dwa osobne source zamiast jednego |
| Logika animacji | 3h | requestAnimationFrame + interpolacja |
| Integracja ze store | 1h | Koordynacja z displayMode |
| Edge cases | 2h | Szybkie przełączanie, błędy sieci |
| **Łącznie** | **~8h** | |

---

## 5. ZMIANY W KODZIE (szkic)

### 5.1 MapContainer.jsx - nowa struktura źródeł

```javascript
// PRZED (jedno źródło):
map.addSource("risk", { type: "geojson", data: emptyGeoJSON });

// PO (dwa źródła):
map.addSource("risk-fast", { type: "geojson", data: emptyGeoJSON });
map.addSource("risk-voronoi", { type: "geojson", data: emptyGeoJSON });

map.addLayer({
  id: "risk-fast-fill",
  type: "fill",
  source: "risk-fast",
  paint: {
    "fill-color": riskColorExpression,
    "fill-opacity": 0.65,
    "fill-opacity-transition": { duration: 0 }  // Wyłącz natywne transition
  }
});

map.addLayer({
  id: "risk-voronoi-fill",
  type: "fill",
  source: "risk-voronoi",
  layout: { visibility: "none" },
  paint: {
    "fill-color": riskColorExpression,
    "fill-opacity": 0,
    "fill-opacity-transition": { duration: 0 }
  }
});
```

### 5.2 Hook do animacji

```javascript
// hooks/useGridTransition.js
export function useGridTransition(map, displayMode) {
  const animationRef = useRef(null);
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => {
    if (!map) return;

    const fastLayer = 'risk-fast-fill';
    const voronoiLayer = 'risk-voronoi-fill';
    const targetIsFast = displayMode === 'fast';

    // Cancel previous animation
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }

    // Ensure target layer is visible
    map.setLayoutProperty(
      targetIsFast ? fastLayer : voronoiLayer,
      'visibility',
      'visible'
    );

    setIsTransitioning(true);

    let progress = 0;
    const duration = 800;  // ms
    const startTime = performance.now();

    const animate = (currentTime) => {
      progress = Math.min((currentTime - startTime) / duration, 1);
      const eased = easeOutCubic(progress);

      const fromOpacity = 0.65 * (1 - eased);
      const toOpacity = 0.65 * eased;

      map.setPaintProperty(
        targetIsFast ? voronoiLayer : fastLayer,
        'fill-opacity',
        fromOpacity
      );
      map.setPaintProperty(
        targetIsFast ? fastLayer : voronoiLayer,
        'fill-opacity',
        toOpacity
      );

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      } else {
        // Hide source layer
        map.setLayoutProperty(
          targetIsFast ? voronoiLayer : fastLayer,
          'visibility',
          'none'
        );
        setIsTransitioning(false);
      }
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [map, displayMode]);

  return isTransitioning;
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}
```

### 5.3 Integracja w MapContainer

```javascript
// W komponencie MapContainer:
import { useGridTransition } from '../hooks/useGridTransition';

export default function MapContainer() {
  // ...existing code...

  const isTransitioning = useGridTransition(
    mapReady ? mapRef.current : null,
    displayMode
  );

  // Opcjonalnie: disable mode toggle podczas animacji
  // ...
}
```

---

## 6. ALTERNATYWA: Blur transition

Jeśli crossfade wygląda zbyt "surowo", można dodać blur:

```javascript
const animate = (progress) => {
  const blur = Math.sin(progress * Math.PI) * 3;  // 0 → 3 → 0

  // CSS blur na całym kontenerze mapy
  containerRef.current.style.filter = `blur(${blur}px)`;

  // ...opacity animation...
};
```

---

## 7. DECYZJA

### Pytanie do użytkownika:

1. **Czy akceptujemy podwójne zużycie pamięci?**
   - Oba gridy w pamięci (~10MB łącznie)
   - Alternatywa: lazy-load z krótkim "loading" state

2. **Preferowany czas animacji?**
   - 500ms (szybko, subtelnie)
   - 800ms (zauważalnie, płynnie)
   - 1200ms (dramatycznie, może irytować)

3. **Czy outline też animować?**
   - Tak: crossfade obu warstw fill + outline
   - Nie: instant switch outline, tylko fill animowany

---

## 8. KOMENTARZ AUTORA

To zadanie jest **wykonalne**, ale wymaga starannej implementacji. MapLibre nie został zaprojektowany z myślą o takich animacjach, więc musimy je "obejść" własnym kodem.

Największe ryzyko: **synchronizacja** - jeśli użytkownik szybko przełączy tryb kilka razy, animacje mogą się "nakładać". Trzeba to obsłużyć przez:
- Anulowanie poprzedniej animacji
- Interpolację od aktualnego stanu (nie od 0/1)
- Debounce na przełączniku trybu

**Ocena wykonalności:** 7/10
**Ocena efektu końcowego:** 9/10 (jeśli dobrze zaimplementowane)

---

*Raport przygotowany dla Claude Code / Claude Chatbot*
*Kontekst: dziki-projekt/frontend*
