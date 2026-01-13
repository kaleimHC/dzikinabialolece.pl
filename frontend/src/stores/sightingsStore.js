import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import { themes, DEFAULT_THEME } from '../themes/registry';

const _getStoredTheme = () => {
  try {
    const s = localStorage.getItem('dziki-theme');
    return (s && themes[s]) ? s : DEFAULT_THEME;
  } catch { return DEFAULT_THEME; }
};

const _applyTheme = (name) => {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', name);
  }
};

export const useSightingsStore = create(
  subscribeWithSelector((set, get) => ({
    // Onboarding
    hasSeenOnboarding: localStorage.getItem('dziki-onboarded') === '1',
    completeOnboarding: () => {
      localStorage.setItem('dziki-onboarded', '1')
      set({ hasSeenOnboarding: true })
    },

    // Theme slice — additive (zero breaking dla istniejących subscribers)
    currentTheme: _getStoredTheme(),
    setTheme: (name) => {
      if (!themes[name]) return;
      set({ currentTheme: name });
      try { localStorage.setItem('dziki-theme', name); } catch {}
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
    pendingLocation: null,  // { lat, lng }

    // Grid visibility per mode
    showFastGrid: true,
    showHeatmap: true,
    showResearchGrid: true,

    // Linked toggles (risk map + population sync/xor)
    linkedToggles: false,
    linkedXor: false,  // true = opposite states (XOR mode), false = same states (sync mode)

    toggleLinked: () => {
      const state = get();
      const wasLinked = state.linkedToggles;
      if (!wasLinked) {
        // Turning ON linking - detect if states are opposite (XOR) or same (sync)
        const riskMapOn = state.displayMode === 'fast'
          ? state.showFastGrid
          : state.displayMode === 'research'
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
          visibleLayers: { ...state.visibleLayers, population: popNewVal }
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
          visibleLayers: { ...state.visibleLayers, population: popNewVal }
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
          visibleLayers: { ...state.visibleLayers, population: popNewVal }
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
        const riskUpdate = state.displayMode === 'fast'
          ? { showFastGrid: riskNewVal }
          : state.displayMode === 'research'
            ? { showResearchGrid: riskNewVal }
            : { showHeatmap: riskNewVal };
        set({
          visibleLayers: { ...state.visibleLayers, population: newVal },
          ...riskUpdate
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
      wMatrix: false,  // W matrix neighbor connections
    },
    toggleLayer: (layerKey) => set((s) => ({
      visibleLayers: { ...s.visibleLayers, [layerKey]: !s.visibleLayers[layerKey] }
    })),

    // Display mode: 'fast' (heuristic), 'publication' (voronoi), or 'research' (spatialWarsaw)
    displayMode: 'fast',
    setDisplayMode: (mode) => set((state) => {
      const updates = { displayMode: mode };
      // Wyłącz macierz W gdy opuszczamy tryb research
      if (state.displayMode === 'research' && mode !== 'research') {
        updates.visibleLayers = { ...state.visibleLayers, wMatrix: false };
      }
      return updates;
    }),

    // Research geometry type: 'voronoi' or 'grid_500'
    researchGeometry: 'voronoi',
    setResearchGeometry: (geom) => {
      const current = get().researchGeometry;
      if (current === geom) return; // Guard: no-op if same value
      set({ researchGeometry: geom });
    },
      if (!db.objectStoreNames.contains('store')) {
        db.createObjectStore('store', { keyPath: 'key' });
      }
    };
  });
}

// Apply initial theme on module load
_applyTheme(_getStoredTheme());
