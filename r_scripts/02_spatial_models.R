#!/usr/bin/env Rscript
# NEW_02_spatial_models.R — SAR/SEM według Kopczewskiej
# ŹRÓDŁO: spatialWarsaw (lagsarlm, errorsarlm, sacsarlm)
# PAPER: Elhorst (2010) "Raising the bar"
#
# MODYFIKACJE:
#   - Friction features jako predyktory (wildlife ecology)
#   - Zapis do bazy (integracja Django)

cat("============================================================\n")
cat("NEW_02_spatial_models.R — SAR/SEM według Kopczewskiej\n")
cat("============================================================\n")

library(sf)
library(spdep)
library(DBI)
library(RPostgres)

# Sprawdź spatialreg
if (!requireNamespace("spatialreg", quietly = TRUE)) {
  cat("BŁĄD: Brak pakietu spatialreg. Instaluję...\n")
  install.packages("spatialreg", repos = "https://cloud.r-project.org")
}
library(spatialreg)

# 1. LOAD DATA

cat("\n[1] Łączenie z bazą danych...\n")

conn <- dbConnect(
  RPostgres::Postgres(),
  dbname = Sys.getenv("DB_NAME", "dziki_db"),
  host = Sys.getenv("DB_HOST", "db"),
  port = as.integer(Sys.getenv("DB_PORT", 5432)),
  user = Sys.getenv("DB_USER", "dziki"),
  password = Sys.getenv("DB_PASSWORD", "dziki_dev_password")
)

cat("Połączono.\n")

# Target table
TARGET_TABLE <- Sys.getenv("RESEARCH_TARGET_TABLE", "sightings_gridcell_voronoi")

.allowed_tables <- c("research_grid_500m", "sightings_gridcell_voronoi", "sightings_gridcell_research")
if (!TARGET_TABLE %in% .allowed_tables) {
  stop(sprintf("Invalid TARGET_TABLE: '%s'. Allowed: %s",
               TARGET_TABLE, paste(.allowed_tables, collapse = ", ")))
}

cat(sprintf("Target table: %s\n", TARGET_TABLE))

# Read Y formula from ENV (set by orchestrator from ResearchConfig)
y_formula <- Sys.getenv("RESEARCH_Y_FORMULA", "log_pop")
cat(sprintf("Y formula: %s\n", y_formula))

# Read model type from ENV (auto/sar/sem/sdm)
model_type <- Sys.getenv("RESEARCH_MODEL_TYPE", "auto")
cat(sprintf("Model type: %s\n", model_type))

# Read regime model settings from ENV
use_regime <- Sys.getenv("RESEARCH_USE_REGIME", "0") == "1"
regime_type <- Sys.getenv("RESEARCH_REGIME_TYPE", "none")
cat(sprintf("Use regime model: %s\n", ifelse(use_regime, "YES", "NO")))
cat(sprintf("Regime type: %s\n", regime_type))

# Read active predictors from ENV (comma-separated config names)
active_predictors_raw <- Sys.getenv("RESEARCH_ACTIVE_PREDICTORS", "")
if (nchar(active_predictors_raw) == 0) {
  active_predictors <- c("forests", "buildings", "roads", "water")
  cat("Active predictors: (default) forests,buildings,roads,water\n")
} else {
  active_predictors <- trimws(strsplit(active_predictors_raw, ",")[[1]])
  cat(sprintf("Active predictors: %s\n", paste(active_predictors, collapse = ", ")))
}

# Mapping: config name -> DB column name
pred_map <- list(
  forests    = "forest_cover",
  buildings  = "building_density",
  roads      = "road_density",
  water      = "distance_to_water",
  parks      = "park_cover",
  meadow     = "meadow_cover",
  farmland   = "farmland_cover",
  allotments = "allotment_cover",
  scrub      = "scrub_cover",
  railway    = "railway_density",
  barriers   = "barrier_resistance",
  population = "population"  # Population density as predictor (will be z-scored)
)

# Resolve active predictors to DB columns
active_columns <- character(0)
for (p in active_predictors) {
  if (p %in% names(pred_map)) {
    active_columns <- c(active_columns, pred_map[[p]])
  } else {
    cat(sprintf("  UWAGA: Nieznany predyktor '%s' — pomijam.\n", p))
  }
}

if (length(active_columns) == 0) {
  cat("BLAD: Brak aktywnych predyktorow! Sprawdz RESEARCH_ACTIVE_PREDICTORS.\n")
  quit(status = 1)
}

cat(sprintf("  Kolumny DB: %s\n", paste(active_columns, collapse = ", ")))

cat("\n[2] Pobieranie komórek Voronoi z predyktorami...\n")

# Dynamicznie buduj SQL z aktywnych predyktorow
pred_sql_parts <- sapply(active_columns, function(col) {
  sprintf("COALESCE(%s, 0) as %s", col, col)
})
pred_sql <- paste(pred_sql_parts, collapse = ",\n    ")

