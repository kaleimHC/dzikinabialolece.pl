/**
 * PipelineTab.jsx - Research Pipeline management
 *
 * Sections:
 * 1. Status overview (active config, sightings, last run)
 * 2. Config list with create/edit/activate
 * 3. Run pipeline button with live step progress
 * 4. Run history with expandable step logs
 *
 * API: /api/research/status/, /configs/, /run/, /runs/
 */

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSightingsStore } from "../../../stores/sightingsStore";
import { RESEARCH_PRESETS, PRESET_GROUPS, getPresetsByGroup } from "../presets";
import RegimeThresholdControl from "../components/RegimeThresholdControl";
import { usePipelineProgress } from "../../../hooks/usePipelineProgress";
import LiveStepsProgress from "../components/LiveStepsProgress";
import RunStepsList from "../components/RunStepsList";
import RunHistory from "../components/RunHistory";
import {
  STATUS_ICON,
  STATUS_COLOR,
  StatusBadge,
  formatDuration,
  formatDate,
} from "../../../utils/pipelineHelpers.jsx";

// OPISY PARAMETRÓW DLA KREATORA (inline hints)

const PARAM_HINTS = {
  // Podstawowe
  name: "Unikalna nazwa konfiguracji do identyfikacji w historii.",
  seed: "Ziarno losowości",

  // Macierz W
  w_method: "Metoda budowy macierzy sąsiedztwa przestrzennego.",
  k_range_min:
    "Minimalna liczba sąsiadów (k). AIC wybierze optymalną wartość z zakresu.",
  k_range_max: "Maksymalna liczba sąsiadów do przetestowania.",

  // Model
  geometry_type:
    "Typ siatki przestrzennej. Grid = stała rozdzielczość, Voronoi = adaptacyjna.",
  population_method: "Metoda przypisania populacji do komórek siatki.",
  y_formula: "Zmienna zależna modelu. Transformacja danych wejściowych.",
  model_type:
    "Typ modelu przestrzennego. SAR = autoregresja, SEM = błędy przestrzenne, SDM = Durbin.",

  // Diagnostyka
  vif_threshold:
    "Próg multikolinearności (Variance Inflation Factor). Zmienne z VIF > próg są usuwane. 5 = restrykcyjny, 10 = tolerancyjny.",
  alpha:
    "Poziom istotności statystycznej (α). Współczynniki z p-value < α są uznawane za istotne.",

  // Reżimy
  regime_type:
    "Podział przestrzeni na reżimy. Każdy reżim ma własne współczynniki modelu.",
  regime_threshold:
    "Próg klasyfikacji lasu. Komórki z ≥X% lasu → kategoria FOREST.",
  regime_threshold_urban:
    "Próg klasyfikacji zabudowy. Komórki z ≥X% zabudowy → kategoria URBAN.",

  // Predyktory
  predictors:
    "Zmienne objaśniające włączone do modelu. Standaryzowane metodą z-score (średnia=0, std=1).",

  // Diagnostyka (checkboxy)
  run_moran: "Moran's I - test autokorelacji przestrzennej residuów.",
  run_lm_tests:
    "Testy LM - porównanie SAR vs SEM na podstawie statystyki Lagrange'a.",
  run_lisa: "LISA - lokalne wskaźniki autokorelacji (hot-spots, cold-spots).",
  run_eta: "ETA - entropia przestrzenna (spatialWarsaw).",
};

// VALIDATION: Invalid combinations (mirrors backend clean())

function getValidationWarnings(form) {
  const warnings = [];
  const { geometry_type, y_formula, model_type } = form;

  // voronoi + binary = invalid (Voronoi 1:1 → Y=1 always)
  if (geometry_type === "voronoi" && y_formula === "binary") {
    warnings.push(
      "Voronoi + binary: Voronoi 1:1 oznacza Y=1 zawsze (brak wariancji)",
    );
  }

  // voronoi + log_count = invalid (Voronoi 1:1 → log(1+1)=0.693 always)
  if (geometry_type === "voronoi" && y_formula === "log_count") {
    warnings.push(
      "Voronoi + log(count+1): Każda komórka ma count=1, więc Y=0.693 dla wszystkich (brak wariancji)",
    );
  }

  // sar/sem/sdm + binary = invalid (requires continuous Y)
  if (["sar", "sem", "sdm"].includes(model_type) && y_formula === "binary") {
    warnings.push(
      `${model_type.toUpperCase()} + binary: SAR/SEM/SDM wymaga continuous Y (nie binary)`,
    );
  }

  // probit/logit = not implemented
  if (["probit", "logit"].includes(model_type)) {
    warnings.push(
      `${model_type.toUpperCase()}: Nie zaimplementowane w R (wybierz inny model)`,
    );
  }

  // k_range validation
  if (form.k_range_min >= form.k_range_max) {
    warnings.push("k min musi być mniejsze od k max");
  }

  // minimum 1 predictor
  if (!form.active_predictors || form.active_predictors.length === 0) {
    warnings.push("Wybierz co najmniej jeden predyktor");
  }

  return warnings;
}

