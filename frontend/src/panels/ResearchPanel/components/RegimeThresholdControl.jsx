/**
 * RegimeThresholdControl.jsx - Swiss Design regime threshold configuration
 *
 * Compact, functional interface for setting forest/urban thresholds.
 * One line per threshold, inline input, proportional result bars.
 *
 * Features:
 * - Geometry-aware (grid_500 or voronoi)
 * - Refresh button to regenerate preview data
 * - Handles missing data with warning message
 */

import React, { useState, useEffect, useCallback, useMemo } from "react";

const API = "/api/research";

function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

function ThresholdRow({
  label,
  value,
  onChange,
  countAbove,
  percentAbove,
  color,
  maxValue = 100,
}) {
  const colorClasses = {
    forest: { text: "text-emerald-400", accent: "accent-emerald-500" },
    urban: { text: "text-slate-400", accent: "accent-slate-500" },
  };
  const colors = colorClasses[color] || colorClasses.forest;
  const percent = Math.round(value * 100);

  return (
    <div className="space-y-1">
      {/* Top row: label, value, count */}
      <div className="flex items-center gap-2 font-mono text-[13px]">
        <span className={`w-14 font-medium ${colors.text}`}>{label}</span>
        <span className="text-gray-500">&ge;</span>
        <span className="w-10 text-right text-white font-medium">
          {percent}%
        </span>
        <div className="flex-1" />
        <span className="tabular-nums text-gray-300">
          {countAbove?.toLocaleString("pl-PL") || 0}
        </span>
        <span className="w-14 text-right tabular-nums text-gray-500">
          ({percentAbove?.toFixed(1) || 0}%)
        </span>
      </div>
      {/* Slider */}
      <input
        type="range"
        min={0}
        max={maxValue}
        step={1}
        value={percent}
        onChange={(e) => onChange(parseInt(e.target.value, 10) / 100)}
        className={`w-full h-1.5 bg-gray-700 rounded-sm cursor-pointer ${colors.accent}`}
      />
    </div>
  );
}

function ResultRow({ label, count, total, color }) {
  const percent = total > 0 ? (count / total) * 100 : 0;

  const colorClasses = {
    forest: { text: "text-emerald-400", bar: "bg-emerald-500" },
    urban: { text: "text-slate-400", bar: "bg-slate-500" },
    mixed: { text: "text-amber-400", bar: "bg-amber-500" },
  };

  const colors = colorClasses[color] || colorClasses.mixed;

  return (
    <div className="flex items-center gap-2 h-6 font-mono text-[12px]">
      <span
        className={`w-14 font-semibold uppercase tracking-wide ${colors.text}`}
      >
        {label}
      </span>
      <span className="w-12 text-right tabular-nums text-gray-300">
        {count?.toLocaleString("pl-PL") || 0}
      </span>
      <div className="flex-1 h-1.5 bg-gray-800 rounded-sm overflow-hidden">
        <div
          className={`h-full transition-all duration-200 ${colors.bar}`}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="w-12 text-right tabular-nums text-gray-500">
        {percent.toFixed(1)}%
      </span>
    </div>
  );
}

