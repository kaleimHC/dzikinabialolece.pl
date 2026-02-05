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
}));
