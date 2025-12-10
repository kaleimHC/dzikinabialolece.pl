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

    submitSighting: async (payload) => {
      set({ isLoading: true, error: null });
      // Optimistic update: add placeholder
      const tempId = `temp-${Date.now()}`;
      const optimistic = {
        id: tempId,
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [payload.longitude, payload.latitude] },
        properties: { ...payload, status: 'pending' },
      };
      set(state => ({ sightings: [optimistic, ...state.sightings] }));

      try {
        const res = await fetch('/api/sightings/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(JSON.stringify(err));
        }
        const created = await res.json();
        // Replace optimistic with real
        set(state => ({
          sightings: state.sightings.map(s => s.id === tempId ? created : s),
          isLoading: false,
        }));
      } catch (err) {
        // Rollback optimistic
        set(state => ({
          sightings: state.sightings.filter(s => s.id !== tempId),
          error: err.message,
          isLoading: false,
        }));
        throw err;
      }
    },
  }))
);