const API = "/api/research";

// CONFIG FORM CHOICES (mirrors models_research.py enums)

const GEOMETRY_CHOICES = [
  {
    value: "voronoi",
    label: "Voronoi tessellation",
    desc: "Dokładność lokalizacji",
  },
  {
    value: "grid_500",
    label: "Regular grid 500m (+)",
    desc: "Stabilność, szybkość",
  },
];

const Y_FORMULA_CHOICES = [
  {
    value: "log_count",
    label: "log(obserwacje+1) (+)",
    desc: "Bezpośrednia miara dzików",
  },
  {
    value: "inv_pop",
    label: "1 / populacja",
    desc: "Gęstość zaludnienia (odwrotna!)",
  },
  { value: "log_pop", label: "log(populacja)", desc: "Normalizacja rozkładu" },
  {
    value: "count_pop",
    label: "zliczenia / populacja",
    desc: "Prosta interpretacja",
  },
  {
    value: "binary",
    label: "binary (0/1)",
    desc: "Dla probit/logit",
    notImplemented: true,
  },
];

const W_METHOD_CHOICES = [
  { value: "knn_aic", label: "KNN (auto k) (+)", desc: "Stabilny, bez NAs" },
  {
    value: "contiguity",
    label: "Queen contiguity",
    desc: "Może mieć NAs dla grid",
  },
  {
    value: "tessw",
    label: "tessW (spatialWarsaw)",
    desc: "Wrażliwy na geometrię",
  },
];

const MODEL_TYPE_CHOICES = [
  {
    value: "auto",
    label: "Automatyczny (+)",
    desc: "Wybiera najlepszy model po AIC",
  },
  {
    value: "sar",
    label: "SAR (Spatial Lag)",
    desc: "Autoregresja przestrzenna",
  },
  { value: "sem", label: "SEM (Spatial Error)", desc: "Błędy przestrzenne" },
  {
    value: "sdm",
    label: "SDM (Spatial Durbin)",
    desc: "SAR + lag predyktorów",
  },
  {
    value: "probit",
    label: "Spatial Probit",
    desc: "Nie zaimplementowane",
    notImplemented: true,
  },
  {
    value: "logit",
    label: "Spatial Logit",
    desc: "Nie zaimplementowane",
    notImplemented: true,
  },
];

const POPULATION_CHOICES = [
  { value: "spatial_join", label: "Spatial join (GUS)", desc: "Dla grid_500" },
  { value: "points", label: "Point-in-polygon", desc: "Dla voronoi" },
  {
    value: "centroid",
    label: "Centroid lookup",
    desc: "Szybki, mniej dokładny",
  },
];

// Merged: regime_type includes 'none' option (no separate checkbox)
const REGIME_TYPE_CHOICES = [
  { value: "none", label: "Wyłączony", desc: "Jeden model globalny" },
  {
    value: "trinary",
    label: "Trinary (las/miasto/mixed) (+) - Regime switching",
    desc: "Każdy typ terenu ma własne współczynniki - oddzielne estymacje wg 3 oddzielnych modeli",
  },
];

// HELPERS

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

// SECTION: Status Overview

