import { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ErrorBoundary from "./components/ErrorBoundary";
import MapContainer from "./components/MapContainer";
import ReportSheet from "./components/ReportSheet";
import CenteredPin from "./components/CenteredPin";
import Header from "./components/Header";
import ReportFAB from "./components/ReportFAB";
import ModeToggle from "./components/ModeToggle";
import RecalcPanel from "./components/RecalcPanel";
import ResearchPanel from "./panels/ResearchPanel";
import LayersBottomBar from "./components/LayersBottomBar";
import ProbaBottomBar from "./components/ProbaBottomBar";
import { useSightingsStore, useOfflineQueue } from "./stores/sightingsStore";
import { Onboarding } from "./components/Onboarding";
import { useIsMobile } from "./hooks/useMediaQuery";
import { useLayoutTransition } from "./hooks/useLayoutTransition";
import {
  containerVariants,
  desktopChildVariants,
} from "./config/layoutAnimations";
import "./styles/globals.css";

export default function App() {
  const {
    fetchSightings,
    showResearchPanel,
    isAddMode,
    enterAddMode,
    displayMode,
    showFastGrid,
    showHeatmap,
    toggleFastGrid,
    toggleHeatmap,
    hasSeenOnboarding,
  } = useSightingsStore();
  const { loadFromStorage, processQueue } = useOfflineQueue();
  const isMobile = useIsMobile();
  const { layout, onExitComplete } = useLayoutTransition(isMobile);

  // Stan dla bottom barów na mobile
  const [probaBarOpen, setProbaBarOpen] = useState(false);
  const [layersBarOpen, setLayersBarOpen] = useState(false);
  // Ref do zapamiętania stanu mapy ryzyka (synchroniczny, bez re-renderów)
  const riskMapWasOnRef = useRef(false);

  // Sprawdź czy którykolwiek bottom bar jest otwarty
  const anyBarOpen = probaBarOpen || layersBarOpen;

  // Obsługa otwarcia proba bottom bar
  const openProbaBar = () => {
    setLayersBarOpen(false);
    setProbaBarOpen(true);
  };

  // Obsługa otwarcia layers bottom bar
  const openLayersBar = () => {
    const isFastMode = displayMode === "fast";
    const isRiskMapOn = isFastMode ? showFastGrid : showHeatmap;
    const toggleRiskMap = isFastMode ? toggleFastGrid : toggleHeatmap;

    // Save state and turn off risk map
    riskMapWasOnRef.current = isRiskMapOn;
    if (isRiskMapOn) toggleRiskMap();

    setProbaBarOpen(false);
    setLayersBarOpen(true);
  };

  // Obsługa zamknięcia layers bottom bar
  const closeLayersBar = () => {
    const isFastMode = displayMode === "fast";
    const toggleRiskMap = isFastMode ? toggleFastGrid : toggleHeatmap;

    // Restore risk map if it was on
    if (riskMapWasOnRef.current) {
      toggleRiskMap();
      riskMapWasOnRef.current = false;
    }

    setLayersBarOpen(false);
  };

  useEffect(() => {
    fetchSightings();
    loadFromStorage();
    const handleOnline = () => {
      processQueue();
      fetchSightings();
    };
    window.addEventListener("online", handleOnline);
    return () => window.removeEventListener("online", handleOnline);
  }, []);

  // Toggle body class for MapLibre controls visibility (research panel, bottom bars)
  useEffect(() => {
    if (showResearchPanel || anyBarOpen) {
      document.body.classList.add("ui-hidden");
    } else {
      document.body.classList.remove("ui-hidden");
    }
  }, [showResearchPanel, anyBarOpen]);

  return (
    <ErrorBoundary>
      <div className="relative w-full h-screen overflow-hidden font-sans">
        <MapContainer />
        <Header />
        <CenteredPin />
        <ReportSheet />

        {/* === SKOORDYNOWANE LAYOUTY Desktop/Mobile === */}
        <AnimatePresence mode="wait" onExitComplete={onExitComplete}>
          {!showResearchPanel && !isAddMode && layout === "desktop" && (
            <motion.div
              key="desktop-layout"
              variants={containerVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              {/* RecalcPanel - lewy dolny */}
              <motion.div
                variants={desktopChildVariants.left}
                initial="initial"
                animate="animate"
                exit="exit"
                className="absolute bottom-6 left-4 z-20"
                data-onboard="calc-panel"
              >
                <RecalcPanel />
              </motion.div>

              {/* ModeToggle - prawy górny */}
              <motion.div
                variants={desktopChildVariants.right}
                initial="initial"
                animate="animate"
                exit="exit"
                className="absolute top-20 right-4 z-20 w-56"
                data-onboard="mode-toggle"
              >
                <ModeToggle />
              </motion.div>

              {/* FAB - prawy dolny */}
              <motion.div
                variants={desktopChildVariants.fab}
                initial="initial"
                animate="animate"
                exit="exit"
                className="fixed bottom-6 right-6 z-[200]"
                data-onboard="report-fab"
              >
                <ReportFAB />
              </motion.div>
            </motion.div>
          )}

          {!showResearchPanel && !isAddMode && layout === "mobile" && (
            <motion.div
              key="mobile-layout"
              variants={containerVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              {/* Belka dolna: Próba | FAB | Warstwy - jeden kontener, flex centruje FAB bez translate */}
              <AnimatePresence>
                {!anyBarOpen && (
                  <motion.div
                    key="bottom-bar"
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 30 }}
                    transition={{ duration: 0.3, ease: "easeOut" }}
                    className="fixed bottom-4 left-4 right-4 z-40 grid items-center gap-3"
                    style={{
                      bottom: "calc(1rem + env(safe-area-inset-bottom, 0px))",
                      gridTemplateColumns: "1fr 56px 1fr",
                    }}
                  >
                    {/* Próba pill */}
                    <motion.button
                      data-qa="mobile.proba-open"
                      onClick={openProbaBar}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      className="
                      justify-self-start flex items-center gap-2
                      px-4 py-3
                      bg-gray-800/95 backdrop-blur-lg
                      rounded-xl border border-white/10
                      shadow-lg text-white font-medium text-sm
                    "
                    >
                      <span>Próba</span>
                      <span className="text-primary">▲</span>
                    </motion.button>

                    {/* FAB - środkowy element flexa, zero translate */}
                    <motion.button
                      data-qa="mobile.fab-add-sighting"
                      onClick={enterAddMode}
                      whileTap={{ scale: 0.9 }}
                      className="w-14 h-14 rounded-2xl flex-shrink-0 flex items-center justify-center border-none cursor-pointer fab-primary"
                      aria-label="Zgłoś obserwację"
                    >
                      <svg
                        width="24"
                        height="24"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="white"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                      >
                        <path d="M12 5v14M5 12h14" />
                      </svg>
                    </motion.button>

                    {/* Warstwy pill */}
                    <motion.button
                      data-qa="mobile.layers-open"
                      onClick={openLayersBar}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      className="
                      justify-self-end flex items-center gap-2
                      px-4 py-3
                      bg-gray-800/95 backdrop-blur-lg
                      rounded-xl border border-white/10
                      shadow-lg text-white font-medium text-sm
                    "
                    >
                      <span>Warstwy</span>
                      <span className="text-primary">▲</span>
                    </motion.button>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Bottom Bars */}
              <ProbaBottomBar
                isOpen={probaBarOpen}
                onClose={() => setProbaBarOpen(false)}
              />
              <LayersBottomBar
                isOpen={layersBarOpen}
                onClose={closeLayersBar}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Research Panel - fullscreen when active */}
        <ResearchPanel />

        {/* Onboarding - shown on first visit, z-[500] covers all UI */}
        <AnimatePresence>
          {!hasSeenOnboarding && <Onboarding key="onboarding" />}
        </AnimatePresence>
      </div>
    </ErrorBoundary>
  );
}
