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
