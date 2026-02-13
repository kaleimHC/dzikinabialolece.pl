#!/usr/bin/env Rscript
# NEW_03_inverse_area_risk.R — Inverse Area jako proxy ryzyka
# ŹRÓDŁO INSPIRACJI: spatialWarsaw/R/eta.R (funkcja ETA używa relative_area)
#
# UZASADNIENIE METODOLOGICZNE:
#   - Voronoi 1:1 oznacza sighting_count = 1 zawsze
#   - log(count+1) = 0.693 dla WSZYSTKICH komórek → brak wariancji
#   - SAR/SEM failują bo macierz kowariancji jest singular
#
# ROZWIĄZANIE:
#   - Używamy GEOMETRII (area) zamiast count jako źródło wariancji
#   - Mały Voronoi tile = gęste obserwacje = WYSOKIE ryzyko
#   - Duży Voronoi tile = rzadkie obserwacje = NISKIE ryzyko
#
# ALGORYTM (inspiracja ETA z spatialWarsaw):
#   1. relative_area = ST_Area(geometry) / SUM(ST_Area)
#   2. intensity = 1 / relative_area
#   3. spatial_risk = PERCENTILE_RANK(intensity) — równomierny rozkład!
#
# NORMALIZACJA: PERCENTILE RANK (nie min-max!)
#   - Min-max: outliers (małe komórki) powodują że 96% ma risk < 0.2
#   - Percentile rank: równomierny rozkład ~20% w każdym przedziale
#
# DATA: 2026-01-19
# WERSJA: 2.0.0 (percentile rank)

cat("============================================================\n")
cat("NEW_03_inverse_area_risk.R — Inverse Area Risk v2.0\n")
cat("============================================================\n")
cat("Normalizacja: PERCENTILE RANK (równomierny rozkład)\n")
cat("Inspiracja: spatialWarsaw::ETA() → relative_area\n")
cat("============================================================\n\n")

# Suppress package startup messages (prevent false error detection in Docker)
suppressPackageStartupMessages({
  library(sf)
  library(DBI)
  library(RPostgres)
})

# 1. POŁĄCZENIE Z BAZĄ

cat("[1] Łączenie z bazą danych...\n")

conn <- dbConnect(
  RPostgres::Postgres(),
  dbname = Sys.getenv("DB_NAME", "dziki_db"),
  host = Sys.getenv("DB_HOST", "db"),
  port = as.integer(Sys.getenv("DB_PORT", 5432)),
  user = Sys.getenv("DB_USER", "dziki"),
  password = Sys.getenv("DB_PASSWORD", "dziki_dev_password")
)

cat("Połączono.\n")

# 2. POBRANIE KOMÓREK VORONOI

cat("\n[2] Pobieranie komórek Voronoi...\n")

