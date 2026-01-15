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
  # W matrix metrics
  k_selected = k_selected,
  mean_neighbors = mean_neighbors,
  # Impacts (SAR/SDM only)
  impacts = "null"            # JSON string
)

# Spatial parameters
if (!is.na(best_result$rho))    diag$rho <- best_result$rho
if (!is.na(best_result$lambda)) diag$lambda_param <- best_result$lambda

# Log-likelihood
diag$log_likelihood <- tryCatch({
  as.numeric(logLik(best_result$model))
}, error = function(e) NA_real_)

# 3. Coefficients & Pseudo-R²

cat("\n[2] Wspolczynniki modelu...\n")

coef_table <- tryCatch({
  s <- summary(best_result$model)
  if (best_result$type == "OLS") {
    s$coefficients
  } else {
    # spatialreg: summary has $Coef or $coefficients
    if (!is.null(s$Coef)) s$Coef else s$coefficients
  }
}, error = function(e) {
  cat(sprintf("  Nie mozna wyciagnac wspolczynnikow: %s\n", e$message))
  NULL
})

if (!is.null(coef_table) && is.matrix(coef_table)) {
  cat("  Wspolczynniki:\n")
  print(round(coef_table, 4))

  # Build JSON: {name: {estimate, std_error, z, p}}
  coef_names <- rownames(coef_table)
  coef_list <- list()
  for (i in seq_along(coef_names)) {
    nm <- coef_names[i]
    coef_list[[nm]] <- list(
      estimate  = round(coef_table[i, 1], 6),
      std_error = round(coef_table[i, 2], 6),
      z         = round(coef_table[i, 3], 4),
      p         = round(coef_table[i, 4], 6)
    )
  }

  # Manual JSON construction (avoid jsonlite dependency)
  json_parts <- sapply(names(coef_list), function(nm) {
    cl <- coef_list[[nm]]
    sprintf('"%s": {"estimate": %s, "std_error": %s, "z": %s, "p": %s}',
            nm,
            ifelse(is.na(cl$estimate), "null", as.character(cl$estimate)),
            ifelse(is.na(cl$std_error), "null", as.character(cl$std_error)),
            ifelse(is.na(cl$z), "null", as.character(cl$z)),
            ifelse(is.na(cl$p), "null", as.character(cl$p)))
  })
  diag$coefficients <- paste0("{", paste(json_parts, collapse = ", "), "}")
}

# Pseudo R²: 1 - RSS/TSS
# Y column: "Y" (from step 06 fix) or legacy "log_density"
if ("Y" %in% names(model_df)) {
  Y <- model_df$Y
} else if ("log_density" %in% names(model_df)) {
  Y <- model_df$log_density
} else {
  Y <- NULL
  cat("  Brak kolumny Y/log_density w danych modelu.\n")
}
resids <- tryCatch(residuals(best_result$model), error = function(e) NULL)

if (!is.null(resids) && length(resids) == length(Y)) {
  rss <- sum(resids^2)
  tss <- sum((Y - mean(Y))^2)
  if (tss > 0) {
    diag$r_squared <- round(1 - rss / tss, 6)
    cat(sprintf("  Pseudo R²: %.4f\n", diag$r_squared))
  }
} else {
  cat("  Brak residuow — nie mozna obliczyc R².\n")
}

# 4. VIF (Variance Inflation Factor)

cat("\n[3] VIF (multicollinearity)...\n")

ols_model <- tryCatch(lm(eq, data = model_df), error = function(e) NULL)

if (!is.null(ols_model)) {
  X <- model.matrix(ols_model)[, -1, drop = FALSE]  # exclude intercept

  if (ncol(X) >= 2) {
    vif_vals <- numeric(ncol(X))
    names(vif_vals) <- colnames(X)

    for (j in seq_len(ncol(X))) {
      r2 <- summary(lm(X[, j] ~ X[, -j]))$r.squared
      vif_vals[j] <- 1 / (1 - r2)
    }

    cat("  VIF:\n")
    for (nm in names(vif_vals)) {
      v <- vif_vals[nm]
      if (is.na(v) || !is.finite(v)) {
        cat(sprintf("    %-15s NA (aliased/zero-variance)\n", nm))
      } else {
        flag <- if (v > vif_threshold) " *** WYSOKI!" else ""
        cat(sprintf("    %-15s %.2f%s\n", nm, v, flag))
      }
    }

    # JSON for VIF results (handle NA/Inf)
    vif_parts <- sapply(names(vif_vals), function(nm) {
      v <- vif_vals[nm]
      if (is.na(v) || !is.finite(v)) {
        sprintf('"%s": null', nm)
      } else {
        sprintf('"%s": %.4f', nm, v)
      }
    })
    diag$vif_results <- paste0("{", paste(vif_parts, collapse = ", "), "}")

    # Predictors dropped (guard against NA)
    dropped <- names(vif_vals[!is.na(vif_vals) & is.finite(vif_vals) & vif_vals > vif_threshold])
    if (length(dropped) > 0) {
      cat(sprintf("  Predyktory z VIF > %.1f: %s\n",
                  vif_threshold, paste(dropped, collapse = ", ")))
      diag$predictors_dropped <- paste0(
        "[", paste(sprintf('"%s"', dropped), collapse = ", "), "]")
    }
  } else {
    cat("  Za malo predyktorow (<2) do obliczenia VIF.\n")
  }
} else {
  cat("  OLS nie zbiegnal — brak VIF.\n")
}

# 5. Moran's I (residuals)

if (run_moran) {
  cat("\n[4] Moran's I na resztach modelu...\n")

  moran_input <- if (!is.null(resids)) resids else Y

  moran_result <- tryCatch({
    moran.test(moran_input, listw = listw, zero.policy = TRUE)
