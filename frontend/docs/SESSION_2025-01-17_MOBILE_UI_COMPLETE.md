# KOMPLETNY RAPORT SESJI - Mobile UI Refactor
**Data:** 2025-01-17
**Status:** W TRAKCIE (wymaga kontynuacji)

---

## CEL SESJI
Implementacja responsywnego UI (Desktop ↔ Mobile) z płynnymi, skoordynowanymi animacjami.

---

## ZREALIZOWANE

### 1. FSM dla koordynacji animacji Desktop ↔ Mobile
**Plik:** `src/hooks/useLayoutTransition.js`
```javascript
// Hook zwraca:
// - layout: 'desktop' | 'mobile'
// - onExitComplete: callback dla AnimatePresence
// - isTransitioning: boolean
```

**Użycie w App.jsx:**
```javascript
const isMobile = useIsMobile();
const { layout, onExitComplete } = useLayoutTransition(isMobile);
```

### 2. Variants dla animacji
**Plik:** `src/config/layoutAnimations.js`
```javascript
// Eksportuje:
// - containerVariants (when: beforeChildren/afterChildren)
// - desktopChildVariants.left (x: -50)
// - desktopChildVariants.right (x: 50)
// - desktopChildVariants.fab (scale)
// - mobileChildVariants (y: 30)
// - ANIMATION_DURATION = 0.3
// - ANIMATION_EASE = 'easeOut'
```

### 3. App.jsx - jeden AnimatePresence mode="wait"
```jsx
<AnimatePresence mode="wait" onExitComplete={onExitComplete}>
  {layout === 'desktop' && (
    <motion.div key="desktop-layout">
      <RecalcPanel />      // lewy dolny
      <ModeToggle />       // prawy górny
      <ReportFAB />        // prawy dolny
    </motion.div>
  )}
  {layout === 'mobile' && (
    <motion.div key="mobile-layout">
      <FloatingPill "Próba" />    // lewy dolny
      <FloatingPill "Warstwy" />  // prawy dolny
    </motion.div>
  )}
</AnimatePresence>
```

### 4. Uproszczone komponenty (zero duplikatów)

| Komponent | Przed | Po |
|-----------|-------|-----|
| RecalcPanel | AnimatePresence + hidden + isAddMode | Prosty div, tylko `embedded` prop |
| ReportFAB | AnimatePresence + warunki | Prosty button, zero warunków |
| FloatingPill | Bez animacji wejścia | Własne initial/animate/exit (position:fixed) |
| ModeToggle | Już OK | Bez zmian |

### 5. Header - crossfade z isAddMode
```jsx
// Warunek zmieniony z:
{!isMobile ? <Dzik /> : <MiniFAB />}

// Na:
{(!isMobile || isAddMode) ? <Dzik /> : <MiniFAB />}
```
**Efekt:** Na mobile podczas dodawania dzika (isAddMode) - pokazuje 🐗 zamiast +

### 6. Header - "Tryb badawczy" animacja szerokości
```jsx
<motion.button
  initial={{ opacity: 0, width: 0, marginLeft: 0 }}
  animate={{ opacity: 1, width: 'auto', marginLeft: 12 }}
  exit={{ opacity: 0, width: 0, marginLeft: 0 }}
  transition={{ duration: 0.3, ease: 'easeOut' }}
  style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}
>
```
**Efekt:** "Mapa ryzyka" płynnie przesuwa się gdy "Tryb badawczy" znika/pojawia się

### 7. Atrybucja OpenStreetMap przeniesiona do Header
```jsx
// Zamiast kontrolki na mapie, teraz w Header pod tytułem:
<p className="text-gray-500 text-xs">
  <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap</a>
</p>
```

---

## NIEROZWIĄZANE PROBLEMY

### 1. Przycisk "Mapa ryzyka" - szerokość przy wrap
**Problem:** Gdy tekst łamie się na 2 linie, button nie zmniejsza szerokości.

