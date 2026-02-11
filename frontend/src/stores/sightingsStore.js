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
}));
