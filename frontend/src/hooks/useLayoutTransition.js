import { useState, useCallback, useEffect } from "react";

/**
 * Hook do koordynacji animacji Desktop ↔ Mobile.
 *
 * AnimatePresence mode="wait" automatycznie:
 * 1. Animuje EXIT starego layoutu
 * 2. CZEKA na zakończenie
 * 3. Animuje ENTER nowego layoutu
 *
 * Ten hook tylko śledzi stan i dostarcza callback.
 */
export function useLayoutTransition(isMobile) {
  // Layout bezpośrednio z breakpointu - AnimatePresence mode="wait" zajmie się sekwencją
  const layout = isMobile ? "mobile" : "desktop";

  // Śledzenie czy jesteśmy w trakcie przejścia
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [prevLayout, setPrevLayout] = useState(layout);

  // Wykryj zmianę layoutu
  useEffect(() => {
    if (layout !== prevLayout) {
      setIsTransitioning(true);
      setPrevLayout(layout);
    }
  }, [layout, prevLayout]);

  // Callback dla AnimatePresence onExitComplete
  const onExitComplete = useCallback(() => {
    setIsTransitioning(false);
  }, []);

  return {
    layout,
    onExitComplete,
    isTransitioning,
  };
}

export default useLayoutTransition;
