#!/usr/bin/env Rscript
# export_w_edges.R
# Eksportuje krawędzie macierzy W jako GeoJSON do wizualizacji
#
# Output: /app/data/w_matrix_edges.geojson

library(sf)
library(spdep)
library(DBI)
library(RPostgres)

cat("============================================================\n")
cat("export_w_edges.R — Eksport krawędzi macierzy W\n")
cat("============================================================\n")

# 1. Wczytaj macierz W

w_rds_path <- "/app/data/research_W.rds"
if (!file.exists(w_rds_path)) {
  cat("BŁĄD: Brak pliku research_W.rds\n")
  quit(status = 1)
}

w_data <- readRDS(w_rds_path)
nb <- w_data$nb
n_regions <- length(nb)

cat(sprintf("Macierz W: metoda=%s, k=%s, regiony=%d\n",
            w_data$method,
            ifelse(is.null(w_data$k_optimal), "N/A", w_data$k_optimal),
            n_regions))

# 2. Pobierz centroidy z bazy

TARGET_TABLE <- Sys.getenv("RESEARCH_TARGET_TABLE", "research_grid_500m")
cat(sprintf("Tabela: %s\n", TARGET_TABLE))

conn <- dbConnect(
  RPostgres::Postgres(),
  dbname = Sys.getenv("DB_NAME", "dziki_db"),
  host   = Sys.getenv("DB_HOST", "db"),
  port   = as.integer(Sys.getenv("DB_PORT", "5432")),
  user   = Sys.getenv("DB_USER", "dziki"),
  password = Sys.getenv("DB_PASSWORD", "dziki_dev_password")
)

# Pobierz centroidy w tej samej kolejności co W matrix
centroids_sql <- sprintf("
  SELECT
    id,
    ST_X(ST_Centroid(geometry)) as x,
    ST_Y(ST_Centroid(geometry)) as y
  FROM %s
  ORDER BY id
", TARGET_TABLE)

centroids <- dbGetQuery(conn, centroids_sql)
dbDisconnect(conn)

cat(sprintf("Pobrano %d centroidów\n", nrow(centroids)))

if (nrow(centroids) != n_regions) {
  cat(sprintf("UWAGA: Niezgodność! Centroidy=%d, regiony W=%d\n",
              nrow(centroids), n_regions))
  cat("Używam minimum z obu\n")
  n_regions <- min(nrow(centroids), n_regions)
}

# 3. Zbuduj krawędzie (linie od-do)

cat("Budowanie krawędzi...\n")

edges <- list()
edge_id <- 0

for (i in 1:n_regions) {
  neighbors <- nb[[i]]
  for (j in neighbors) {
    if (j > i && j <= n_regions) {  # Unikaj duplikatów (i,j) i (j,i)
      edge_id <- edge_id + 1

      # Współrzędne
      x1 <- centroids$x[i]
      y1 <- centroids$y[i]
      x2 <- centroids$x[j]
      y2 <- centroids$y[j]

      # Utwórz linię
      line <- st_linestring(matrix(c(x1, x2, y1, y2), ncol = 2))
      edges[[edge_id]] <- line
    }
  }
}

cat(sprintf("Utworzono %d krawędzi\n", length(edges)))

# 4. Utwórz obiekt sf i zapisz GeoJSON

edges_sfc <- st_sfc(edges, crs = 4326)
edges_sf <- st_sf(
  id = 1:length(edges),
  geometry = edges_sfc
)

output_path <- "/app/data/w_matrix_edges.geojson"
st_write(edges_sf, output_path, driver = "GeoJSON", delete_dsn = TRUE)

cat(sprintf("Zapisano: %s\n", output_path))

# Statystyki
file_size <- file.info(output_path)$size / 1024
cat(sprintf("Rozmiar: %.1f KB\n", file_size))

cat("\n============================================================\n")
cat("export_w_edges.R ZAKOŃCZONY\n")
cat("============================================================\n")
