#!/usr/bin/env Rscript
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

library(sf)
library(DBI)
library(RPostgres)
library(spdep)

# CONFIGURATION

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

# Validate TARGET_TABLE against allowlist — prevents injection if env is compromised
.allowed_tables <- c("research_grid_500m", "sightings_gridcell_voronoi", "sightings_gridcell_research")
if (!TARGET_TABLE %in% .allowed_tables) {
  stop(sprintf("Invalid TARGET_TABLE: '%s'. Allowed: %s",
               TARGET_TABLE, paste(.allowed_tables, collapse = ", ")))
}

# 1. DATABASE CONNECTION
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

# 2. LOAD SIGHTINGS
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

# 3. LOAD REGION BOUNDARY
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

# 4. GEOMETRY GENERATION — CONDITIONAL BY TYPE

cat(sprintf("\n[4] Generowanie geometrii: %s\n", toupper(geometry_type)))
