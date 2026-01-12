#!/usr/bin/env Rscript
# 04_variable_y.R
# Obliczenie zmiennej zaleznej Y wedlug wybranej formuly
#
# Formuly:
#   log_intensity - Y = log((sighting_count + 1) / area_km2)  [DEFAULT]
#   count_pop     - Y = sighting_count / population (rate)
#   inv_pop       - Y = 1 / population (opt-in; wariancja z mianownika)
#   log_pop       - Y = -log(population) (opt-in; skosne rozklady)
#   log_count     - Y = log(sighting_count + 1) (opt-in)
#   binary        - Y = 1 if count > 0, else 0 (opt-in; probit/logit)
#
# Input:  sightings_gridcell_voronoi z population (krok 02) i sighting_count
# Output: UPDATE sightings_gridcell_voronoi SET y_<formula> = ..., spatial_risk = ...
#
# ENV vars:
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
#   RESEARCH_TARGET_TABLE  (default: sightings_gridcell_voronoi)
#   RESEARCH_Y_FORMULA     (log_intensity [default] / count_pop / inv_pop / log_pop / log_count / binary)

library(DBI)
library(RPostgres)

cat("============================================================\n")
cat("04_variable_y.R - Zmienna zalezna Y\n")
cat("============================================================\n")

# 1. Parametry z ENV

TARGET_TABLE <- Sys.getenv("RESEARCH_TARGET_TABLE", "sightings_gridcell_voronoi")

.allowed_tables <- c("research_grid_500m", "sightings_gridcell_voronoi", "sightings_gridcell_research")
if (!TARGET_TABLE %in% .allowed_tables) {
  stop(sprintf("Invalid TARGET_TABLE: '%s'. Allowed: %s",
               TARGET_TABLE, paste(.allowed_tables, collapse = ", ")))
}

y_formula <- Sys.getenv("RESEARCH_Y_FORMULA", "log_intensity")

cat(sprintf("Target table: %s\n", TARGET_TABLE))

VALID_FORMULAS <- c("log_intensity", "count_pop", "inv_pop", "log_pop", "log_count", "binary")

cat(sprintf("Formula: %s\n", y_formula))

if (!(y_formula %in% VALID_FORMULAS)) {
  cat(sprintf("BLAD: Nieznana formula '%s'. Dostepne: %s\n",
              y_formula, paste(VALID_FORMULAS, collapse = ", ")))
  quit(status = 1)
}

# 2. Polaczenie z baza

cat("\n[1] Laczenie z baza danych...\n")

conn <- dbConnect(
  RPostgres::Postgres(),
  dbname = Sys.getenv("DB_NAME", "dziki_db"),
  host   = Sys.getenv("DB_HOST", "db"),
  port   = as.integer(Sys.getenv("DB_PORT", "5432")),
  user   = Sys.getenv("DB_USER", "dziki"),
  password = Sys.getenv("DB_PASSWORD", "dziki_dev_password")
)

cat("Polaczono.\n")

on.exit({
  if (exists("conn") && dbIsValid(conn)) dbDisconnect(conn)
}, add = TRUE)

# 3. Walidacja: sprawdz dane wejsciowe

cat("\n[2] Sprawdzanie danych wejsciowych...\n")

