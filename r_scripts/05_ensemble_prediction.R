#!/usr/bin/env Rscript
# =============================================================================
# 05_ensemble_prediction.R
# ETAP 6: Ensemble prediction
# Łączy ETA (gęstość) + SAR/SEM (proces przestrzenny) + density
# Wagi: 0.3*density + 0.4*spatial + 0.3*ETA
#
# CLEANUP 2026-01-18:
# - spatial_risk zastępuje gwr_risk (SAR/SEM z NEW_02)
# - COALESCE fallback dla kompatybilności wstecznej
# - Usuwa zależność od halucynacji eta_local/eta_weighted
# =============================================================================

library(DBI)
library(RPostgres)

cat("=== ETAP 6: Ensemble Prediction ===\n")

# Target table
TARGET_TABLE <- Sys.getenv("RESEARCH_TARGET_TABLE", "sightings_gridcell_voronoi")

.allowed_tables <- c("research_grid_500m", "sightings_gridcell_voronoi")
if (!TARGET_TABLE %in% .allowed_tables) {
  stop(sprintf("Invalid TARGET_TABLE: '%s'. Allowed: %s",
               TARGET_TABLE, paste(.allowed_tables, collapse = ", ")))
}

cat(sprintf("Target table: %s\n", TARGET_TABLE))

# ---- Parametr: use_population (command-line argument) ----
# Użycie: Rscript 05_ensemble_prediction.R true
# Domyślnie: false (używa spatial_risk)
# Jeśli true: używa spatial_risk_pop (korekta populacyjna z NEW_04)
args <- commandArgs(trailingOnly = TRUE)
use_population <- ifelse(length(args) >= 1, tolower(args[1]) == "true", FALSE)

if (use_population) {
  cat(">>> TRYB POPULACYJNY: używam spatial_risk_pop (z korektą populacyjną)\n")
} else {
  cat(">>> TRYB STANDARDOWY: używam spatial_risk (bez korekty populacyjnej)\n")
}

# -----------------------------------------------------------------------------
# 1. Polaczenie z baza
# -----------------------------------------------------------------------------
cat("Laczenie z baza danych...\n")

conn <- dbConnect(
  RPostgres::Postgres(),
  dbname = Sys.getenv("DB_NAME", "dziki_db"),
  host = "db",  # Bezposrednio do PostgreSQL
  port = 5432,
  user = Sys.getenv("DB_USER", "dziki_user"),
  password = Sys.getenv("DB_PASSWORD", "dziki_dev_password")
)

cat("Polaczono.\n")

# -----------------------------------------------------------------------------
# 2. Pobranie danych z GridCell
# -----------------------------------------------------------------------------
cat("Pobieranie danych z GridCell...\n")
# WAŻNE: Obliczamy area_proportion BEZPOŚREDNIO z geometrii!
# Spatial join w 02_compute_tessw_eta.R często zawodzi dla komórek przy krawędzi.
# Dynamiczny wybór kolumny spatial w zależności od trybu
if (use_population) {
  spatial_col_sql <- "COALESCE(spatial_risk_pop, model_fitted, spatial_risk, gwr_score, 0.5)"
  cat("  SQL spatial_score: COALESCE(spatial_risk_pop, model_fitted, spatial_risk, gwr_score, 0.5)\n")
} else {
  spatial_col_sql <- "COALESCE(model_fitted, spatial_risk, gwr_score, 0.5)"
  cat("  SQL spatial_score: COALESCE(model_fitted, spatial_risk, gwr_score, 0.5)\n")
}

