import { useEffect, useRef } from "react";
import { animateOpacity, waitForMapIdle } from "../utils/animateOpacity";

const FADE_DURATION = 300;

const LAYER_CONFIG = {
  forests: {
    layerId: "forests-fill",
    type: "fill",
    targetOpacity: 0.5,
    endpoint: "forests",
  },
  water: {
    layerId: "water-fill",
    type: "fill",
    targetOpacity: 0.6,
    endpoint: "water",
  },
  waterways: {
    layerId: "waterways-line",
    type: "line",
    targetOpacity: 0.8,
    endpoint: "waterways",
  },
  buildings: {
    layerId: "buildings-fill",
    type: "fill",
    targetOpacity: 0.7,
    endpoint: "buildings",
  },
  roads: {
    layerId: "roads-line",
    type: "line",
    targetOpacity: 0.8,
    endpoint: "roads",
  },
  barriers: {
    layerId: "barriers-line",
    type: "line",
    targetOpacity: 0.8,
    endpoint: "barriers",
  },
  allotments: {
    layerId: "allotments-fill",
    type: "fill",
    targetOpacity: 0.5,
    endpoint: "allotments",
  },
  meadows: {
    layerId: "meadows-fill",
    type: "fill",
    targetOpacity: 0.5,
    endpoint: "meadows",
  },
  farmland: {
    layerId: "farmland-fill",
    type: "fill",
    targetOpacity: 0.4,
    endpoint: "farmland",
  },
  parks: {
    layerId: "parks-fill",
    type: "fill",
    targetOpacity: 0.5,
    endpoint: "parks",
  },
  scrub: {
    layerId: "scrub-fill",
    type: "fill",
    targetOpacity: 0.5,
    endpoint: "scrub",
  },
  railway: {
    layerId: "railway-line",
    type: "line",
    targetOpacity: 0.8,
    endpoint: "railway",
  },
  population: {
    layerId: "population-fill",
    type: "fill",
    targetOpacity: 0.55,
    endpoint: "population",
    outlineLayerId: "population-outline",
    outlineOpacity: 0.15,
  },
  wMatrix: {
    layerId: "w-matrix-lines",
    type: "line",
    targetOpacity: 0.6,
    endpoint: "w-matrix/edges",
    sourceId: "w-matrix",
  },
};

/**
 * Hook do lazy-loading warstw OSM
 *
 * Prosty przepływ:
 * - Toggle ON: jeśli nie w cache → fetch + fade-in, jeśli w cache → tylko fade-in
 * - Toggle OFF: tylko fade-out (dane zostają w cache)
 */