input_stats <- dbGetQuery(conn, sprintf("
  SELECT
    COUNT(*)::int AS n,
    MIN(sighting_count)::int AS sc_min,
    MAX(sighting_count)::int AS sc_max,
    MIN(population) AS pop_min,
    MAX(population) AS pop_max,
    AVG(population) AS pop_avg,
    COUNT(*) FILTER (WHERE population IS NULL OR population = 0)::int AS pop_zero
  FROM %s
  WHERE geometry IS NOT NULL
", TARGET_TABLE))

cat(sprintf("  Kafli: %d\n", input_stats$n))
cat(sprintf("  sighting_count: min=%d, max=%d\n", input_stats$sc_min, input_stats$sc_max))
cat(sprintf("  population: min=%.0f, max=%.0f, avg=%.0f, zeros=%d\n",
            input_stats$pop_min, input_stats$pop_max, input_stats$pop_avg, input_stats$pop_zero))

if (input_stats$n == 0) {
  cat("BLAD: Brak kafli Voronoi.\n")
  quit(status = 1)
}

if (input_stats$pop_zero > 0) {
  cat(sprintf("UWAGA: %d kafli z population=0. Ustawiam na 1 (ochrona /0).\n",
              input_stats$pop_zero))
  dbExecute(conn, sprintf("
    UPDATE %s
    SET population = 1
    WHERE population IS NULL OR population = 0
  ", TARGET_TABLE))
}

# 4. Ensure Y columns exist

cat("\n[3] Sprawdzanie kolumn Y...\n")

for (col in c("y_log_intensity", "y_count_pop", "y_inv_pop", "y_log_pop", "y_log_count", "y_binary")) {
  dbExecute(conn, sprintf("
    ALTER TABLE %s
    ADD COLUMN IF NOT EXISTS %s DOUBLE PRECISION DEFAULT 0
  ", TARGET_TABLE, col))
}

# 5. Oblicz Y i zapisz

cat(sprintf("\n[4] Obliczanie Y (formula: %s)...\n", y_formula))

# SQL expression for Y
y_sql <- switch(y_formula,
  # DEFAULT: sighting intensity per area with +1 continuity (matches 02_spatial_models.R).
  "log_intensity" = "ln((sighting_count + 1.0) / GREATEST(ST_Area(geometry::geography) / 1000000.0, 1e-6))",
  "count_pop" = "sighting_count::double precision / population",
  "inv_pop"   = "1.0 / population",
  "log_pop"   = "-ln(population)",
  "log_count" = "ln(sighting_count + 1)",
  "binary"    = "CASE WHEN sighting_count > 0 THEN 1.0 ELSE 0.0 END"
)

if (is.null(y_sql)) {
  cat(sprintf("  UWAGA: Nieznana formula '%s', fallback do log_intensity.\n", y_formula))
  y_formula <- "log_intensity"
  y_sql <- "ln((sighting_count + 1.0) / GREATEST(ST_Area(geometry::geography) / 1000000.0, 1e-6))"
}

# Target column name
y_column <- paste0("y_", y_formula)

cat(sprintf("  SQL: %s\n", y_sql))
cat(sprintf("  Kolumna: %s\n", y_column))

# Update formula-specific column
n1 <- dbExecute(conn, sprintf("
  UPDATE %s
  SET %s = %s
  WHERE geometry IS NOT NULL
", TARGET_TABLE, y_column, y_sql))

cat(sprintf("  Zaktualizowano %d kafli (%s).\n", n1, y_column))

# Copy to spatial_risk (main column for downstream steps)
n2 <- dbExecute(conn, sprintf("
  UPDATE %s
  SET spatial_risk = %s,
      updated_at = NOW()
  WHERE geometry IS NOT NULL
", TARGET_TABLE, y_column))

cat(sprintf("  Zaktualizowano %d kafli (spatial_risk).\n", n2))

# 6. Statystyki i walidacja

cat(sprintf("\n[5] Statystyki Y (%s):\n", y_formula))

y_stats <- dbGetQuery(conn, sprintf("
  SELECT
    MIN(%s) AS y_min,
    MAX(%s) AS y_max,
    AVG(%s) AS y_avg,
    STDDEV(%s) AS y_stddev,
    COUNT(*) FILTER (WHERE %s = 0)::int AS y_zeros,
    COUNT(*) FILTER (WHERE %s IS NOT NULL)::int AS y_notnull,
    COUNT(*)::int AS total
  FROM %s
", y_column, y_column, y_column, y_column, y_column, y_column, TARGET_TABLE))

cat(sprintf("  MIN:    %.6f\n", y_stats$y_min))
cat(sprintf("  MAX:    %.6f\n", y_stats$y_max))
cat(sprintf("  AVG:    %.6f\n", y_stats$y_avg))
cat(sprintf("  STDDEV: %.6f\n", y_stats$y_stddev))
cat(sprintf("  Zeros:  %d / %d\n", y_stats$y_zeros, y_stats$total))

# Kluczowa walidacja: variance > 0
if (is.na(y_stats$y_stddev) || y_stats$y_stddev == 0) {
  cat("\n  OSTRZEZENIE: STDDEV = 0! Brak wariancji w Y.\n")
  cat("  Model przestrzenny NIE zadziala z ta formula.\n")
  if (y_formula == "binary") {
    cat("  (Oczekiwane dla binary w Voronoi 1:1 - count > 0 wszedzie)\n")
  }
  # Not a fatal error - step succeeds, model step will handle it
}

# Verify spatial_risk matches
sr_stats <- dbGetQuery(conn, sprintf("
  SELECT MIN(spatial_risk) AS sr_min, MAX(spatial_risk) AS sr_max,
         STDDEV(spatial_risk) AS sr_stddev
  FROM %s
", TARGET_TABLE))

cat(sprintf("\n  spatial_risk: min=%.6f, max=%.6f, stddev=%.6f\n",
            sr_stats$sr_min, sr_stats$sr_max, sr_stats$sr_stddev))

# Podsumowanie interpretowalnosci
cat(sprintf("\n[6] Interpretacja (%s):\n", y_formula))

if (y_formula == "log_intensity") {
  cat("  Y = log((sighting_count + 1) / area_km2)  [DEFAULT]\n")
  cat("  Intensywnosc zgloszen na powierzchnie = sygnal ryzyka (nie populacja).\n")
  cat("  Model (02_spatial_models.R) liczy Y samodzielnie; kolumny y_* sa pogladowe.\n")
} else if (y_formula == "count_pop") {
  cat("  Y = sighting_count / population\n")
  cat("  Wysokie Y = duzo zgloszen na mieszkanca (nizka populacja)\n")
  cat("  Uwaga: W Voronoi 1:1, count=1 wszedzie -> identyczne z inv_pop\n")
} else if (y_formula == "inv_pop") {
  cat("  Y = 1 / population\n")
  cat("  Wysokie Y = niska populacja = teren 'dziki'\n")
  cat(sprintf("  Zakres: 1/%d = %.6f do 1/%d = %.6f\n",
              as.integer(input_stats$pop_max),
              1.0 / input_stats$pop_max,
              as.integer(input_stats$pop_min),
              1.0 / input_stats$pop_min))
} else if (y_formula == "log_pop") {
  cat("  Y = -log(population)\n")
  cat("  Wysokie Y (blisko 0) = niska populacja\n")
  cat("  Niskie Y (ujemne) = wysoka populacja\n")
  cat(sprintf("  Zakres: -log(%d) = %.4f do -log(%d) = %.4f\n",
              as.integer(input_stats$pop_max),
              -log(input_stats$pop_max),
              as.integer(input_stats$pop_min),
              -log(input_stats$pop_min)))
} else if (y_formula == "log_count") {
  cat("  Y = log(sighting_count + 1)\n")
  cat("  Wysokie Y = DUZO obserwacji dzikow (POPRAWNA interpretacja!)\n")
  cat("  Niskie Y = MALO obserwacji dzikow\n")
  cat("  Zakres: log(1)=0 do log(max+1)\n")
  cat("  UWAGA: To bezposrednia miara obecnosci dzikow!\n")
} else if (y_formula == "binary") {
  cat("  Y = 1 if sighting_count > 0, else 0\n")
  cat("  Dla Voronoi 1:1: Y=1 wszedzie (brak wariancji!)\n")
}

# 7. REGIME CLASSIFICATION (Trinary forest/urban/mixed)

use_regime <- Sys.getenv("RESEARCH_USE_REGIME", "0") == "1"
regime_type <- Sys.getenv("RESEARCH_REGIME_TYPE", "none")
regime_threshold <- as.numeric(Sys.getenv("RESEARCH_REGIME_THRESHOLD", "0.3"))
regime_threshold_urban <- as.numeric(Sys.getenv("RESEARCH_REGIME_THRESHOLD_URBAN", "0.15"))

cat("\n============================================================\n")
cat("=== REGIME CLASSIFICATION ===\n")
cat(sprintf("Use regime:  %s\n", ifelse(use_regime, "YES", "NO")))
cat(sprintf("Regime type: %s\n", regime_type))
cat(sprintf("Forest threshold:   %.2f\n", regime_threshold))
cat(sprintf("Urban threshold:    %.2f\n", regime_threshold_urban))
cat("============================================================\n")

if (use_regime && regime_type %in% c("binary", "trinary")) {
    cat(">>> Classifying cells into trinary regimes (forest/urban/mixed)\n")

    # First ensure regime column exists
    dbExecute(conn, sprintf("
        ALTER TABLE %s ADD COLUMN IF NOT EXISTS regime VARCHAR(10) DEFAULT 'mixed'
    ", TARGET_TABLE))

    # Classification logic:
    # - forest: forest_cover > regime_threshold AND building_density < regime_threshold_urban
    # - urban:  building_density >= regime_threshold_urban AND forest_cover < regime_threshold
    # - mixed:  everything else
    update_query <- sprintf("
        UPDATE %s
        SET regime = CASE
            WHEN COALESCE(forest_cover, 0) > %.2f
                 AND COALESCE(building_density, 0) < %.2f THEN 'forest'
            WHEN COALESCE(building_density, 0) >= %.2f
                 AND COALESCE(forest_cover, 0) < %.2f THEN 'urban'
            ELSE 'mixed'
        END
    ", TARGET_TABLE, regime_threshold, regime_threshold_urban,
                     regime_threshold_urban, regime_threshold)

    result <- dbExecute(conn, update_query)
    cat(sprintf(">>> Updated %d rows\n", result))

    # Statistics
    stats <- dbGetQuery(conn, sprintf("
        SELECT
            regime,
            COUNT(*) as n,
            ROUND(AVG(COALESCE(forest_cover, 0))::numeric, 3) as avg_forest,
            ROUND(AVG(COALESCE(building_density, 0))::numeric, 3) as avg_building,
            ROUND(AVG(COALESCE(population, 0))::numeric, 0) as avg_pop
        FROM %s
        GROUP BY regime
        ORDER BY regime
    ", TARGET_TABLE))

    cat("\n>>> Regime distribution:\n")
    print(stats)

    # Validate we have variation and enough observations per regime
    n_regimes <- nrow(stats)
    if (n_regimes < 2) {
        cat("\n  UWAGA: Tylko jeden regime! Model regime nie ma sensu.\n")
        cat("  Kontynuuje, ale efektywnie bedzie jeden model.\n")
    }

    # Merge small regimes (< 5 cells) into 'mixed' to avoid aliased variables
    MIN_CELLS_PER_REGIME <- 5
    small_regimes <- stats$regime[stats$n < MIN_CELLS_PER_REGIME]

    if (length(small_regimes) > 0) {
        cat(sprintf("\n>>> Merging small regimes (n < %d) into 'mixed':\n", MIN_CELLS_PER_REGIME))
        for (r in small_regimes) {
            cat(sprintf("    %s (%.0f cells) -> mixed\n", r, stats$n[stats$regime == r]))
        }

        # Merge small regimes into 'mixed'
        small_list <- paste0("'", paste(small_regimes, collapse="','"), "'")
        merge_query <- sprintf("
            UPDATE %s
            SET regime = 'mixed'
            WHERE regime IN (%s)
        ", TARGET_TABLE, small_list)

        n_merged <- dbExecute(conn, merge_query)
        cat(sprintf(">>> Merged %d cells into 'mixed'\n", n_merged))

        # Recompute stats
        stats <- dbGetQuery(conn, sprintf("
            SELECT
                regime,
                COUNT(*) as n,
                ROUND(AVG(COALESCE(forest_cover, 0))::numeric, 3) as avg_forest,
                ROUND(AVG(COALESCE(building_density, 0))::numeric, 3) as avg_building,
                ROUND(AVG(COALESCE(population, 0))::numeric, 0) as avg_pop
            FROM %s
            GROUP BY regime
            ORDER BY regime
        ", TARGET_TABLE))

        cat("\n>>> Updated regime distribution:\n")
        print(stats)
    }
} else {
    cat(">>> Regime model disabled, skipping classification\n")
}

cat("\n============================================================\n")
cat("04_variable_y ZAKONCZONY POMYSLNIE\n")
cat("============================================================\n")