query <- sprintf("
  WITH cell_areas AS (
    SELECT
      grid_id, sighting_count, eta_contribution,
      %s AS spatial_score,
      ST_X(centroid) as centroid_x, ST_Y(centroid) as centroid_y,
      ST_Area(geometry::geography) as cell_area_m2
    FROM %s
    WHERE centroid IS NOT NULL
  ),
  total_area AS (SELECT SUM(cell_area_m2) as sum_area FROM cell_areas)
  SELECT c.*, c.cell_area_m2 / NULLIF(t.sum_area, 0) as area_proportion
  FROM cell_areas c, total_area t
", spatial_col_sql, TARGET_TABLE)

gridcells <- dbGetQuery(conn, query)

n_cells <- nrow(gridcells)
cat(sprintf("Pobrano %d cells.\n", n_cells))

# -----------------------------------------------------------------------------
# 3. Obliczenie GĘSTOŚCI OBSERWACJI (główny predyktor!)
# -----------------------------------------------------------------------------
cat("Obliczanie gestosci obserwacji...\n")

# KLUCZOWE: gestosc = sighting_count / area_proportion
# area_proportion to udzial komorki w calkowitej powierzchni
# Wieksza gestosc = wiecej obserwacji na jednostke powierzchni = wyzsze ryzyko

gridcells$density <- gridcells$sighting_count / (gridcells$area_proportion + 0.0001)

# PERCENTILE RANK normalizacja gestosci do 0-1 (v2.0)
# Zmiana z min-max na percentile rank - unika problemu outliers
n_cells <- nrow(gridcells)
if (n_cells > 1) {
  density_rank <- rank(gridcells$density, ties.method = "average", na.last = "keep")
  gridcells$density_score <- (density_rank - 1) / (n_cells - 1)
} else {
  gridcells$density_score <- 0.5
}

cat(sprintf("  Density: min=%.2f, max=%.2f (PERCENTILE RANK)\n",
            min(gridcells$density, na.rm=TRUE), max(gridcells$density, na.rm=TRUE)))
cat(sprintf("  Cells with 0 sightings: %d\n", sum(gridcells$sighting_count == 0)))

# ETA score: bazowany na area_proportion z teselacji Voronoi
# Mniejsze kafelki = większe skupienie = wyższe ryzyko
# PERCENTILE RANK (v2.0) - odwrócony: mały area = wysoki rank = wysoki score
if (any(gridcells$area_proportion > 0, na.rm = TRUE) && n_cells > 1) {
  # Rank area_proportion: mały area = rank 1, duży area = rank n
  area_rank <- rank(gridcells$area_proportion, ties.method = "average", na.last = "keep")
  # Odwróć: mały area (rank 1) -> score ~1, duży area (rank n) -> score ~0
  gridcells$area_rank_score <- 1 - (area_rank - 1) / (n_cells - 1)
  cat("  area_rank_score z area_proportion (PERCENTILE RANK, mniejszy kafelek = wyższe ryzyko)\n")
} else {
  gridcells$area_rank_score <- 0.5
  cat("  Brak danych area_rank - default 0.5\n")
}

# Spatial score: z NEW_03 (PERCENTILE RANK) - już znormalizowane!
# NIE re-normalizujemy - spatial_risk jest już w [0,1] z percentile rank
gridcells$spatial_score_final <- gridcells$spatial_score
gridcells$spatial_score_final[is.na(gridcells$spatial_score_final)] <- 0.5
# v2.0: Usunięto min-max re-normalizację - spatial_risk jest już percentile rank
cat(sprintf("  Spatial score (z NEW_03 percentile rank): min=%.3f, max=%.3f\n",
            min(gridcells$spatial_score_final, na.rm=TRUE),
            max(gridcells$spatial_score_final, na.rm=TRUE)))
# spatial_score_final już ustawione powyżej (bez re-normalizacji)

# -----------------------------------------------------------------------------
# 4. Obliczenie ensemble
#
# Wagi:
# - 30% density (gęstość obserwacji per cell)
# - 40% spatial (SAR/SEM z NEW_02_spatial_models.R)
# - 30% ETA (clustering z area_proportion)
# -----------------------------------------------------------------------------
cat("Obliczanie ensemble prediction...\n")

W_DENSITY <- 0.30   # 30% - gęstość obserwacji
W_SPATIAL <- 0.40   # 40% - SAR/SEM spatial trend
W_ETA <- 0.30       # 30% - clustering pattern

cat(sprintf("Wagi: %.0f%% density + %.0f%% spatial + %.0f%% ETA\n",
            W_DENSITY*100, W_SPATIAL*100, W_ETA*100))

# Ensemble prediction
gridcells$ensemble_risk <- W_DENSITY * gridcells$density_score +
                           W_SPATIAL * gridcells$spatial_score_final +
                           W_ETA * gridcells$area_rank_score

# Confidence: bazowane na liczbie obserwacji w komorce
# Wiecej obserwacji = wyzsza pewnosc predykcji
max_sightings <- max(gridcells$sighting_count, na.rm = TRUE)
if (max_sightings > 0) {
  gridcells$confidence <- gridcells$sighting_count / max_sightings
} else {
  gridcells$confidence <- 0
}
# Minimum confidence 0.1 dla komórek z obserwacjami
gridcells$confidence[gridcells$sighting_count > 0] <-
  pmax(gridcells$confidence[gridcells$sighting_count > 0], 0.1)

# -----------------------------------------------------------------------------
# 4a. PROXIMITY FACTOR - tłumienie ryzyka dla komórek daleko od obserwacji
#
# Problem: GWR predykuje wysokie ryzyko na podstawie środowiska,
# nawet gdy nie ma żadnych obserwacji w pobliżu.
#
# Rozwiązanie: Waga odwrotnie proporcjonalna do odległości od obserwacji
# proximity_weight = 1 / (1 + dist_to_nearest_sighting / DECAY_DISTANCE)
#
# DECAY_DISTANCE = 200m - ryzyko spada o połowę co 200m od obserwacji
# -----------------------------------------------------------------------------
cat("\nObliczanie proximity factor...\n")

DECAY_DISTANCE <- 200  # metry - parametr tłumienia

# Komórki z obserwacjami (źródła)
cells_with_sightings <- gridcells[gridcells$sighting_count > 0, ]
n_sources <- nrow(cells_with_sightings)
cat(sprintf("  Źródła (cells with sightings): %d\n", n_sources))

if (n_sources > 0) {
  # Współrzędne źródeł (EPSG:4326, stopnie)
  source_coords <- as.matrix(cells_with_sightings[, c("centroid_x", "centroid_y")])

  # Dla każdej komórki oblicz odległość do najbliższej obserwacji
  # Używamy przybliżenia: 1 stopień ≈ 111km (dla szerokości geograficznej Polski)
  DEG_TO_M <- 111000  # przybliżenie dla lat ~52°

  gridcells$dist_to_nearest_sighting <- sapply(seq_len(nrow(gridcells)), function(i) {
    cell_x <- gridcells$centroid_x[i]
    cell_y <- gridcells$centroid_y[i]

    # Odległości do wszystkich źródeł (w metrach, przybliżone)
    dx <- (source_coords[, 1] - cell_x) * DEG_TO_M * cos(cell_y * pi / 180)
    dy <- (source_coords[, 2] - cell_y) * DEG_TO_M
    dists <- sqrt(dx^2 + dy^2)

    min(dists)
  })

  # Proximity weight: 1/(1 + d/DECAY_DISTANCE)
  # d=0 → weight=1.0 (pełne ryzyko)
  # d=200 → weight=0.5 (połowa ryzyka)
  # d=400 → weight=0.33
  # d=1000 → weight=0.17
  gridcells$proximity_weight <- 1 / (1 + gridcells$dist_to_nearest_sighting / DECAY_DISTANCE)

  # Zastosuj proximity weight do ensemble_risk
  gridcells$ensemble_risk_raw <- gridcells$ensemble_risk  # zachowaj oryginał
  gridcells$ensemble_risk <- gridcells$ensemble_risk * gridcells$proximity_weight

  cat(sprintf("  Dist to nearest sighting: min=%.0fm, max=%.0fm, mean=%.0fm\n",
              min(gridcells$dist_to_nearest_sighting),
              max(gridcells$dist_to_nearest_sighting),
              mean(gridcells$dist_to_nearest_sighting)))
  cat(sprintf("  Proximity weight: min=%.3f, max=%.3f, mean=%.3f\n",
              min(gridcells$proximity_weight),
              max(gridcells$proximity_weight),
              mean(gridcells$proximity_weight)))
  cat(sprintf("  Risk reduction: %.1f%% średnio\n",
              100 * (1 - mean(gridcells$ensemble_risk) / mean(gridcells$ensemble_risk_raw))))
} else {
  cat("  UWAGA: Brak obserwacji - proximity factor nie zastosowany.\n")
  gridcells$dist_to_nearest_sighting <- NA
  gridcells$proximity_weight <- 1.0
  gridcells$ensemble_risk_raw <- gridcells$ensemble_risk
}

# Statystyki
cat(sprintf("\nStatystyki ensemble (po proximity factor):\n"))
cat(sprintf("  Density score: min=%.3f, max=%.3f, mean=%.3f\n",
            min(gridcells$density_score, na.rm = TRUE),
            max(gridcells$density_score, na.rm = TRUE),
            mean(gridcells$density_score, na.rm = TRUE)))
cat(sprintf("  area_rank_score: min=%.3f, max=%.3f, mean=%.3f\n",
            min(gridcells$area_rank_score, na.rm = TRUE),
            max(gridcells$area_rank_score, na.rm = TRUE),
            mean(gridcells$area_rank_score, na.rm = TRUE)))
cat(sprintf("  Spatial score: min=%.3f, max=%.3f, mean=%.3f\n",
            min(gridcells$spatial_score_final, na.rm = TRUE),
            max(gridcells$spatial_score_final, na.rm = TRUE),
            mean(gridcells$spatial_score_final, na.rm = TRUE)))
cat(sprintf("  Ensemble:  min=%.3f, max=%.3f, mean=%.3f\n",
            min(gridcells$ensemble_risk, na.rm = TRUE),
            max(gridcells$ensemble_risk, na.rm = TRUE),
            mean(gridcells$ensemble_risk, na.rm = TRUE)))
cat(sprintf("  Confidence: min=%.3f, max=%.3f, mean=%.3f\n",
            min(gridcells$confidence, na.rm = TRUE),
            max(gridcells$confidence, na.rm = TRUE),
            mean(gridcells$confidence, na.rm = TRUE)))

# -----------------------------------------------------------------------------
# 5. Zapis do bazy
# -----------------------------------------------------------------------------
cat("\nZapisywanie do bazy...\n")

# Dodaj kolumny jesli nie istnieja (w tym proximity_weight)
dbExecute(conn, sprintf("
  ALTER TABLE %s
  ADD COLUMN IF NOT EXISTS area_rank_score DOUBLE PRECISION DEFAULT 0,
  ADD COLUMN IF NOT EXISTS gwr_score DOUBLE PRECISION DEFAULT 0,
  ADD COLUMN IF NOT EXISTS ensemble_risk DOUBLE PRECISION DEFAULT 0,
  ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION DEFAULT 0.5,
  ADD COLUMN IF NOT EXISTS proximity_weight DOUBLE PRECISION DEFAULT 1.0
", TARGET_TABLE))

# Aktualizacja przez temp table i batch update
dbExecute(conn, "DROP TABLE IF EXISTS temp_ensemble_scores")
dbExecute(conn, "
  CREATE TEMP TABLE temp_ensemble_scores (
    grid_id TEXT PRIMARY KEY,
    area_rank_score DOUBLE PRECISION,
    gwr_score DOUBLE PRECISION,
    ensemble_risk DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    proximity_weight DOUBLE PRECISION
  )
")

# Batch insert do temp table (z proximity_weight)
# UWAGA: gwr_score zachowujemy dla kompatybilności z API (= spatial_score_final)
scores_df <- data.frame(
  grid_id = gridcells$grid_id,
  area_rank_score = gridcells$area_rank_score,
  gwr_score = gridcells$spatial_score_final,  # backwards compat alias
  ensemble_risk = gridcells$ensemble_risk,
  confidence = gridcells$confidence,
  proximity_weight = gridcells$proximity_weight
)
dbWriteTable(conn, "temp_ensemble_scores", scores_df, append = TRUE, row.names = FALSE)

# Single UPDATE z JOIN
dbExecute(conn, sprintf("
  UPDATE %s g
  SET
    area_rank_score = t.area_rank_score,
    gwr_score = t.gwr_score,
    ensemble_risk = t.ensemble_risk,
    confidence = t.confidence,
    proximity_weight = t.proximity_weight
  FROM temp_ensemble_scores t
  WHERE g.grid_id = t.grid_id
", TARGET_TABLE))

dbExecute(conn, "DROP TABLE IF EXISTS temp_ensemble_scores")

cat(sprintf("Zaktualizowano %d cells.\n", nrow(gridcells)))

# Zapis podsumowania
dbExecute(conn, "
  CREATE TABLE IF NOT EXISTS analytics_ensemble_result (
    id SERIAL PRIMARY KEY,
    computed_at TIMESTAMP DEFAULT NOW(),
    n_cells INTEGER,
    w_density DOUBLE PRECISION,
    w_eta DOUBLE PRECISION,
    w_gwr DOUBLE PRECISION,
    mean_ensemble DOUBLE PRECISION,
    mean_confidence DOUBLE PRECISION
  )
")

dbExecute(conn, sprintf("
  INSERT INTO analytics_ensemble_result
    (n_cells, w_density, w_eta, w_gwr, mean_ensemble, mean_confidence)
  VALUES (%d, %.2f, %.2f, %.2f, %.6f, %.6f)
", n_cells, W_DENSITY, W_ETA, W_SPATIAL,  # w_gwr column zachowane dla kompatybilności
   mean(gridcells$ensemble_risk, na.rm = TRUE),
   mean(gridcells$confidence, na.rm = TRUE)))

cat(sprintf("Ensemble weights: density=%.0f%%, spatial=%.0f%%, ETA=%.0f%%\n",
            W_DENSITY*100, W_SPATIAL*100, W_ETA*100))

# -----------------------------------------------------------------------------
# 6. Cleanup
# -----------------------------------------------------------------------------
dbDisconnect(conn)

cat("\n=== ETAP 6 ZAKONCZONY ===\n")
cat(sprintf("Ensemble: %d cells, mean risk=%.3f, mean confidence=%.3f\n",
            n_cells,
            mean(gridcells$ensemble_risk, na.rm = TRUE),
            mean(gridcells$confidence, na.rm = TRUE)))
