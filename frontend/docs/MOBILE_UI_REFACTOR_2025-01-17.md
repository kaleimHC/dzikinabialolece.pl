# Mobile UI Refactor - Raport Sesji
**Data:** 2025-01-17
**Status:** UKOŃCZONY

---

## CEL SESJI
Implementacja responsywnego UI (Desktop ↔ Mobile) z płynnymi, skoordynowanymi animacjami.

---

## ZREALIZOWANE

### 1. FSM dla koordynacji animacji
- **Hook:** `src/hooks/useLayoutTransition.js`
- **Cel:** Gwarantuje sekwencję: stary layout WYCHODZI → nowy WCHODZI
- **Użycie:** `AnimatePresence mode="wait"` + FSM

### 2. Variants dla animacji
- **Plik:** `src/config/layoutAnimations.js`
- **Zawartość:**
  - `containerVariants` - wrapper z `when: beforeChildren/afterChildren`
  - `desktopChildVariants` - left (x:-50), right (x:50), fab (scale)
  - `mobileChildVariants` - slide z dołu (y:30)
  - Stałe: `ANIMATION_DURATION=0.3`, `ANIMATION_EASE='easeOut'`

### 3. Uproszczona architektura komponentów

| Komponent | Przed | Po |
|-----------|-------|-----|
| RecalcPanel | AnimatePresence + hidden + isAddMode | Prosty div, tylko `embedded` prop |
| ReportFAB | AnimatePresence + warunki isDesktop/showResearchPanel | Prosty button, zero warunków |
| FloatingPill | Bez animacji wejścia | Własne initial/animate/exit (position:fixed) |
| ModeToggle | Już OK | Bez zmian |

### 4. App.jsx - jeden punkt kontroli
- `AnimatePresence mode="wait"` dla Desktop/Mobile
- Pozycjonowanie w wrapperach (`className="absolute bottom-6 left-4"`)
- FSM hook kontroluje `layout` ('desktop' | 'mobile')

---

## PLIKI ZMIENIONE/DODANE

### Nowe pliki:
```
src/hooks/useLayoutTransition.js   - FSM hook
src/config/layoutAnimations.js     - Variants dla animacji
```

### Zmodyfikowane:
```
src/App.jsx                        - FSM + AnimatePresence mode="wait"
src/components/RecalcPanel.jsx     - Usunięta AnimatePresence, uproszczony
src/components/ReportFAB.jsx       - Usunięte warunki i AnimatePresence
src/components/FloatingPill.jsx    - Dodane własne animacje wejścia
src/components/Header.jsx          - Crossfade boar/+, ukryty "Tryb badawczy"
src/components/ModeToggle.jsx      - Prop embedded, AnimatePresence dla WeightSliders
src/hooks/useMediaQuery.js         - useIsMobile(), useIsDesktop()
```

### Do usunięcia (nieużywane):
```
src/components/MobileDrawer.jsx    - Zastąpiony przez FloatingPill
src/components/EdgeTrigger.jsx     - Część MobileDrawer
src/hooks/useDrawerPhysics.js      - Część MobileDrawer
```

---

## ARCHITEKTURA PO REFAKTORZE

```
App.jsx (KONTROLER)
├── useLayoutTransition(isMobile) → FSM
├── AnimatePresence mode="wait"
│   ├── layout === 'desktop'
│   │   ├── motion.div → RecalcPanel (lewy dolny)
│   │   ├── motion.div → ModeToggle (prawy górny)
│   │   └── motion.div → ReportFAB (prawy dolny)
│   │
│   └── layout === 'mobile'
│       ├── FloatingPill "Próba" → RecalcPanel embedded
│       └── FloatingPill "Warstwy" → ModeToggle embedded
│
├── Header (zawsze, własne AnimatePresence dla crossfade)
├── MapContainer (zawsze)
└── ResearchPanel (gdy showResearchPanel)
```

---

## KLUCZOWE DECYZJE

1. **FSM zamiast delay** - gwarantuje sekwencję bez hacków
2. **mode="wait"** - czeka na exit przed enter
3. **Komponenty "głupie"** - tylko treść, zero logiki widoczności
4. **FloatingPill własne animacje** - position:fixed wyjęty z flow
5. **Jeden plik variants** - spójność animacji

---

## ŹRÓDŁA WIEDZY

- DR: "Orkiestracja Animacji w React z Framer Motion"
- Sekcja 3: FSM z useReducer
- Sekcja 6: Desktop ↔ Mobile implementation

---

## ZNANE OGRANICZENIA

1. FloatingPill ma position:fixed - nie może być animowany przez rodzica
2. Wewnętrzne AnimatePresence (expand slider) - niezależne od FSM
3. Header ma własne AnimatePresence - niezależne od FSM

---

## TESTOWANIE

| Test | Oczekiwane | Status |
|------|------------|--------|
| Desktop → Mobile | Sekwencja: desktop exit → mobile enter | Do weryfikacji |
| Mobile → Desktop | Sekwencja: mobile exit → desktop enter | Do weryfikacji |
| Pills expand/collapse | Płynna animacja panelu | OK |
| Desktop interakcje | RecalcPanel, ModeToggle, FAB działają | OK |

---

## GIT COMMIT

```
571eb38 Responsive mobile UI with FloatingPills
```

Kolejny commit potrzebny dla FSM refaktoru.
