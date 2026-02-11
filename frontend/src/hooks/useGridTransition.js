import { useRef, useEffect, useCallback } from "react";
import {
  animateOpacity,
  waitForSourceData,
  waitForMapIdle,
} from "../utils/animateOpacity";

const FADE_DURATION = 300;
const FILL_OPACITY = 0.65;
const OUTLINE_OPACITY = 0.3;

export function useGridTransition(
  mapRef,
  mapReady,
  displayMode,
  showFastGrid,
  showHeatmap,
  showResearchGrid,
  researchGeometry = "voronoi",
) {
  const transitionTokenRef = useRef(0);
  const abortControllerRef = useRef(null);
  const isFirstLoadRef = useRef(true);
  const prevDisplayModeRef = useRef(displayMode);
  const prevResearchGeometryRef = useRef(researchGeometry);
  const prevShouldBeVisibleRef = useRef(null);
  const isAnimatingRef = useRef(false);
  const crossfadePendingRef = useRef(false);

  const shouldBeVisible =
    displayMode === "fast"
      ? showFastGrid
      : displayMode === "research"
        ? showResearchGrid
        : showHeatmap;

  // Helper: determine URL based on display mode and research geometry
  const getGridUrl = (mode, geometry) => {
    if (mode === "fast") {
      return "/api/analytics/grid/";
    } else if (mode === "research") {
      return geometry === "grid_500"
        ? "/api/analytics/research-grid-500/"
        : "/api/analytics/research-grid/";
    } else {
      return "/api/analytics/voronoi/";
    }
  };

  // EFEKT 1: Animowany toggle (TYLKO gdy displayMode się NIE zmienił)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    // Jeśli displayMode się zmienił, EFEKT 2 (crossfade) przejmie kontrolę
    const modeChanged = displayMode !== prevDisplayModeRef.current;
    if (modeChanged) return;

    // Sprawdź czy visibility się zmieniła
    const visibilityChanged =
      prevShouldBeVisibleRef.current !== null &&
      prevShouldBeVisibleRef.current !== shouldBeVisible;
    prevShouldBeVisibleRef.current = shouldBeVisible;

    // Jeśli visibility się nie zmieniła lub animacja w toku, skip
    if (
      !visibilityChanged ||
      crossfadePendingRef.current ||
      isAnimatingRef.current
    )
      return;

    const runToggleAnimation = async () => {
      isAnimatingRef.current = true;

      const targetFillOpacity = shouldBeVisible ? FILL_OPACITY : 0;
      const targetOutlineOpacity = shouldBeVisible ? OUTLINE_OPACITY : 0;

      const currentFillOpacity = map.getLayer("risk-fill")
        ? map.getPaintProperty("risk-fill", "fill-opacity") || 0
        : 0;
      const currentOutlineOpacity = map.getLayer("risk-outline")
        ? map.getPaintProperty("risk-outline", "line-opacity") || 0
        : 0;

      const fadePromises = [];
      if (map.getLayer("risk-fill")) {
        fadePromises.push(
          animateOpacity(
            map,
            "risk-fill",
            "fill-opacity",
            currentFillOpacity,
            targetFillOpacity,
            FADE_DURATION,
          ),
        );
      }
      if (map.getLayer("risk-outline")) {
        fadePromises.push(
          animateOpacity(
            map,
            "risk-outline",
            "line-opacity",
            currentOutlineOpacity,
            targetOutlineOpacity,
            FADE_DURATION,
          ),
        );
      }

      await Promise.all(fadePromises);
      isAnimatingRef.current = false;
    };

    runToggleAnimation();
  }, [mapRef, mapReady, shouldBeVisible, displayMode]);

  // EFEKT 2: Crossfade przy zmianie displayMode LUB researchGeometry
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const modeChanged = prevDisplayModeRef.current !== displayMode;
    const geometryChanged =
      displayMode === "research" &&
      prevResearchGeometryRef.current !== researchGeometry;

    prevDisplayModeRef.current = displayMode;
    prevResearchGeometryRef.current = researchGeometry;

    // Trigger refetch if mode changed OR geometry changed (while in research mode)
    if (!modeChanged && !geometryChanged) return;

    crossfadePendingRef.current = true;

    const runCrossfade = async () => {
      const myToken = ++transitionTokenRef.current;

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();
      const { signal } = abortControllerRef.current;

      const url = getGridUrl(displayMode, researchGeometry);

      isAnimatingRef.current = true;

      try {
        const currentFillOpacity = map.getLayer("risk-fill")
          ? map.getPaintProperty("risk-fill", "fill-opacity") || 0
          : 0;

        // FAZA 1: Fade-out (tylko jeśli coś jest widoczne)
        if (currentFillOpacity > 0) {
          const fadeOutPromises = [];
          if (map.getLayer("risk-fill")) {
            fadeOutPromises.push(
              animateOpacity(
                map,
                "risk-fill",
                "fill-opacity",
                currentFillOpacity,
                0,
                FADE_DURATION,
              ),
            );
          }
          if (map.getLayer("risk-outline")) {
            const currentOutline =
              map.getPaintProperty("risk-outline", "line-opacity") || 0;
            fadeOutPromises.push(
              animateOpacity(
                map,
                "risk-outline",
                "line-opacity",
                currentOutline,
                0,
                FADE_DURATION,
              ),
            );
          }

          const fetchPromise = fetch(url, { signal }).then((r) => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
          });

          const results = await Promise.all([...fadeOutPromises, fetchPromise]);
          const data = results[results.length - 1];

          if (myToken !== transitionTokenRef.current) return;

          // FAZA 2: setData
          const source = map.getSource("risk");
          if (source) {
            source.setData(data);

            const isLargeDataset = data.features?.length > 5000;
            if (isLargeDataset) {
              await waitForMapIdle(map, 2000);
            } else {
              await waitForSourceData(map, "risk", 500);
            }
          }

          if (myToken !== transitionTokenRef.current) return;

          // FAZA 3: Fade-in (TYLKO jeśli toggle ON)
          if (shouldBeVisible) {
            const fadeInPromises = [];
            if (map.getLayer("risk-fill")) {
              fadeInPromises.push(
                animateOpacity(
                  map,
                  "risk-fill",
                  "fill-opacity",
                  0,
                  FILL_OPACITY,
                  FADE_DURATION,
                ),
              );
            }
            if (map.getLayer("risk-outline")) {
              fadeInPromises.push(
                animateOpacity(
                  map,
                  "risk-outline",
                  "line-opacity",
                  0,
                  OUTLINE_OPACITY,
                  FADE_DURATION,
                ),
              );
            }
            await Promise.all(fadeInPromises);
          }
        } else {
          // Grid był niewidoczny — tylko fetch bez animacji fade-out
          const response = await fetch(url, { signal });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const data = await response.json();

          if (myToken !== transitionTokenRef.current) return;

          const source = map.getSource("risk");
          if (source) {
            source.setData(data);

            const isLargeDataset = data.features?.length > 5000;
            if (isLargeDataset) {
              await waitForMapIdle(map, 2000);
            } else {
              await waitForSourceData(map, "risk", 500);
            }
          }

          if (myToken !== transitionTokenRef.current) return;

          // Fade-in (spójność z główną ścieżką)
          if (shouldBeVisible) {
            const fadeInPromises = [];
            if (map.getLayer("risk-fill")) {
              fadeInPromises.push(
                animateOpacity(
                  map,
                  "risk-fill",
                  "fill-opacity",
                  0,
                  FILL_OPACITY,
                  FADE_DURATION,
                ),
              );
            }
            if (map.getLayer("risk-outline")) {
              fadeInPromises.push(
                animateOpacity(
                  map,
                  "risk-outline",
                  "line-opacity",
                  0,
                  OUTLINE_OPACITY,
                  FADE_DURATION,
                ),
              );
            }
            if (fadeInPromises.length > 0) {
              await Promise.all(fadeInPromises);
            }
          }
        }
      } catch (err) {
        if (err.name === "AbortError") return;
        console.error("[GridTransition] Crossfade error:", err);

        if (myToken === transitionTokenRef.current && shouldBeVisible) {
          if (map.getLayer("risk-fill")) {
            map.setPaintProperty("risk-fill", "fill-opacity", FILL_OPACITY);
          }
          if (map.getLayer("risk-outline")) {
            map.setPaintProperty(
              "risk-outline",
              "line-opacity",
              OUTLINE_OPACITY,
            );
          }
        }
      } finally {
        isAnimatingRef.current = false;
        crossfadePendingRef.current = false;
        // Sync visibility ref after crossfade
        prevShouldBeVisibleRef.current = shouldBeVisible;
      }
    };

    runCrossfade();
  }, [mapRef, mapReady, displayMode, shouldBeVisible, researchGeometry]);

  // EFEKT 3: Pierwszy load
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !isFirstLoadRef.current) return;

    isFirstLoadRef.current = false;
    // Initialize visibility ref on first load
    prevShouldBeVisibleRef.current = shouldBeVisible;

    const url = getGridUrl(displayMode, researchGeometry);

    fetch(url)
      .then((r) => r.json())
      .then((data) => {
        const source = map.getSource("risk");
        if (source) {
          source.setData(data);
          // Set initial opacity based on current toggle state
          if (shouldBeVisible) {
            if (map.getLayer("risk-fill")) {
              map.setPaintProperty("risk-fill", "fill-opacity", FILL_OPACITY);
            }
            if (map.getLayer("risk-outline")) {
              map.setPaintProperty(
                "risk-outline",
                "line-opacity",
                OUTLINE_OPACITY,
              );
            }
          }
        }
      })
      .catch((err) =>
        console.error("[GridTransition] Initial load error:", err),
      );
  }, [mapRef, mapReady, displayMode, shouldBeVisible, researchGeometry]);

  // Event listener voronoi-refresh
  const handleRefresh = useCallback(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const url = getGridUrl(displayMode, researchGeometry);

    fetch(url)
      .then((r) => r.json())
      .then((data) => {
        const source = map.getSource("risk");
        if (source) {
          source.setData(data);
          // Force layer visibility if it was hidden
          if (map.getLayer("risk-fill")) {
            const currentOpacity =
              map.getPaintProperty("risk-fill", "fill-opacity") || 0;
            if (currentOpacity === 0) {
              map.setPaintProperty("risk-fill", "fill-opacity", FILL_OPACITY);
              if (map.getLayer("risk-outline")) {
                map.setPaintProperty(
                  "risk-outline",
                  "line-opacity",
                  OUTLINE_OPACITY,
                );
              }
            }
          }
        }
      })
      .catch((err) => console.error("[GridTransition] Refresh error:", err));
  }, [mapRef, mapReady, displayMode, researchGeometry]);

  useEffect(() => {
    window.addEventListener("voronoi-refresh", handleRefresh);
    return () => window.removeEventListener("voronoi-refresh", handleRefresh);
  }, [handleRefresh]);

  return { isAnimating: isAnimatingRef.current };
}

export default useGridTransition;
