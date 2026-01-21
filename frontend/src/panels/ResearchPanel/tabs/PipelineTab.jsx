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
  qaId,
}) {
  // Find selected option to show its description
  const selectedOption = options.find((o) => o.value === value);

  return (
    <label className="block">
      <span className="text-xs text-gray-400">{label}</span>
      <select
        data-qa={qaId}
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

function NumberField({ label, value, onChange, min, max, step, hint, qaId }) {
  return (
    <label className="block">
      <span className="text-xs text-gray-400">{label}</span>
      <input
        data-qa={qaId}
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
          data-qa="config.cancel"
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
              data-qa="config.preset-select"
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
            data-qa="config.name-input"
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
          qaId="config.geometry-select"
        />
        <SelectField
          label="Populacja"
          value={form.population_method}
          onChange={set("population_method")}
          options={populationChoices}
          qaId="config.population-select"
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
          qaId="config.y-formula-select"
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
          qaId="config.model-select"
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
          qaId="config.w-method-select"
        />
        <NumberField
          label="Seed"
          value={form.seed}
          onChange={set("seed")}
          min={1}
          hint={PARAM_HINTS.seed}
          qaId="config.seed-input"
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
          qaId="config.k-min-input"
        />
        <NumberField
          label="k_range_max"
          value={form.k_range_max}
          onChange={set("k_range_max")}
          min={2}
          max={200}
          hint={PARAM_HINTS.k_range_max}
          qaId="config.k-max-input"
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
          qaId="config.vif-input"
        />
        <NumberField
          label="Alpha (α)"
          value={form.alpha}
          onChange={set("alpha")}
          min={0.001}
          max={0.5}
          step={0.01}
          hint={PARAM_HINTS.alpha}
          qaId="config.alpha-input"
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
