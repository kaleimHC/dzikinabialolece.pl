/**
 * methodology.js - Dokumentacja metodologii spatialModel
 *
 * Źródło prawdy dla tessW i ETA.
 * Używane przez DocsTab.jsx do renderowania dokumentacji.
 *
 * @version 2.0.0
 * @date 2026-01-18
 */

// ═══════════════════════════════════════════════════════════════════════════════
// tessW - Macierz wag przestrzennych
// ═══════════════════════════════════════════════════════════════════════════════

export const TESSW = {
  name: "tessW",
  fullName:
    "Contiguity spatial weight matrix for point data based on Voronoi tessellation",
  source: {
    package: "spatialModel",
    file: "R/W_matrix.R",
    lines: "42-103",
    author: "Katarzyna Kopczewska",
  },
  paper: {
    title: "spatialWarsaw: Spatial Analysis for Warsaw Metropolitan Area",
    authors: "Kopczewska, K.",
    year: 2021,
    url: "https://github.com/kopczewska/spatialWarsaw",
  },
  status: "verified",
  statusEmoji: "✅",
  description: `
    Funkcja konstruuje alternatywną macierz wag przestrzennych W dla danych punktowych.
    Najpierw wykonuje teselację Voronoi, dzieląc obszar regionu na kafelki,
    gdzie punkty są centroidami tych kafelków. Na podstawie nowo utworzonych
    poligonów konstruuje macierz sąsiedztwa (contiguity matrix) W.
  `.trim(),
  algorithm: [
    "Walidacja input: region_sf musi być sf (POLYGON/MULTIPOLYGON)",
    "Przygotowanie punktów: sf (POINT) lub data.frame z X,Y",
    "Transformacja CRS do EPSG:3857 (Web Mercator)",
    "Opcjonalne losowe próbkowanie (sample_size)",
    "Teselacja Voronoi: st_voronoi() + st_intersection()",
    "Konstrukcja sąsiedztwa: poly2nb()",
    'Macierz wag: nb2listw(style="W") - row-standardized',
  ],
  code: `
tessW <- function(points_sf, region_sf, sample_size) {
  # Transform do EPSG:3857
  crds_sf <- st_transform(crds_sf, crs=3857)
  region_sf <- st_transform(region_sf, crs=3857)

  # Voronoi tessellation
  crds_union <- st_union(st_geometry(crds_sf))
  tess <- st_voronoi(crds_union, st_geometry(region_sf))
  tess <- st_intersection(st_cast(tess), st_union(st_geometry(region_sf)))

  # Macierz wag
  nb <- poly2nb(tess)
  listw <- nb2listw(nb, style="W")

  return(listw)
}`.trim(),
  output: {
    type: "listw",
    description: "Obiekt macierzy wag spdep (row-standardized)",
    properties: [
      { name: "style", value: '"W"', description: "Row-standardized weights" },
      { name: "neighbours", description: "Lista sąsiadów dla każdego regionu" },
      { name: "weights", description: "Wagi (1/liczba_sąsiadów dla każdego)" },
    ],
  },
  extensions: [
    {
      name: "Jittering",
      reason: "Oryginał nie obsługuje duplikatów współrzędnych GPS",
      implementation: "Losowe przesunięcie ±1m dla duplikatów",
      status: "documented",
    },
    {
      name: "Zapis do RDS",
      reason: "Integracja z Django pipeline",
      implementation: 'saveRDS(listw, "/app/data/listw_tessellation.rds")',
      status: "documented",
    },
  ],
};

// ═══════════════════════════════════════════════════════════════════════════════
// ETA - Entropia i Teselacja dla Aglomeracji
// ═══════════════════════════════════════════════════════════════════════════════

