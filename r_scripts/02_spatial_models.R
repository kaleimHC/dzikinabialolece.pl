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
}

# Standaryzacja z-score predyktorow
zscore <- function(x) {
  m <- mean(x, na.rm = TRUE)
  s <- sd(x, na.rm = TRUE)
  if (s == 0 || is.na(s)) return(rep(0, length(x)))
  return((x - m) / s)
}

# Dynamiczna standaryzacja aktywnych predyktorow
z_names <- character(0)
for (col in active_columns) {
  z_col <- paste0(gsub("_", "", col), "_z")  # forest_cover -> forestcover_z
  # Uzyj krotszych nazw z-score
  z_col <- sub("cover_z$", "_z", z_col)
  z_col <- sub("density_z$", "_z", z_col)
  z_col <- sub("distance_to_", "", z_col)
  z_col <- sub("resistance_z$", "_z", z_col)
  # Prostsza logika: config_name + "_z"
  cfg_name <- names(pred_map)[sapply(pred_map, function(x) x == col)]
  z_col <- paste0(cfg_name, "_z")

  gridcells_raw[[z_col]] <- zscore(gridcells_raw[[col]])
  z_names <- c(z_names, z_col)
  cat(sprintf("  %s -> %s (sd=%.4f)\n", col, z_col, sd(gridcells_raw[[col]], na.rm = TRUE)))
}

cat(sprintf("  Standaryzacja z-score zakonczona: %d predyktorow.\n", length(z_names)))

# 4. FIT MODELS

# Dynamiczna formula z aktywnych predyktorow
# Check for binary/trinary regime model (both use same 3-way classification)
if (use_regime && regime_type %in% c("binary", "trinary")) {
  cat("\n>>> Building TRINARY REGIME formula (forest/urban/mixed)\n")

  # Konwertuj regime na factor
  gridcells_raw$regime <- factor(gridcells_raw$regime,
                                  levels = c("urban", "mixed", "forest"))

  # Sprawdz czy mamy wiecej niz jeden regime
  n_regimes <- length(unique(gridcells_raw$regime))
  cat(sprintf("  Liczba regimes: %d (%s)\n", n_regimes,
              paste(unique(gridcells_raw$regime), collapse = ", ")))

  if (n_regimes > 1) {
    # Formuła z interakcjami: Y ~ 0 + regime + regime:(predictors)
    # "0 +" usuwa intercept globalny — każdy regime ma swój
    predictors_str <- paste(z_names, collapse = " + ")
    eq_str <- sprintf("Y ~ 0 + regime + regime:(%s)", predictors_str)
    cat("  Model regime: TAK\n")
  } else {
    # Jeden regime — standardowa formula
    eq_str <- paste("Y ~", paste(z_names, collapse = " + "))
    cat("  UWAGA: Tylko jeden regime — fallback do modelu globalnego\n")
  }
} else {
  # Standard (bez regime)
  eq_str <- paste("Y ~", paste(z_names, collapse = " + "))
}

eq <- as.formula(eq_str)
cat(sprintf("  Formula: %s\n", eq_str))

# Initialize results
sar_result <- list(success = FALSE)
sem_result <- list(success = FALSE)
sdm_result <- list(success = FALSE)

# Determine which models to fit based on model_type config
fit_sar <- model_type %in% c("auto", "sar")
fit_sem <- model_type %in% c("auto", "sem")
fit_sdm <- (model_type == "sdm")

if (model_type != "auto") {
  cat(sprintf("\n  Wymuszony model: %s\n", toupper(model_type)))
}

