#!/usr/bin/env Rscript
# 05_ensemble_prediction.R
# ETAP 6: Ensemble prediction
#
# PUB mode (TARGET_TABLE=sightings_gridcell_voronoi):
#   model_fitted=0 → COALESCE falls through to spatial_risk = PERCENTILE_RANK(1/area)
#   density_score ≈ area_rank_score ≈ spatial_score (all = PERCENTILE_RANK(1/area))
#   ensemble_risk = 0.30×S + 0.40×S + 0.30×S = 1.0×PERCENTILE_RANK(1/area)  (measured corr=1.000000)
#   proximity_weight = 1.0 constant → not written (column dropped in migration)
#
# RESEARCH mode (TARGET_TABLE=research_grid_500m or sightings_gridcell_research):
#   spatial_score = model_fitted from SAR/SEM (non-zero, independent signal)
#   ensemble_risk = 0.30×density + 0.40×model_fitted + 0.30×area_rank, modulated by proximity_weight


library(DBI)
library(RPostgres)

cat("=== ETAP 6: Ensemble Prediction ===\n")

# Target table
TARGET_TABLE <- Sys.getenv("RESEARCH_TARGET_TABLE", "sightings_gridcell_voronoi")

.allowed_tables <- c("research_grid_500m", "sightings_gridcell_voronoi", "sightings_gridcell_research")
if (!TARGET_TABLE %in% .allowed_tables) {
  stop(sprintf("Invalid TARGET_TABLE: '%s'. Allowed: %s",
               TARGET_TABLE, paste(.allowed_tables, collapse = ", ")))
}

cat(sprintf("Target table: %s\n", TARGET_TABLE))

is_pub_voronoi <- (TARGET_TABLE == "sightings_gridcell_voronoi")
if (is_pub_voronoi) {
  cat(">>> PUB mode: spatial_score = PERCENTILE_RANK(1/area) [corr z area_rank = 1.000000, zmierzone]\n")
  cat(">>> PUB mode: density ≈ area_rank ≈ spatial → ensemble = 1×PERCENTILE_RANK(1/area)\n")
  cat(">>> PUB mode: proximity_weight = 1.0 (stała) — pomijam zapis (kolumna usunięta migracją)\n")
}

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

# 1. Polaczenie z baza
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

# 2. Pobranie danych z GridCell
cat("Pobieranie danych z GridCell...\n")
# WAŻNE: Obliczamy area_proportion BEZPOŚREDNIO z geometrii!
# Spatial join w 02_compute_tessw_eta.R często zawodzi dla komórek przy krawędzi.
# Dynamiczny wybór kolumny spatial w zależności od trybu
# NULLIF(model_fitted, 0): column default is 0 (not NULL).
# In RESEARCH, SAR/SEM fills it with non-zero values — NULLIF is a no-op.
# In PUB, model_fitted stays at default 0 → NULLIF converts to NULL
# so COALESCE falls through to spatial_risk (area-rank from 03_inverse_area_risk.R).
if (use_population) {
  spatial_col_sql <- "GREATEST(0, LEAST(1, COALESCE(spatial_risk_pop, NULLIF(model_fitted, 0), spatial_risk, gwr_score, 0.5)))"
  cat("  SQL spatial_score: GREATEST(0,LEAST(1,COALESCE(spatial_risk_pop,NULLIF(model_fitted,0),spatial_risk,gwr_score,0.5)))\n")
} else {
  # D-09: clamp to [0,1] — spatial_risk in RESEARCH is raw Y (log_pop, range ~-9..0);
  # the cell with model_fitted=0 (min of min-max normalisation) falls through to negative spatial_risk.
  # GREATEST/LEAST guarantees [0,1] for both PUB (spatial_risk already in [0,1]) and RESEARCH.
  spatial_col_sql <- "GREATEST(0, LEAST(1, COALESCE(NULLIF(model_fitted, 0), spatial_risk, gwr_score, 0.5)))"
  cat("  SQL spatial_score: GREATEST(0,LEAST(1,COALESCE(NULLIF(model_fitted,0),spatial_risk,gwr_score,0.5)))\n")
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

# 3. Obliczenie GĘSTOŚCI OBSERWACJI (główny predyktor!)
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
cat(sprintf("  Spatial score (z 03 percentile rank): min=%.3f, max=%.3f\n",
            min(gridcells$spatial_score_final, na.rm=TRUE),
            max(gridcells$spatial_score_final, na.rm=TRUE)))
# spatial_score_final już ustawione powyżej (bez re-normalizacji)

# 4. Obliczenie ensemble
#
# Wagi:
# - 30% density (gęstość obserwacji per cell)
# - 40% spatial (SAR/SEM z NEW_02_spatial_models.R)
# - 30% ETA (clustering z area_proportion)
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
