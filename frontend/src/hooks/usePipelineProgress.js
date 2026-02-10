/**
 * usePipelineProgress - WebSocket hook for real-time pipeline progress
 *
 * Connects to ws://host/ws/research/run/<runId>/ and receives:
 * - pipeline_start: Pipeline started
 * - step_start: Step is starting
 * - step_complete: Step finished (status, duration, stdout)
 * - pipeline_complete: Pipeline finished (success/failed)
 *
 * Falls back to polling if WebSocket fails to connect.
 */

import { useEffect, useState, useRef, useCallback } from "react";

// Pipeline step definitions (must match backend PIPELINE_STEPS)
const STEP_NAMES = [
  { name: "01_geometry", description: "Generate spatial units" },
  { name: "02_population", description: "Assign population" },
  { name: "03_osm_features", description: "Calculate OSM features" },
  { name: "04_variable_y", description: "Compute variable Y" },
  { name: "05_matrix_w", description: "Build spatial weights W" },
  { name: "06_model", description: "Fit spatial model" },
  { name: "07_diagnostics", description: "Run diagnostics" },
  { name: "08_results", description: "Generate results" },
];

const INITIAL_STATE = {
  connected: false,
  connecting: false,
  totalSteps: STEP_NAMES.length,
  currentStep: 0,
  steps: [],
  status: "pending", // pending | running | success | failed
  error: null,
  runId: null,
};

export function usePipelineProgress(runId) {
  const [progress, setProgress] = useState(INITIAL_STATE);
  const wsRef = useRef(null);
  const fallbackToPollingRef = useRef(false);

  // Reset state when runId changes
  useEffect(() => {
    if (!runId) {
      setProgress(INITIAL_STATE);
      return;
    }

    setProgress((prev) => ({
      ...INITIAL_STATE,
      runId,
      connecting: true,
    }));
  }, [runId]);

  // WebSocket connection
  useEffect(() => {
    if (!runId) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/research/run/${runId}/`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setProgress((prev) => ({
        ...prev,
        connected: true,
        connecting: false,
        error: null,
      }));
      fallbackToPollingRef.current = false;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleProgressEvent(data);
      } catch (e) {
        console.error("[WS] Parse error:", e);
      }
    };

    ws.onerror = (error) => {
      console.error("[WS] Error:", error);
      setProgress((prev) => ({
        ...prev,
        error: "WebSocket connection error",
        connecting: false,
      }));
    };

    ws.onclose = (event) => {
      setProgress((prev) => ({
        ...prev,
        connected: false,
        connecting: false,
      }));

      // Set fallback flag if connection was never established
      if (!fallbackToPollingRef.current && event.code !== 1000) {
        fallbackToPollingRef.current = true;
      }
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close(1000, "Component unmount");
        wsRef.current = null;
      }
    };
  }, [runId]);

  // Handle progress events from WebSocket
  const handleProgressEvent = useCallback((data) => {
    setProgress((prev) => {
      switch (data.event) {
        case "connected":
          return {
            ...prev,
            connected: true,
            connecting: false,
          };

        case "pipeline_start":
          return {
            ...prev,
            status: "running",
            totalSteps: data.total_steps || STEP_NAMES.length,
            currentStep: 0,
            steps: [],
            error: null,
          };

        case "step_start": {
          const stepNum = data.step_number;
          const newSteps = [...prev.steps];

          // Ensure we have all previous steps
          while (newSteps.length < stepNum - 1) {
            const idx = newSteps.length;
            newSteps.push({
              number: idx + 1,
              name: STEP_NAMES[idx]?.name || `step_${idx + 1}`,
              description: STEP_NAMES[idx]?.description || "",
              status: "pending",
            });
          }

          // Add/update current step
          newSteps[stepNum - 1] = {
            number: stepNum,
            name: data.step_name,
            description:
              data.step_description ||
              STEP_NAMES[stepNum - 1]?.description ||
              "",
            status: "running",
          };

          return {
            ...prev,
            currentStep: stepNum,
            steps: newSteps,
          };
        }

        case "step_complete": {
          const stepNum = data.step_number;
          const newSteps = [...prev.steps];

          // Ensure we have all steps up to this one (handles fast completion)
          while (newSteps.length < stepNum) {
            const idx = newSteps.length;
            newSteps.push({
              number: idx + 1,
              name: STEP_NAMES[idx]?.name || `step_${idx + 1}`,
              description: STEP_NAMES[idx]?.description || "",
              status: "pending",
            });
          }

          // Update the completed step
          newSteps[stepNum - 1] = {
            ...newSteps[stepNum - 1],
            name:
              data.step_name ||
              newSteps[stepNum - 1]?.name ||
              STEP_NAMES[stepNum - 1]?.name,
            status: data.status,
            duration: data.duration_seconds,
            exitCode: data.exit_code,
            stdout: data.stdout,
            stderr: data.stderr,
          };

          return {
            ...prev,
            steps: newSteps,
          };
        }

        case "pipeline_complete":
          return {
            ...prev,
            status: data.status,
            error: data.error_message || null,
          };

        case "pong":
          // Heartbeat response, ignore
          return prev;

        default:
          return prev;
      }
    });
  }, []);

  // Manual reset
  const reset = useCallback(() => {
    setProgress(INITIAL_STATE);
  }, []);

  // Check if using polling fallback
  const isUsingFallback = fallbackToPollingRef.current && !progress.connected;

  return {
    ...progress,
    isUsingFallback,
    reset,
  };
}

export default usePipelineProgress;