export function useOsmLayerTransition(mapRef, mapReady, visibleLayers) {
  const loadedLayersRef = useRef(new Set());
  const prevVisibleRef = useRef({});
  const animatingRef = useRef({});

  // Inicjalizacja - wszystkie warstwy niewidoczne
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    Object.entries(LAYER_CONFIG).forEach(([key, config]) => {
      if (!map.getLayer(config.layerId)) return;
      const opacityProp =
        config.type === "fill" ? "fill-opacity" : "line-opacity";
      map.setPaintProperty(config.layerId, opacityProp, 0);
      if (config.outlineLayerId && map.getLayer(config.outlineLayerId)) {
        map.setPaintProperty(config.outlineLayerId, "line-opacity", 0);
      }
      prevVisibleRef.current[key] = false;
    });
  }, [mapRef, mapReady]);

  // Nasłuchuj na voronoi-refresh aby odświeżyć macierz W po pipeline
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const handlePipelineRefresh = async () => {
      // Wyczyść cache macierzy W - zmienia się po każdym uruchomieniu pipeline
      loadedLayersRef.current.delete("wMatrix");

      // Jeśli warstwa jest widoczna, odśwież ją
      const isVisible = visibleLayers?.wMatrix ?? false;
      if (isVisible && !animatingRef.current.wMatrix) {
        const config = LAYER_CONFIG.wMatrix;
        animatingRef.current.wMatrix = true;
        loadedLayersRef.current.add("wMatrix");

        try {
          const res = await fetch(`/api/analytics/${config.endpoint}/`);
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data = await res.json();

          const source = map.getSource(config.sourceId);
          if (source) {
            source.setData(data);
            console.log(
              "[wMatrix] Refreshed after pipeline, edges:",
              data.features?.length,
            );
          }
        } catch (err) {
          console.warn("wMatrix refresh failed:", err);
          loadedLayersRef.current.delete("wMatrix");
        } finally {
          animatingRef.current.wMatrix = false;
        }
      }
    };

    window.addEventListener("voronoi-refresh", handlePipelineRefresh);
    return () =>
      window.removeEventListener("voronoi-refresh", handlePipelineRefresh);
  }, [mapRef, mapReady, visibleLayers]);

  // Reaguj na zmiany visibleLayers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    Object.entries(LAYER_CONFIG).forEach(([key, config]) => {
      const isVisible = visibleLayers?.[key] ?? false;
      const wasVisible = prevVisibleRef.current[key] ?? false;

      if (isVisible === wasVisible || animatingRef.current[key]) return;
      prevVisibleRef.current[key] = isVisible;

      if (!map.getLayer(config.layerId)) return;

      const opacityProp =
        config.type === "fill" ? "fill-opacity" : "line-opacity";

      if (isVisible) {
        // === TOGGLE ON ===
        const isLoaded = loadedLayersRef.current.has(key);

        if (!isLoaded) {
          // LAZY-LOAD: fetch + fade-in
          animatingRef.current[key] = true;
          loadedLayersRef.current.add(key);

          (async () => {
            try {
              const res = await fetch(`/api/analytics/${config.endpoint}/`);
              if (!res.ok) throw new Error(`HTTP ${res.status}`);
              const data = await res.json();

              const sourceId = config.sourceId || key;
              const source = map.getSource(sourceId);
              if (source) {
                source.setData(data);
                await waitForMapIdle(map, 1000);
                await animateOpacity(
                  map,
                  config.layerId,
                  opacityProp,
                  0,
                  config.targetOpacity,
                  FADE_DURATION,
                );
                if (
                  config.outlineLayerId &&
                  map.getLayer(config.outlineLayerId)
                ) {
                  map.setPaintProperty(
                    config.outlineLayerId,
                    "line-opacity",
                    config.outlineOpacity,
                  );
                }
              }
            } catch (err) {
              console.warn(`${key} fetch failed:`, err);
              loadedLayersRef.current.delete(key);
            } finally {
              animatingRef.current[key] = false;
            }
          })();
        } else {
          // Z CACHE: tylko fade-in
          animatingRef.current[key] = true;
          const currentOpacity =
            map.getPaintProperty(config.layerId, opacityProp) ?? 0;
          animateOpacity(
            map,
            config.layerId,
            opacityProp,
            currentOpacity,
            config.targetOpacity,
            FADE_DURATION,
          ).then(() => {
            if (config.outlineLayerId && map.getLayer(config.outlineLayerId)) {
              map.setPaintProperty(
                config.outlineLayerId,
                "line-opacity",
                config.outlineOpacity,
              );
            }
            animatingRef.current[key] = false;
          });
        }
      } else {
        // === TOGGLE OFF === (tylko fade-out, dane zostają)
        animatingRef.current[key] = true;
        const currentOpacity =
          map.getPaintProperty(config.layerId, opacityProp) ??
          config.targetOpacity;
        animateOpacity(
          map,
          config.layerId,
          opacityProp,
          currentOpacity,
          0,
          FADE_DURATION,
        ).then(() => {
          if (config.outlineLayerId && map.getLayer(config.outlineLayerId)) {
            map.setPaintProperty(config.outlineLayerId, "line-opacity", 0);
          }
          animatingRef.current[key] = false;
        });
      }
    });
  }, [mapRef, mapReady, visibleLayers]);
}

export default useOsmLayerTransition;
