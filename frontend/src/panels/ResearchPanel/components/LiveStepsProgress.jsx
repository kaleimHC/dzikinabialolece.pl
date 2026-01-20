/**
 * LiveStepsProgress - Real-time pipeline progress display
 *
 * Shows:
 * - Progress bar with percentage
 * - List of steps with status icons (clickable to expand stdout)
 * - Auto-expanded stdout for last completed step
 * - Connection status indicator
 */

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

const STATUS_ICONS = {
  success: { icon: "\u2713", color: "text-green-400" },
  failed: { icon: "\u2717", color: "text-red-400" },
  running: { icon: "\u2026", color: "text-blue-400" },
  pending: { icon: "\u25CB", color: "text-gray-600" },
  skipped: { icon: "\u2014", color: "text-gray-500" },
};

function formatDuration(seconds) {
  if (seconds == null) return "";
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(0);
  return `${mins}m ${secs}s`;
}

function StepRow({ step, isExpanded, onToggle, isLast }) {
  const { icon, color } = STATUS_ICONS[step.status] || STATUS_ICONS.pending;
  const isRunning = step.status === "running";
  const hasOutput = step.stdout || step.stderr;
  const isCompleted = step.status === "success" || step.status === "failed";

  return (
    <div className={!isLast ? "border-b border-gray-800/50" : ""}>
      <motion.button
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.2 }}
        onClick={() => hasOutput && onToggle()}
        className={`w-full flex items-center gap-2 text-sm py-1.5 px-1 rounded transition-colors ${
          hasOutput ? "hover:bg-gray-800/50 cursor-pointer" : "cursor-default"
        }`}
      >
        {/* Step number */}
        <span className="w-5 text-center text-xs text-gray-600 font-mono">
          {step.number}
        </span>

        {/* Status icon */}
        <span className={`w-4 text-center ${color}`}>
          {isRunning ? <span className="animate-pulse">{icon}</span> : icon}
        </span>

        {/* Step name */}
        <span
          className={`flex-1 text-left truncate ${
            isRunning
              ? "text-blue-300 font-medium"
              : step.status === "failed"
                ? "text-red-300"
                : "text-gray-400"
          }`}
        >
          {step.name}
        </span>

        {/* Duration */}
        {step.duration != null && (
          <span className="text-xs text-gray-500 tabular-nums">
            {formatDuration(step.duration)}
          </span>
        )}

        {/* Exit code if non-zero */}
        {step.exitCode != null && step.exitCode !== 0 && (
          <span className="text-xs text-red-400 font-mono">
            exit={step.exitCode}
          </span>
        )}

        {/* Expand indicator */}
        {hasOutput && (
          <span
            className={`text-xs text-gray-600 transition-transform ${isExpanded ? "rotate-90" : ""}`}
          >
            {"\u25B6"}
          </span>
        )}
      </motion.button>

      {/* Expandable stdout/stderr */}
      <AnimatePresence>
        {isExpanded && hasOutput && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="pl-9 pr-2 pb-2 space-y-1">
              {step.stdout && (
                <pre className="text-[11px] text-gray-400 bg-gray-950 rounded p-2 max-h-32 overflow-y-auto overflow-x-auto font-mono whitespace-pre-wrap">
                  {step.stdout}
                </pre>
              )}
              {step.stderr && (
                <pre className="text-[11px] text-red-400/80 bg-red-950/30 rounded p-2 max-h-24 overflow-y-auto overflow-x-auto font-mono whitespace-pre-wrap">
                  {step.stderr}
                </pre>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function LiveStepsProgress({ progress }) {
  const {
    connected,
    connecting,
    totalSteps,
    currentStep,
    steps,
    status,
    error,
    isUsingFallback,
  } = progress;

  // Track which step is expanded (auto-expand last completed)
  const [expandedStep, setExpandedStep] = useState(null);

  // Auto-expand the last completed step with output
  useEffect(() => {
    const completedWithOutput = steps
      .filter(
        (s) =>
          (s.status === "success" || s.status === "failed") &&
          (s.stdout || s.stderr),
      )
      .pop();

    if (completedWithOutput) {
      setExpandedStep(completedWithOutput.number);
    }
  }, [steps]);

  // Calculate completion percentage
  const completedCount = steps.filter((s) => s.status === "success").length;
  const percent = totalSteps > 0 ? (completedCount / totalSteps) * 100 : 0;

  // Find the currently running step
  const runningStep = steps.find((s) => s.status === "running");

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden">
      {/* Header with connection status */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-800">
        <span className="text-xs font-medium text-gray-300">
          Pipeline Progress
        </span>
        <div className="flex items-center gap-2">
          {/* Connection indicator */}
          <span className="flex items-center gap-1.5 text-xs">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                connected
                  ? "bg-green-400"
                  : connecting
                    ? "bg-yellow-400 animate-pulse"
                    : "bg-gray-600"
              }`}
            />
            <span className="text-gray-500">
              {connected
                ? "Live"
                : connecting
                  ? "Connecting..."
                  : isUsingFallback
                    ? "Polling"
                    : "Offline"}
            </span>
          </span>
        </div>
      </div>

      <div className="p-3 space-y-3">
        {/* Progress bar */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-400">
              {status === "running"
                ? runningStep
                  ? `Wykonywanie: ${runningStep.name}`
                  : `Krok ${currentStep}/${totalSteps}`
                : status === "success"
                  ? "Zakonczone pomyslnie"
                  : status === "failed"
                    ? "Blad wykonania"
                    : "Oczekiwanie..."}
            </span>
            <span className="text-gray-500 tabular-nums">
              {completedCount}/{totalSteps}
            </span>
          </div>
          <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <motion.div
              className={`h-full ${
                status === "failed"
                  ? "bg-red-500"
                  : status === "success"
                    ? "bg-green-500"
                    : "bg-blue-500"
              }`}
              initial={{ width: 0 }}
              animate={{ width: `${percent}%` }}
              transition={{ duration: 0.3, ease: "easeOut" }}
            />
          </div>
        </div>

        {/* Steps list with expandable stdout */}
        <div className="space-y-0">
          <AnimatePresence>
            {steps.map((step, idx) => (
              <StepRow
                key={step.number}
                step={step}
                isExpanded={expandedStep === step.number}
                onToggle={() =>
                  setExpandedStep(
                    expandedStep === step.number ? null : step.number,
                  )
                }
                isLast={idx === steps.length - 1}
              />
            ))}
          </AnimatePresence>

          {/* Placeholder for remaining steps */}
          {steps.length < totalSteps && status === "running" && (
            <div className="text-xs text-gray-600 py-1 pl-9">
              + {totalSteps - steps.length} pozostalych krokow...
            </div>
          )}
        </div>

        {/* Running step indicator */}
        {runningStep && (
          <div className="flex items-center gap-2 text-xs text-blue-400 bg-blue-950/20 rounded px-2 py-1.5">
            <span className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
            <span>Wykonywanie: {runningStep.name}...</span>
          </div>
        )}

        {/* Error message */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-xs text-red-400 bg-red-950/30 border border-red-900/50 rounded p-2"
          >
            {error}
          </motion.div>
        )}
      </div>
    </div>
  );
}