**Próbowane (nie działa):**
- width: fit-content
- width: min-content (wymusza 2 linie na sztywno)
- width: max-content (wymusza 1 linię na sztywno)
- flexShrink: 1 + minWidth: 0
- display: inline-flex + różne kombinacje

**Z DR:** CSS nie może automatycznie zmniejszyć szerokości buttona do najdłuższej linii po zawinięciu tekstu. Flexbox pamięta szerokość intrinsic (max-content) z stanu przed zawinięciem.

**Możliwe rozwiązanie:** JavaScript (ResizeObserver) do dynamicznego mierzenia szerokości.

**Status:** Cofnięte do wersji podstawowej (display: flex, alignItems: center, gap: 6px)

---

## PLIKI ZMIENIONE/DODANE

### Nowe pliki:
```
src/hooks/useLayoutTransition.js    - FSM hook dla Desktop↔Mobile
src/hooks/useMediaQuery.js          - useIsMobile(), useIsDesktop()
src/config/layoutAnimations.js      - Variants dla animacji
docs/MOBILE_UI_REFACTOR_2025-01-17.md - Raport (poprzedni)
```

### Zmodyfikowane:
```
src/App.jsx                         - FSM + AnimatePresence mode="wait"
src/components/Header.jsx           - crossfade + isAddMode, animacja Tryb badawczy, atrybucja OSM
src/components/RecalcPanel.jsx      - Usunięta AnimatePresence, tylko embedded prop
src/components/ReportFAB.jsx        - Usunięte warunki i AnimatePresence
src/components/FloatingPill.jsx     - Własne animacje wejścia (y: 30)
src/components/ModeToggle.jsx       - Prop embedded
src/components/MapContainer.jsx     - Usunięta kontrolka atrybucji (przeniesiona do Header)
public/styles/dark-wildlife.json    - Dodana atrybucja do source
```

### Do usunięcia (nieużywane):
```
src/components/MobileDrawer.jsx     - Zastąpiony przez FloatingPill
src/components/EdgeTrigger.jsx      - Część MobileDrawer
src/hooks/useDrawerPhysics.js       - Część MobileDrawer
```

---

## ARCHITEKTURA PO REFAKTORZE

```
App.jsx (KONTROLER)
├── useIsMobile() → breakpoint 768px
├── useLayoutTransition(isMobile) → FSM ('desktop'|'mobile')
│
├── AnimatePresence mode="wait" onExitComplete={onExitComplete}
│   ├── key="desktop-layout" (gdy layout === 'desktop')
│   │   ├── motion.div → RecalcPanel (absolute bottom-6 left-4)
│   │   ├── motion.div → ModeToggle (absolute top-20 right-4)
│   │   └── motion.div → ReportFAB (fixed bottom-6 right-6)
│   │
│   └── key="mobile-layout" (gdy layout === 'mobile')
│       ├── FloatingPill "Próba" (fixed bottom-4 left-4)
│       │   └── RecalcPanel embedded=true
│       └── FloatingPill "Warstwy" (fixed bottom-4 right-4)
│           └── ModeToggle embedded=true
│
├── Header (zawsze widoczny)
│   ├── AnimatePresence mode="wait" → crossfade 🐗/+ (warunek: !isMobile || isAddMode)
│   ├── "Mapa ryzyka" → zwykły button
│   ├── AnimatePresence → "Tryb badawczy" (width animation)
│   └── © OpenStreetMap (atrybucja)
│
├── MapContainer (zawsze)
├── ReportSheet (gdy isAddMode)
└── ResearchPanel (gdy showResearchPanel)
```

---

## KLUCZOWE DECYZJE I DLACZEGO

### 1. FSM zamiast delay
**Dlaczego:** 12 osobnych AnimatePresence nie synchronizowało się. Delay nie działał bo liczył od MOUNT, nie od końca poprzedniej animacji.
**Źródło:** DR "Orkiestracja Animacji w React z Framer Motion" - Sekcja 3

