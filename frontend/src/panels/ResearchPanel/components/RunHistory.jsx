import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import DiagnosticsReport from "./DiagnosticsReport";
import { StatusBadge, formatDate } from "../../../utils/pipelineHelpers.jsx";

function ExpandedRunTabs({ run }) {
  return (
    <DiagnosticsReport
      diagnostics={run.diagnostics}
      configSnapshot={run.config_snapshot}
      steps={run.steps}
    />
  );
}

export default function RunHistory({ runs, onSelectRun, selectedRunId, selectedRunDetail }) {
  if (!runs || runs.length === 0) return null;

  return (
    <div className="space-y-1.5">
      {runs.map((r) => (
        <div key={r.id}>
          <button
            data-qa={`run.select-${r.id}`}
            onClick={() => onSelectRun(r.id)}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-colors ${
              selectedRunId === r.id
                ? "bg-gray-700 border border-gray-600 rounded-b-none"
                : "bg-gray-800/30 border border-transparent hover:bg-gray-800/60"
            }`}
          >
            <StatusBadge status={r.status} />
            <span className="text-gray-300 truncate">
              {r.config_name || "?"}
            </span>
            <span className="text-gray-500 ml-auto flex-shrink-0">
              {formatDate(r.started_at)}
            </span>
            <span className="text-gray-600">{r.n_sightings} obs</span>
            <span
              className={`text-gray-500 transition-transform ${selectedRunId === r.id ? "rotate-180" : ""}`}
            >
              {"▼"}
            </span>
          </button>

          <AnimatePresence>
            {selectedRunId === r.id && selectedRunDetail && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="border border-t-0 border-gray-600 rounded-b-lg bg-gray-800/30">
                  <ExpandedRunTabs run={selectedRunDetail} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ))}
    </div>
  );
}
