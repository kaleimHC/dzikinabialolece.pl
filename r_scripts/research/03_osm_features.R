#!/usr/bin/env Rscript
# 03_osm_features.R
# Obliczenie predyktorow srodowiskowych (OSM) dla kafli Voronoi
#
# Predyktory powierzchniowe (% pokrycia):
#   forest_cover, building_density, park_cover, meadow_cover,
#   farmland_cover, allotment_cover, scrub_cover
#
# Predyktory liniowe (km / km²):
#   road_density, barrier_resistance
#
# Predyktory odleglosciowe (metry):
#   distance_to_water
#
# Input:  sightings_gridcell_voronoi + tabele osm_*
# Output: UPDATE sightings_gridcell_voronoi SET <predictor> = ...
#
# ENV vars:
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
#   RESEARCH_TARGET_TABLE       (default: sightings_gridcell_voronoi)
#   RESEARCH_ACTIVE_PREDICTORS  (comma-separated, empty = all)

library(DBI)
library(RPostgres)

cat("============================================================\n")
cat("03_osm_features.R — Predyktory srodowiskowe OSM\n")
cat("============================================================\n")

# 1. Parametry z ENV

TARGET_TABLE <- Sys.getenv("RESEARCH_TARGET_TABLE", "sightings_gridcell_voronoi")
active_predictors_raw <- Sys.getenv("RESEARCH_ACTIVE_PREDICTORS", "")

# Validate TARGET_TABLE against allowlist — prevents injection if env is compromised
.allowed_tables <- c("research_grid_500m", "sightings_gridcell_voronoi", "sightings_gridcell_research")
if (!TARGET_TABLE %in% .allowed_tables) {
  stop(sprintf("Invalid TARGET_TABLE: '%s'. Allowed: %s",
               TARGET_TABLE, paste(.allowed_tables, collapse = ", ")))
}

cat(sprintf("Target table: %s\n", TARGET_TABLE))

# All available predictors
ALL_PREDICTORS <- c(
  "forests", "buildings", "roads", "water", "parks",
  "meadow", "farmland", "allotments", "scrub", "railway", "barriers"
)

# Parse active predictors
if (nchar(trimws(active_predictors_raw)) == 0) {
  predictors_to_run <- ALL_PREDICTORS
  cat("ACTIVE_PREDICTORS: (puste) -> obliczam WSZYSTKIE\n")
} else {
  predictors_to_run <- trimws(strsplit(active_predictors_raw, ",")[[1]])
  predictors_to_run <- predictors_to_run[predictors_to_run %in% ALL_PREDICTORS]
  cat(sprintf("ACTIVE_PREDICTORS: %s\n", paste(predictors_to_run, collapse = ", ")))
}

if (length(predictors_to_run) == 0) {
  cat("UWAGA: Brak predyktorow do obliczenia. Koniec.\n")
  quit(status = 0)
}

# 2. Definicje predyktorow
# Trzy typy obliczen:
#   "area"     — % powierzchni kafla pokrytej obiektem (polygon layers)
#   "line"     — km linii / km² kafla (line layers)
#   "distance" — odleglosc centroidu do najblizszego obiektu (m)

PREDICTOR_DEFS <- list(
  forests = list(
    osm_table  = "osm_forests",
    column     = "forest_cover",
    type       = "area"
  ),
  buildings = list(
    osm_table  = "osm_buildings",
    column     = "building_density",
    type       = "area"
  ),
  parks = list(
    osm_table  = "osm_parks",
    column     = "park_cover",
    type       = "area"
  ),
  meadow = list(
    osm_table  = "osm_meadow",
    column     = "meadow_cover",
    type       = "area"
  ),
  farmland = list(
    osm_table  = "osm_farmland",
    column     = "farmland_cover",
    type       = "area"
  ),
  allotments = list(
    osm_table  = "osm_allotments",
    column     = "allotment_cover",
    type       = "area"
  ),
  scrub = list(
    osm_table  = "osm_scrub",
    column     = "scrub_cover",
    type       = "area"
  ),
  roads = list(
    osm_table  = "osm_roads",
    column     = "road_density",
    type       = "line"
  ),
  railway = list(
    osm_table  = "osm_railway",
    column     = "railway_density",
    type       = "line"
  ),
  barriers = list(
    osm_table  = "osm_barriers",
    column     = "barrier_resistance",
    type       = "line"
  ),
  water = list(
    osm_table  = "osm_water",
    column     = "distance_to_water",
    type       = "distance"
  )
)

