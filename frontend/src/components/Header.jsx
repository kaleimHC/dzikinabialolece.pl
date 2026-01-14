import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSightingsStore } from '../stores/sightingsStore';
import { useIsMobile } from '../hooks/useMediaQuery';
import { themes } from '../themes/registry';
import { getTokens } from '../tokens/colors';

function contrastColor(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 > 128 ? '#1a1a1a' : '#ffffff';
}

function contrastColorRgb(rgbStr) {
  const clean = rgbStr.replace(/^rgb\(\s*|\s*\)$/g, '');
  const [r, g, b] = clean.trim().split(/\s+/).map(Number);
  return (r * 299 + g * 587 + b * 114) / 1000 > 128 ? '#1a1a1a' : '#ffffff';
}

export default function Header() {
  const {
    showResearchPanel,
    toggleResearchPanel,
    displayMode,
    showFastGrid,
    toggleFastGrid,
    showHeatmap,
    toggleHeatmap,
    showResearchGrid,
    toggleResearchGrid,
    visibleLayers,
    toggleLayer,
    togglePopulation,
    linkedToggles,
    linkedXor,
    toggleLinked,
  } = useSightingsStore();

  const currentTheme = useSightingsStore((s) => s.currentTheme);
  const setTheme = useSightingsStore((s) => s.setTheme);
  const tk = useMemo(() => getTokens(currentTheme), [currentTheme]);

  const cycleTheme = () => {
    const keys = Object.keys(themes);
    const next = keys[(keys.indexOf(currentTheme) + 1) % keys.length];
    setTheme(next);
  };

  const isWMatrixVisible = visibleLayers?.wMatrix ?? false;

  const isMobile = useIsMobile();

  // Mapa ryzyka toggle depends on current mode (fast / publication / research)
  const isMapVisible = displayMode === 'fast'
    ? showFastGrid
    : displayMode === 'research'
      ? showResearchGrid
      : showHeatmap;

  const toggleMap = displayMode === 'fast'
    ? toggleFastGrid
    : displayMode === 'research'
      ? toggleResearchGrid
      : toggleHeatmap;
  const isPopulationVisible = visibleLayers?.population ?? false;

  return (
    <div className="absolute top-0 left-0 right-0 z-30 header-bg">
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-3">
          {/* Logo — cycles through themes on click */}
          <motion.button
            onClick={cycleTheme}
            whileHover={{ scale: 1.12, rotate: 8 }}
            whileTap={{ scale: 0.82, rotate: -18 }}
            className="w-11 h-11 rounded-xl flex items-center justify-center text-xl logo-gradient cursor-pointer"
            aria-label="Następny motyw"
            title={themes[currentTheme]?.name}
          >
            🐗
          </motion.button>
          <div>
            <h1 className="font-bold text-base tracking-tight" style={{ color: 'rgb(var(--color-text))' }}>Dziki na Białołęce</h1>
            {!isMobile && <p className="text-xs" style={{ color: 'rgb(var(--color-muted))' }}>Mapa obserwacji ryzyka</p>}
          </div>
        </div>

        <div className="flex items-center gap-0">

          {/* Risk Map + Link + Population group */}
          <div className="flex items-center gap-0">
            {/* Risk Map Toggle */}
            <button
              onClick={toggleMap}
              className={`btn-hdr ${isMapVisible ? '' : 'btn-off'}`}
              style={{
                ...(isMapVisible ? { backgroundColor: tk.encounter, color: contrastColor(tk.encounter), border: `1px solid ${tk.encounter}` } : {}),
                ...(linkedToggles ? { borderRadius: '8px 0 0 8px', borderRight: 'none' } : {})
              }}
            >
              <span>🗺️</span>
              <span>Mapa ryzyka</span>
            </button>


            {/* Population Toggle */}
            <button
              onClick={togglePopulation}
              className={`btn-hdr ${isPopulationVisible ? '' : 'btn-off'}`}
              style={{
                ...(isPopulationVisible ? { backgroundColor: tk.layerResearch, color: contrastColorRgb(tk.layerResearch), border: `1px solid ${tk.layerResearch}` } : {}),
                ...(linkedToggles ? { borderRadius: '0 8px 8px 0', borderLeft: 'none' } : {})
              }}
            >
              <span>👥</span>
              <span>Populacja</span>
            </button>
          </div>

          {/* Research Panel Toggle - animuje WIDTH przy wejściu/wyjściu */}
          <AnimatePresence>
            {!isMobile && (
              <motion.button
                key="research-toggle"
                initial={{ opacity: 0, width: 0, marginLeft: 0 }}
                animate={{ opacity: 1, width: 'auto', marginLeft: 12 }}
                exit={{ opacity: 0, width: 0, marginLeft: 0 }}
                transition={{ duration: 0.3, ease: 'easeOut' }}
                onClick={() => {
                  toggleResearchPanel();
                }}
                className={`btn-hdr btn-hdr-animated ${showResearchPanel ? 'btn-on-research' : 'btn-off'}`}
              >
                <span>🔬</span>
                <span>Tryb badawczy</span>
              </motion.button>
            )}
          </AnimatePresence>

          <OfflineIndicator />
        </div>
      </div>
    </div>
  );
}

function OfflineIndicator() {
  const isOnline = useOnlineStatus();
  
  if (isOnline) return null;
  
  return (
    <div className="px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 badge-offline">
      <div className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
      Offline
    </div>
  );
}

function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(typeof navigator !== "undefined" ? navigator.onLine : true);
  
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);
  
  return isOnline;
}
