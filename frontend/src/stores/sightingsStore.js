import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import { themes, DEFAULT_THEME } from "../themes/registry";

const _getStoredTheme = () => {
  try {
    const s = localStorage.getItem("dziki-theme");
    return s && themes[s] ? s : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
};

const _applyTheme = (name) => {
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", name);
  }
};

export const useSightingsStore = create(
  subscribeWithSelector((set, get) => ({
    // Onboarding
    hasSeenOnboarding: localStorage.getItem("dziki-onboarded") === "1",
    completeOnboarding: () => {
      localStorage.setItem("dziki-onboarded", "1");
      set({ hasSeenOnboarding: true });
    },

    // Theme slice - additive (zero breaking dla istniejących subscribers)
    currentTheme: _getStoredTheme(),
    setTheme: (name) => {
      if (!themes[name]) return;
      set({ currentTheme: name });
      try {
        localStorage.setItem("dziki-theme", name);
      } catch {}
      _applyTheme(name);
    },

    // State
    sightings: [],
    selectedSighting: null,
    isLoading: false,
    error: null,

    // Map state (transient - don't persist)
    mapCenter: [20.98, 52.33],
    mapZoom: 12,

    // Add sighting mode (centered pin pattern)
    isAddMode: false,
    pendingLocation: null, // { lat, lng }

    // Grid visibility per mode
    showFastGrid: true,
    showHeatmap: true,
    showResearchGrid: true,

    // Linked toggles (risk map + population sync/xor)
    linkedToggles: false,
    linkedXor: false, // true = opposite states (XOR mode), false = same states (sync mode)

    toggleLinked: () => {
      const state = get();
      const wasLinked = state.linkedToggles;
      if (!wasLinked) {
        // Turning ON linking - detect if states are opposite (XOR) or same (sync)
        const riskMapOn =
          state.displayMode === "fast"
            ? state.showFastGrid
            : state.displayMode === "research"
              ? state.showResearchGrid
              : state.showHeatmap;
        const populationOn = state.visibleLayers.population;
        const isXor = riskMapOn !== populationOn;
        set({ linkedToggles: true, linkedXor: isXor });
      } else {
        set({ linkedToggles: false, linkedXor: false });
      }
    },

    toggleFastGrid: () => {
      const state = get();
      const newVal = !state.showFastGrid;
      if (state.linkedToggles) {
        // XOR mode: population gets opposite, Sync mode: population gets same
        const popNewVal = state.linkedXor ? !newVal : newVal;
        set({
          showFastGrid: newVal,
          visibleLayers: { ...state.visibleLayers, population: popNewVal },
        });
      } else {
        set({ showFastGrid: newVal });
      }
    },
    toggleHeatmap: () => {
      const state = get();
      const newVal = !state.showHeatmap;
      if (state.linkedToggles) {
        const popNewVal = state.linkedXor ? !newVal : newVal;
        set({
          showHeatmap: newVal,
          visibleLayers: { ...state.visibleLayers, population: popNewVal },
        });
      } else {
        set({ showHeatmap: newVal });
      }
    },
    toggleResearchGrid: () => {
      const state = get();
      const newVal = !state.showResearchGrid;
      if (state.linkedToggles) {
        const popNewVal = state.linkedXor ? !newVal : newVal;
        set({
          showResearchGrid: newVal,
          visibleLayers: { ...state.visibleLayers, population: popNewVal },
        });
      } else {
        set({ showResearchGrid: newVal });
      }
    },

    // Population toggle with linked sync/xor
    togglePopulation: () => {
      const state = get();
      const newVal = !state.visibleLayers.population;
      if (state.linkedToggles) {
        // XOR mode: risk map gets opposite, Sync mode: risk map gets same
        const riskNewVal = state.linkedXor ? !newVal : newVal;
        const riskUpdate =
          state.displayMode === "fast"
            ? { showFastGrid: riskNewVal }
            : state.displayMode === "research"
              ? { showResearchGrid: riskNewVal }
              : { showHeatmap: riskNewVal };
        set({
          visibleLayers: { ...state.visibleLayers, population: newVal },
          ...riskUpdate,
        });
      } else {
        set({ visibleLayers: { ...state.visibleLayers, population: newVal } });
      }
    },

    // OSM layer visibility for comparison
    visibleLayers: {
      forests: false,
      scrub: false,
      meadows: false,
      parks: false,
      water: false,
      waterways: false,
      farmland: false,
      allotments: false,
      buildings: false,
      barriers: false,
      roads: false,
      railway: false,
      population: false,
      wMatrix: false, // W matrix neighbor connections
    },
    toggleLayer: (layerKey) =>
      set((s) => ({
        visibleLayers: {
          ...s.visibleLayers,
          [layerKey]: !s.visibleLayers[layerKey],
        },
      })),

    // Display mode: 'fast' (heuristic), 'publication' (voronoi), or 'research' (spatialModel)
    displayMode: "fast",
    setDisplayMode: (mode) =>
      set((state) => {
        const updates = { displayMode: mode };
        // Wyłącz macierz W gdy opuszczamy tryb research
        if (state.displayMode === "research" && mode !== "research") {
          updates.visibleLayers = { ...state.visibleLayers, wMatrix: false };
        }
        return updates;
      }),

    // Research geometry type: 'voronoi' or 'grid_500'
    researchGeometry: "voronoi",
    setResearchGeometry: (geom) => {
      const current = get().researchGeometry;
      if (current === geom) return; // Guard: no-op if same value
      set({ researchGeometry: geom });
    },

    // Research panel visibility
    showResearchPanel: false,
    toggleResearchPanel: () =>
      set({ showResearchPanel: !get().showResearchPanel }),

    // Actions
    setSightings: (sightings) => set({ sightings }),

    setSelectedSighting: (sighting) => set({ selectedSighting: sighting }),

    setLoading: (isLoading) => set({ isLoading }),

    setError: (error) => set({ error }),

    // Add mode actions
    enterAddMode: () => {
      const state = get();
      set({
        isAddMode: true,
        pendingLocation: { lat: state.mapCenter[1], lng: state.mapCenter[0] },
      });
    },
    exitAddMode: () => set({ isAddMode: false, pendingLocation: null }),
    setPendingLocation: (lat, lng) => set({ pendingLocation: { lat, lng } }),

    // Transient updates (60 FPS safe - don't trigger re-renders)
    updateMapView: (center, zoom) => {
      // Direct mutation for performance - no React re-render
      const state = get();
      state.mapCenter = center;
      state.mapZoom = zoom;
    },

    // Async actions
    fetchSightings: async () => {
      set({ isLoading: true, error: null });
      try {
        const response = await fetch("/api/sightings/");
        if (!response.ok) throw new Error("Błąd pobierania danych");
        const data = await response.json();
        const features = data.results?.features || data.features || [];
        set({ sightings: features, isLoading: false });
      } catch (error) {
        set({ error: error.message, isLoading: false });
      }
    },

    submitSighting: async (sightingData) => {
      set({ isLoading: true, error: null });
      try {
        const response = await fetch("/api/sightings/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(sightingData),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.location?.[0] || "Błąd zapisu");
        }

        const newSighting = await response.json();
        set((state) => ({
          sightings: [...state.sightings, newSighting],
          isLoading: false,
          isAddMode: false,
          pendingLocation: null,
        }));

        return newSighting;
      } catch (error) {
        set({ error: error.message, isLoading: false });
        throw error;
      }
    },

    // Computed
    get totalBoars() {
      return get().sightings.reduce(
        (sum, s) => sum + (s.properties?.boar_count || 1),
        0,
      );
    },

    get recentSightings() {
      const weekAgo = new Date();
      weekAgo.setDate(weekAgo.getDate() - 7);
      return get().sightings.filter((s) => {
        const date = new Date(s.properties?.observed_at);
        return date > weekAgo;
      });
    },
  })),
);