if (!is_binary) {

  # ==========================================================
  # 4a. SAR (Spatial Autoregressive / Lag Model)
  # ==========================================================
  # Wzor: y = rhoWy + Xbeta + epsilon

  if (fit_sar) {
    cat("\n[5] Estymacja modelu SAR (lagsarlm)...\n")

    sar_result <- tryCatch({
      model <- lagsarlm(eq, data = gridcells_raw, listw = listw, method = "LU")

      cat("SAR zakonczony.\n")
      cat(sprintf("  rho: %.4f\n", model$rho))
      cat(sprintf("  AIC: %.2f\n", AIC(model)))
      cat("  Wspolczynniki:\n")
      print(round(coef(model), 4))

      list(
        model = model,
        type = "SAR",
        rho = model$rho,
        lambda = NA,
        AIC = AIC(model),
        fitted = fitted(model),
        success = TRUE
      )
    }, error = function(e) {
      cat(sprintf("SAR BLAD: %s\n", e$message))
      list(success = FALSE, error = e$message)
    })
  } else {
    cat("\n[5] Pominieto SAR (model_type != auto/sar).\n")
  }

  # ==========================================================
  # 4b. SEM (Spatial Error Model)
  # ==========================================================
  # Wzor: y = Xbeta + u, gdzie u = lambdaWu + epsilon

  if (fit_sem) {
    cat("\n[6] Estymacja modelu SEM (errorsarlm)...\n")

    sem_result <- tryCatch({
      model <- errorsarlm(eq, data = gridcells_raw, listw = listw,
                          method = "LU", Durbin = FALSE)

      cat("SEM zakonczony.\n")
      cat(sprintf("  lambda: %.4f\n", model$lambda))
      cat(sprintf("  AIC: %.2f\n", AIC(model)))
      cat("  Wspolczynniki:\n")
      print(round(coef(model), 4))

      list(
        model = model,
        type = "SEM",
        rho = NA,
        lambda = model$lambda,
        AIC = AIC(model),
        fitted = fitted(model),
        success = TRUE
      )
    }, error = function(e) {
      cat(sprintf("SEM BLAD: %s\n", e$message))
      list(success = FALSE, error = e$message)
    })
  } else {
    cat("\n[6] Pominieto SEM (model_type != auto/sem).\n")
  }

  # ==========================================================
  # 4d. SDM (Spatial Durbin Model = SAR with WX)
  # ==========================================================
  # Wzor: y = rhoWy + Xbeta + WXgamma + epsilon

  if (fit_sdm) {
    cat("\n[5-6] Estymacja modelu SDM (lagsarlm type='mixed')...\n")

    sdm_result <- tryCatch({
      model <- lagsarlm(eq, data = gridcells_raw, listw = listw,
                        method = "LU", type = "mixed")

      cat("SDM zakonczony.\n")
      cat(sprintf("  rho: %.4f\n", model$rho))
      cat(sprintf("  AIC: %.2f\n", AIC(model)))
      cat("  Wspolczynniki:\n")
      print(round(coef(model), 4))

      list(
        model = model,
        type = "SDM",
        rho = model$rho,
        lambda = NA,
        AIC = AIC(model),
        fitted = fitted(model),
        success = TRUE
      )
    }, error = function(e) {
      cat(sprintf("SDM BLAD: %s\n", e$message))
      list(success = FALSE, error = e$message)
    })
  }

} else {
  # ==========================================================
  # 4c. BINARY Y -> GLM (logit) — brak modelu przestrzennego
  # ==========================================================
  cat("\n[5-6] Binary Y -> GLM (logit) zamiast SAR/SEM...\n")
  cat("  UWAGA: GLM nie modeluje autokorelacji przestrzennej.\n")
}

# 5. MODEL SELECTION (by AIC)

cat("\n[7] Selekcja modelu (AIC)...\n")

