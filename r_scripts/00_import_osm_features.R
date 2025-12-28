#!/usr/bin/env Rscript
# 00_import_osm_features.R
# Import OSM buildings and barriers for Białołęka district
# Uses 'out geom' for direct geometry (no manual polygon building)

library(sf)
library(DBI)
library(RPostgres)
library(httr)
library(jsonlite)

cat("=== OSM Features Import (Buildings & Barriers) ===\n")
cat(format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "\n\n")

# 1. Database connection
cat("Connecting to database...\n")

conn <- dbConnect(
  RPostgres::Postgres(),
  dbname = Sys.getenv("DB_NAME", "dziki_db"),
  host = "db",
  port = 5432,
  user = Sys.getenv("DB_USER", "dziki_user"),
  password = Sys.getenv("DB_PASSWORD", "dziki_dev_password")
)

on.exit(dbDisconnect(conn), add = TRUE)

# 2. Get bbox from boundaries table
cat("Fetching Białołęka bbox from boundaries table...\n")

bbox_result <- dbGetQuery(conn, "
  SELECT ST_XMin(geom) as xmin, ST_YMin(geom) as ymin,
         ST_XMax(geom) as xmax, ST_YMax(geom) as ymax
  FROM boundaries WHERE name = 'bialoleka'
")

if (nrow(bbox_result) == 0) stop("ERROR: Białołęka boundary not found!")

BBOX <- as.list(bbox_result[1, ])
cat(sprintf("Bbox: [%.4f, %.4f, %.4f, %.4f]\n",
            BBOX$xmin, BBOX$ymin, BBOX$xmax, BBOX$ymax))

# 3. Overpass API function (uses 'out geom' for direct geometry)
fetch_osm <- function(query, timeout = 180) {
  url <- "https://overpass.kumi.systems/api/interpreter"

  tryCatch({
    r <- httr::POST(url, body = list(data = query), encode = "form",
                    httr::timeout(timeout))

    if (httr::status_code(r) == 200) {
      return(jsonlite::fromJSON(httr::content(r, "text", encoding = "UTF-8")))
    } else if (httr::status_code(r) == 429) {
      cat("    Rate limited, waiting 30s...\n")
      Sys.sleep(30)
      return(fetch_osm(query, timeout))
    } else {
      cat(sprintf("    API error: %d\n", httr::status_code(r)))
      return(NULL)
    }
  }, error = function(e) {
    cat(sprintf("    Error: %s\n", e$message))
    return(NULL)
  })
}

# Split bbox into 4 quadrants
mid_x <- (BBOX$xmin + BBOX$xmax) / 2
mid_y <- (BBOX$ymin + BBOX$ymax) / 2
quadrants <- list(
  list(ymin = BBOX$ymin, xmin = BBOX$xmin, ymax = mid_y, xmax = mid_x),
  list(ymin = BBOX$ymin, xmin = mid_x, ymax = mid_y, xmax = BBOX$xmax),
  list(ymin = mid_y, xmin = BBOX$xmin, ymax = BBOX$ymax, xmax = mid_x),
  list(ymin = mid_y, xmin = mid_x, ymax = BBOX$ymax, xmax = BBOX$xmax)
)

# 4. Import BUILDINGS
cat("\n--- BUILDINGS ---\n")

dbExecute(conn, "TRUNCATE TABLE osm_buildings RESTART IDENTITY")
total_buildings <- 0

for (q_idx in 1:4) {
  q <- quadrants[[q_idx]]
  cat(sprintf("  Quadrant %d/4: ", q_idx))

  # Use 'out geom' to get geometry directly on way elements
  query <- sprintf('
[out:json][timeout:180][bbox:%.6f,%.6f,%.6f,%.6f];
way["building"];
out geom;
', q$ymin, q$xmin, q$ymax, q$xmax)

  data <- fetch_osm(query)

  if (is.null(data) || length(data$elements) == 0) {
    cat("no data\n")
    next
  }

  ways <- data$elements
  cat(sprintf("%d ways... ", nrow(ways)))

  inserted <- 0
  for (i in 1:nrow(ways)) {
    way <- ways[i, ]

    # Get geometry from 'geometry' field (list of lat/lon)
    geom_data <- way$geometry
    if (is.null(geom_data) || length(geom_data) < 1) next

    # geom_data is a data.frame with lon, lat columns
    if (!is.data.frame(geom_data[[1]])) next
    coords <- geom_data[[1]]
    if (nrow(coords) < 4) next

    # Close polygon if needed
    if (coords$lon[1] != coords$lon[nrow(coords)] ||
        coords$lat[1] != coords$lat[nrow(coords)]) {
      coords <- rbind(coords, coords[1, ])
    }

    # Build WKT
    wkt_coords <- paste(sprintf("%.7f %.7f", coords$lon, coords$lat), collapse = ", ")
    wkt <- sprintf("POLYGON((%s))", wkt_coords)

    # Get building type
    btype <- "yes"
    if (!is.null(way$tags) && is.data.frame(way$tags) && "building" %in% names(way$tags)) {
      btype <- way$tags$building[1]
    }

    tryCatch({
      dbExecute(conn, sprintf(
        "INSERT INTO osm_buildings (osm_id, building_type, geom, fetched_at)
         VALUES (%s, '%s', ST_GeomFromText('%s', 4326), NOW())",
        way$id, gsub("'", "''", btype), wkt
      ))
      inserted <- inserted + 1
    }, error = function(e) NULL)
  }

  cat(sprintf("%d inserted\n", inserted))
  total_buildings <- total_buildings + inserted
  Sys.sleep(2)
}

cat(sprintf("  TOTAL BUILDINGS: %d\n", total_buildings))

# 5. Import BARRIERS
cat("\n--- BARRIERS ---\n")

dbExecute(conn, "TRUNCATE TABLE osm_barriers RESTART IDENTITY")
total_barriers <- 0

# Permeability values
PERM <- list(fence=0.3, wall=0.1, hedge=0.5, gate=0.8, retaining_wall=0.1,
             guard_rail=0.4, city_wall=0.0, ditch=0.6)

for (q_idx in 1:4) {
  q <- quadrants[[q_idx]]
  cat(sprintf("  Quadrant %d/4: ", q_idx))

  query <- sprintf('
[out:json][timeout:180][bbox:%.6f,%.6f,%.6f,%.6f];
way["barrier"];
out geom;
', q$ymin, q$xmin, q$ymax, q$xmax)

  data <- fetch_osm(query)

  if (is.null(data) || length(data$elements) == 0) {
    cat("no data\n")
    next
  }

  ways <- data$elements
  cat(sprintf("%d ways... ", nrow(ways)))

  inserted <- 0
  for (i in 1:nrow(ways)) {
    way <- ways[i, ]

    geom_data <- way$geometry
    if (is.null(geom_data) || length(geom_data) < 1) next
    if (!is.data.frame(geom_data[[1]])) next
    coords <- geom_data[[1]]
    if (nrow(coords) < 2) next

    # Build LineString WKT
    wkt_coords <- paste(sprintf("%.7f %.7f", coords$lon, coords$lat), collapse = ", ")
    wkt <- sprintf("LINESTRING(%s)", wkt_coords)

    # Get barrier type and permeability
    btype <- "unknown"
    if (!is.null(way$tags) && is.data.frame(way$tags) && "barrier" %in% names(way$tags)) {
      btype <- way$tags$barrier[1]
    }
    perm <- if (btype %in% names(PERM)) PERM[[btype]] else 0.5

    tryCatch({
      dbExecute(conn, sprintf(
        "INSERT INTO osm_barriers (osm_id, barrier_type, permeability, geom)
         VALUES (%s, '%s', %f, ST_GeomFromText('%s', 4326))",
        way$id, gsub("'", "''", btype), perm, wkt
      ))
      inserted <- inserted + 1
    }, error = function(e) NULL)
  }

  cat(sprintf("%d inserted\n", inserted))
  total_barriers <- total_barriers + inserted
  Sys.sleep(2)
}

cat(sprintf("  TOTAL BARRIERS: %d\n", total_barriers))

# 6. Summary
cat("\n=== IMPORT SUMMARY ===\n")

counts <- dbGetQuery(conn, "
  SELECT 'osm_buildings' as tbl, COUNT(*) as cnt FROM osm_buildings
  UNION ALL
  SELECT 'osm_barriers', COUNT(*) FROM osm_barriers
")
print(counts)

# Sample data
if (total_buildings > 0) {
  cat("\nSample buildings:\n")
  print(dbGetQuery(conn, "SELECT osm_id, building_type FROM osm_buildings LIMIT 3"))
}

if (total_barriers > 0) {
  cat("\nSample barriers:\n")
  print(dbGetQuery(conn, "SELECT osm_id, barrier_type, permeability FROM osm_barriers LIMIT 3"))
}

cat("\n=== DONE ===\n")
cat(format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "\n")
