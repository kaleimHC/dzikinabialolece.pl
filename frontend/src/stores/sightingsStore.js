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
      if (!db.objectStoreNames.contains('store')) {
        db.createObjectStore('store', { keyPath: 'key' });
      }
    };
  });
}

// Apply initial theme on module load
_applyTheme(_getStoredTheme());
