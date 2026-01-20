import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  STATUS_ICON,
  STATUS_COLOR,
  StatusBadge,
  formatDate,
  formatDuration,
} from "../../../utils/pipelineHelpers.jsx";

export default function RunStepsList({ run }) {
  const [expandedStep, setExpandedStep] = useState(null);
  const statusIcon = STATUS_ICON;
  const statusColor = STATUS_COLOR;

  return (
    <div className="bg-gray-800/50 rounded-lg border border-gray-700 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <StatusBadge status={run.status} />
          <span className="text-xs text-gray-400">
            {run.config_name && <span>{run.config_name} / </span>}
            {run.n_sightings != null && <span>{run.n_sightings} obs</span>}
          </span>
        </div>
        <span className="text-xs text-gray-500">
          {formatDate(run.started_at)}
        </span>
      </div>

      {run.error_message && (
        <div className="px-3 py-2 text-xs text-red-400 bg-red-900/10 border-b border-gray-700">
          {run.error_message}
        </div>
      )}

      {(run.steps || []).map((step) => (
        <div key={step.step_order}>
          <button
            onClick={() =>
              setExpandedStep(
                expandedStep === step.step_order ? null : step.step_order,
              )
            }
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-gray-700/50 transition-colors"
          >
            <span className="w-4 text-center font-mono text-gray-600">
              {step.step_order}
            </span>
            <span
              className={`w-4 text-center ${statusColor[step.status] || ""}`}
            >
              {statusIcon[step.status] || "?"}
            </span>
            <span className="flex-1 text-left text-gray-300 font-mono">
              {step.step_name}
            </span>
            <span className="text-gray-500">
              {formatDuration(step.duration_seconds)}
            </span>
            {step.exit_code != null && step.exit_code !== 0 && (
              <span className="text-red-400">exit={step.exit_code}</span>
            )}
          </button>

          <AnimatePresence>
            {expandedStep === step.step_order &&
              (step.stdout || step.stderr) && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  className="overflow-hidden"
                >
                  <div className="px-3 pb-2 ml-8">
                    {step.stdout && (
                      <pre className="text-xs text-gray-400 bg-gray-950 rounded p-2 overflow-x-auto max-h-32 overflow-y-auto font-mono">
                        {step.stdout}
                      </pre>
                    )}
                    {step.stderr && (
                      <pre className="text-xs text-red-400/80 bg-red-950/30 rounded p-2 mt-1 overflow-x-auto max-h-32 overflow-y-auto font-mono">
                        {step.stderr}
                      </pre>
                    )}
                  </div>
                </motion.div>
              )}
          </AnimatePresence>
        </div>
      ))}
    </div>
  );
}
