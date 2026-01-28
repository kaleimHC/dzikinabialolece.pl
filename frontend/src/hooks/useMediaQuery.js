import { useSyncExternalStore, useCallback } from "react";

/**
 * Hook do reaktywnego śledzenia media queries.
 * Używa useSyncExternalStore dla bezpieczeństwa w React 18 Concurrent Mode.
 *
 * @param {string} query - Media query string, np. "(min-width: 768px)"
 * @returns {boolean} - Czy query jest spełnione
 */
export function useMediaQuery(query) {
  const subscribe = useCallback(
    (callback) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", callback);
      return () => mql.removeEventListener("change", callback);
    },
    [query],
  );

  const getSnapshot = useCallback(
    () =>
      typeof window !== "undefined" ? window.matchMedia(query).matches : false,
    [query],
  );

  const getServerSnapshot = useCallback(() => false, []);

  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/**
 * Hook sprawdzający czy jesteśmy na mobile (<768px)
 * @returns {boolean}
 */
export function useIsMobile() {
  return !useMediaQuery("(min-width: 768px)");
}

/**
 * Hook sprawdzający czy jesteśmy na desktop (≥768px)
 * @returns {boolean}
 */
export function useIsDesktop() {
  return useMediaQuery("(min-width: 768px)");
}

export default useMediaQuery;
