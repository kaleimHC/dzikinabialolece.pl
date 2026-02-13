#!/usr/bin/env Rscript
# 02_population.R
# Obliczenie populacji dla kafli grid metoda punktow populacyjnych
# (Kopczewska: 1 punkt = 100 osob)
#
# Input:  TARGET_TABLE (kafle z kroku 01_geometry)
#         gus_population_grid_500m   (gridy GUS z populacja)
# Output: UPDATE TARGET_TABLE SET population = ...
#
# ENV vars:
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
#   RESEARCH_TARGET_TABLE       (default: sightings_gridcell_voronoi)
#   RESEARCH_POPULATION_METHOD  (only "points" supported)
#   RESEARCH_SEED               (for reproducibility)

library(sf)
library(DBI)
library(RPostgres)

cat("============================================================\n")
cat("02_population.R — Populacja dla kafli\n")
cat("============================================================\n")

# 1. Parametry z ENV

TARGET_TABLE <- Sys.getenv("RESEARCH_TARGET_TABLE", "sightings_gridcell_voronoi")

# Validate TARGET_TABLE against allowlist — prevents injection if env is compromised
.allowed_tables <- c("research_grid_500m", "sightings_gridcell_voronoi")
if (!TARGET_TABLE %in% .allowed_tables) {
  stop(sprintf("Invalid TARGET_TABLE: '%s'. Allowed: %s",
               TARGET_TABLE, paste(.allowed_tables, collapse = ", ")))
}

population_method <- Sys.getenv("RESEARCH_POPULATION_METHOD", "points")
seed_val <- as.integer(Sys.getenv("RESEARCH_SEED", "42"))

cat(sprintf("Target table: %s\n", TARGET_TABLE))
cat(sprintf("Metoda: %s\n", population_method))
cat(sprintf("Seed: %d\n", seed_val))

# Valid methods: points (Voronoi), spatial_join (GUS-aligned grids)
if (!(population_method %in% c("points", "spatial_join"))) {
  cat(sprintf("BLAD: Metoda '%s' nie jest zaimplementowana. Dostepne: 'points', 'spatial_join'.\n",
              population_method))
  quit(status = 1)
}

set.seed(seed_val)

# 2. Polaczenie z baza

cat("\n[1] Laczenie z baza danych...\n")

conn <- dbConnect(
  RPostgres::Postgres(),
  dbname = Sys.getenv("DB_NAME", "dziki_db"),
  host = Sys.getenv("DB_HOST", "db"),
  port = as.integer(Sys.getenv("DB_PORT", "5432")),
  user = Sys.getenv("DB_USER", "dziki"),
  password = Sys.getenv("DB_PASSWORD", "dziki_dev_password")
)

cat("Polaczono.\n")

# Cleanup on exit
on.exit({
  if (exists("conn") && dbIsValid(conn)) dbDisconnect(conn)
}, add = TRUE)

