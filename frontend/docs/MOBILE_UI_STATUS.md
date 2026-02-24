# Mobile UI Status

**Status:** KOMPLETNE
**Ostatnia aktualizacja:** 2025-01-17
**Zrodlo:** Frontend Audit 2025-01-17

---

## AKTUALNY STAN

### Zrealizowane

| Feature | Status | Opis |
|---------|--------|------|
| FSM hook | OK | `useLayoutTransition.js` - koordynacja Desktop <-> Mobile |
| Animation variants | OK | `layoutAnimations.js` - container + child variants |
| App jako kontroler | OK | `AnimatePresence mode="wait"` |
| FloatingPill | OK | Unified panel + button, position: fixed |
| Header crossfade | OK | emoji dzika <-> + (mini FAB) |
| Research panel hide | OK | Ukryty na mobile |
| Conditional content | OK | FAST: LayerToggles bare, PUB: ModeToggle embedded |
| Panel animations | OK | isAddMode -> panele animuja sie out |

---

## KLUCZOWE PLIKI

### Komponenty Mobile UI

| Plik | LOC | Rola | Status |
|------|-----|------|--------|
| `FloatingPill.jsx` | 99 | Pill na mobile | OK |
| `RecalcPanel.jsx` | 264 | Panel "Proba" + wybor trybu | OK |
| `ModeToggle.jsx` | 52 | Panel "Warstwy" (LayerToggles + WeightSliders) | OK |
| `LayerToggles.jsx` | 183 | Grid 12 warstw OSM, prop `bare` | OK |
| `Header.jsx` | 181 | Crossfade + animacje | OK |
| `ReportFAB.jsx` | 21 | FAB desktop | OK |

### Hooki i config

| Plik | LOC | Rola |
|------|-----|------|
| `useLayoutTransition.js` | 41 | FSM dla Desktop <-> Mobile |
| `useMediaQuery.js` | 46 | useIsMobile(), useIsDesktop() |
| `layoutAnimations.js` | 107 | Variants dla Framer Motion |

---

## ARCHITEKTURA MOBILE UI

```
App.jsx (KONTROLER)
|
+-- useIsMobile() -> breakpoint 768px
+-- useLayoutTransition(isMobile) -> { layout, onExitComplete }
|
+-- AnimatePresence mode="wait" onExitComplete={onExitComplete}
|   |
|   +-- [Desktop] key="desktop-layout"
|   |   +-- RecalcPanel (absolute bottom-6 left-4)
|   |   +-- ModeToggle (absolute top-20 right-4)
|   |   +-- ReportFAB (fixed bottom-6 right-6)
|   |
|   +-- [Mobile] key="mobile-layout"
|       +-- FloatingPill "Proba" (fixed bottom-4 left-4)
|       |   +-- RecalcPanel embedded=true
|       |
|       +-- FloatingPill "Warstwy" (fixed bottom-4 right-4)
|           +-- [displayMode === 'fast']
|           |   +-- LayerToggles bare=true  <-- tylko checkboxy
|           |
|           +-- [displayMode === 'publication']
|               +-- ModeToggle embedded=true  <-- pelny accordion
|
+-- Header (zawsze widoczny)
|   +-- [Mobile + !isAddMode] -> mini FAB (+)
|   +-- [Desktop | isAddMode] -> emoji dzika
|
+-- MapContainer (zawsze)
+-- CenteredPin (gdy isAddMode)
+-- ReportSheet (gdy isAddMode)
+-- ResearchPanel (gdy showResearchPanel, tylko Desktop)
```

---

## WARUNKOWA ZAWARTOSC PILL "Warstwy"

```jsx
// App.jsx linii 119-126
<FloatingPill side="right" label="Warstwy" ...>
  {displayMode === 'fast' ? (
    // fastPython: tylko checkboxy warstw (bez naglowka i accordion)
    <LayerToggles bare />
  ) : (
    // spatialWarsaw: pelny ModeToggle z accordion
    <ModeToggle embedded />
  )}
</FloatingPill>
```

**Dlaczego?**
- FAST mode nie ma WeightSliders (wagi srodowiskowe)
- PUB mode potrzebuje WeightSliders do dostrajania wag

