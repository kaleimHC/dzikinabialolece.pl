#!/usr/bin/env Rscript
# =============================================================================
# 01_generate_voronoi.R (aka 01_geometry.R)
# Generuje geometrie przestrzenne: Voronoi tessellation LUB regular grids
# Zapisuje do PostGIS jako GridCell
# Wzorowane na spatialWarsaw::tessW() i ETA()
#
# GEOMETRY TYPES:
#   voronoi  — Voronoi tessellation (1 point = 1 cell) [DEFAULT]
#   grid_500 — Regular grid 500m x 500m (~80 cells)
#
# ENV VARIABLES:
#   RESEARCH_GEOMETRY_TYPE  — voronoi/grid_500
#   RESEARCH_TARGET_TABLE   — target table name
# =============================================================================

library(sf)
library(DBI)
library(RPostgres)
library(spdep)

# =============================================================================
# CONFIGURATION
# =============================================================================

geometry_type <- Sys.getenv("RESEARCH_GEOMETRY_TYPE", "voronoi")
TARGET_TABLE <- Sys.getenv("RESEARCH_TARGET_TABLE", "sightings_gridcell_voronoi")

cat("============================================================\n")
cat("=== 01_geometry.R — Spatial Unit Generation ===\n")
cat("============================================================\n")
cat(sprintf("Geometry type: %s\n", geometry_type))
cat(sprintf("Target table:  %s\n", TARGET_TABLE))
cat("============================================================\n")

# Validate geometry type
valid_types <- c("voronoi", "grid_500")
if (!(geometry_type %in% valid_types)) {
  cat(sprintf("BLAD: Nieznany typ geometrii '%s'\n", geometry_type))
  cat(sprintf("Dostepne: %s\n", paste(valid_types, collapse = ", ")))
  quit(status = 1)
}

# =============================================================================
# 1. DATABASE CONNECTION
# =============================================================================
cat("\n[1] Laczenie z baza danych...\n")

conn <- dbConnect(
  RPostgres::Postgres(),
  dbname = Sys.getenv("DB_NAME", "dziki_db"),
  host = Sys.getenv("DB_HOST", "db"),
  port = as.integer(Sys.getenv("DB_PORT", "5432")),
  user = Sys.getenv("DB_USER", "dziki"),
  password = Sys.getenv("DB_PASSWORD", "dziki_dev_password")
)

cat("Polaczono z baza.\n")

# Cleanup on exit
on.exit({
  if (exists("conn") && dbIsValid(conn)) dbDisconnect(conn)
}, add = TRUE)

# =============================================================================
# 2. LOAD SIGHTINGS
# =============================================================================
cat("\n[2] Pobieranie obserwacji...\n")

