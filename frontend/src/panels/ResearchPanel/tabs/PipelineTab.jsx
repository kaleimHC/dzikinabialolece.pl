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