---

## STRUKTURA FloatingPill

```jsx
<motion.div class="fixed bottom-4 left-4|right-4 z-40">
  {/* Wlasne animacje wejscia/wyjscia */}
  initial={{ opacity: 0, y: 30 }}
  animate={{ opacity: 1, y: 0 }}
  exit={{ opacity: 0, y: 30 }}

  {/* PANEL - absolute NAD przyciskiem */}
  <AnimatePresence>
    {isOpen && (
      <motion.div
        class="absolute bottom-full mb-2 bg-gray-800/95 rounded-xl min-w-[240px]"
        initial={{ height: 0, opacity: 0 }}
        animate={{ height: 'auto', opacity: 1 }}
        exit={{ height: 0, opacity: 0 }}
        onAnimationComplete={onOpenComplete}
      >
        <div class="p-4">{children}</div>
      </motion.div>
    )}
  </AnimatePresence>

  {/* BUTTON - zawsze widoczny */}
  <motion.button class="px-4 py-3 bg-gray-800/95 rounded-xl">
    {label} <span rotate={isOpen ? 180 : 0}>arrow</span>
  </motion.button>
</motion.div>
```

---

## ANIMACJE

| Element | Typ | Czas | Trigger |
|---------|-----|------|---------|
| Desktop <-> Mobile | AnimatePresence wait | 0.3s | breakpoint 768px |
| Desktop panels | x slide (+/-50px) | 0.3s | layout change |
| FloatingPill wejscie | y slide (30px) | 0.3s | layout = mobile |
| FloatingPill panel | height auto | 0.3s | isOpen toggle |
| Header FAB crossfade | scale + opacity | 0.2s | isMobile + isAddMode |
| Panels on isAddMode | exit animation | 0.3s | isAddMode = true |

---

## KOLORY (UJEDNOLICONE)

| Element | Kolor |
|---------|-------|
| FloatingPill panel | `bg-gray-800/95` |
| FloatingPill button | `bg-gray-800/95` |
| FloatingPill hover | `hover:bg-gray-700/95` |
| RecalcPanel desktop | `rgba(31, 41, 55, 0.95)` |
| ModeToggle desktop | `bg-gray-800/90` |
| Header gradient | `rgba(15, 23, 42, 0.95) -> transparent` |

---

## DECYZJE ARCHITEKTONICZNE

### 1. AnimatePresence mode="wait"

**Decyzja:** Uzyc `mode="wait"` zamiast default
**Dlaczego:** Sekwencyjna animacja - najpierw exit, potem enter

### 2. FloatingPill z position: fixed

**Decyzja:** FloatingPill kontroluje wlasne animacje, nie variants
**Dlaczego:** `position: fixed` + AnimatePresence wymaga wlasnych `initial/animate/exit`

### 3. Conditional content zamiast defaultExpanded

**Decyzja:** Rozne komponenty dla FAST vs PUB zamiast jednego z props
**Dlaczego:** Prostsze, unika problemu z synchronizacja animacji

### 4. Header mini FAB na mobile

**Decyzja:** Przeniesc FAB do Header na mobile, zachowac na desktop
**Dlaczego:** Miejsce na FloatingPills w dolnych rogach

---

## GIT COMMITS

```
f69fba1 UI reorganization: mode selection to RecalcPanel, FloatingPill fixes
6d3efd7 Header animations + OSM attribution to header
0975d77 FSM animation orchestration for Desktop/Mobile layouts
571eb38 Responsive mobile UI with FloatingPills
```

---

## RESOLVED ISSUES

| Issue | Rozwiazanie |
|-------|-------------|
| Double animation on open | Warunkowy content zamiast onOpenComplete |
| useRef initialization bug | Uproszczone podejscie bez ref tracking |
| setTimeout cleanup in StrictMode | onAnimationComplete zamiast setTimeout |
| Padding asymetry | paddingBottom conditional z transition |

---

## KNOWN ISSUES

| Issue | Priorytet | Status |
|-------|-----------|--------|
| ReportSheet na mobile za waski | Low | Open |
| Brak skeleton states | Low | Open |