### 2. mode="wait" na jednym AnimatePresence
**Dlaczego:** Gwarantuje sekwencję: desktop exit → POTEM → mobile enter
**Źródło:** DR Sekcja 2.2

### 3. Komponenty "głupie" (bez własnych AnimatePresence)
**Dlaczego:** Uniknięcie duplikacji logiki, jeden punkt kontroli w App.jsx
**Wyjątek:** FloatingPill ma własne animacje bo position:fixed wyjmuje z flow

### 4. Header niezależny od FSM
**Dlaczego:** Header jest zawsze widoczny, tylko wewnętrzne elementy się zmieniają. Dodanie do FSM opóźniłoby reakcję i skomplikowało kod.

### 5. Animacja width zamiast layout prop
**Dlaczego:** layout prop (Framer Motion) nie działał - animacja nie startowała. Animacja width na "Tryb badawczy" sprawia że "Mapa ryzyka" naturalnie się przesuwa.

### 6. Atrybucja OSM w Header zamiast na mapie
**Dlaczego:** Kontrolka MapLibre z "i" kolidowała z innymi elementami. Przeniesienie do Header jest czystsze i spełnia wymogi licencji OSM.

---

## ŹRÓDŁA WIEDZY (DR)

1. **"Orkiestracja Animacji w React z Framer Motion"**
   - Sekcja 2: AnimatePresence mode (sync/wait/popLayout)
   - Sekcja 3: FSM z useReducer dla rozłącznych drzew
   - Sekcja 4: staggerChildren, delayChildren
   - Sekcja 6: Desktop ↔ Mobile implementation

2. **CSS button width auto-shrink** (nierozwiązane)
   - CSS nie może automatycznie zmniejszyć szerokości po wrap
   - Potrzebne JS (ResizeObserver) lub maxWidth constraint

---

## CO PRZETESTOWAĆ

| Test | Oczekiwane | Status |
|------|------------|--------|
| Desktop → Mobile | Sekwencja: desktop exit → mobile enter | ✅ |
| Mobile → Desktop | Sekwencja: mobile exit → desktop enter | ✅ |
| Mobile + klik + | Crossfade + → 🐗 | ✅ |
| Mobile + zamknij ReportSheet | Crossfade 🐗 → + | ✅ |
| "Tryb badawczy" znika | "Mapa ryzyka" płynnie się przesuwa | ✅ |
| Pills expand/collapse | Płynna animacja panelu | ✅ |
| "Mapa ryzyka" wrap | Szerokość zmniejsza się | ❌ DO NAPRAWY |

---

## TODO NA NASTĘPNĄ SESJĘ

1. [ ] **"Mapa ryzyka" szerokość** - spróbować maxWidth: 150px lub JS ResizeObserver
2. [ ] **ReportSheet na mobile** - za wąski pasek
3. [ ] **Usunąć nieużywane pliki** - MobileDrawer, EdgeTrigger, useDrawerPhysics
4. [ ] **Testy automatyczne** - dla animacji i responsywności
5. [ ] **Optymalizacja** - sprawdzić performance animacji

---

## NOTATKI DLA PRZYSZŁEJ SESJI

- `@use-gesture/react` jest zainstalowany ale NIEUŻYWANY (było dla MobileDrawer)
- Timing animacji: 0.3s dla transitions, 0.5s dla expand/collapse paneli
- FloatingPill ma position:fixed - nie można animować z parenta
- Header ma własne AnimatePresence - niezależne od FSM głównego
- Atrybucja OSM jest wymagana prawnie - nie można usunąć, tylko przenieść

---

## GIT COMMITS

```
571eb38 Responsive mobile UI with FloatingPills
0975d77 FSM animation orchestration for Desktop/Mobile layouts
```

Następny commit powinien zawierać: Header animations + OSM attribution move
