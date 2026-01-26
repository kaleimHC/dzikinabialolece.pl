import React from "react";

export const STATUS_ICON = {
  success: "✓",
  failed: "✗",
  skipped: "-",
  running: "…",
};

export const STATUS_COLOR = {
  success: "text-green-400",
  failed: "text-red-400",
  skipped: "text-gray-500",
  running: "text-blue-400",
};

export function StatusBadge({ status }) {
  const colors = {
    success: "bg-green-600/30 text-green-400",
    failed: "bg-red-600/30 text-red-400",
    running: "bg-blue-600/30 text-blue-400",
    pending: "bg-yellow-600/30 text-yellow-400",
    skipped: "bg-gray-600/30 text-gray-400",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-mono ${colors[status] || "bg-gray-600/30 text-gray-400"}`}
    >
      {status}
    </span>
  );
}

export function formatDuration(seconds) {
  if (seconds == null) return "-";
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
  return `${seconds.toFixed(1)}s`;
}

export function formatDate(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