# 3. Polaczenie z baza

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

# 4. Walidacja: czy sa kafle Voronoi?

n_voronoi <- as.integer(dbGetQuery(conn,
  sprintf("SELECT COUNT(*) as n FROM %s WHERE geometry IS NOT NULL", TARGET_TABLE)
)$n)

cat(sprintf("\n[2] Kafli Voronoi: %d\n", n_voronoi))

if (n_voronoi == 0) {
  cat("BLAD: Brak kafli Voronoi. Uruchom najpierw krok 01_geometry.\n")
  quit(status = 1)
}

# 5. Ensure columns exist (railway_density may be missing)

cat("\n[3] Sprawdzanie kolumn...\n")

dbExecute(conn, sprintf("
  ALTER TABLE %s
  ADD COLUMN IF NOT EXISTS railway_density DOUBLE PRECISION DEFAULT 0
", TARGET_TABLE))

# 6. SQL templates

# Template: area coverage (polygon layers)
# Cover = sum(intersection area) / cell area
sql_area <- function(osm_table, column, target_table) {
  sprintf("
    UPDATE %s gc
    SET %s = COALESCE(subq.val, 0)
    FROM (
      SELECT
        gc2.id,
        SUM(ST_Area(ST_Intersection(gc2.geometry, osm.geom)::geography)) /
            NULLIF(ST_Area(gc2.geometry::geography), 0) AS val
      FROM %s gc2
      LEFT JOIN %s osm ON ST_Intersects(gc2.geometry, osm.geom)
      GROUP BY gc2.id
    ) subq
    WHERE gc.id = subq.id
  ", target_table, column, target_table, osm_table)
}

# Template: line density (line layers)
# Density = total_length_km / cell_area_km2
sql_line <- function(osm_table, column, target_table) {
  sprintf("
    UPDATE %s gc
    SET %s = COALESCE(subq.val, 0)
    FROM (
      SELECT
        gc2.id,
        SUM(ST_Length(ST_Intersection(gc2.geometry, osm.geom)::geography)) / 1000.0 /
            NULLIF(ST_Area(gc2.geometry::geography) / 1000000.0, 0) AS val
      FROM %s gc2
      LEFT JOIN %s osm ON ST_Intersects(gc2.geometry, osm.geom)
      GROUP BY gc2.id
    ) subq
    WHERE gc.id = subq.id
  ", target_table, column, target_table, osm_table)
}

# Template: distance to nearest feature (meters)
sql_distance <- function(osm_table, column, target_table) {
  sprintf("
    UPDATE %s gc
    SET %s = COALESCE(subq.val, 9999)
    FROM (
      SELECT
        gc2.id,
        MIN(ST_Distance(gc2.centroid::geography, osm.geom::geography)) AS val
      FROM %s gc2
      CROSS JOIN %s osm
      GROUP BY gc2.id
    ) subq
    WHERE gc.id = subq.id
  ", target_table, column, target_table, osm_table)
}

# 7. Oblicz predyktory

cat("\n[4] Obliczanie predyktorow...\n\n")

results <- list()
total_time <- proc.time()

for (pred_name in predictors_to_run) {
  def <- PREDICTOR_DEFS[[pred_name]]

  if (is.null(def)) {
    cat(sprintf("  UWAGA: Nieznany predyktor '%s' — pomijam.\n", pred_name))
    next
  }

  cat(sprintf("  [%s] %s (%s -> %s)...",
              pred_name, def$type, def$osm_table, def$column))

  # Check if OSM table exists and has data
  table_check <- tryCatch({
    as.integer(dbGetQuery(conn, sprintf(
      "SELECT COUNT(*) as n FROM %s LIMIT 1", def$osm_table
    ))$n)
  }, error = function(e) {
    cat(sprintf(" BLAD tabeli: %s\n", e$message))
    -1
  })

  if (table_check < 0) {
    results[[pred_name]] <- list(status = "error", message = "table not found")
    next
  }
  if (table_check == 0) {
    cat(sprintf(" pusta tabela (%d rows) — ustawiam 0.\n", table_check))
    dbExecute(conn, sprintf(
      "UPDATE %s SET %s = 0", TARGET_TABLE, def$column
    ))
    results[[pred_name]] <- list(status = "empty", rows = 0)
    next
  }

  # Build and execute SQL
  t0 <- proc.time()

  sql <- switch(def$type,
    "area"     = sql_area(def$osm_table, def$column, TARGET_TABLE),
    "line"     = sql_line(def$osm_table, def$column, TARGET_TABLE),
    "distance" = sql_distance(def$osm_table, def$column, TARGET_TABLE)
  )

  n_updated <- tryCatch({
    dbExecute(conn, sql)
  }, error = function(e) {
    cat(sprintf(" BLAD SQL: %s\n", e$message))
    -1
  })

  elapsed <- (proc.time() - t0)["elapsed"]

  if (n_updated < 0) {
    results[[pred_name]] <- list(status = "error", duration = elapsed)
    next
  }

  # Get stats for this predictor
  stats <- dbGetQuery(conn, sprintf("
    SELECT
      MIN(%s) as val_min,
      MAX(%s) as val_max,
      AVG(%s) as val_avg,
      COUNT(*) FILTER (WHERE %s > 0) as n_nonzero
    FROM %s
  ", def$column, def$column, def$column, def$column, TARGET_TABLE))

  cat(sprintf(" OK %.1fs  min=%.4f max=%.4f avg=%.4f nonzero=%d/%d\n",
              elapsed,
              stats$val_min, stats$val_max, stats$val_avg,
              as.integer(stats$n_nonzero), n_voronoi))

  results[[pred_name]] <- list(
    status   = "success",
    duration = elapsed,
    min      = stats$val_min,
    max      = stats$val_max,
    avg      = stats$val_avg,
    nonzero  = as.integer(stats$n_nonzero)
  )
}

# Update timestamp
dbExecute(conn, sprintf("UPDATE %s SET updated_at = NOW()", TARGET_TABLE))

total_elapsed <- (proc.time() - total_time)["elapsed"]

# 8. Podsumowanie

cat("\n============================================================\n")
cat("PODSUMOWANIE\n")
cat("============================================================\n")

n_success <- sum(sapply(results, function(r) r$status == "success"))
n_empty   <- sum(sapply(results, function(r) r$status == "empty"))
n_error   <- sum(sapply(results, function(r) r$status == "error"))

cat(sprintf("Predyktorow: %d requested, %d success, %d empty, %d error\n",
            length(predictors_to_run), n_success, n_empty, n_error))
cat(sprintf("Czas calkowity: %.1f s\n", total_elapsed))

cat("\nWyniki per predyktor:\n")
for (name in names(results)) {
  r <- results[[name]]
  if (r$status == "success") {
    cat(sprintf("  %-20s OK  min=%.4f  max=%.4f  avg=%.4f  nonzero=%d\n",
                name, r$min, r$max, r$avg, r$nonzero))
  } else if (r$status == "empty") {
    cat(sprintf("  %-20s EMPTY (tabela pusta, ustawiono 0)\n", name))
  } else {
    cat(sprintf("  %-20s ERROR\n", name))
  }
}

# Exit with error if any predictor failed (not empty — empty is ok)
if (n_error > 0) {
  cat(sprintf("\nBLAD: %d predyktorow zawiodlo.\n", n_error))
  quit(status = 1)
}

cat("\n============================================================\n")
cat("03_osm_features ZAKONCZONY POMYSLNIE\n")
cat("============================================================\n")
