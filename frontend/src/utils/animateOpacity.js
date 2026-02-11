/**
 * Animuje opacity warstwy MapLibre przez requestAnimationFrame
 * Działa dla fill-opacity i line-opacity
 */
export function animateOpacity(
  map,
  layerId,
  property,
  from,
  to,
  duration = 300,
) {
  return new Promise((resolve) => {
    if (!map || !map.getLayer(layerId)) {
      resolve();
      return;
    }

    const start = performance.now();

    // Wyłącz natywne transition
    const transitionProp = property + "-transition";
    try {
      map.setPaintProperty(layerId, transitionProp, { duration: 0, delay: 0 });
    } catch (e) {
      // Niektóre warstwy nie mają transition property
    }

    function frame(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic

      const currentValue = from + (to - from) * eased;
      // Clamp to valid range [0, 1] to avoid MapLibre errors
      const clampedValue = Math.max(0, Math.min(1, currentValue));
      map.setPaintProperty(layerId, property, clampedValue);

      if (progress < 1) {
        requestAnimationFrame(frame);
      } else {
        resolve();
      }
    }

    requestAnimationFrame(frame);
  });
}

/**
 * Czeka aż mapa będzie "idle" (wszystkie operacje renderowania zakończone)
 * Bardziej niezawodne niż sourcedata dla dużych datasetów
 */
export function waitForMapIdle(map, maxWait = 2000) {
  return new Promise((resolve) => {
    let resolved = false;

    const onIdle = () => {
      if (resolved) return;
      resolved = true;
      clearTimeout(timeoutId);
      resolve();
    };

    const timeoutId = setTimeout(() => {
      if (resolved) return;
      resolved = true;
      map.off("idle", onIdle);
      console.warn("[waitForMapIdle] Timeout after", maxWait, "ms");
      resolve();
    }, maxWait);

    map.once("idle", onIdle);
  });
}

/**
 * Wait for MapLibre to finish processing source data after setData()
 * Uses the 'sourcedata' event which fires when tiles are loaded
 * Falls back to requestAnimationFrame if event doesn't fire within timeout
 */
export function waitForSourceData(map, sourceId, timeout = 500) {
  return new Promise((resolve) => {
    let resolved = false;

    const handleSourceData = (e) => {
      if (e.sourceId === sourceId && e.isSourceLoaded && !resolved) {
        resolved = true;
        map.off("sourcedata", handleSourceData);
        // Extra frame to ensure render is complete
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            resolve();
          });
        });
      }
    };

    map.on("sourcedata", handleSourceData);

    // Fallback timeout
    setTimeout(() => {
      if (!resolved) {
        resolved = true;
        map.off("sourcedata", handleSourceData);
        console.warn("[waitForSourceData] Timeout after", timeout, "ms");
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            resolve();
          });
        });
      }
    }, timeout);
  });
}