# SPATIAL_JOIN METHOD: Population already set from GUS in 01_geometry
if (population_method == "spatial_join") {
  cat("\n[SPATIAL_JOIN] Populacja juz ustawiona w kroku 01_geometry (GUS direct)\n")

  # Verify population is set
  verify <- dbGetQuery(conn, sprintf("
    SELECT
      COUNT(*) as total,
      COUNT(*) FILTER (WHERE population > 0) as with_pop,
      COUNT(*) FILTER (WHERE population = 0 OR population IS NULL) as no_pop,
      MIN(population)::int as pop_min,
      MAX(population)::int as pop_max,
      ROUND(AVG(population))::int as pop_avg,
      SUM(population)::int as pop_sum
    FROM %s
  ", TARGET_TABLE))

  cat(sprintf("  Kafli: %d\n", as.integer(verify$total)))
  cat(sprintf("  Z populacja > 0: %d (%.1f%%)\n",
              as.integer(verify$with_pop), 100.0 * verify$with_pop / verify$total))
  cat(sprintf("  Bez populacji: %d\n", as.integer(verify$no_pop)))
  cat(sprintf("  Population: min=%d, max=%d, avg=%d, sum=%d\n",
              as.integer(verify$pop_min), as.integer(verify$pop_max),
              as.integer(verify$pop_avg), as.integer(verify$pop_sum)))

  if (verify$no_pop > 0) {
    cat("\n[WARNING] Ustawiam population=1 dla kafli bez populacji...\n")
    dbExecute(conn, sprintf("
      UPDATE %s SET population = 1 WHERE population = 0 OR population IS NULL
    ", TARGET_TABLE))
    cat(sprintf("  Zaktualizowano %.0f kafli.\n", verify$no_pop))
  }

  cat("\n============================================================\n")
  cat("02_population ZAKONCZONY (spatial_join: populacja z GUS)\n")
  cat("============================================================\n")
  quit(status = 0)
}

# POINTS METHOD: Original implementation for Voronoi

# 3. Wczytaj kafle

cat(sprintf("\n[2] Pobieranie kafli z %s...\n", TARGET_TABLE))

voronoi_raw <- dbGetQuery(conn, sprintf("
  SELECT id, grid_id, ST_AsText(geometry) as wkt
  FROM %s
  WHERE geometry IS NOT NULL
  ORDER BY id
", TARGET_TABLE))

n_voronoi <- nrow(voronoi_raw)
cat(sprintf("Pobrano %d kafli.\n", n_voronoi))

if (n_voronoi == 0) {
  cat("BLAD: Brak kafli. Uruchom najpierw krok 01_geometry.\n")
  quit(status = 1)
}

voronoi_sf <- st_as_sf(voronoi_raw, wkt = "wkt", crs = 4326)
voronoi_sf <- st_make_valid(voronoi_sf)

# 4. Wczytaj gridy GUS 500m

cat("\n[3] Pobieranie gridow GUS 500m...\n")

gus_raw <- dbGetQuery(conn, "
  SELECT id, code, tot, ST_AsText(geom) as wkt
  FROM gus_population_grid_500m
  WHERE tot > 0
    AND geom IS NOT NULL
")

n_gus <- nrow(gus_raw)
cat(sprintf("Pobrano %d gridow GUS z populacja > 0.\n", n_gus))

if (n_gus == 0) {
  cat("BLAD: Brak danych populacyjnych GUS. Tabela gus_population_grid_500m pusta.\n")
  quit(status = 1)
}

gus_sf <- st_as_sf(gus_raw, wkt = "wkt", crs = 4326)
gus_sf <- st_make_valid(gus_sf)

cat(sprintf("Populacja GUS: min=%d, max=%d, sum=%d\n",
            min(gus_raw$tot), max(gus_raw$tot), sum(gus_raw$tot)))

# 5. Generuj punkty populacyjne (metoda Kopczewskiej)
# Kazda komorka GUS generuje floor(population / 100) punktow
# 1 punkt = 100 osob

cat("\n[4] Generowanie punktow populacyjnych (1 punkt = 100 osob)...\n")

points_list <- list()
total_points <- 0
skipped_cells <- 0

for (i in seq_len(n_gus)) {
  pop <- gus_sf$tot[i]
  n_points <- floor(pop / 100)

  if (n_points == 0) {
    skipped_cells <- skipped_cells + 1
    next
  }

  cell_geom <- st_geometry(gus_sf[i, ])

  # st_sample generates random points inside a polygon
  pts <- tryCatch({
    st_sample(cell_geom, size = n_points, type = "random")
  }, error = function(e) {
    # Fallback: use centroid repeated
    cat(sprintf("  UWAGA: st_sample nie powiodl sie dla GUS cell %d (%s). Uzywam centroidu.\n",
                gus_sf$id[i], e$message))
    centroid <- st_centroid(cell_geom)
    # Repeat centroid n_points times
    do.call(c, replicate(n_points, centroid, simplify = FALSE))
  })

  if (length(pts) > 0) {
    points_list[[length(points_list) + 1]] <- pts
    total_points <- total_points + length(pts)
  }

  # Progress every 50 cells
  if (i %% 50 == 0) {
    cat(sprintf("  Przetworzono %d/%d gridow GUS, wygenerowano %d punktow...\n",
                i, n_gus, total_points))
  }
}

cat(sprintf("Wygenerowano %d punktow populacyjnych z %d gridow GUS.\n",
            total_points, n_gus))
cat(sprintf("Pominieto %d gridow GUS (populacja < 100).\n", skipped_cells))

if (total_points == 0) {
  cat("UWAGA: Zero punktow populacyjnych. Wszystkie kafle dostana population=1.\n")
  # Set all to 1 and exit
  dbExecute(conn, sprintf("UPDATE %s SET population = 1", TARGET_TABLE))
  cat("Ustawiono population=1 dla wszystkich kafli.\n")
  cat("\n============================================================\n")
  cat("02_population ZAKONCZONY (fallback: population=1 wszedzie)\n")
  cat("============================================================\n")
  quit(status = 0)
}

# Combine all points into one sfc
pop_points <- do.call(c, points_list)
cat(sprintf("Laczna liczba punktow: %d\n", length(pop_points)))

# Ensure CRS match
pop_points_sf <- st_sf(geometry = pop_points)
st_crs(pop_points_sf) <- 4326

# 6. Zlicz punkty w kaflach

cat("\n[5] Zliczanie punktow populacyjnych w kaflach...\n")

# st_intersects returns sparse matrix: for each voronoi cell, which points are inside
intersections <- st_intersects(voronoi_sf, pop_points_sf)
point_counts <- lengths(intersections)

# population = count * 100
voronoi_population <- point_counts * 100L

cat(sprintf("Zliczono punkty. Rozmiar: %d kafli.\n", length(voronoi_population)))

# 7. Obsluz population = 0 (lasy, woda — brak mieszkancow)

n_zeros <- sum(voronoi_population == 0)
cat(sprintf("\n[6] Kafle z populacja=0: %d (%.1f%%)\n",
            n_zeros, 100 * n_zeros / n_voronoi))

# Ustaw minimum na 1 (unikniecie dzielenia przez 0)
voronoi_population[voronoi_population == 0] <- 1L

# 8. UPDATE bazy danych

cat("\n[7] Zapis do bazy (UPDATE population)...\n")

# Build batch update for efficiency
n_updated <- 0
batch_size <- 50
for (start_idx in seq(1, n_voronoi, by = batch_size)) {
  end_idx <- min(start_idx + batch_size - 1, n_voronoi)

  # Build CASE statement for batch update
  cases <- paste(
    sapply(start_idx:end_idx, function(i) {
      sprintf("WHEN %d THEN %d", voronoi_raw$id[i], voronoi_population[i])
    }),
    collapse = " "
  )
  ids <- paste(voronoi_raw$id[start_idx:end_idx], collapse = ", ")

  sql <- sprintf("
    UPDATE %s
    SET population = CASE id %s END,
        updated_at = NOW()
    WHERE id IN (%s)
  ", TARGET_TABLE, cases, ids)

  result <- dbExecute(conn, sql)
  n_updated <- n_updated + result
}

cat(sprintf("Zaktualizowano %d kafli.\n", n_updated))

# 9. Podsumowanie

cat("\n[8] Podsumowanie:\n")
cat(sprintf("  Kafli:                %d\n", n_voronoi))
cat(sprintf("  Gridow GUS (>0):      %d\n", n_gus))
cat(sprintf("  Punktow populacyjnych: %d\n", total_points))
cat(sprintf("  MIN population:       %d\n", min(voronoi_population)))
cat(sprintf("  MAX population:       %d\n", max(voronoi_population)))
cat(sprintf("  MEAN population:      %.0f\n", mean(voronoi_population)))
cat(sprintf("  MEDIAN population:    %.0f\n", median(voronoi_population)))
cat(sprintf("  Kafli z pop=1 (zero->1): %d\n", sum(voronoi_population == 1)))

# Verify from DB
verify <- dbGetQuery(conn, sprintf("
  SELECT
    MIN(population) as pop_min,
    MAX(population) as pop_max,
    AVG(population)::int as pop_avg,
    COUNT(*) FILTER (WHERE population = 1) as zeros_converted,
    COUNT(*) as total
  FROM %s
", TARGET_TABLE))
cat(sprintf("\n  DB verify: min=%s, max=%s, avg=%s, zeros_converted=%s, total=%s\n",
            verify$pop_min, verify$pop_max, verify$pop_avg,
            verify$zeros_converted, verify$total))

cat("\n============================================================\n")
cat("02_population ZAKONCZONY POMYSLNIE\n")
cat("============================================================\n")