query <- sprintf("
  SELECT
    id,
    grid_id,
    ST_AsText(geometry) as wkt,
    sighting_count,
    COALESCE(population, 0) as population,
    COALESCE(regime, 'mixed') as regime,
    %s
  FROM %s
  WHERE geometry IS NOT NULL
  ORDER BY id  -- Kluczowe: kolejnosc musi zgadzac sie z listw!
", pred_sql, TARGET_TABLE)

gridcells_raw <- dbGetQuery(conn, query)

n_cells <- nrow(gridcells_raw)
cat(sprintf("Pobrano %d komórek.\n", n_cells))

# Statystyki Y
cat(sprintf("\nPopulation (Y source): min=%.1f, max=%.1f, mean=%.1f, sd=%.1f, zeros=%d/%d\n",
            min(gridcells_raw$population), max(gridcells_raw$population),
            mean(gridcells_raw$population), sd(gridcells_raw$population),
            sum(gridcells_raw$population == 0), n_cells))

# Statystyki predyktorow (dynamiczne)
cat("\nStatystyki predyktorow:\n")
for (col in active_columns) {
  vals <- gridcells_raw[[col]]
  cat(sprintf("  %s: min=%.4f, max=%.4f, mean=%.4f, sd=%.4f, nonzero=%d/%d\n",
              col, min(vals), max(vals), mean(vals), sd(vals),
              sum(vals != 0), length(vals)))
}

# Sprawdz czy mamy predyktory > 0 (przynajmniej jeden)
any_nonzero <- any(sapply(active_columns, function(col) {
  sum(gridcells_raw[[col]] != 0) > 0
}))

if (!any_nonzero) {
  cat("BLAD: Wszystkie predyktory maja same zera! Uruchom recalculate_features.py!\n")
  dbDisconnect(conn)
  quit(status = 1)
}

# 2. BUILD LISTW FROM VORONOI CELLS (spatialWarsaw-style)

cat("\n[3] Budowanie macierzy wag listw z komórek Voronoi...\n")

# Konwertuj do sf
gridcells_sf <- st_as_sf(gridcells_raw, wkt = "wkt", crs = 4326)

# Napraw ewentualne błędy geometrii
gridcells_sf <- st_make_valid(gridcells_sf)

# Sprawdź czy krok 05_matrix_w zapisał gotową macierz W
rds_path <- "/app/data/research_W.rds"

if (file.exists(rds_path)) {
  cat(sprintf("  Wczytywanie macierzy W z RDS (%s)...\n", rds_path))
  w_data <- readRDS(rds_path)

  if (!is.null(w_data$listw) && inherits(w_data$listw, "listw")) {
    listw <- w_data$listw
    nb <- w_data$nb
    cat(sprintf("  Metoda W: %s\n", w_data$method))
    if (!is.na(w_data$k_optimal)) {
      cat(sprintf("  Optymalny k: %d (AIC=%.2f)\n", w_data$k_optimal, w_data$aic))
    }
  } else {
    cat("  UWAGA: RDS nie zawiera poprawnego listw — buduje inline.\n")
    nb <- poly2nb(gridcells_sf, queen = TRUE)
    listw <- nb2listw(nb, style = "W", zero.policy = TRUE)
  }
} else {
  cat("  Brak RDS z kroku 05 — budowanie W inline (Queen contiguity)...\n")

  # Buduj sąsiedztwo (poly2nb) - styk krawędzi/wierzchołków = sąsiad
  # queen=TRUE oznacza że komórki dzielące wierzchołek są sąsiadami
  nb <- poly2nb(gridcells_sf, queen = TRUE)

  # Konwertuj do listw (macierz wag) - row-standardized (style="W")
  # zero.policy=TRUE pozwala na regiony bez sąsiadów
  listw <- nb2listw(nb, style = "W", zero.policy = TRUE)
}

# Sprawdź czy są izolowane regiony (brak sąsiadów)
n_isolated <- sum(card(nb) == 0)
if (n_isolated > 0) {
  cat(sprintf("  UWAGA: %d komórek bez sąsiadów (izolowane).\n", n_isolated))
}

cat(sprintf("  Utworzono listw: %d regionów, style=%s\n",
            length(listw$neighbours), listw$style))
cat(sprintf("  Średnia liczba sąsiadów: %.1f\n",
            mean(card(nb))))

# 3. PREPARE VARIABLES

cat("\n[4] Przygotowanie zmiennych...\n")

# Zmienna zależna Y — wedlug RESEARCH_Y_FORMULA (zgodnie z step 04)
cat(sprintf("  Budowanie Y z formuly: %s\n", y_formula))

if (y_formula == "inv_pop") {
  gridcells_raw$Y <- 1.0 / pmax(gridcells_raw$population, 1)
} else if (y_formula == "log_pop") {
  gridcells_raw$Y <- -log(pmax(gridcells_raw$population, 1))
} else if (y_formula == "count_pop") {
  gridcells_raw$Y <- gridcells_raw$sighting_count / pmax(gridcells_raw$population, 1)
} else if (y_formula == "log_count") {
  # Direct measure of boar presence (consistent with 04_variable_y.R)
  gridcells_raw$Y <- log(gridcells_raw$sighting_count + 1)
} else if (y_formula == "binary") {
  gridcells_raw$Y <- ifelse(gridcells_raw$sighting_count > 0, 1.0, 0.0)
} else {
  cat(sprintf("  UWAGA: Nieznana formula '%s', fallback do log_pop.\n", y_formula))
  y_formula <- "log_pop"
  gridcells_raw$Y <- -log(pmax(gridcells_raw$population, 1))
}

cat(sprintf("  Y: min=%.6f, max=%.6f, mean=%.6f, sd=%.6f\n",
            min(gridcells_raw$Y), max(gridcells_raw$Y),
            mean(gridcells_raw$Y), sd(gridcells_raw$Y)))

# Walidacja: Y musi miec wariancje dla SAR/SEM
y_sd <- sd(gridcells_raw$Y, na.rm = TRUE)
is_binary <- (y_formula == "binary")

if (is.na(y_sd) || y_sd == 0) {
  cat("  BLAD: Y nie ma wariancji (sd=0)! Model przestrzenny nie zadziala.\n")
  cat("  Sprawdz y_formula i dane wejsciowe.\n")
  dbDisconnect(conn)
  quit(status = 3)
