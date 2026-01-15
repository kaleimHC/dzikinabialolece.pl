#!/usr/bin/env Rscript
# 07_diagnostics.R
# Testy diagnostyczne modelu przestrzennego
#
# Testy:
#   Moran I     — autokorelacja przestrzenna reszt (obowiazkowe)
#   LM tests    — LM-lag vs LM-error (obowiazkowe)
#   LISA        — Local Moran I, klasyfikacja HH/LL/HL/LH/NS (opcjonalne)
#   ETA         — entropia globalna tessellacji (opcjonalne)
#   VIF         — Variance Inflation Factor (zawsze)
#   Coefficients— wspolczynniki modelu (zawsze)
#
# Input:
#   /app/data/research_W.rds      (macierz W z kroku 05)
#   /app/data/research_model.rds  (model z kroku 06)
#   sightings_gridcell_voronoi    (geometria dla ETA)
#
# Output: INSERT INTO analytics_researchdiagnostics
#
# ENV vars:
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
#   RESEARCH_TARGET_TABLE    (default: sightings_gridcell_voronoi)
#   RESEARCH_RUN_ID          (UUID runu)
#   RESEARCH_RUN_MORAN       (1/0, default: 1)
#   RESEARCH_RUN_LM_TESTS    (1/0, default: 1)
#   RESEARCH_RUN_LISA        (1/0, default: 0)
#   RESEARCH_RUN_ETA         (1/0, default: 0)
#   RESEARCH_ALPHA           (poziom istotnosci, default: 0.05)
#   RESEARCH_VIF_THRESHOLD   (prog VIF, default: 5.0)

library(sf)
library(spdep)
library(DBI)
library(RPostgres)

cat("============================================================\n")
cat("07_diagnostics.R — Testy diagnostyczne\n")
cat("============================================================\n")

# 1. Parametry z ENV

TARGET_TABLE <- Sys.getenv("RESEARCH_TARGET_TABLE", "sightings_gridcell_voronoi")
run_id        <- Sys.getenv("RESEARCH_RUN_ID", "")
run_moran     <- Sys.getenv("RESEARCH_RUN_MORAN", "1") == "1"

cat(sprintf("Target table: %s\n", TARGET_TABLE))
run_lm_tests  <- Sys.getenv("RESEARCH_RUN_LM_TESTS", "1") == "1"
run_lisa       <- Sys.getenv("RESEARCH_RUN_LISA", "0") == "1"
run_eta       <- Sys.getenv("RESEARCH_RUN_ETA", "0") == "1"
alpha         <- as.numeric(Sys.getenv("RESEARCH_ALPHA", "0.05"))
vif_threshold <- as.numeric(Sys.getenv("RESEARCH_VIF_THRESHOLD", "5.0"))

cat(sprintf("Run ID: %s\n", run_id))
cat(sprintf("Testy: Moran=%s, LM=%s, LISA=%s, ETA=%s\n",
            run_moran, run_lm_tests, run_lisa, run_eta))
cat(sprintf("Alpha: %.3f, VIF threshold: %.1f\n", alpha, vif_threshold))

if (nchar(run_id) == 0) {
  cat("UWAGA: Brak RESEARCH_RUN_ID — wyniki nie beda zapisane do bazy.\n")
}

# 2. Wczytaj dane z RDS

cat("\n[1] Wczytywanie danych...\n")

# Macierz W z kroku 05
w_rds_path <- "/app/data/research_W.rds"
if (!file.exists(w_rds_path)) {
  cat(sprintf("BLAD: Brak pliku %s (krok 05 nie uruchomiony).\n", w_rds_path))
  quit(status = 1)
}
w_data <- readRDS(w_rds_path)
listw <- w_data$listw
nb <- w_data$nb
cat(sprintf("  W: metoda=%s, regionow=%d\n", w_data$method, length(nb)))

# Extract W matrix metrics for diagnostics
k_selected <- if (!is.null(w_data$k_optimal)) as.integer(w_data$k_optimal) else NA_integer_
mean_neighbors <- mean(card(nb))
cat(sprintf("  k_selected: %s\n", ifelse(is.na(k_selected), "N/A (non-KNN method)", k_selected)))
cat(sprintf("  mean_neighbors: %.2f\n", mean_neighbors))

# Model z kroku 06
model_rds_path <- "/app/data/research_model.rds"
if (!file.exists(model_rds_path)) {
  cat(sprintf("BLAD: Brak pliku %s (krok 06 nie uruchomiony).\n", model_rds_path))
  quit(status = 1)
}
model_data <- readRDS(model_rds_path)
best_result <- model_data$best_result
sar_result  <- model_data$sar_result
sem_result  <- model_data$sem_result
model_df    <- model_data$data
eq          <- model_data$formula
n_cells     <- model_data$n_cells

cat(sprintf("  Model: %s, AIC=%.2f, n=%d\n",
            best_result$type, best_result$AIC, n_cells))
cat(sprintf("  Formula: %s\n", deparse(eq)))

# Wczytaj impacts (SAR/SDM only) z kroku 06
# Używamy isTRUE() dla bezpieczeństwa (stare RDS mogą nie mieć tego pola)
impacts_result <- model_data$impacts_result
has_impacts <- !is.null(impacts_result) && isTRUE(impacts_result$success)
if (has_impacts) {
  cat(sprintf("  Impacts: TAK (%d predyktorow)\n", length(impacts_result$direct)))
} else {
  cat("  Impacts: NIE (model nie wymaga lub blad)\n")
}

# Load spatialreg for model functions
if (!requireNamespace("spatialreg", quietly = TRUE)) {
  install.packages("spatialreg", repos = "https://cloud.r-project.org")
}
library(spatialreg)

# Storage for results (will be inserted into DB at the end)

diag <- list(
  # Moran I
  moran_i = NA_real_, moran_expected = NA_real_, moran_variance = NA_real_,
  moran_z = NA_real_, moran_p = NA_real_,
  # LM tests
  lm_lag_stat = NA_real_, lm_lag_p = NA_real_,
  lm_error_stat = NA_real_, lm_error_p = NA_real_,
  rlm_lag_stat = NA_real_, rlm_lag_p = NA_real_,
  rlm_error_stat = NA_real_, rlm_error_p = NA_real_,
  # Model info
  model_selected = best_result$type,
  aic = best_result$AIC,
  log_likelihood = NA_real_,
  coefficients = "null",   # JSON string
  r_squared = NA_real_,
  rho = NA_real_, lambda_param = NA_real_,
  # LISA
  lisa_hh = NA_integer_, lisa_ll = NA_integer_,
  lisa_hl = NA_integer_, lisa_lh = NA_integer_, lisa_ns = NA_integer_,
  # VIF
  vif_results = "null",       # JSON string
  predictors_dropped = "[]",  # JSON string
