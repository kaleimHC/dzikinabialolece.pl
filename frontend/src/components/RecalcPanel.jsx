import { useState, useEffect, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import { useSightingsStore } from "../stores/sightingsStore";
import SampleSlider from "./SampleSlider";
import { getTokens } from "../tokens/colors";

function contrastColor(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 > 128 ? "#1a1a1a" : "#ffffff";
}

function contrastColorRgb(rgbStr) {
  const clean = rgbStr.replace(/^rgb\(\s*|\s*\)$/g, "");
  const [r, g, b] = clean.trim().split(/\s+/).map(Number);
  return (r * 299 + g * 587 + b * 114) / 1000 > 128 ? "#1a1a1a" : "#ffffff";
}

function getModeStyle(modeId, tk) {
  if (modeId === "fast")
    return {
      background: tk.ryjowisko,
      color: contrastColor(tk.ryjowisko),
    };
  if (modeId === "publication")
    return {
      background: tk.encounter,
      color: contrastColor(tk.encounter),
    };
  return {
    background: tk.layerResearch,
    color: contrastColorRgb(tk.layerResearch),
  };
}

// Fetch research geometry based on LAST SUCCESSFUL RUN (not selected config)
// This ensures map shows computed results, not pending selection
const fetchComputedResearchGeometry = async () => {
  try {
    const [statusRes, configsRes] = await Promise.all([
      fetch("/api/research/status/"),
      fetch("/api/research/configs/"),
    ]);
    if (!statusRes.ok || !configsRes.ok) return null;

    const status = await statusRes.json();
    const configsData = await configsRes.json();

    // Get geometry from last successful run
    const lastSuccess =
      status?.last_run?.status === "success" ? status.last_run : null;
    if (lastSuccess) {
      const successConfig = (configsData.configs || []).find(
        (c) => c.id === lastSuccess.config_id,
      );
      if (successConfig?.geometry_type) {
        return successConfig.geometry_type;
      }
    }

    // Fallback: if no successful run yet, use active config
    return status?.active_config?.geometry_type || "voronoi";
  } catch (e) {
    console.warn("Failed to fetch research status:", e);
    return null;
  }
};

const MODES = [
  { id: "fast", label: "fastPython" },
  { id: "publication", label: "voronoiGrids" },
  { id: "research", label: "spatialWarsaw" },
];

export default function RecalcPanel({ embedded = false }) {
  const { fetchSightings, displayMode, setDisplayMode, setResearchGeometry } =
    useSightingsStore();
  const currentTheme = useSightingsStore((s) => s.currentTheme);
  const tk = useMemo(() => getTokens(currentTheme), [currentTheme]);

  // Compute state
  const [computeStatus, setComputeStatus] = useState({
    running: false,
    error: null,
    completed: false,
    progress: null,
    currentStep: 0,
    totalSteps: 1,
    currentScript: "",
    taskId: null, // For PUB pipeline async task tracking
  });

  // Panel rozwijania - domyślnie zwinięty
  const [sampleExpanded, setSampleExpanded] = useState(false);

  // Determine mode from store
  const isFastMode = displayMode === "fast";
  const isResearchMode = displayMode === "research";

  // Sync research geometry on mount if in research mode
  useEffect(() => {
    if (displayMode === "research") {
      fetchComputedResearchGeometry().then((geomType) => {
        if (geomType) setResearchGeometry(geomType);
      });
    }
  }, [displayMode, setResearchGeometry]);

  // Poll status when running
  useEffect(() => {
    if (!computeStatus.running) return;

    const interval = setInterval(async () => {
      try {
        // Use task-specific endpoint for PUB pipeline, old endpoint for FAST
        const statusUrl = computeStatus.taskId
          ? `/api/analytics/pipeline/${computeStatus.taskId}/status/`
          : "/api/analytics/recalculate/status/";

        const res = await fetch(statusUrl);
        const data = await res.json();

        // Parse result for pipeline endpoint (different format)
        const isCompleted = computeStatus.taskId
          ? data.status === "success" || data.status === "error"
          : data.completed;
        const isRunning = computeStatus.taskId
          ? data.status === "pending" || data.status === "running"
          : data.running;
        const hasError = computeStatus.taskId
          ? data.status === "error"
            ? data.message
            : null
          : data.error;

        const justCompleted =
          isCompleted && !isRunning && computeStatus.running;

        setComputeStatus((prev) => ({
          ...prev,
          running: isRunning,
          currentStep: data.current_step || (isCompleted ? prev.totalSteps : 0),
          totalSteps: data.total_steps || prev.totalSteps,
          currentScript: data.current_script || "",
          error: hasError,
          completed: isCompleted && !hasError,
        }));

        if (justCompleted) {
          fetchSightings();
          setTimeout(
            () => window.dispatchEvent(new CustomEvent("voronoi-refresh")),
            500,
          );
          setTimeout(
            () =>
              setComputeStatus((s) => ({
                ...s,
                completed: false,
                taskId: null,
              })),
            3000,
          );
        }
      } catch (e) {
        console.error("Status poll failed:", e);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [computeStatus.running, computeStatus.taskId, fetchSightings]);

  // Main compute handler
  const handleCompute = useCallback(async () => {
    setComputeStatus({
      running: true,
      error: null,
      completed: false,
      progress: "Uruchamiam...",
      currentStep: 0,
      totalSteps: 1, // Simplified - no step tracking from backend
      currentScript: "",
    });

    try {
      if (isFastMode) {
        // FAST mode - synchronous, quick Python-based calculation
        const res = await fetch("/api/analytics/pipeline/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: "FAST", async: false }),
        });
        const data = await res.json();

        if (res.ok) {
          setComputeStatus({
            running: false,
            error: null,
            completed: true,
            progress: null,
            currentStep: 1,
            totalSteps: 1,
            currentScript: `Cells: ${data.result?.ensemble?.count || "?"}`,
          });
          fetchSightings();
          setTimeout(
            () => window.dispatchEvent(new CustomEvent("voronoi-refresh")),
            500,
          );
          setTimeout(
            () => setComputeStatus((s) => ({ ...s, completed: false })),
            3000,
          );
        } else {
          throw new Error(data.message || "FAST failed");
        }
      } else {
        // PUB or RESEARCH mode - async R pipeline
        // PUB = voronoi grid, RESEARCH = research grid (spatialWarsaw experiments)
        const pipelineMode = isResearchMode ? "RESEARCH" : "PUB";
        const res = await fetch("/api/analytics/pipeline/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: pipelineMode, async: true }),
        });
        const data = await res.json();

        if (res.ok && data.task_id) {
          // Pipeline started - poll for status
          setComputeStatus((prev) => ({
            ...prev,
            taskId: data.task_id,
            progress: `${pipelineMode} pipeline uruchomiony...`,
          }));
        } else {
          throw new Error(
            data.message || `${pipelineMode} pipeline failed to start`,
          );
        }
      }
    } catch (e) {
      setComputeStatus((prev) => ({
        ...prev,
        running: false,
        error: e.message || "Błąd",
        progress: null,
      }));
    }
  }, [isFastMode, isResearchMode, fetchSightings]);

  const progress =
    computeStatus.totalSteps > 0
      ? (computeStatus.currentStep / computeStatus.totalSteps) * 100
      : 0;

  // Wspólna zawartość panelu
  const panelContent = (
    <>
      {/* SAMPLE SLIDER */}
      <SampleSlider
        isExpanded={sampleExpanded}
        onToggle={() => setSampleExpanded((prev) => !prev)}
      />

      {/* MODE SELECTION */}
      <div className="flex gap-1 my-3">
        {MODES.map((mode) => {
          return (
            <button
              key={mode.id}
              data-qa={`recalc.mode-${mode.id}`}
              onClick={async () => {
                setDisplayMode(mode.id);
                // When switching to research mode, sync geometry type from backend
                if (mode.id === "research") {
                  const geomType = await fetchComputedResearchGeometry();
                  if (geomType) {
                    setResearchGeometry(geomType);
                  }
                }
              }}
              className={`flex-1 px-3 py-2 rounded-md text-xs font-medium transition-all ${
                displayMode !== mode.id
                  ? "bg-gray-700 text-gray-400 hover:bg-gray-600"
                  : ""
              }`}
              style={
                displayMode === mode.id ? getModeStyle(mode.id, tk) : undefined
              }
            >
              {mode.label}
            </button>
          );
        })}
      </div>

      {/* MAIN COMPUTE BUTTON or RESEARCH INFO */}
      {isResearchMode ? (
        <div
          style={{
            width: "100%",
            padding: "8px 12px",
            borderRadius: "6px",
            fontSize: "11px",
            background: "rgb(var(--color-gray-700))",
            color: "rgb(var(--color-gray-400))",
            textAlign: "center",
            border: "1px solid rgb(var(--color-gray-600))",
          }}
        >
          Użyj trybu badawczego aby utworzyć mapę
        </div>
      ) : (
        <button
          data-qa="recalc.compute"
          onClick={() => {
            handleCompute();
          }}
          disabled={computeStatus.running}
          style={{
            width: "100%",
            padding: "8px 12px",
            borderRadius: "6px",
            border: "none",
            fontSize: "12px",
            fontWeight: "500",
            cursor: computeStatus.running ? "not-allowed" : "pointer",
            transition: "all 0.2s",
            background: computeStatus.running
              ? "rgb(var(--color-gray-700))"
              : isFastMode
                ? tk.ryjowisko
                : tk.encounter,
            color: computeStatus.running
              ? "#fff"
              : isFastMode
                ? contrastColor(tk.ryjowisko)
                : contrastColor(tk.encounter),
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
          }}
        >
          {computeStatus.running ? (
            <>
              <span
                style={{
                  width: "14px",
                  height: "14px",
                  border: "2px solid #fff",
                  borderTopColor: "transparent",
                  borderRadius: "50%",
                  animation: "spin 1s linear infinite",
                }}
              />
              Obliczam...
            </>
          ) : (
            <>Oblicz mapę ryzyka</>
          )}
        </button>
      )}

      {/* STATUS MESSAGES */}
      {computeStatus.error && (
        <div style={{ marginTop: "8px", fontSize: "10px", color: "#EF4444" }}>
          {computeStatus.error}
        </div>
      )}
      {computeStatus.completed && !computeStatus.running && (
        <div
          style={{
            marginTop: "8px",
            fontSize: "10px",
            color: "rgb(var(--color-primary))",
          }}
        >
          Gotowe!
        </div>
      )}

      {/* CSS for spinner animation */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </>
  );

  // EMBEDDED (mobile w FloatingPill)
  if (embedded) {
    return <div className="space-y-3">{panelContent}</div>;
  }

  // DESKTOP (stylizowany panel, pozycjonowanie kontrolowane przez App.jsx)
  return (
    <div
      className="p-3 rounded-lg min-w-[220px]"
      style={{
        background: "rgb(var(--color-surface) / 0.95)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        border: "1px solid rgb(var(--color-border))",
        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
      }}
    >
      {panelContent}
    </div>
  );
}