# Pobierz dane z geometrią
gridcells_raw <- dbGetQuery(conn, "
  SELECT
    id,
    grid_id,
    ST_AsText(geometry) as wkt,
    sighting_count,
    -- Oblicz area w metrach kwadratowych (geography)
    ST_Area(geometry::geography) as area_m2
  FROM sightings_gridcell_voronoi
  WHERE geometry IS NOT NULL
  ORDER BY id
")

n_cells <- nrow(gridcells_raw)
cat(sprintf("Pobrano %d komórek Voronoi.\n", n_cells))

if (n_cells < 3) {
  cat("BŁĄD: Za mało komórek (min. 3)!\n")
  dbDisconnect(conn)
  quit(status = 1)
}

# Statystyki wejściowe
cat("\nStatystyki komórek:\n")
cat(sprintf("  sighting_count: min=%d, max=%d, mean=%.2f\n",
            min(gridcells_raw$sighting_count),
            max(gridcells_raw$sighting_count),
            mean(gridcells_raw$sighting_count)))
cat(sprintf("  area_m2: min=%.0f, max=%.0f, mean=%.0f\n",
            min(gridcells_raw$area_m2),
            max(gridcells_raw$area_m2),
            mean(gridcells_raw$area_m2)))

# 3. OBLICZENIE RELATIVE AREA (inspiracja: ETA z spatialWarsaw)
# Źródło: spatialWarsaw/R/eta.R, linie 121-122:
#   tess_area_rel <- tess_area / sum(tess_area)

cat("\n[3] Obliczanie relative_area (jak ETA w spatialWarsaw)...\n")

# Total area
total_area_m2 <- sum(gridcells_raw$area_m2)
cat(sprintf("  Total area: %.2f km²\n", total_area_m2 / 1e6))

# Relative area per cell
# relative_area = area_i / sum(area)
gridcells_raw$relative_area <- gridcells_raw$area_m2 / total_area_m2

cat(sprintf("  relative_area: min=%.6f, max=%.6f, mean=%.6f\n",
            min(gridcells_raw$relative_area),
            max(gridcells_raw$relative_area),
            mean(gridcells_raw$relative_area)))

# Sprawdź czy suma = 1 (kontrola)
sum_rel <- sum(gridcells_raw$relative_area)
cat(sprintf("  Suma relative_area: %.6f (powinno być 1.0)\n", sum_rel))

# 4. OBLICZENIE INTENSITY (inverse area)
# Logika:
#   - Mały tile → duża intensity → wysokie ryzyko
#   - Duży tile → mała intensity → niskie ryzyko
#
# intensity = 1 / relative_area

cat("\n[4] Obliczanie intensity (1 / relative_area)...\n")

gridcells_raw$intensity <- 1 / gridcells_raw$relative_area

cat(sprintf("  intensity: min=%.2f, max=%.2f, mean=%.2f\n",
            min(gridcells_raw$intensity),
            max(gridcells_raw$intensity),
            mean(gridcells_raw$intensity)))

# 5. NORMALIZACJA DO [0,1] → spatial_risk (PERCENTILE RANK)
# ZMIANA v2.0: Używamy PERCENTILE RANK zamiast min-max!
#
# Problem z min-max:
#   - Outliers (bardzo małe komórki) dostają risk=1.0
#   - Reszta jest "zgnieciona" do bardzo niskich wartości
#   - Dla n=500: 96% komórek miało risk < 0.2
#
# Rozwiązanie - percentile rank:
#   - spatial_risk = (rank - 1) / (n - 1)
#   - Równomierny rozkład: ~20% w każdym przedziale [0-0.2], [0.2-0.4], etc.
#   - Ranking zachowany: mała area → wysoki rank → wysoki risk

cat("\n[5] Normalizacja intensity do [0,1] → spatial_risk (PERCENTILE RANK)...\n")

if (n_cells == 1) {
  # Edge case: tylko jedna komórka
  gridcells_raw$spatial_risk <- 0.5
} else {
  # PERCENTILE RANK: (rank - 1) / (n - 1)
  # rank() domyślnie: ties = "average"
  # Wynik: wartości od 0 (najniższa intensity) do 1 (najwyższa intensity)
  intensity_rank <- rank(gridcells_raw$intensity, ties.method = "average")
  gridcells_raw$spatial_risk <- (intensity_rank - 1) / (n_cells - 1)
}

cat(sprintf("  Metoda: PERCENTILE RANK (rank/n)\n"))
cat(sprintf("  spatial_risk: min=%.4f, max=%.4f, mean=%.4f, sd=%.4f\n",
            min(gridcells_raw$spatial_risk),
            max(gridcells_raw$spatial_risk),
            mean(gridcells_raw$spatial_risk),
            sd(gridcells_raw$spatial_risk)))

# Rozkład w bucketach (powinno być ~20% każdy)
bucket_0_20 <- sum(gridcells_raw$spatial_risk < 0.2)
bucket_20_40 <- sum(gridcells_raw$spatial_risk >= 0.2 & gridcells_raw$spatial_risk < 0.4)
bucket_40_60 <- sum(gridcells_raw$spatial_risk >= 0.4 & gridcells_raw$spatial_risk < 0.6)
bucket_60_80 <- sum(gridcells_raw$spatial_risk >= 0.6 & gridcells_raw$spatial_risk < 0.8)
bucket_80_100 <- sum(gridcells_raw$spatial_risk >= 0.8)

cat(sprintf("  Rozkład bucketów:\n"))
cat(sprintf("    [0.0-0.2]: %d (%.1f%%)\n", bucket_0_20, 100 * bucket_0_20 / n_cells))
cat(sprintf("    [0.2-0.4]: %d (%.1f%%)\n", bucket_20_40, 100 * bucket_20_40 / n_cells))
cat(sprintf("    [0.4-0.6]: %d (%.1f%%)\n", bucket_40_60, 100 * bucket_40_60 / n_cells))
cat(sprintf("    [0.6-0.8]: %d (%.1f%%)\n", bucket_60_80, 100 * bucket_60_80 / n_cells))
cat(sprintf("    [0.8-1.0]: %d (%.1f%%)\n", bucket_80_100, 100 * bucket_80_100 / n_cells))

# Weryfikacja rankingu: najmniejsza area powinna mieć najwyższy risk
min_area_idx <- which.min(gridcells_raw$area_m2)
max_area_idx <- which.max(gridcells_raw$area_m2)
cat(sprintf("  Weryfikacja rankingu:\n"))
cat(sprintf("    Najmniejsza area (%.0f m²): risk = %.4f (powinno być ~1.0)\n",
            gridcells_raw$area_m2[min_area_idx],
            gridcells_raw$spatial_risk[min_area_idx]))
cat(sprintf("    Największa area (%.0f m²): risk = %.4f (powinno być ~0.0)\n",
            gridcells_raw$area_m2[max_area_idx],
            gridcells_raw$spatial_risk[max_area_idx]))

# 6. ZAPIS DO BAZY — UPDATE spatial_risk

cat("\n[6] Aktualizacja spatial_risk w bazie...\n")

# Dodaj kolumnę jeśli nie istnieje
dbExecute(conn, "
  ALTER TABLE sightings_gridcell_voronoi
  ADD COLUMN IF NOT EXISTS spatial_risk DOUBLE PRECISION DEFAULT 0
")

# Aktualizuj wartości (batch update via temp table)
dbExecute(conn, "DROP TABLE IF EXISTS temp_inverse_area_risk")
dbExecute(conn, "
  CREATE TEMP TABLE temp_inverse_area_risk (
    id INTEGER PRIMARY KEY,
    spatial_risk DOUBLE PRECISION
  )
")

# Wstaw dane
risk_df <- data.frame(
  id = gridcells_raw$id,
  spatial_risk = gridcells_raw$spatial_risk
)
dbWriteTable(conn, "temp_inverse_area_risk", risk_df, append = TRUE, row.names = FALSE)

# Single UPDATE z JOIN
n_updated <- dbExecute(conn, "
  UPDATE sightings_gridcell_voronoi g
  SET spatial_risk = t.spatial_risk
  FROM temp_inverse_area_risk t
  WHERE g.id = t.id
")

dbExecute(conn, "DROP TABLE IF EXISTS temp_inverse_area_risk")

cat(sprintf("Zaktualizowano %d komórek.\n", n_updated))

# 7. ZAPIS METADANYCH DO analytics_spatial_result

cat("\n[7] Zapis metadanych modelu...\n")

# Utwórz tabelę jeśli nie istnieje
dbExecute(conn, "
  CREATE TABLE IF NOT EXISTS analytics_spatial_result (
    id SERIAL PRIMARY KEY,
    computed_at TIMESTAMP DEFAULT NOW(),
    model_type VARCHAR(20),
    n_cells INTEGER,
    rho DOUBLE PRECISION,
    lambda DOUBLE PRECISION,
    aic DOUBLE PRECISION,
    formula TEXT
  )
")

# Wstaw rekord
# model_type = 'INVERSE_AREA' (nowy typ!)
# rho/lambda/aic = NULL (nie dotyczy)
dbExecute(conn, sprintf("
  INSERT INTO analytics_spatial_result
    (model_type, n_cells, rho, lambda, aic, formula)
  VALUES ('INV_AREA_PCTL', %d, NULL, NULL, NULL, 'spatial_risk = percentile_rank(1 / relative_area)')
", n_cells))

cat("Metadane zapisane (model_type = 'INV_AREA_PCTL').\n")

# 8. WERYFIKACJA

cat("\n[8] Weryfikacja zapisu...\n")

verification <- dbGetQuery(conn, "
  SELECT
    COUNT(*) as n_cells,
    MIN(spatial_risk) as min_risk,
    MAX(spatial_risk) as max_risk,
    AVG(spatial_risk) as avg_risk,
    STDDEV(spatial_risk) as std_risk
  FROM sightings_gridcell_voronoi
")

cat(sprintf("  n_cells: %.0f\n", verification$n_cells))
cat(sprintf("  spatial_risk: min=%.4f, max=%.4f, avg=%.4f, std=%.4f\n",
            verification$min_risk,
            verification$max_risk,
            verification$avg_risk,
            verification$std_risk))

# KLUCZOWA WERYFIKACJA: std > 0 (mamy wariancję!)
if (verification$std_risk > 0) {
  cat("\n  ✅ SUKCES: spatial_risk ma wariancję (std > 0)!\n")
} else {
  cat("\n  ⚠️ UWAGA: spatial_risk nie ma wariancji (std = 0)!\n")
}

# 9. CLEANUP

dbDisconnect(conn)

cat("\n============================================================\n")
cat("NEW_03 ZAKOŃCZONY — INVERSE AREA RISK (PERCENTILE RANK)\n")
cat("============================================================\n")
cat(sprintf("Model: INV_AREA_PCTL (percentile rank normalization)\n"))
cat(sprintf("N cells: %d\n", n_cells))
cat(sprintf("spatial_risk: [%.4f, %.4f], mean=%.4f, std=%.4f\n",
            min(gridcells_raw$spatial_risk),
            max(gridcells_raw$spatial_risk),
            mean(gridcells_raw$spatial_risk),
            sd(gridcells_raw$spatial_risk)))
cat(sprintf("Oczekiwany rozkład: ~20%% w każdym przedziale [0-0.2], [0.2-0.4], ...\n"))
cat("============================================================\n")
cat("\nNastępny krok: uruchom 05_ensemble_prediction.R\n")