function StatusSection({ status, onRefresh, researchGeometry }) {
  if (!status)
    return <div className="text-gray-500 text-sm">Ładowanie statusu...</div>;

  const geometryLabel =
    researchGeometry === "voronoi" ? "Centroidy voronoi" : "Grid 500x500m";

  // Computed config = last successful run's config
  const lastSuccessRun =
    status.last_run?.status === "success" ? status.last_run : null;
  const computedConfigId = lastSuccessRun?.config_id;
  const computedConfigName = lastSuccessRun?.config_name;

  // Selected config = currently marked as is_active
  const selectedConfigId = status.active_config?.id;
  const selectedConfigName = status.active_config?.name;

  // Check if recalculation is needed
  const needsRecalculation =
    selectedConfigId &&
    computedConfigId &&
    selectedConfigId !== computedConfigId;
  const noComputedYet = selectedConfigId && !computedConfigId;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-gray-800 rounded-lg p-3 col-span-2">
          <div className="text-xs text-gray-500 mb-1">
            Aktywna konfiguracja (przeliczona)
          </div>
          <div className="text-sm font-medium text-white truncate">
            {computedConfigName ? (
              computedConfigName
            ) : (
              <span className="text-gray-500">Brak - uruchom pipeline</span>
            )}
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">Obecny tryb mapy</div>
          <div className="text-sm font-medium text-white truncate">
            {geometryLabel}
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">Ostatni run</div>
          <div className="text-sm font-medium text-white">
            {status.last_run ? (
              <span className="flex items-center gap-1.5">
                <StatusBadge status={status.last_run.status} />
                <span className="text-gray-400 text-xs">
                  {formatDate(status.last_run.started_at)}
                </span>
              </span>
            ) : (
              <span className="text-gray-500">-</span>
            )}
          </div>
        </div>
      </div>

      {/* Warning: recalculation needed */}
      {(needsRecalculation || noComputedYet) && (
        <div className="bg-amber-900/20 border border-amber-700/40 rounded-lg p-3 flex items-start gap-3">
          <span className="text-amber-400 text-lg">⚠️</span>
          <div className="flex-1">
            <div className="text-sm text-amber-300 font-medium">
              Wybrana konfiguracja:{" "}
              <span className="text-white">{selectedConfigName}</span>
            </div>
            <div className="text-xs text-amber-400/80 mt-1">
              Uruchom pipeline, żeby przeliczyć nowy tryb
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// SECTION: Config Form

const EMPTY_CONFIG = {
  name: "",
  geometry_type: "grid_500", // (+) recommended
  population_method: "spatial_join",
  y_formula: "log_count", // (+) NEW: direct boar presence measure
  w_method: "knn_aic", // (+) stable
  k_range_min: 2,
  k_range_max: 30, // (+) optimal range
  model_type: "auto", // (+) AIC selection
  active_predictors: [],
  run_moran: true,
  run_lm_tests: true,
  run_lisa: false,
  run_eta: true,
  vif_threshold: 5.0,
  alpha: 0.05,
  seed: 42,
  // Regime model - enabled by default (+)
  use_regime_model: true,
  regime_type: "trinary", // (+) improves AIC by ~6
  regime_threshold: 0.3, // (+) forest threshold
  regime_threshold_urban: 0.15, // (+) urban threshold
};

function SelectField({
  label,
  value,
  onChange,
  options,
  disabledValues = [],
  disabledReasons = {},
  warning,
  showDesc = false,
}) {
  // Find selected option to show its description
  const selectedOption = options.find((o) => o.value === value);

  return (
    <label className="block">
      <span className="text-xs text-gray-400">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`mt-1 block w-full bg-gray-700 border rounded px-2 py-1.5 text-sm text-white focus:outline-none ${
          warning
            ? "border-amber-500/50 focus:border-amber-500"
            : "border-gray-600 focus:border-blue-500"
        }`}
      >
        {options.map((o) => {
          const isDisabled =
            disabledValues.includes(o.value) || o.notImplemented;
          const reason =
            disabledReasons[o.value] || (o.notImplemented ? "N/A" : null);
          return (
            <option key={o.value} value={o.value} disabled={isDisabled}>
              {o.label}
              {isDisabled && reason ? ` - ${reason}` : ""}
            </option>
          );
        })}
      </select>
      {/* Show description below select for selected option */}
      {selectedOption?.desc && !warning && (
        <span className="text-xs text-gray-500 mt-0.5 block">
          {selectedOption.desc}
        </span>
      )}
      {warning && (
        <span className="text-xs text-amber-400 mt-0.5 block">{warning}</span>
      )}
    </label>
  );
}

function NumberField({ label, value, onChange, min, max, step, hint }) {
  return (
    <label className="block">
      <span className="text-xs text-gray-400">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step || 1}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 block w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none"
      />
      {hint && (
        <span className="text-xs text-slate-500 mt-0.5 block">{hint}</span>
      )}
    </label>
  );
}

function ConfigForm({ config, availablePredictors, onSave, onCancel, saving }) {
  const [form, setForm] = useState(config || { ...EMPTY_CONFIG });
  const [error, setError] = useState(null);
  const [selectedPreset, setSelectedPreset] = useState("");
  const [presetModified, setPresetModified] = useState(false);
  const isEdit = !!config?.id;

  const set = (field) => (val) => {
    setForm((f) => ({ ...f, [field]: val }));
    // Mark as modified if a preset was selected
    if (selectedPreset) {
      setPresetModified(true);
    }
  };

  // Handle preset selection
  const handlePresetChange = (e) => {
    const presetId = e.target.value;
    setSelectedPreset(presetId);
    setPresetModified(false);

    if (!presetId) return;

    const preset = RESEARCH_PRESETS[presetId];
    if (!preset) return;

    // Apply preset config while preserving name
    setForm((prev) => ({
      ...prev,
      ...preset.config,
      name: prev.name || "", // Keep existing name
    }));
  };

  // Get presets grouped for dropdown
  const presetsByGroup = useMemo(() => getPresetsByGroup(), []);

  // Validation warnings (computed on every form change)
  const warnings = useMemo(() => getValidationWarnings(form), [form]);
  const hasWarnings = warnings.length > 0;

  // Compute which Y formula options are invalid for current geometry
  const disabledYFormulas = useMemo(() => {
    const disabled = ["binary"]; // Always disabled - no probit/logit implemented
    if (form.geometry_type === "voronoi") {
      disabled.push("log_count"); // Voronoi 1:1 → log(1+1)=0.693 always
      // count_pop OK: Y = 1/population ma wariancję (population różna per komórka)
    }
    return disabled;
  }, [form.geometry_type]);

  // Reasons for disabled Y formulas
  const disabledYReasons = useMemo(() => {
    const reasons = {
      binary: "brak probit/logit",
    };
    if (form.geometry_type === "voronoi") {
      reasons.log_count = "Voronoi 1:1";
    }
    return reasons;
  }, [form.geometry_type]);

  // Compute which model types are invalid for current Y formula
  const disabledModelTypes = useMemo(() => {
    if (form.y_formula === "binary") {
      return ["sar", "sem", "sdm"];
    }
    return [];
  }, [form.y_formula]);

  // Reasons for disabled model types
  const disabledModelReasons = useMemo(() => {
    const reasons = {
      probit: "nie zaimplementowane",
      logit: "nie zaimplementowane",
    };
    if (form.y_formula === "binary") {
      reasons.sar = "wymaga continuous Y";
      reasons.sem = "wymaga continuous Y";
      reasons.sdm = "wymaga continuous Y";
    }
    return reasons;
  }, [form.y_formula]);

  // Compute which W methods may cause problems for current geometry
  const disabledWMethods = useMemo(() => {
    // contiguity/tessw can have NAs for grid_500 (floating point precision)
    // but we don't disable - just warn
    return [];
  }, [form.geometry_type]);

  // Dynamic W method descriptions based on geometry
  const wMethodChoices = useMemo(() => {
    const base = W_METHOD_CHOICES.map((c) => ({ ...c }));
    if (form.geometry_type === "grid_500") {
      // Add warning for contiguity/tessw with grid
      const contiguity = base.find((c) => c.value === "contiguity");
      const tessw = base.find((c) => c.value === "tessw");
      if (contiguity) contiguity.desc = "1 wyspa w grid_500 (NAs)";
      if (tessw) tessw.desc = "1 wyspa + krótkie granice";
    }
    return base;
  }, [form.geometry_type]);

  // Dynamic population method based on geometry
  const populationChoices = useMemo(() => {
    return POPULATION_CHOICES.map((c) => {
      const copy = { ...c };
      if (form.geometry_type === "voronoi") {
        if (c.value === "spatial_join") copy.desc = "Wolniejszy dla Voronoi";
        if (c.value === "points") copy.desc = "Optymalny dla Voronoi (+)";
      } else {
        if (c.value === "spatial_join") copy.desc = "Optymalny dla grid (+)";
        if (c.value === "points") copy.desc = "Dla Voronoi";
      }
      return copy;
    });
  }, [form.geometry_type]);

  const togglePredictor = (name) => {
    setForm((f) => {
      const current = f.active_predictors || [];
      return {
        ...f,
        active_predictors: current.includes(name)
          ? current.filter((p) => p !== name)
          : [...current, name],
      };
    });
  };

  const handleSubmit = async () => {
    setError(null);
    try {
      await onSave(form, isEdit);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">
          {isEdit ? `Edycja: ${form.name}` : "Nowa konfiguracja"}
        </h3>
        <button
          onClick={onCancel}
          className="text-gray-400 hover:text-white text-sm"
        >
          Anuluj
        </button>
      </div>

      {/* Preset selector - only for new configs */}
      {!isEdit && (
        <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-3">
          <label className="block">
            <span className="text-xs text-gray-400 flex items-center gap-2">
              Preset
              {selectedPreset && presetModified && (
                <span className="text-amber-400 text-[10px]">
                  (zmodyfikowany)
                </span>
              )}
            </span>
            <select
              value={selectedPreset}
              onChange={handlePresetChange}
              className="mt-1 block w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none"
            >
              <option value="">-- Wybierz preset --</option>
              {PRESET_GROUPS.map((group) => (
                <optgroup key={group.id} label={group.label}>
                  {(presetsByGroup[group.id] || []).map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.recommended ? "★ " : ""}
                      {preset.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
          {selectedPreset && RESEARCH_PRESETS[selectedPreset] && (
            <p className="text-xs text-gray-500 mt-1.5">
              {RESEARCH_PRESETS[selectedPreset].description}
            </p>
          )}
        </div>
      )}

      {/* Name */}
      {!isEdit && (
        <label className="block">
          <span className="text-xs text-gray-400">Nazwa</span>
          <input
            type="text"
            value={form.name}
            onChange={(e) => set("name")(e.target.value)}
            placeholder="np. test_voronoi_v1"
            className="mt-1 block w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none"
          />
          <span className="text-xs text-slate-500 mt-0.5 block">
            {PARAM_HINTS.name}
          </span>
        </label>
      )}

      {/* Main dropdowns - 2 column grid */}
      <div className="grid grid-cols-2 gap-3">
        <SelectField
          label="Geometria"
          value={form.geometry_type}
          onChange={set("geometry_type")}
          options={GEOMETRY_CHOICES}
        />
        <SelectField
          label="Populacja"
          value={form.population_method}
          onChange={set("population_method")}
          options={populationChoices}
        />
        <SelectField
          label="Zmienna Y"
          value={form.y_formula}
          onChange={set("y_formula")}
          options={Y_FORMULA_CHOICES}
          disabledValues={disabledYFormulas}
          disabledReasons={disabledYReasons}
          warning={
            disabledYFormulas.includes(form.y_formula)
              ? "Nieprawidłowe dla Voronoi"
              : null
          }
        />
        <SelectField
          label="Model"
          value={form.model_type}
          onChange={set("model_type")}
          options={MODEL_TYPE_CHOICES}
          disabledValues={disabledModelTypes}
          disabledReasons={disabledModelReasons}
          warning={
            disabledModelTypes.includes(form.model_type)
              ? "Wymaga continuous Y"
              : ["probit", "logit"].includes(form.model_type)
                ? "Nie zaimplementowane"
                : null
          }
        />
        <SelectField
          label="Macierz W"
          value={form.w_method}
          onChange={set("w_method")}
          options={wMethodChoices}
          warning={
            form.geometry_type === "grid_500" &&
            ["contiguity", "tessw"].includes(form.w_method)
              ? "Może mieć NAs dla grid_500"
              : null
          }
        />
        <NumberField
          label="Seed"
          value={form.seed}
          onChange={set("seed")}
          min={1}
          hint={PARAM_HINTS.seed}
        />
      </div>

      {/* K range */}
      <div className="grid grid-cols-2 gap-3">
        <NumberField
          label="k_range_min"
          value={form.k_range_min}
          onChange={set("k_range_min")}
          min={1}
          max={100}
          hint={PARAM_HINTS.k_range_min}
        />
        <NumberField
          label="k_range_max"
          value={form.k_range_max}
          onChange={set("k_range_max")}
          min={2}
          max={200}
          hint={PARAM_HINTS.k_range_max}
        />
      </div>

      {/* Thresholds */}
      <div className="grid grid-cols-2 gap-3">
        <NumberField
          label="VIF threshold"
          value={form.vif_threshold}
          onChange={set("vif_threshold")}
          min={1}
          max={100}
          step={0.5}
          hint={PARAM_HINTS.vif_threshold}
        />
        <NumberField
          label="Alpha (α)"
          value={form.alpha}
          onChange={set("alpha")}
          min={0.001}
          max={0.5}
          step={0.01}
          hint={PARAM_HINTS.alpha}
        />
      </div>

      {/* OSM predictors */}
      <div>
        <span className="text-xs text-gray-400 block mb-1">Predyktory OSM</span>
        <span className="text-xs text-slate-500 block mb-2">
          {PARAM_HINTS.predictors}
        </span>
        <div className="flex flex-wrap gap-1.5">
          {(availablePredictors || []).map((p) => {
            const active = (form.active_predictors || []).includes(p);
            return (
              <button
                key={p}
                onClick={() => togglePredictor(p)}
                className={`px-2 py-1 rounded text-xs transition-colors ${
                  active
                    ? "bg-blue-600/40 text-blue-300 border border-blue-500/50"
                    : "bg-gray-700 text-gray-400 border border-gray-600 hover:text-white"
                }`}
              >
                {p}
              </button>
            );
          })}
        </div>
      </div>

      {/* Diagnostics toggles */}
      <div>
        <span className="text-xs text-gray-400 block mb-1">Diagnostyka</span>
        <span className="text-xs text-slate-500 block mb-2">
          Testy statystyczne wykonywane po estymacji modelu.
        </span>
        <div className="grid grid-cols-2 gap-2">
          {[
            {
              key: "run_moran",
              label: "Moran's I",
              desc: PARAM_HINTS.run_moran,
              implemented: true,
            },
            {
              key: "run_lm_tests",
              label: "Testy LM",
              desc: PARAM_HINTS.run_lm_tests,
              implemented: true,
            },
            {
              key: "run_lisa",
              label: "LISA",
              desc: PARAM_HINTS.run_lisa,
              implemented: false,
            },
            {
              key: "run_eta",
              label: "ETA",
              desc: PARAM_HINTS.run_eta,
              implemented: true,
              voronoiOnly: true,
            },
          ].map(({ key, label, desc, implemented, voronoiOnly }) => {
            const isVoronoi = form.geometry_type === "voronoi";
            const isDisabled = !implemented || (voronoiOnly && !isVoronoi);
            const disabledReason = !implemented
              ? "(N/A)"
              : voronoiOnly && !isVoronoi
                ? "(tylko Voronoi)"
                : null;

            return (
              <label
                key={key}
                className={`flex flex-col p-2 rounded border ${
                  !isDisabled
                    ? "border-gray-600 bg-gray-800/50 cursor-pointer hover:border-gray-500"
                    : "border-gray-700 bg-gray-900/30 cursor-not-allowed opacity-60"
                }`}
              >
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={form[key]}
                    onChange={() => !isDisabled && set(key)(!form[key])}
                    disabled={isDisabled}
                    className={`rounded bg-gray-700 border-gray-600 focus:ring-0 ${
                      !isDisabled
                        ? "text-blue-500"
                        : "text-gray-600 cursor-not-allowed"
                    }`}
                  />
                  <span
                    className={`text-xs font-medium ${!isDisabled ? "text-gray-200" : "text-gray-500"}`}
                  >
                    {label}
                    {disabledReason && (
                      <span className="text-gray-600 ml-1">
                        {disabledReason}
                      </span>
                    )}
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 mt-1 ml-5">
                  {desc}
                </span>
              </label>
            );
          })}
        </div>
      </div>

      {/* Regime model - merged: regime_type controls use_regime_model */}
      <div>
        <span className="text-xs text-gray-400 block mb-2">Model rezimowy</span>
        <div className="mb-3">
          <SelectField
            label="Rezim przestrzenny"
            value={form.regime_type}
            onChange={(val) => {
              set("regime_type")(val);
              // Auto-sync use_regime_model based on regime_type
              set("use_regime_model")(val !== "none");
            }}
            options={REGIME_TYPE_CHOICES}
          />
        </div>

        {/* Interactive threshold sliders with histograms */}
        {form.regime_type !== "none" && (
          <RegimeThresholdControl
            forestThreshold={form.regime_threshold}
            urbanThreshold={form.regime_threshold_urban}
            onForestChange={set("regime_threshold")}
            onUrbanChange={set("regime_threshold_urban")}
            geometryType={form.geometry_type}
            disabled={form.regime_type === "none"}
          />
        )}
      </div>

      {/* Validation warnings */}
      {hasWarnings && (
        <div className="text-amber-400 text-xs bg-amber-900/20 border border-amber-700/30 rounded p-2 space-y-1">
          <div className="font-medium">Nieprawidłowa kombinacja:</div>
          {warnings.map((w, i) => (
            <div key={i} className="pl-2">
              - {w}
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="text-red-400 text-xs bg-red-900/20 rounded p-2">
          {error}
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={saving || hasWarnings}
        className={`w-full py-2 rounded text-white text-sm font-medium transition-colors ${
          hasWarnings
            ? "bg-gray-600 cursor-not-allowed"
            : "bg-blue-600 hover:bg-blue-500 disabled:opacity-50"
        }`}
        title={hasWarnings ? "Napraw ostrzeżenia przed zapisaniem" : undefined}
      >
        {saving
          ? "Zapisywanie..."
          : hasWarnings
            ? "Napraw ostrzeżenia"
            : isEdit
              ? "Zapisz zmiany"
              : "Utwórz konfigurację"}
      </button>
    </div>
  );
}

// SECTION: Config List

function ConfigList({
  configs,
  activeConfigId,
  onActivate,
  onEdit,
  activating,
}) {
  if (!configs || configs.length === 0) {
    return (
      <div className="text-gray-500 text-sm">
        Brak konfiguracji. Utwórz pierwszą.
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {configs.map((c) => (
        <div
          key={c.id}
          className={`flex items-center gap-2 p-2.5 rounded-lg border transition-colors ${
            c.is_active
              ? "bg-green-900/20 border-green-700/50"
              : "bg-gray-800/50 border-gray-700/50 hover:bg-gray-800"
          }`}
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-white truncate">
                {c.name}
              </span>
              {c.is_active && (
                <span className="text-xs bg-green-600/30 text-green-400 px-1.5 py-0.5 rounded">
                  aktywna
                </span>
              )}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">
              {c.geometry_type} / {c.y_formula} / {c.model_type}
            </div>
          </div>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <button
              onClick={() => onEdit(c)}
              className="px-2 py-1 text-xs text-gray-400 hover:text-white bg-gray-700 rounded transition-colors"
            >
              Edytuj
            </button>
            {!c.is_active && (
              <button
                onClick={() => onActivate(c.id)}
                disabled={activating}
                className="px-2 py-1 text-xs text-green-400 hover:text-green-300 bg-green-900/30 rounded disabled:opacity-50 transition-colors"
              >
                Aktywuj
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// SECTION: Run Button + Progress

function RunSection({
  hasActiveConfig,
  onRun,
  runResult,
  isRunning,
  wsProgress,
  currentRunId,
}) {
  return (
    <div className="space-y-3">
      <button
        onClick={onRun}
        disabled={!hasActiveConfig || isRunning}
        className={`w-full py-3 rounded-lg font-medium text-sm transition-colors ${
          isRunning
            ? "bg-blue-800 text-blue-300 cursor-wait"
            : hasActiveConfig
              ? "bg-emerald-600 hover:bg-emerald-500 text-white"
              : "bg-gray-700 text-gray-500 cursor-not-allowed"
        }`}
      >
        {isRunning ? (
          <span className="flex items-center justify-center gap-2">
            <span className="animate-spin inline-block w-4 h-4 border-2 border-blue-300 border-t-transparent rounded-full" />
            Pipeline uruchomiony...
          </span>
        ) : hasActiveConfig ? (
          "Uruchom pipeline"
        ) : (
          "Brak aktywnej konfiguracji"
        )}
      </button>

      {/* Live WebSocket progress */}
      {isRunning && currentRunId && <LiveStepsProgress progress={wsProgress} />}

      {/* Step results (after completion) */}
      {!isRunning && runResult && runResult.status !== "running" && (
        <RunStepsList run={runResult} />
      )}
    </div>
  );
}

// MAIN: PipelineTab

export default function PipelineTab() {
  // --- store ---
  const { setDisplayMode, setResearchGeometry, researchGeometry } =
    useSightingsStore();

  // --- data state ---
  const [status, setStatus] = useState(null);
  const [configs, setConfigs] = useState([]);
  const [availablePredictors, setAvailablePredictors] = useState([]);
  const [runs, setRuns] = useState([]);

  // --- UI state ---
  const [showForm, setShowForm] = useState(false);
  const [editingConfig, setEditingConfig] = useState(null);
  const [saving, setSaving] = useState(false);
  const [activating, setActivating] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [selectedRunDetail, setSelectedRunDetail] = useState(null);
  const [currentRunId, setCurrentRunId] = useState(null);

  // --- WebSocket progress hook ---
  const wsProgress = usePipelineProgress(currentRunId);

  // --- Fetch all data ---
  const refresh = useCallback(async () => {
    try {
      const [statusData, configData, runData] = await Promise.all([
        apiFetch("/status/"),
        apiFetch("/configs/"),
        apiFetch("/runs/"),
      ]);
      setStatus(statusData);
      setConfigs(configData.configs || []);
      setAvailablePredictors(configData.available_predictors || []);
      setRuns(runData.runs || []);
      // Update researchGeometry based on LAST SUCCESSFUL RUN (not selected config)
      // This ensures map shows computed results, not pending selection
      const lastSuccess =
        statusData?.last_run?.status === "success" ? statusData.last_run : null;
      if (lastSuccess) {
        // Find config geometry from the successful run
        const successConfig = (configData.configs || []).find(
          (c) => c.id === lastSuccess.config_id,
        );
        if (successConfig?.geometry_type) {
          setResearchGeometry(successConfig.geometry_type);
        }
      }
    } catch (e) {
      console.error("PipelineTab refresh error:", e);
    }
  }, [setResearchGeometry]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // --- Config CRUD ---
  const handleSaveConfig = async (form, isEdit) => {
    setSaving(true);
    try {
      if (isEdit) {
        await apiFetch(`/configs/${form.id}/`, {
          method: "PUT",
          body: JSON.stringify(form),
        });
      } else {
        await apiFetch("/configs/", {
          method: "POST",
          body: JSON.stringify(form),
        });
      }
      setShowForm(false);
      setEditingConfig(null);
      await refresh();
    } finally {
      setSaving(false);
    }
  };

  // --- Activation error state ---
  const [activateError, setActivateError] = useState(null);

  const handleActivate = async (configId) => {
    setActivating(true);
    setActivateError(null);
    try {
      await apiFetch(`/configs/${configId}/activate/`, { method: "POST" });
      // NOTE: Don't change researchGeometry here - it should only change after pipeline runs
      await refresh();
    } catch (e) {
      console.error("Activate error:", e);
      setActivateError(e.message);
    } finally {
      setActivating(false);
    }
  };

  const handleEdit = (config) => {
    setEditingConfig(config);
    setShowForm(true);
  };

  // --- Run pipeline (ASYNC with polling) ---
  const handleRun = async () => {
    setIsRunning(true);
    setRunResult(null);
    setCurrentRunId(null); // Reset WebSocket connection
    try {
      const data = await apiFetch("/run/", { method: "POST" });
      console.log("[Pipeline] Started:", data);

      // NEW: Handle async response (status: 'pending')
      if (data.status === "pending") {
        // Set run_id to connect WebSocket for live progress
        if (data.run_id) {
          setCurrentRunId(data.run_id);
          console.log(
            "[Pipeline] WebSocket connecting to run_id:",
            data.run_id,
          );
        }

        setRunResult({
          status: "running",
          message: "Pipeline uruchomiony...",
          task_id: data.task_id,
          run_id: data.run_id,
        });

        // Poll for completion (fallback if WebSocket doesn't work)
        const pollInterval = setInterval(async () => {
          try {
            const statusData = await apiFetch("/status/");
            const lastRun = statusData.last_run;
            console.log("[Polling] Status:", lastRun?.status);

            if (lastRun?.status === "success") {
              clearInterval(pollInterval);
              setIsRunning(false);
              setCurrentRunId(null); // Close WebSocket
              setRunResult({ status: "success", ...lastRun });
              await refresh(); // This sets researchGeometry based on successful run

              // Switch to RESEARCH mode and refresh map
              setDisplayMode("research");
              // NOTE: researchGeometry already set by refresh() based on last successful run
              setTimeout(
                () => window.dispatchEvent(new CustomEvent("voronoi-refresh")),
                600,
              );
            } else if (
              lastRun?.status === "error" ||
              lastRun?.status === "failed"
            ) {
              clearInterval(pollInterval);
              setIsRunning(false);
              setCurrentRunId(null); // Close WebSocket
              setRunResult({
                status: "failed",
                error_message: lastRun?.error_message || "Pipeline failed",
                steps: [],
              });
            } else {
              // Still running - update progress message (WebSocket provides live updates)
              setRunResult((prev) => ({
                ...prev,
                message: `Pipeline w toku... (${lastRun?.status || "running"})`,
              }));
            }
          } catch (pollErr) {
            console.error("[Polling] Error:", pollErr);
          }
        }, 3000); // Poll every 3 seconds

        // Timeout after 10 minutes
        setTimeout(() => {
          clearInterval(pollInterval);
          if (isRunning) {
            setIsRunning(false);
            setCurrentRunId(null);
            setRunResult({
              status: "failed",
              error_message: "Pipeline timeout (10 min)",
              steps: [],
            });
          }
        }, 600000);
      } else {
        // Legacy: synchronous response (shouldn't happen anymore)
        setRunResult(data);
        await refresh();
        if (data.status === "success") {
          setDisplayMode("research");
          setTimeout(
            () => window.dispatchEvent(new CustomEvent("voronoi-refresh")),
            600,
          );
        }
        setIsRunning(false);
      }
    } catch (e) {
      setRunResult({ status: "failed", error_message: e.message, steps: [] });
      setIsRunning(false);
      setCurrentRunId(null);
    }
  };

  // --- Run detail ---
  const handleSelectRun = async (runId) => {
    // Toggle: if same run clicked, close it
    if (runId === null || runId === selectedRunId) {
      setSelectedRunId(null);
      setSelectedRunDetail(null);
      return;
    }

    setSelectedRunId(runId);
    try {
      const [detail, stepsData, diagData] = await Promise.all([
        apiFetch(`/runs/${runId}/`),
        apiFetch(`/runs/${runId}/steps/`),
        apiFetch(`/runs/${runId}/diagnostics/`).catch(() => ({
          diagnostics: null,
        })),
      ]);
      setSelectedRunDetail({
        ...detail,
        steps: stepsData.steps || [],
        diagnostics: diagData.diagnostics || null,
      });
    } catch (e) {
      console.error("Run detail error:", e);
      setSelectedRunDetail(null);
    }
  };

  // --- Clear history ---
  const handleClearHistory = async () => {
    if (
      !window.confirm("Czy na pewno chcesz wyczyścić całą historię uruchomień?")
    ) {
      return;
    }
    try {
      await apiFetch("/runs/clear/", { method: "DELETE" });
      setRuns([]);
      setSelectedRunId(null);
      setSelectedRunDetail(null);
      setRunResult(null);
    } catch (e) {
      console.error("Clear history error:", e);
    }
  };

  // --- active config id ---
  const activeConfigId = status?.active_config?.id;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* ── STATUS ── */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">
            Status
          </h2>
          <button
            onClick={refresh}
            className="text-xs text-gray-500 hover:text-white transition-colors"
          >
            Odśwież
          </button>
        </div>
        <StatusSection
          status={status}
          onRefresh={refresh}
          researchGeometry={researchGeometry}
        />
      </section>

      {/* ── RUN PIPELINE ── */}
      <section>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">
          Uruchomienie
        </h2>
        <RunSection
          hasActiveConfig={!!activeConfigId}
          onRun={handleRun}
          runResult={runResult}
          isRunning={isRunning}
          wsProgress={wsProgress}
          currentRunId={currentRunId}
        />
      </section>

      {/* ── CONFIGS ── */}
      <section>
        {activateError && (
          <div className="mb-3 text-xs text-red-400 bg-red-900/20 border border-red-700/30 rounded p-2">
            Błąd aktywacji: {activateError}
          </div>
        )}
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">
            Konfiguracje
          </h2>
          {!showForm && (
            <button
              onClick={() => {
                setEditingConfig(null);
                setShowForm(true);
              }}
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              + Nowa
            </button>
          )}
        </div>

        <AnimatePresence mode="wait">
          {showForm ? (
            <motion.div
              key="form"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.15 }}
            >
              <ConfigForm
                config={editingConfig}
                availablePredictors={availablePredictors}
                onSave={handleSaveConfig}
                onCancel={() => {
                  setShowForm(false);
                  setEditingConfig(null);
                }}
                saving={saving}
              />
            </motion.div>
          ) : (
            <motion.div
              key="list"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.1 }}
            >
              <ConfigList
                configs={configs}
                activeConfigId={activeConfigId}
                onActivate={handleActivate}
                onEdit={handleEdit}
                activating={activating}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      {/* ── HISTORY ── */}
      {runs.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">
              Historia ({runs.length})
            </h2>
            <button
              onClick={handleClearHistory}
              className="text-xs text-red-400 hover:text-red-300 transition-colors"
            >
              Wyczyść
            </button>
          </div>
          <RunHistory
            runs={runs}
            onSelectRun={handleSelectRun}
            selectedRunId={selectedRunId}
            selectedRunDetail={selectedRunDetail}
          />
        </section>
      )}
    </div>
  );
}