sightings_raw <- dbGetQuery(conn, "
  SELECT id, ST_AsText(location) as wkt
  FROM sightings_sighting
  WHERE status = 'verified'
    AND location IS NOT NULL
")
sightings <- st_as_sf(sightings_raw, wkt = "wkt", crs = 4326)

n_sightings <- nrow(sightings)
cat(sprintf("Pobrano %d obserwacji.\n", n_sightings))

# Validation for Voronoi (minimum 3 points)
if (geometry_type == "voronoi" && n_sightings < 3) {
  cat("BLAD: Za malo obserwacji dla Voronoi (min. 3). Przerywam.\n")
  quit(status = 2)
}

# =============================================================================
# 3. LOAD REGION BOUNDARY
# =============================================================================
cat("\n[3] Pobieranie granic Bialoleki...\n")

bialoleka_raw <- dbGetQuery(conn, "
  SELECT ST_AsText(geom) as wkt FROM boundaries WHERE name = 'bialoleka'
")
if (nrow(bialoleka_raw) == 0 || is.na(bialoleka_raw$wkt[1])) {
  cat("BLAD KRYTYCZNY: Brak granicy Bialoleki w tabeli boundaries!\n")
  quit(status = 3)
}

region_sf <- st_as_sf(bialoleka_raw, wkt = "wkt", crs = 4326)
n_boundary_pts <- nrow(st_coordinates(region_sf))
cat(sprintf("Granica Bialoleki: %d punktow\n", n_boundary_pts))

# Fix geometry if needed
if (!st_is_valid(region_sf)) {
  cat("Naprawa geometrii granicy...\n")
  region_sf <- st_make_valid(region_sf)
}

# Extent
bbox <- st_bbox(region_sf)
cat(sprintf("  Extent: lon %.4f-%.4f, lat %.4f-%.4f\n",
            bbox["xmin"], bbox["xmax"], bbox["ymin"], bbox["ymax"]))

# Load Wisla (optional exclusion)
wisla_raw <- dbGetQuery(conn, "
  SELECT ST_AsText(geom) as wkt FROM boundaries WHERE name = 'wisla'
")
if (nrow(wisla_raw) > 0 && !is.na(wisla_raw$wkt[1])) {
  wisla_sf <- st_as_sf(wisla_raw, wkt = "wkt", crs = 4326)
  wisla_buffered <- st_transform(wisla_sf, 2180)
  wisla_buffered <- st_buffer(wisla_buffered, 50)
  wisla_buffered <- st_transform(wisla_buffered, 4326)
  cat("Wisla z buforem 50m zaladowana.\n")
} else {
  wisla_sf <- NULL
  wisla_buffered <- NULL
  cat("Brak Wisly w bazie - pomijam wykluczenie.\n")
}

# =============================================================================
# 4. GEOMETRY GENERATION — CONDITIONAL BY TYPE
# =============================================================================

cat(sprintf("\n[4] Generowanie geometrii: %s\n", toupper(geometry_type)))

if (geometry_type == "voronoi") {
  # =========================================================================
  # VORONOI TESSELLATION (existing logic)
  # =========================================================================
  cat(">>> Generating VORONOI tessellation\n")

  # Transform to EPSG:3857 (Web Mercator)
  cat("Transformacja do EPSG:3857 (Web Mercator)...\n")
  sightings_3857 <- st_transform(sightings, 3857)
  region_3857 <- st_transform(region_sf, 3857)

  # Jittering - critical to avoid duplicates
  cat("Aplikowanie jittering...\n")
  set.seed(42)
  crds <- as.data.frame(st_coordinates(sightings_3857))
  colnames(crds) <- c("X_coord", "Y_coord")
  crds$X_coord <- crds$X_coord + rnorm(n_sightings, 0, sd(crds$X_coord) / 1000)
  crds$Y_coord <- crds$Y_coord + rnorm(n_sightings, 0, sd(crds$Y_coord) / 1000)
  sightings_jittered <- st_as_sf(crds, coords = c("X_coord", "Y_coord"), crs = 3857)

  # Voronoi tessellation
  cat("Generowanie tessellation Voronoi...\n")
  crds_sfc <- st_geometry(sightings_jittered)
  region_sfc <- st_geometry(region_3857)
  crds_union <- st_union(crds_sfc)

  voronoi_raw <- st_voronoi(crds_union, region_sfc)
  voronoi_cast <- st_cast(voronoi_raw)
  cat(sprintf("  Raw Voronoi: %d polygons\n", length(voronoi_cast)))

  # Clip to region boundary
  region_union <- st_union(region_sfc)
  voronoi_clipped <- st_intersection(voronoi_cast, region_union)
  cat(sprintf("  Po intersection: %d polygons\n", length(voronoi_clipped)))

  # Transform back to WGS84
  voronoi_4326 <- st_transform(voronoi_clipped, 4326)

  # Exclude Wisla if available
  if (!is.null(wisla_buffered)) {
    cat("Wykluczanie Wisly z siatki...\n")
    wisla_union <- st_union(wisla_buffered)
    voronoi_4326 <- st_difference(voronoi_4326, wisla_union)
    voronoi_4326 <- voronoi_4326[!st_is_empty(voronoi_4326)]
    cat(sprintf("Po wykluczeniu Wisly: %d komorek.\n", length(voronoi_4326)))
  }

  n_cells <- length(voronoi_4326)
  cat(sprintf("Wygenerowano %d komorek Voronoi.\n", n_cells))

  # Build sf object
  grid_cells <- st_sf(
    grid_id = sprintf("VORONOI_%04d", seq_along(voronoi_4326)),
    geometry = voronoi_4326,
    sighting_count = 0L,
    district = "Bialoleka"
  )

  # Calculate centroids
  suppressWarnings({
    centroids <- st_centroid(grid_cells)
  })
  grid_cells$centroid <- st_geometry(centroids)

  # Spatial join - count sightings per cell
  cat("Zliczanie obserwacji per komorka...\n")
  intersects <- st_intersects(grid_cells, sightings)
  grid_cells$sighting_count <- lengths(intersects)

} else if (geometry_type == "grid_500") {
  # =========================================================================
  # GRID 500m — USE GUS GRID DIRECTLY (1:1 alignment)
  # =========================================================================
  cat(">>> Using GUS 500m grid (1:1 alignment with population data)\n")

  # Load GUS grid cells that intersect with Bialoleka
  cat("Pobieranie komorek GUS dla Bialoleki...\n")
  gus_raw <- dbGetQuery(conn, "
    SELECT
      g.id as gus_id,
      g.code as gus_code,
      g.tot as population,
      ST_AsText(g.geom) as wkt
    FROM gus_population_grid_500m g, boundaries b
    WHERE b.name = 'bialoleka'
    AND ST_Intersects(g.geom, b.geom)
    ORDER BY g.id
  ")

  if (nrow(gus_raw) == 0) {
    cat("BLAD: Brak komorek GUS dla Bialoleki!\n")
    quit(status = 3)
  }

  cat(sprintf("  Pobrano %d komorek GUS\n", nrow(gus_raw)))

  # Convert to sf
  grid_sf <- st_as_sf(gus_raw, wkt = "wkt", crs = 4326)
  grid_sf <- st_make_valid(grid_sf)

  # Generate grid_id based on GUS ID
  grid_sf$grid_id <- sprintf("G500_%04d", seq_len(nrow(grid_sf)))
  grid_sf$gus_grid_id <- grid_sf$gus_id
  grid_sf$district <- "Bialoleka"
  grid_sf$sighting_count <- 0L
  grid_sf$regime <- "mixed"

  # Population is already in gus_raw, rename for consistency
  # (will be used directly, no interpolation needed!)

  n_cells <- nrow(grid_sf)
  cat(sprintf("Zaladowano %d komorek GUS 500m.\n", n_cells))

  # Population stats
  cat(sprintf("  Population: min=%d, max=%d, total=%d\n",
              min(grid_sf$population), max(grid_sf$population), sum(grid_sf$population)))

  # Calculate centroids
  suppressWarnings({
    centroids <- st_centroid(grid_sf)
  })
  grid_sf$centroid <- st_geometry(centroids)

  # Count sightings per cell
  cat("Zliczanie obserwacji per komorka...\n")
  intersects <- st_intersects(grid_sf, sightings)
  grid_sf$sighting_count <- lengths(intersects)

  # Summary statistics (before modifying grid_sf)
  total_area <- sum(as.numeric(st_area(grid_sf))) / 1e6  # km2
  cat(sprintf("Calkowita powierzchnia: %.2f km²\n", total_area))

  # Rename geometry column from 'wkt' to 'geometry' FIRST
  # (st_as_sf converts wkt in-place, keeping the column name)
  geom_col <- attr(grid_sf, "sf_column")
  if (!is.null(geom_col) && geom_col != "geometry") {
    cat(sprintf("Renaming geometry column from '%s' to 'geometry'\n", geom_col))
    names(grid_sf)[names(grid_sf) == geom_col] <- "geometry"
    attr(grid_sf, "sf_column") <- "geometry"
  }

  # Now remove non-DB columns: gus_id
  grid_cells <- grid_sf
  if ("gus_id" %in% names(grid_cells)) grid_cells$gus_id <- NULL

  cat(sprintf("Columns after cleanup: %s\n", paste(names(grid_cells), collapse = ", ")))
}

# =============================================================================
# 5. STATISTICS
# =============================================================================
cat("\n[5] Statystyki...\n")

cat(sprintf("  Liczba komorek: %d\n", nrow(grid_cells)))
cat(sprintf("  Min sightings per cell: %d\n", min(grid_cells$sighting_count)))
cat(sprintf("  Max sightings per cell: %d\n", max(grid_cells$sighting_count)))
cat(sprintf("  Mean sightings per cell: %.2f\n", mean(grid_cells$sighting_count)))
cat(sprintf("  Cells with 0 sightings: %d\n", sum(grid_cells$sighting_count == 0)))
cat(sprintf("  Cells with >0 sightings: %d\n", sum(grid_cells$sighting_count > 0)))

# Validation
total_in_cells <- sum(grid_cells$sighting_count)
if (total_in_cells != n_sightings) {
  cat(sprintf("  UWAGA: Suma w komorkach (%d) != liczba sightings (%d)\n",
              total_in_cells, n_sightings))
  cat("  (Normalne dla gridow regularnych - niektore punkty poza granica)\n")
}

# =============================================================================
# 6. SAVE TO DATABASE
# =============================================================================
cat(sprintf("\n[6] Zapisywanie do %s...\n", TARGET_TABLE))

# Remove centroid column for saving (can't save two geometry columns)
grid_cells_save <- grid_cells
grid_cells_save$centroid <- NULL

# Clear existing data
dbExecute(conn, sprintf("TRUNCATE TABLE %s RESTART IDENTITY", TARGET_TABLE))

# Save using st_write
st_write(
  grid_cells_save,
  conn,
  layer = TARGET_TABLE,
  driver = "PostgreSQL",
  append = TRUE
)

# Update centroids in PostGIS
cat("Aktualizacja centroidow...\n")
dbExecute(conn, sprintf("
  UPDATE %s
  SET centroid = ST_Centroid(geometry)
  WHERE centroid IS NULL
", TARGET_TABLE))

# Update timestamp
dbExecute(conn, sprintf("
  UPDATE %s
  SET updated_at = NOW()
", TARGET_TABLE))

# For grids: also set area_proportion
if (geometry_type == "grid_500") {
  cat("Obliczanie area_proportion...\n")
  dbExecute(conn, sprintf("
    WITH total AS (SELECT SUM(ST_Area(geometry::geography)) as sum_area FROM %s)
    UPDATE %s g
    SET area_proportion = ST_Area(g.geometry::geography) / total.sum_area
    FROM total
  ", TARGET_TABLE, TARGET_TABLE))
}

cat("Zapisano do bazy.\n")

# =============================================================================
# 7. VERIFICATION
# =============================================================================
cat("\n[7] Weryfikacja...\n")

verify <- dbGetQuery(conn, sprintf("
  SELECT
    COUNT(*)::int as n_cells,
    COALESCE(SUM(sighting_count), 0)::int as total_sightings,
    COUNT(*) FILTER (WHERE sighting_count > 0)::int as cells_with_sightings
  FROM %s
", TARGET_TABLE))

cat(sprintf("  Komorki w bazie: %d\n", as.integer(verify$n_cells)))
cat(sprintf("  Suma sightings: %d\n", as.integer(verify$total_sightings)))
cat(sprintf("  Komorki z obserwacjami: %d\n", as.integer(verify$cells_with_sightings)))

# =============================================================================
# 8. DONE
# =============================================================================
cat("\n============================================================\n")
cat("=== 01_geometry.R ZAKONCZONY POMYSLNIE ===\n")
cat("============================================================\n")
cat(sprintf("Geometry type: %s\n", geometry_type))
cat(sprintf("Target table:  %s\n", TARGET_TABLE))
cat(sprintf("Cells created: %d\n", as.integer(verify$n_cells)))
cat(sprintf("Sightings:     %d\n", as.integer(n_sightings)))
cat("============================================================\n")