if (is_binary) {
  # Binary: use GLM with binomial family
  glm_result <- tryCatch({
    model <- glm(eq, data = gridcells_raw, family = binomial(link = "logit"))

    cat("GLM (logit) zakonczony.\n")
    cat(sprintf("  AIC: %.2f\n", AIC(model)))
    cat("  Wspolczynniki:\n")
    print(round(coef(model), 4))

    list(
      model = model,
      type = "GLM_logit",
      rho = NA,
      lambda = NA,
      AIC = AIC(model),
      fitted = fitted(model, type = "response"),
      success = TRUE
    )
  }, error = function(e) {
    cat(sprintf("GLM BLAD: %s\n", e$message))
    list(success = FALSE, error = e$message)
  })

  if (glm_result$success) {
    best_result <- glm_result
  } else {
    cat("GLM zawiodl — fallback do OLS.\n")
    ols_model <- lm(eq, data = gridcells_raw)
    best_result <- list(
      model = ols_model, type = "OLS", rho = NA, lambda = NA,
      AIC = AIC(ols_model), fitted = fitted(ols_model)
    )
  }

} else if (model_type == "sar") {
  # --- Wymuszony SAR ---
  if (sar_result$success) {
    cat(sprintf("SAR AIC: %.2f\n", sar_result$AIC))
    cat("WYMUSZONO: SAR (model_type=sar)\n")
    best_result <- sar_result
  } else {
    cat("BLAD: Wymuszony SAR nie zbiegl! Fallback do OLS.\n")
    ols_model <- lm(eq, data = gridcells_raw)
    best_result <- list(
      model = ols_model, type = "OLS", rho = NA, lambda = NA,
      AIC = AIC(ols_model), fitted = fitted(ols_model), success = TRUE
    )
    cat(sprintf("OLS AIC: %.2f\n", best_result$AIC))
  }

} else if (model_type == "sem") {
  # --- Wymuszony SEM ---
  if (sem_result$success) {
    cat(sprintf("SEM AIC: %.2f\n", sem_result$AIC))
    cat("WYMUSZONO: SEM (model_type=sem)\n")
    best_result <- sem_result
  } else {
    cat("BLAD: Wymuszony SEM nie zbiegl! Fallback do OLS.\n")
    ols_model <- lm(eq, data = gridcells_raw)
    best_result <- list(
      model = ols_model, type = "OLS", rho = NA, lambda = NA,
      AIC = AIC(ols_model), fitted = fitted(ols_model), success = TRUE
    )
    cat(sprintf("OLS AIC: %.2f\n", best_result$AIC))
  }

} else if (model_type == "sdm") {
  # --- Wymuszony SDM ---
  if (sdm_result$success) {
    cat(sprintf("SDM AIC: %.2f\n", sdm_result$AIC))
    cat("WYMUSZONO: SDM (model_type=sdm)\n")
    best_result <- sdm_result
  } else {
    cat("BLAD: Wymuszony SDM nie zbiegl! Fallback do OLS.\n")
    ols_model <- lm(eq, data = gridcells_raw)
    best_result <- list(
      model = ols_model, type = "OLS", rho = NA, lambda = NA,
      AIC = AIC(ols_model), fitted = fitted(ols_model), success = TRUE
    )
    cat(sprintf("OLS AIC: %.2f\n", best_result$AIC))
  }

} else {
  # --- auto: wybor przez AIC ---
  if (!sar_result$success && !sem_result$success) {
    cat("BLAD: Oba modele przestrzenne zawiodly!\n")
    cat("Fallback do prostego OLS...\n")
    ols_model <- lm(eq, data = gridcells_raw)
    best_result <- list(
      model = ols_model, type = "OLS", rho = NA, lambda = NA,
      AIC = AIC(ols_model), fitted = fitted(ols_model), success = TRUE
    )
    cat(sprintf("OLS AIC: %.2f\n", AIC(ols_model)))
  } else if (!sar_result$success) {
    cat("SAR nieudany, uzywam SEM.\n")
    best_result <- sem_result
  } else if (!sem_result$success) {
    cat("SEM nieudany, uzywam SAR.\n")
    best_result <- sar_result
  } else {
    cat(sprintf("SAR AIC: %.2f\n", sar_result$AIC))
    cat(sprintf("SEM AIC: %.2f\n", sem_result$AIC))
