import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSightingsStore } from "../stores/sightingsStore";
import { getTokens } from "../tokens/colors";

export default function ReportSheet() {
  const { isAddMode, pendingLocation, exitAddMode, submitSighting, isLoading } =
    useSightingsStore();
  const currentTheme = useSightingsStore((s) => s.currentTheme);
  const tk = useMemo(() => getTokens(currentTheme), [currentTheme]);
  const [type, setType] = useState("encounter");

  const handleSubmit = async () => {
    if (!pendingLocation) return;
    try {
      await submitSighting({
        latitude: pendingLocation.lat,
        longitude: pendingLocation.lng,
        boar_count: "1",
        sighting_type: type,
      });
    } catch (error) {
      console.error("ReportSheet submit error:", error);
    }
  };

  return (
    <AnimatePresence>
      {isAddMode && (
        <motion.div
          initial={{ y: 80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 80, opacity: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          style={{
            position: "fixed",
            bottom: 0,
            left: 0,
            right: 0,
            zIndex: 200,
            padding: "12px",
            paddingBottom: "calc(12px + env(safe-area-inset-bottom, 0px))",
            background: "rgb(var(--color-bg) / 0.95)",
            backdropFilter: "blur(16px)",
            borderTop: "1px solid rgb(var(--color-border) / 0.5)",
          }}
        >
          <div
            style={{
              maxWidth: "420px",
              margin: "0 auto",
              display: "flex",
              gap: "8px",
            }}
          >
            <motion.button
              data-qa="sighting.cancel"
              onClick={() => {
                exitAddMode();
              }}
              whileTap={{ scale: 0.9 }}
              style={{
                width: "48px",
                padding: "12px",
                borderRadius: "12px",
                border: "none",
                background: "rgba(239, 68, 68, 0.15)",
                color: "#EF4444",
                fontSize: "18px",
                cursor: "pointer",
                flexShrink: 0,
              }}
            >
              ✕
            </motion.button>
            <motion.button
              data-qa="sighting.type-encounter"
              onClick={() => {
                setType("encounter");
              }}
              whileTap={{ scale: 0.95 }}
              // NOTE: framer-motion animate + CSS var = no smooth color interpolation
              //       (instant switch zamiast 0.2s transition - known limitation, Phase 5+ scope)
              animate={{
                background:
                  type === "encounter"
                    ? tk.encounter
                    : "rgb(var(--color-gray-700) / 0.5)",
                color:
                  type === "encounter" ? "white" : "rgb(var(--color-muted))",
              }}
              transition={{ duration: 0.2 }}
              style={{
                flex: 1,
                padding: "12px",
                borderRadius: "12px",
                border: "none",
                fontSize: "14px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              🐗 Spotkanie
            </motion.button>
            <motion.button
              data-qa="sighting.type-ryjowisko"
              onClick={() => {
                setType("ryjowisko");
              }}
              whileTap={{ scale: 0.95 }}
              animate={{
                background:
                  type === "ryjowisko"
                    ? tk.ryjowisko
                    : "rgb(var(--color-gray-700) / 0.5)",
                color:
                  type === "ryjowisko" ? "white" : "rgb(var(--color-muted))",
              }}
              transition={{ duration: 0.2 }}
              style={{
                flex: 1,
                padding: "12px",
                borderRadius: "12px",
                border: "none",
                fontSize: "14px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              📍 Ryjowisko
            </motion.button>
            <motion.button
              data-qa="sighting.submit"
              onClick={handleSubmit}
              disabled={isLoading}
              whileTap={{ scale: 0.9 }}
              style={{
                width: "48px",
                padding: "12px",
                borderRadius: "12px",
                border: "none",
                background: "rgb(var(--color-primary-dark))",
                color: "white",
                fontSize: "18px",
                cursor: "pointer",
                flexShrink: 0,
              }}
            >
              {isLoading ? "•••" : "✓"}
            </motion.button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