export const ETA = {
  name: "ETA",
  fullName: "Entropy and Tessellation for Agglomeration",
  source: {
    package: "spatialModel",
    file: "R/eta.R",
    lines: "68-142",
    author: "Katarzyna Kopczewska",
  },
  paper: {
    title: "Entropy as measure of agglomeration",
    subtitle:
      "Interactions of business locations and housing transactions in Warsaw metropolitan area",
    authors: "Kopczewska, K.",
    year: 2021,
    book: 'Handbook on "Entropy, Complexity, and Spatial Dynamics: The Rebirth of Theory?"',
    publisher: "Edward Elgar",
    editors: "Reggiani, A., Schintler, L., Czamanski, D., Patuelli, R.",
  },
  status: "verified",
  statusEmoji: "✅",
  description: `
    ETA mierzy stopień aglomeracji geolokalnych wzorców punktowych.
    Wyraża go względna entropia Shannona udziałów powierzchni
    kafelków teselacji Voronoi.

    ETA przyjmuje wartości między 0 a 1:
    - Wartości bliskie 1 odzwierciedlają silnie rozproszone punkty i przestrzennie równomierny rozkład
    - Im niższa wartość ETA, tym silniejsza aglomeracja
  `.trim(),
  formulas: {
    proportions: {
      latex: "r_i = \\frac{A_i}{\\sum_{j} A_j}",
      text: "rᵢ = Aᵢ / Σ Aⱼ",
      description: "Proporcja powierzchni kafelka i",
    },
    shannon: {
      latex: "H = -\\sum_{i}(r_i \\cdot \\ln(r_i))",
      text: "H = -Σ(rᵢ × ln(rᵢ))",
      description: "Entropia Shannona",
    },
    maxEntropy: {
      latex: "H_{max} = \\ln(n)",
      text: "H_max = ln(n)",
      description: "Maksymalna entropia (rozkład równomierny)",
    },
    eta: {
      latex: "ETA = \\frac{H}{H_{max}}",
      text: "ETA = H / H_max",
      description: "Względna entropia [0,1]",
    },
  },
  code: `
ETA <- function(points_sf, region_sf, sample_size) {
  # Voronoi tessellation (jak tessW)
  tess <- st_voronoi(...)

  # Powierzchnie kafelków
  tess_area <- st_area(tess)
  tess_area_rel <- tess_area / sum(tess_area)

  # Entropia Shannona
  S_ent <- sum(-1 * tess_area_rel * log(tess_area_rel))

  # Maksymalna entropia
  H_max <- log(length(tess_area))

  # ETA (względna entropia)
  H_rel <- S_ent / H_max

  return(list(S_ent=S_ent, H_ent=H_rel, n_points=n))
}`.trim(),
  interpretation: [
    {
      range: "ETA > 0.9",
      meaning: "Rozkład równomierny (brak aglomeracji)",
      color: "#10B981",
    },
    { range: "0.7 < ETA ≤ 0.9", meaning: "Lekkie skupienie", color: "#F59E0B" },
    {
      range: "0.5 < ETA ≤ 0.7",
      meaning: "Umiarkowane skupienie",
      color: "#F97316",
    },
    { range: "ETA ≤ 0.5", meaning: "Silna aglomeracja", color: "#EF4444" },
  ],
  warnings: [
    {
      type: "critical",
      message: "ETA jest wartością GLOBALNĄ dla całego zbioru punktów",
      detail:
        'NIE istnieje "eta_local" ani "eta per cell" w oryginalnym spatialModel',
    },
    {
      type: "info",
      message: "Liczba punktów wpływa na szybkość obliczeń",
      detail: "Dla dużych zbiorów użyj sample_size < nrow(points)",
    },
  ],
  output: {
    type: "list",
    properties: [
      {
        name: "S_ent",
        type: "numeric",
        description: "Entropia empiryczna (surowa)",
      },
      {
        name: "H_ent",
        type: "numeric",
        description: "ETA - główna wartość [0,1]",
      },
      {
        name: "n_points",
        type: "integer",
        description: "Liczba kafelków/punktów",
      },
    ],
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// SAR - Spatial Autoregressive Model (Lag Model)
// ═══════════════════════════════════════════════════════════════════════════════

export const SAR = {
  name: "SAR",
  fullName: "Spatial Autoregressive Model (Lag Model)",
  source: {
    package: "spatialreg",
    file: "lagsarlm.R",
    function: "lagsarlm()",
    author: "Roger Bivand",
  },
  paper: {
    title: "Applied Spatial Data Analysis with R",
    authors: "Bivand, R.S., Pebesma, E., Gómez-Rubio, V.",
    year: 2013,
    publisher: "Springer",
    note: "Metodologia zgodna z bootspatreg.R w spatialWarsaw (upstream)",
  },
  status: "verified",
  statusEmoji: "✅",
  description: `
    Model autoregresji przestrzennej (Spatial Lag Model). Część zmiennej
    zależnej wyjaśniają wartości sąsiadów (spatial lag).

    Wzór: y = ρWy + Xβ + ε

    gdzie ρ (rho) to parametr autokorelacji przestrzennej, W to macierz
    wag z tessW(), X to predyktory środowiskowe.

    SAR jest odpowiedni gdy:
    - Obserwacje w sąsiednich komórkach są ze sobą powiązane
    - Istnieje "efekt sąsiedztwa" (spillover effect)
  `.trim(),
  formulas: {
    model: {
      text: "y = ρWy + Xβ + ε",
      description: "Model SAR - zmienna zależna zależy od sąsiadów",
    },
    rho: {
      text: "ρ ∈ [-1, 1]",
      description: "Parametr autokorelacji przestrzennej",
    },
    fitted: {
      text: "ŷ = (I - ρW)⁻¹ Xβ",
      description: "Predykcja uwzględniająca efekt przestrzenny",
    },
  },
  interpretation: [
    {
      range: "ρ ≈ 0",
      meaning: "Brak autokorelacji przestrzennej",
      color: "#6B7280",
    },
    {
      range: "ρ > 0",
      meaning: "Dodatnia zależność (sąsiedzi podobni)",
      color: "#10B981",
    },
    {
      range: "ρ < 0",
      meaning: "Ujemna zależność (sąsiedzi różni)",
      color: "#EF4444",
    },
  ],
  code: `
# SAR (Spatial Lag Model) - spatialreg
model <- lagsarlm(
  log_density ~ forest_z + water_z + building_z + road_z,
  data = gridcells,
  listw = listw,  # z tessW()
  method = "LU"
)

# Wyniki
rho <- model$rho           # autokorelacja przestrzenna
beta <- coef(model)        # współczynniki
fitted <- fitted(model)    # predykcje
aic <- AIC(model)          # kryterium wyboru`.trim(),
  extensions: [
    {
      name: "Friction features jako predyktory",
      reason: "Kopczewska nie definiuje konkretnych predyktorów dla dzików",
      implementation:
        "forest_cover, distance_to_water, building_density, road_density",
      source: "Wildlife ecology (Balčiauskas 2020)",
    },
    {
      name: "Z-score standaryzacja",
      reason: "Różne jednostki predyktorów (m, %, km/km²)",
      implementation: "zscore(x) = (x - mean(x)) / sd(x)",
    },
  ],
};

// Aktualne wartości modelu przestrzennego (z ostatniego uruchomienia)
// SEM wybrany jako lepszy model (niższe AIC: 831.22 vs SAR 861.21)
export const SAR_CURRENT = {
  model_type: "SEM",
  lambda: 0.3661,
  rho: null, // SEM nie ma rho
  aic: 831.22,
  n_cells: 500,
  coefficients: {
    intercept: 1.903,
    forest_z: 0.0241,
    water_z: -0.0203,
    building_z: -0.0211,
    road_z: 0.0011,
  },
  interpretation: "Umiarkowana autokorelacja błędów (λ=0.37)",
  computed_at: "2026-01-19",
  source: "02_spatial_models.R",
  note: "SEM wybrany automatycznie (niższe AIC niż SAR)",
};

// ═══════════════════════════════════════════════════════════════════════════════
// SEM - Spatial Error Model
// ═══════════════════════════════════════════════════════════════════════════════

export const SEM = {
  name: "SEM",
  fullName: "Spatial Error Model",
  source: {
    package: "spatialreg",
    file: "errorsarlm.R",
    function: "errorsarlm()",
    author: "Roger Bivand",
  },
  paper: {
    title: "Applied Spatial Data Analysis with R",
    authors: "Bivand, R.S., Pebesma, E., Gómez-Rubio, V.",
    year: 2013,
    publisher: "Springer",
  },
  status: "verified",
  statusEmoji: "✅",
  description: `
    Model błędów przestrzennych. Błędy modelu korelują przestrzennie
    - odzwierciedlają pominięte zmienne o charakterze przestrzennym.

    Wzór: y = Xβ + u, gdzie u = λWu + ε

    gdzie λ (lambda) to parametr autokorelacji błędów.

    SEM jest odpowiedni gdy:
    - Pominięte zmienne mają charakter przestrzenny
    - Błędy w sąsiednich komórkach są skorelowane
  `.trim(),
  formulas: {
    model: {
      text: "y = Xβ + u",
      description: "Model liniowy z błędem przestrzennym",
    },
    error: {
      text: "u = λWu + ε",
      description: "Błąd zależy od błędów sąsiadów",
    },
    lambda: {
      text: "λ ∈ [-1, 1]",
      description: "Parametr autokorelacji błędów",
    },
  },
  interpretation: [
    { range: "λ ≈ 0", meaning: "Brak autokorelacji błędów", color: "#6B7280" },
    { range: "λ > 0", meaning: "Dodatnia korelacja błędów", color: "#F59E0B" },
    { range: "λ < 0", meaning: "Ujemna korelacja błędów", color: "#3B82F6" },
  ],
  code: `
# SEM (Spatial Error Model) - spatialreg
model <- errorsarlm(
  log_density ~ forest_z + water_z + building_z + road_z,
  data = gridcells,
  listw = listw,  # z tessW()
  method = "LU"
)

# Wyniki
lambda <- model$lambda     # autokorelacja błędów
beta <- coef(model)        # współczynniki
fitted <- fitted(model)    # predykcje
aic <- AIC(model)          # kryterium wyboru`.trim(),
  note: "W testach SAR miał niższy AIC, więc wybrano SAR jako model domyślny.",
};

// ═══════════════════════════════════════════════════════════════════════════════
// USUNIĘTE HALUCYNACJE
// ═══════════════════════════════════════════════════════════════════════════════

export const REMOVED_HALLUCINATIONS = [
  {
    what: "M(n) rescaling factor",
    formula: "M(n) = 0.015 × log(n) + 0.8957",
    where: "Stary 02_compute_tessw_eta.R, linie 161-167",
    why: `
      Ta formuła NIE ISTNIEJE w oryginalnym spatialModel.
      Została prawdopodobnie wygenerowana przez LLM jako "poprawa"
      porównywalności między zbiorami o różnej liczbie obserwacji.
      W rzeczywistości ETA jest już znormalizowana przez H_max = log(n),
      więc dodatkowy rescaling jest matematycznie nieuzasadniony.
    `.trim(),
    evidence: 'grep -n "0.015" /opt/dziki/spatialModel/R/*.R → brak wyników',
    fixed: "2026-01-18",
    fixedIn: "01_generate_voronoi.R",
  },
  {
    what: "eta_local (per-cell ETA)",
    formula: "eta_local = 1 - (tile_area / mean(tile_area))",
    where: "Stary 02_compute_tessw_eta.R, linie 237-240",
    why: `
      ETA w oryginalnym spatialModel jest wartością GLOBALNĄ.
      "eta_local" to wymysł - nie ma takiego pojęcia w literaturze
      Kopczewskiej ani w kodzie pakietu spatialModel.
    `.trim(),
    evidence:
      'grep -n "eta_local" /opt/dziki/spatialModel/R/*.R → brak wyników',
    fixed: "2026-01-18",
    fixedIn: "01_generate_voronoi.R",
  },
  {
    what: "eta_weighted",
    formula: "eta_weighted = eta_local × (1 - h_rel_global)",
    where: "Stary 02_compute_tessw_eta.R, linie 244-245",
    why: `
      Konsekwencja halucynacji eta_local.
      Nie ma podstaw teoretycznych w metodologii Kopczewskiej.
    `.trim(),
    evidence:
      'grep -n "eta_weighted" /opt/dziki/spatialModel/R/*.R → brak wyników',
    fixed: "2026-01-18",
    fixedIn: "01_generate_voronoi.R",
  },
  {
    what: "h_rel_rescaled ≠ h_rel_raw",
    where: "Tabela analytics_eta_result, rekordy sprzed 2026-01-18",
    why: `
      Stary kod zapisywał h_rel_raw (poprawne) i h_rel_rescaled (z M(n)),
      co dawało różne wartości. Po naprawie obie kolumny są RÓWNE.
    `.trim(),
    evidence: "SELECT id=11: h_rel_raw=0.867, h_rel_rescaled=0.877 (BŁĄD)",
    fixed: "2026-01-18",
    fixedIn:
      "01_generate_voronoi.R zapisuje h_rel_raw = h_rel_rescaled, m_n_factor = 1.0",
  },
];

// ═══════════════════════════════════════════════════════════════════════════════
// AKTUALNE WARTOŚCI (pobierane z API)
// ═══════════════════════════════════════════════════════════════════════════════

export const CURRENT_VALUES_ENDPOINT = "/api/analytics/eta/current/";

// Fallback jeśli API niedostępne
export const CURRENT_VALUES_FALLBACK = {
  n_tiles: 500,
  s_entropy: 5.4311,
  h_max: 6.2146,
  h_rel: 0.8739,
  interpretation: "lekkie skupienie",
  computed_at: "2026-01-18",
  source: "01_generate_voronoi.R",
};

export const PHASE_G_DISCOVERIES = {
  title: "Odkrycia Fazy G - Problemy metodologiczne",
  date: "2026-01-19",
  summary: "Audyt zgodności z spatialModel ujawnił fundamentalne problemy.",

  discoveries: [
    {
      id: "G1",
      title: "Model SEM nie używał danych OSM",
      status: "fixed",
      statusEmoji: "✅",
      description: `
        Przed naprawą wszystkie predyktory środowiskowe (forest_pct, building_pct,
        road_density, distance_to_water) były równe 0. Model działał jako pure
        spatial smoothing bez wpływu środowiska.
      `.trim(),
      fix: "Dodano _calculate_osm_features() do mode_router.py",
      fixFile: "src/analytics/mode_router.py:180-250",
    },
    {
      id: "G2",
      title: "Voronoi 1:1 → Y bez wariancji",
      status: "structural",
      statusEmoji: "⚠️",
      description: `
        01_generate_voronoi.R tworzy 1 komórkę na 1 obserwację, więc:
        - sighting_count = 1 dla WSZYSTKICH komórek
        - log(1+1) = 0.693 zawsze
        - Wszystkie wartości Y są identyczne - model nie ma czego się uczyć
        - SAR/SEM wymaga różnic między komórkami, a tu ich nie ma
      `.trim(),
      solution:
        "Użyć rozmiar komórki (inverse_area) zamiast count - rozmiary SĄ różne",
    },
    {
      id: "G3",
      title: "Square grid: 77% zer (zero-inflated)",
      status: "structural",
      statusEmoji: "⚠️",
      description: `
        W sightings_gridcell_square:
        - 7582 komórek z count=0 (76.8%)
        - 2293 komórek z count>0 (23.2%)

        SAR/SEM zakładają Gaussian errors - to założenie jest fałszywe dla
        zero-inflated count data.
      `.trim(),
      evidence:
        "SELECT SUM(CASE WHEN sighting_count=0 THEN 1 ELSE 0 END)... → 76.8%",
    },
    {
      id: "G4",
      title: "spatialModel NIE MA modeli dla count data",
      status: "limitation",
      statusEmoji: "❌",
      description: `
        Metodyka Kopczewskiej została zaprojektowana dla:
        - Danych firmowych (firms_sf) z continuous Y (ROA)
        - Gaussian errors
        - Heterogeniczność między punktami w atrybucie Y

        Nasze dane to point patterns - sam punkt = zdarzenie, brak własnego Y.

        Funkcje które NIE PASUJĄ:
        - BootSpatReg() → zakłada continuous Y
        - lagsarlm() → Gaussian assumption
        - errorsarlm() → Gaussian assumption
      `.trim(),
      reference: "spatialModel/R/bootspatreg.R - eq<-roa~empl+dummy.prod+...",
    },
  ],
};

// ═══════════════════════════════════════════════════════════════════════════════
// FUNKCJE SPATIALWARSAW - PEŁNA MAPA UŻYCIA
// ═══════════════════════════════════════════════════════════════════════════════

export const SPATIALWARSAW_FUNCTIONS = {
  title: "Funkcje spatialModel - mapa użycia w projekcie",

  used: [
    {
      name: "tessW()",
      file: "spatialModel/R/W_matrix.R:38-103",
      purpose: "Macierz wag W z Voronoi tessellation",
      ourFile: "r_scripts/01_generate_voronoi.R",
      status: "implemented",
      note: "Identyczny algorytm: st_voronoi → poly2nb → nb2listw",
    },
    {
      name: "ETA()",
      file: "spatialModel/R/eta.R:68-142",
      purpose: "Miara aglomeracji (względna entropia Shannona)",
      ourFile: "r_scripts/01_generate_voronoi.R",
      status: "implemented",
      note: "Używane jako metryka diagnostyczna + INSPIRACJA dla inverse_area",
    },
    {
      name: "bestW()",
      file: "spatialModel/R/W_matrix.R:156-263",
      purpose: "Optymalizacja knn dla macierzy W",
      ourFile: "r_scripts/01_generate_voronoi.R",
      status: "simplified",
      note: "Używamy fixed knn=5 zamiast pełnej optymalizacji",
    },
  ],

  notUsed: [
    {
      name: "BootSpatReg()",
      file: "spatialModel/R/bootspatreg.R:67-224",
      reason:
        "Zakłada continuous Y (ROA firm) - nasze Y to count/point pattern",
    },
    {
      name: "SPAG()",
      file: "spatialModel/R/spag.R",
      reason: "Wymaga size_var (wielkość punktu) - brak dla dzików",
    },
    {
      name: "QDC()",
      file: "spatialModel/R/qdc.R",
      reason: "Clustering, nie regresja - inne zastosowanie",
    },
    {
      name: "rastClustGWR()",
      file: "spatialModel/R/rastclust.R",
      reason: "GWR na coefficients - wymaga continuous Y",
    },
  ],

  potential: [
    {
      name: "FLE()",
      file: "spatialModel/R/fle.R",
      purpose: "Focal Local Entropy - rasteryzuje i liczy punkty",
      note: "Mogłoby być użyte dla square grid (liczy count w cells)",
    },
    {
      name: "ssr()",
      file: "spatialModel/R/ssr.R",
      purpose: "GLM z family parameter (np. poisson)",
      note: "Bez autokorelacji przestrzennej, ale poprawny rozkład",
    },
  ],
};

// ═══════════════════════════════════════════════════════════════════════════════
// NOWA ARCHITEKTURA - INVERSE AREA (inspiracja ETA)
// ═══════════════════════════════════════════════════════════════════════════════

export const INVERSE_AREA_ARCHITECTURE = {
  title: "Nowa architektura: Inverse Area jako proxy ryzyka",
  status: "approved",
  date: "2026-01-19",

  rationale: `
    ETA() z spatialModel używa relative_area = area_tile / sum(area) do entropii.
    Mały Voronoi tile = gęste obserwacje = wysokie ryzyko.

    Odwracając logikę ETA: intensity = 1 / relative_area
    - Duży relative_area → niskie intensity → niskie ryzyko
    - Mały relative_area → wysokie intensity → wysokie ryzyko

    To pozwala ominąć problem danych zliczeniowych (count data) - brak wariancji, założenie Gaussa nie obowiązuje -
    zachowując zgodność z duchem metodyki Kopczewskiej.
  `.trim(),

  algorithm: [
    "1. Voronoi tessellation (tessW)",
    "2. relative_area = ST_Area(geometry) / SUM(ST_Area)",
    "3. intensity = 1 / relative_area",
    "4. spatial_risk = normalize(intensity) do [0,1]",
    "5. Opcjonalnie: risk × wagi środowiskowe",
  ],

  formula: {
    relativeArea: "rᵢ = Aᵢ / Σ Aⱼ",
    intensity: "Iᵢ = 1 / rᵢ",
    normalized: "risk = (I - min(I)) / (max(I) - min(I))",
  },

  sourceInspiration: {
    function: "ETA()",
    file: "spatialModel/R/eta.R:121-122",
    code: `
tess_area <- st_area(tess_result)
tess_area_rel <- tess_area / sum(tess_area)  # ← nasza inspiracja
    `.trim(),
  },

  whatWeAvoid: [
    "NIE używamy lagsarlm() na count data",
    "NIE używamy errorsarlm() na count data",
    "NIE używamy log(count+1) jako Y",
    "NIE zakładamy Gaussian errors dla count",
  ],
};

export const METHODOLOGY_SUMMARY = {
  title: "Podstawy metodologiczne",
  date: "2026-01-19",

  method: {
    name: "Voronoi intensity estimator",
    description: "Ryzyko proporcjonalne do 1/area komórki",
    rationale: `
      Mała komórka Voronoi = gęste obserwacje = wysokie ryzyko.
      Duża komórka = rzadkie obserwacje = niskie ryzyko.
      Metoda nie wymaga danych zliczeniowych (count data) ani założenia Gaussa.
    `.trim(),
  },

  spatialModelRelation: [
    {
      element: "SAR/SEM",
      status: "not_used",
      note: "Brak wariancji Y (count=1 zawsze)",
    },
    {
      element: "ETA",
      status: "inspiration",
      note: "Logika: mała komórka = aglomeracja",
    },
    {
      element: "Voronoi (tessW)",
      status: "used",
      note: "Teselacja zgodna z oryginałem",
    },
    {
      element: "Macierz W",
      status: "built_not_used",
      note: "Budowana, nie używana w modelu",
    },
  ],

  ensemble: {
    description: "Trzy składniki mierzą rozmiar komórki różnymi metodami",
    components: [
      {
        name: "density_score",
        weight: 0.3,
        method: "Kernel density estimation",
      },
      {
        name: "spatial_score",
        weight: 0.4,
        method: "Inverse area (główny sygnał)",
      },
      {
        name: "area_rank_score",
        weight: 0.3,
        method: "Area-based rank score (1 - percentile_rank(area))",
      },
    ],
    note: "area_rank_score to 1 - percentile_rank(area_proportion), nie lokalna entropia",
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// COUNT DATA PROBLEM - SZCZEGÓŁOWA DOKUMENTACJA
// ═══════════════════════════════════════════════════════════════════════════════

export const COUNT_DATA_PROBLEM = {
  title: "Problem count data w kontekście spatialModel",

  kopczewskaApproach: {
    data: "firms_sf - dane firmowe z atrybutami",
    formula:
      "roa ~ empl + dummy.prod + dummy.constr + dummy.serv + dist.big.city",
    yVariable:
      "ROA (Return on Assets) - continuous, może być ujemna i dodatnia",
    assumption: "Gaussian errors - ε ~ N(0, σ²)",
    file: "spatialModel/R/bootspatreg.R:53",
  },

  ourData: {
    type: "Point patterns - sam punkt = zdarzenie (obserwacja dzika)",
    yVariable: '??? - punkt nie ma własnego atrybutu "rentowność dzika"',
    countDistribution: "77% zer w square grid (zero-inflated)",
    problem: "Count data: 0, 1, 2, 3, ... - dyskretne, nie ciągłe",
  },

  testResults: {
    description: "Test AIC dla różnych modeli (symulacja 79% zer)",
    models: [
      {
        name: "SEM Gaussian",
        aic: 330.6,
        note: "NAJGORSZE - błędne założenia",
      },
      { name: "Poisson GLM", aic: 283.4, note: "LEPSZE - poprawny rozkład" },
      {
        name: "Logistic (0/1)",
        aic: 237.1,
        note: "NAJLEPSZE dla presence/absence",
      },
    ],
    conclusion: "Dla zero-inflated data Poisson/logistic >> SEM Gaussian",
  },

  availablePackages: {
    have: ["spdep", "spatialreg", "MASS"],
    missing: ["pscl (zeroinfl)", "CARBayes", "brms", "INLA"],
    note: "Brak pakietów do spatial count regression w worker-r",
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// EKSPORT ZBIORCZY
// ═══════════════════════════════════════════════════════════════════════════════

export const METHODOLOGY = {
  // Oryginalne funkcje
  tessW: TESSW,
  eta: ETA,
  sar: SAR,
  sarCurrent: SAR_CURRENT,
  sem: SEM,

  // Podstawy metodologiczne (podsumowanie)
  summary: METHODOLOGY_SUMMARY,

  // Faza G discoveries
  phaseG: PHASE_G_DISCOVERIES,
  functionsMap: SPATIALWARSAW_FUNCTIONS,
  inverseArea: INVERSE_AREA_ARCHITECTURE,
  countDataProblem: COUNT_DATA_PROBLEM,

  // Legacy
  hallucinations: REMOVED_HALLUCINATIONS,
  currentEndpoint: CURRENT_VALUES_ENDPOINT,
  fallback: CURRENT_VALUES_FALLBACK,
};

export default METHODOLOGY;
