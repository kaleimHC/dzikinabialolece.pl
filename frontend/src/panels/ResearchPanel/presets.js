/**
 * Research Mode Presets
 *
 * Pre-defined configurations for common analysis scenarios.
 * Names include category in parentheses for clarity.
 */

export const RESEARCH_PRESETS = {
  // ─────────────────────────────────────────────────────────────
  // GRUPA A: PODSTAWOWE
  // ─────────────────────────────────────────────────────────────
  "RES-01": {
    name: "Mapa Ryzyka (Podstawowe)",
    group: "Podstawowe",
    description:
      "System sam wybiera lepszy model (SAR lub SEM) na podstawie AIC. Używa 6 głównych zmiennych środowiskowych i dzieli obszar na strefy (las/miasto). Zalecany punkt wyjścia.",
    recommended: true,
    config: {
      geometry_type: "grid_500",
      population_method: "spatial_join",
      y_formula: "log_count",
      model_type: "auto",
      w_method: "knn_aic",
      k_range_min: 2,
      k_range_max: 30,
      use_regime_model: true,
      regime_type: "trinary",
      regime_threshold_urban: 0.15,
      regime_threshold: 0.3,
      active_predictors: [
        "forests",
        "buildings",
        "roads",
        "water",
        "barriers",
        "scrub",
      ],
      vif_threshold: 5.0,
      alpha: 0.05,
      run_moran: true,
      run_lm_tests: true,
      run_lisa: false,
      run_eta: true,
      seed: 42,
    },
  },
  "RES-02": {
    name: "Model SAR (Podstawowe)",
    group: "Podstawowe",
    description:
      'Zakłada że ryzyko "rozlewa się" z hotspotów na sąsiednie komórki. Wartość Y w komórce zależy od Y sąsiadów. Dobre gdy dziki migrują między obszarami.',
    config: {
      geometry_type: "grid_500",
      population_method: "spatial_join",
      y_formula: "log_count",
      model_type: "sar",
      w_method: "knn_aic",
      k_range_min: 2,
      k_range_max: 30,
      use_regime_model: true,
      regime_type: "trinary",
      regime_threshold_urban: 0.15,
      regime_threshold: 0.3,
      active_predictors: ["forests", "buildings", "roads", "water"],
      vif_threshold: 5.0,
      alpha: 0.05,
      run_moran: true,
      run_lm_tests: true,
      run_lisa: false,
      run_eta: true,
      seed: 42,
    },
  },
  "RES-03": {
    name: "Model SEM (Podstawowe)",
    group: "Podstawowe",
    description:
      "Zakłada że podobne środowisko = podobne ryzyko, ale komórki nie wpływają na siebie bezpośrednio. Autokorelacja jest w błędach modelu. Dobre gdy to środowisko determinuje obecność dzików.",
    config: {
      geometry_type: "grid_500",
      population_method: "spatial_join",
      y_formula: "log_count",
      model_type: "sem",
      w_method: "knn_aic",
      k_range_min: 2,
      k_range_max: 30,
      use_regime_model: true,
      regime_type: "trinary",
      regime_threshold_urban: 0.15,
      regime_threshold: 0.3,
      active_predictors: ["forests", "buildings", "roads", "water"],
      vif_threshold: 5.0,
      alpha: 0.05,
      run_moran: true,
      run_lm_tests: true,
      run_lisa: false,
      run_eta: true,
      seed: 42,
    },
  },
  "RES-06": {
    name: "Model Durbina SDM (Podstawowe)",
    group: "Podstawowe",
    description:
      "SAR rozszerzony o opóźnione predyktory (WX). Sprawdza czy środowisko SĄSIADÓW też wpływa na ryzyko w danej komórce. Trudniejsza interpretacja, mniej predyktorów bo SDM podwaja liczbę parametrów.",
    config: {
      geometry_type: "grid_500",
      population_method: "spatial_join",
      y_formula: "log_count",
      model_type: "sdm",
      w_method: "knn_aic",
      k_range_min: 2,
      k_range_max: 30,
      use_regime_model: false,
      regime_type: "none",
      regime_threshold: 0.3,
      active_predictors: ["forests", "buildings", "water"],
      vif_threshold: 5.0,
      alpha: 0.05,
      run_moran: true,
      run_lm_tests: true,
      run_lisa: false,
      run_eta: true,
      seed: 42,
    },
  },

  // ─────────────────────────────────────────────────────────────
  // GRUPA B: ANALIZA ŚRODOWISKOWA
  // ─────────────────────────────────────────────────────────────
  "RES-08": {
    name: "Wpływ lasów (Środowiskowe)",
    group: "Środowiskowe",
    description:
      'Izoluje wpływ samego zalesienia. Współczynnik dodatni = las przyciąga dziki, ujemny = odpycha. Pozwala zobaczyć "czysty" efekt lasu bez wpływu innych zmiennych.',
    config: {
      geometry_type: "grid_500",
      population_method: "spatial_join",
      y_formula: "log_count",
      model_type: "sem",
      w_method: "knn_aic",
      k_range_min: 2,
      k_range_max: 30,
      use_regime_model: false,
      regime_type: "none",
      regime_threshold: 0.3,
      active_predictors: ["forests"],
      vif_threshold: 5.0,
      alpha: 0.05,
      run_moran: true,
      run_lm_tests: false,
      run_lisa: false,
      run_eta: true,
      seed: 42,
    },
  },
  "RES-10": {
    name: "Wpływ urbanizacji (Środowiskowe)",
    group: "Środowiskowe",
    description:
      "Sprawdza łączny wpływ zabudowy miejskiej: budynki, drogi, bariery. Oczekiwane ujemne współczynniki (więcej zabudowy = mniej dzików).",
    config: {
      geometry_type: "grid_500",
      population_method: "spatial_join",
      y_formula: "log_count",
      model_type: "sem",
      w_method: "knn_aic",
      k_range_min: 2,
      k_range_max: 30,
      use_regime_model: false,
      regime_type: "none",
      regime_threshold: 0.3,
      active_predictors: ["buildings", "roads", "barriers"],
      vif_threshold: 5.0,
      alpha: 0.05,
      run_moran: true,
      run_lm_tests: false,
      run_lisa: false,
      run_eta: true,
      seed: 42,
    },
  },
  "RES-12": {
    name: "Pełny model środowiskowy (Środowiskowe)",
    group: "Środowiskowe",
    description:
      "Wszystkie 11 zmiennych środowiskowych OSM. Automatyczna filtracja VIF usuwa zmienne zbyt skorelowane ze sobą. Kompleksowa analiza pokazująca które zmienne są istotne.",
    config: {
      geometry_type: "grid_500",
      population_method: "spatial_join",
      y_formula: "log_count",
      model_type: "auto",
      w_method: "knn_aic",
      k_range_min: 2,
      k_range_max: 30,
      use_regime_model: false,
      regime_type: "none",
      regime_threshold: 0.3,
      active_predictors: [
        "forests",
        "buildings",
        "roads",
        "water",
        "barriers",
        "scrub",
        "parks",
        "meadows",
        "farmland",
        "allotments",
        "railway",
      ],
      vif_threshold: 5.0,
      alpha: 0.05,
      run_moran: true,
      run_lm_tests: true,
      run_lisa: false,
      run_eta: true,
      seed: 42,
    },
  },

  // ─────────────────────────────────────────────────────────────
  // GRUPA D: KOREKTA / PERSPEKTYWY
  // ─────────────────────────────────────────────────────────────
  "RES-16": {
    name: "Pustka populacyjna (Korekta)",
    group: "Korekta",
    description:
      "Mapa terenów słabo zaludnionych - gdzie dziki MOGŁYBY mieć siedliska ze względu na brak ludzi. NIE pokazuje gdzie są dziki, tylko potencjalny habitat na podstawie braku zaludnienia.",
    config: {
      geometry_type: "grid_500",
      population_method: "spatial_join",
      y_formula: "inv_pop",
      model_type: "auto",
      w_method: "knn_aic",
      k_range_min: 2,
      k_range_max: 30,
      use_regime_model: false,
      regime_type: "none",
      regime_threshold: 0.3,
      active_predictors: ["forests", "buildings"],
      vif_threshold: 5.0,
      alpha: 0.05,
      run_moran: true,
      run_lm_tests: true,
      run_lisa: false,
      run_eta: true,
      seed: 42,
    },
  },
  "RES-17": {
    name: "Obserwacje na mieszkanca (Korekta)",
    group: "Korekta",
    description:
      "Normalizuje liczbę obserwacji przez populację. Koryguje za to że w gęsto zaludnionych miejscach więcej osób zgłasza obserwacje. Działa TYLKO z grid_500.",
    config: {
      geometry_type: "grid_500",
      population_method: "spatial_join",
      y_formula: "count_pop",
      model_type: "auto",
      w_method: "knn_aic",
      k_range_min: 2,
      k_range_max: 30,
      use_regime_model: true,
      regime_type: "trinary",
      regime_threshold_urban: 0.15,
      regime_threshold: 0.3,
      active_predictors: ["forests", "buildings", "roads", "water"],
      vif_threshold: 5.0,
      alpha: 0.05,
      run_moran: true,
      run_lm_tests: true,
      run_lisa: false,
      run_eta: true,
      seed: 42,
    },
  },

  // ─────────────────────────────────────────────────────────────
  // GRUPA E: VORONOI
  // ─────────────────────────────────────────────────────────────
  "RES-22": {
    name: "Voronoi podstawowy (Voronoi)",
    group: "Voronoi",
    description:
      "Podstawowa analiza Voronoi z automatycznym doborem sąsiadów (KNN). Każda obserwacja tworzy własną komórkę, Y = odwrotność populacji.",
    config: {
      geometry_type: "voronoi",
      population_method: "points",
      y_formula: "inv_pop",
      model_type: "auto",
      w_method: "knn_aic",
      k_range_min: 2,
      k_range_max: 30,
      use_regime_model: false,
      regime_type: "none",
      regime_threshold: 0.3,
      active_predictors: ["forests", "buildings", "water"],
      vif_threshold: 5.0,
      alpha: 0.05,
      run_moran: true,
      run_lm_tests: true,
      run_lisa: false,
      run_eta: true,
      seed: 42,
    },
  },
  "RES-23": {
    name: "Voronoi gęstość zaludnienia (Voronoi)",
    group: "Voronoi",
    description:
      "Voronoi z Y = log(populacja). Bada jak gęstość zaludnienia wpływa na obserwacje dzików w precyzyjnej geometrii.",
    config: {
      geometry_type: "voronoi",
      population_method: "points",
      y_formula: "log_pop",
      model_type: "auto",
      w_method: "knn_aic",
      k_range_min: 2,
      k_range_max: 30,
      use_regime_model: false,
      regime_type: "none",
      regime_threshold: 0.3,
      active_predictors: ["forests", "buildings", "roads", "water"],
      vif_threshold: 5.0,
      alpha: 0.05,
      run_moran: true,
      run_lm_tests: true,
      run_lisa: false,
      run_eta: true,
      seed: 42,
    },
  },
  "RES-24": {
    name: "Voronoi tessW (Voronoi)",
    group: "Voronoi",
    description:
      "Voronoi z macierzą sąsiedztwa tessW (ważony długością granicy). Metoda z pakietu spatialWarsaw, lepsza dla nieregularnych komórek.",
    config: {
      geometry_type: "voronoi",
      population_method: "points",
      y_formula: "inv_pop",
      model_type: "auto",
      w_method: "tessw",
      k_range_min: 2,
      k_range_max: 30,
      use_regime_model: false,
      regime_type: "none",
      regime_threshold: 0.3,
      active_predictors: ["forests", "buildings", "roads", "water"],
      vif_threshold: 5.0,
      alpha: 0.05,
      run_moran: true,
      run_lm_tests: true,
      run_lisa: false,
      run_eta: true,
      seed: 42,
    },
  },
  "RES-25": {
    name: "Voronoi pełny + ETA (Voronoi)",
    group: "Voronoi",
    description:
      "Pełna analiza Voronoi: tessW, 6 predyktorów, diagnostyka LISA i ETA. Najbardziej kompleksowa opcja dla geometrii Voronoi.",
    config: {
      geometry_type: "voronoi",
      population_method: "points",
      y_formula: "inv_pop",
      model_type: "auto",
      w_method: "tessw",
      k_range_min: 2,
      k_range_max: 30,
      use_regime_model: false,
      regime_type: "none",
      regime_threshold: 0.3,
      active_predictors: [
        "forests",
        "buildings",
        "roads",
        "water",
        "barriers",
        "scrub",
      ],
      vif_threshold: 5.0,
      alpha: 0.05,
      run_moran: true,
      run_lm_tests: true,
      run_lisa: true,
      run_eta: true,
      seed: 42,
    },
  },
};

/**
 * Grouped presets for dropdown optgroups
 */
export const PRESET_GROUPS = [
  { id: "Podstawowe", label: "Podstawowe" },
  { id: "Środowiskowe", label: "Analiza środowiskowa" },
  { id: "Korekta", label: "Korekta / Perspektywy" },
  { id: "Voronoi", label: "Voronoi" },
];

/**
 * Get presets organized by group
 */
export function getPresetsByGroup() {
  const byGroup = {};

  for (const [id, preset] of Object.entries(RESEARCH_PRESETS)) {
    const group = preset.group;
    if (!byGroup[group]) {
      byGroup[group] = [];
    }
    byGroup[group].push({ id, ...preset });
  }

  return byGroup;
}

/**
 * Get a preset by ID
 */
export function getPreset(id) {
  return RESEARCH_PRESETS[id] || null;
}
