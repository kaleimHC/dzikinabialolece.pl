import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

export const useSightingsStore = create(
  subscribeWithSelector((set, get) => ({
    // State
    sightings: [],
    selectedSighting: null,
    isLoading: false,
    error: null,

    // Map state (transient)
    mapCenter: [20.98, 52.33],
    mapZoom: 12,

    // Grid visibility per mode
    showFastGrid: true,
    showHeatmap: true,
    showResearchGrid: true,

    setSightings: (sightings) => set({ sightings }),
    setError: (error) => set({ error }),

    updateMapView: ({ center, zoom }) => set({ mapCenter: center, mapZoom: zoom }),
    setSelectedSighting: (s) => set({ selectedSighting: s }),

    fetchSightings: async () => {
      set({ isLoading: true, error: null });
      try {
        const res = await fetch('/api/sightings/?page_size=5000');
        if (!res.ok) throw new Error('Network response was not ok');
        const data = await res.json();
        const results = data.results || data.features || data;
        set({ sightings: results, isLoading: false });
      } catch (err) {
        set({ error: err.message, isLoading: false });
      }
    },
  }))
);