export default function RegimeThresholdControl({
  forestThreshold,
  urbanThreshold,
  onForestChange,
  onUrbanChange,
  geometryType = "grid_500",
  disabled = false,
}) {
  const [distributions, setDistributions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  // Track last refreshed geometry to detect when user switches without refreshing
  const [lastRefreshedGeometry, setLastRefreshedGeometry] = useState(null);

  const [localForest, setLocalForest] = useState(forestThreshold);
  const [localUrban, setLocalUrban] = useState(urbanThreshold);

  useEffect(() => setLocalForest(forestThreshold), [forestThreshold]);
  useEffect(() => setLocalUrban(urbanThreshold), [urbanThreshold]);

  const debouncedForest = useDebounce(localForest, 300);
  const debouncedUrban = useDebounce(localUrban, 300);

  useEffect(() => {
    if (debouncedForest !== forestThreshold) onForestChange(debouncedForest);
  }, [debouncedForest, forestThreshold, onForestChange]);

  useEffect(() => {
    if (debouncedUrban !== urbanThreshold) onUrbanChange(debouncedUrban);
  }, [debouncedUrban, urbanThreshold, onUrbanChange]);

  const fetchDistributions = useCallback(async () => {
    try {
      setLoading(true);
      const url = `${API}/distributions/?geometry_type=${geometryType}&forest_threshold=${localForest}&building_threshold=${localUrban}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setDistributions(data);
      setError(null);
      // On initial load with available data, track the loaded geometry
      if (data.available && lastRefreshedGeometry === null) {
        setLastRefreshedGeometry(data.geometry_type);
      }
    } catch (e) {
      console.error("Failed to fetch distributions:", e);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [geometryType, localForest, localUrban, lastRefreshedGeometry]);

  // Initial fetch and refetch on geometry change
  useEffect(() => {
    fetchDistributions();
  }, [geometryType]);

  // Refetch on threshold change (debounced)
  useEffect(() => {
    if (!loading) fetchDistributions();
  }, [debouncedForest, debouncedUrban]);

  // Handle refresh button click - regenerate geometry + OSM features
  const handleRefresh = async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`${API}/generate-preview/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ geometry_type: geometryType }),
      });
      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Generowanie nie powiodło się");
      } else {
        // The endpoint returns distributions data directly
        setDistributions(data);
        // Track that we refreshed for this geometry
        setLastRefreshedGeometry(geometryType);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  // Calculate stats from buckets
  const forestStats = useMemo(() => {
    const buckets = distributions?.forest_cover?.buckets || [];
    if (!buckets.length) return { countAbove: 0, percentAbove: 0 };

    let above = 0;
    let total = 0;
    for (const b of buckets) {
      total += b.count;
      if ((b.from + b.to) / 2 >= localForest) above += b.count;
    }
    return {
      countAbove: above,
      percentAbove: total > 0 ? (above / total) * 100 : 0,
    };
  }, [distributions, localForest]);

  const urbanStats = useMemo(() => {
    const buckets = distributions?.building_density?.buckets || [];
    if (!buckets.length) return { countAbove: 0, percentAbove: 0 };

    let above = 0;
    let total = 0;
    for (const b of buckets) {
      total += b.count;
      if ((b.from + b.to) / 2 >= localUrban) above += b.count;
    }
    return {
      countAbove: above,
      percentAbove: total > 0 ? (above / total) * 100 : 0,
    };
  }, [distributions, localUrban]);

  const regimePreview = distributions?.regime_preview;
  const nCells = distributions?.n_cells || 0;
  const isAvailable = distributions?.available !== false;

  // Detect when user changed geometry since last refresh
  const geometryChanged =
    lastRefreshedGeometry !== null && lastRefreshedGeometry !== geometryType;

  // Loading state (initial load only)
  if (loading && !distributions) {
    return (
      <div className="py-4 text-center text-xs text-gray-500 font-mono">
        Ładowanie...
      </div>
    );
  }

  // Error state
  if (error && !distributions) {
    return (
      <div className="py-4 text-center text-xs text-red-400 font-mono">
        Błąd: {error}
      </div>
    );
  }

  return (
    <div
      className={`space-y-3 ${disabled ? "opacity-50 pointer-events-none" : ""}`}
    >
      {/* Header with geometry type, cell count, and refresh button */}
      <div className="flex items-center justify-between">
        <div className="text-xs font-mono">
          <span className="text-gray-500">
            {geometryType === "voronoi" ? "Voronoi" : "Grid 500m"}
          </span>
          {nCells > 0 && (
            <span className="text-gray-600">
              {" "}
              ({nCells.toLocaleString("pl-PL")})
            </span>
          )}
          {geometryChanged && (
            <span className="text-amber-500 ml-2">
              Zmieniono geometrię. Dane nieaktualne - kliknij Odśwież
            </span>
          )}
        </div>
        <button
          onClick={handleRefresh}
          disabled={generating || disabled}
          className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50
                     transition-colors flex items-center gap-1"
          title="Wygeneruj geometrię i oblicz cechy OSM"
        >
          {generating ? (
            <>
              <span className="animate-spin inline-block w-3 h-3 border border-blue-400 border-t-transparent rounded-full" />
              <span>Generowanie...</span>
            </>
          ) : (
            <>
              <span>Odśwież</span>
            </>
          )}
        </button>
      </div>

      {/* Error message */}
      {error && (
        <div className="text-xs text-red-400 bg-red-900/20 border border-red-700/30 p-2 rounded">
          {error}
        </div>
      )}

      {/* Warning for missing data */}
      {!isAvailable && !generating && !error && (
        <div className="text-xs text-amber-400 bg-amber-900/20 border border-amber-700/30 p-2 rounded">
          {distributions?.message ||
            'Brak danych. Kliknij "Odśwież" aby wygenerować.'}
        </div>
      )}

      {/* Data available - show full preview */}
      {isAvailable && (
        <>
          {/* Threshold inputs */}
          <div className="space-y-1">
            <ThresholdRow
              label="Las"
              value={localForest}
              onChange={setLocalForest}
              countAbove={forestStats.countAbove}
              percentAbove={forestStats.percentAbove}
              color="forest"
              maxValue={100}
            />
            <ThresholdRow
              label="Miasto"
              value={localUrban}
              onChange={setLocalUrban}
              countAbove={urbanStats.countAbove}
              percentAbove={urbanStats.percentAbove}
              color="urban"
              maxValue={50}
            />
          </div>

          {/* Separator */}
          <div className="h-px bg-gray-700/50" />

          {/* Classification result */}
          {regimePreview && (
            <div className="space-y-0.5">
              <ResultRow
                label="Forest"
                count={regimePreview.n_forest}
                total={nCells}
                color="forest"
              />
              <ResultRow
                label="Urban"
                count={regimePreview.n_urban}
                total={nCells}
                color="urban"
              />
              <ResultRow
                label="Mixed"
                count={regimePreview.n_mixed}
                total={nCells}
                color="mixed"
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