// Offline queue for PWA
export const useOfflineQueue = create((set, get) => ({
  queue: [],

  addToQueue: (sighting) => {
    set((state) => ({ queue: [...state.queue, sighting] }));
    // Persist to IndexedDB
    if (typeof indexedDB !== "undefined") {
      saveToIndexedDB("offlineQueue", get().queue);
    }
  },

  processQueue: async () => {
    const { queue } = get();
    if (queue.length === 0) return;

    const processed = [];
    for (const sighting of queue) {
      try {
        await useSightingsStore.getState().submitSighting(sighting);
        processed.push(sighting);
      } catch {
        // Keep in queue if offline
      }
    }

    set((state) => ({
      queue: state.queue.filter((s) => !processed.includes(s)),
    }));
  },

  loadFromStorage: async () => {
    if (typeof indexedDB !== "undefined") {
      const queue = await loadFromIndexedDB("offlineQueue");
      if (queue) set({ queue });
    }
  },
}));

// IndexedDB helpers
async function saveToIndexedDB(key, value) {
  const db = await openDB();
  const tx = db.transaction("store", "readwrite");
  tx.objectStore("store").put({ key, value });
}

async function loadFromIndexedDB(key) {
  const db = await openDB();
  const tx = db.transaction("store", "readonly");
  const result = await tx.objectStore("store").get(key);
  return result?.value;
}

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("dziki-offline", 1);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains("store")) {
        db.createObjectStore("store", { keyPath: "key" });
      }
    };
  });
}

// Apply initial theme on module load
_applyTheme(_getStoredTheme());
