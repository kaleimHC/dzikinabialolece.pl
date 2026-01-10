#!/usr/bin/env Rscript
# 05_matrix_w.R
# Budowanie macierzy wag przestrzennych W
#
# Metody:
#   contiguity - Queen contiguity (poly2nb) [principled choice; NIE jest operacyjnym defaultem - env RESEARCH_W_METHOD ustawia Django, realnie knn_aic]
#   knn_aic    - k-NN z optymalizacja AIC (lagsarlm Y~1, lag-form); heurystyka wrazliwosci
#   tessw      - tessW style: contiguity z wagami dl. wspolnej granicy
#
# Input:  sightings_gridcell_voronoi z geometry + spatial_risk (Y z kroku 04)
# Output: /app/data/research_W.rds (listw + metadata)
#
# ENV vars:
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
#   RESEARCH_TARGET_TABLE (default: sightings_gridcell_voronoi)
#   RESEARCH_W_METHOD     (contiguity / knn_aic / tessw)
#   RESEARCH_K_RANGE_MIN  (dla knn_aic, default: 2)
#   RESEARCH_K_RANGE_MAX  (dla knn_aic, default: 50)

library(sf)
library(spdep)
library(DBI)
library(RPostgres)

cat("============================================================\n")
cat("05_matrix_w.R - Macierz wag przestrzennych W\n")
cat("============================================================\n")

# 1. Parametry z ENV

TARGET_TABLE <- Sys.getenv("RESEARCH_TARGET_TABLE", "sightings_gridcell_voronoi")
# Validate TARGET_TABLE against allowlist - prevents identifier injection
# (TARGET_TABLE is interpolated into a 'FROM %s' query below).
.allowed_tables <- c("research_grid_500m", "sightings_gridcell_voronoi", "sightings_gridcell_research")
if (!TARGET_TABLE %in% .allowed_tables) {
  stop(sprintf("Invalid TARGET_TABLE: '%s'. Allowed: %s",
               TARGET_TABLE, paste(.allowed_tables, collapse = ", ")))
}
w_method <- Sys.getenv("RESEARCH_W_METHOD", "knn_aic")  # env zawsze ustawiany przez Django (to_env_dict), fallback nieosiagalny - wyrownany do realnego defaultu
k_min <- as.integer(Sys.getenv("RESEARCH_K_RANGE_MIN", "2"))
k_max <- as.integer(Sys.getenv("RESEARCH_K_RANGE_MAX", "50"))

cat(sprintf("Target table: %s\n", TARGET_TABLE))

VALID_METHODS <- c("contiguity", "knn_aic", "tessw")

cat(sprintf("Metoda: %s\n", w_method))

if (!(w_method %in% VALID_METHODS)) {
  cat(sprintf("BLAD: Nieznana metoda '%s'. Dostepne: %s\n",
              w_method, paste(VALID_METHODS, collapse = ", ")))
  quit(status = 1)
}

if (w_method == "knn_aic") {
  cat(sprintf("k range: %d - %d\n", k_min, k_max))
  if (k_min >= k_max) {
    cat("BLAD: k_range_min >= k_range_max\n")
    quit(status = 1)
  }
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

# 3. Wczytaj kafle Voronoi

cat(sprintf("\n[2] Pobieranie kafli z %s...\n", TARGET_TABLE))

voronoi_raw <- dbGetQuery(conn, sprintf("
  SELECT
    id,
    ST_AsText(geometry) as wkt,
    COALESCE(spatial_risk, 0) as spatial_risk,
    ST_X(centroid) as cx,
    ST_Y(centroid) as cy
  FROM %s
  WHERE geometry IS NOT NULL
  ORDER BY id
", TARGET_TABLE))

n <- nrow(voronoi_raw)
cat(sprintf("Kafli: %d\n", n))

if (n < 3) {
  cat("BLAD: Za malo kafli (<3) do budowy macierzy W.\n")
  quit(status = 1)
}

voronoi_sf <- st_as_sf(voronoi_raw, wkt = "wkt", crs = 4326)
voronoi_sf <- st_make_valid(voronoi_sf)

cat(sprintf("Y (spatial_risk): min=%.4f, max=%.4f, sd=%.4f\n",
            min(voronoi_raw$spatial_risk),
            max(voronoi_raw$spatial_risk),
            sd(voronoi_raw$spatial_risk)))

# 4. Budowa macierzy W

cat(sprintf("\n[3] Budowanie W (metoda: %s)...\n", w_method))

build_result <- NULL
t0 <- proc.time()

if (w_method == "contiguity") {
  # Queen contiguity - sasiedzi dziela krawedz lub wierzcholek

  nb <- poly2nb(voronoi_sf, queen = TRUE)
  W <- nb2listw(nb, style = "W", zero.policy = TRUE)

  build_result <- list(
    listw     = W,
    nb        = nb,
    method    = "contiguity",
    k_optimal = NA_integer_,
    aic       = NA_real_
  )

} else if (w_method == "knn_aic") {
  # k-NN z optymalizacja AIC
  # Fitujemy lagsarlm(Y ~ 1) (lag-form) dla kazdego k i wybieramy najlepszy AIC.
  # To heurystyka wrazliwosci, nie glowny selektor - contiguity jest principled, ale nie operacyjnym defaultem (realnie knn_aic).

  if (!requireNamespace("spatialreg", quietly = TRUE)) {
    cat("  Instalacja spatialreg...\n")
    install.packages("spatialreg", repos = "https://cloud.r-project.org")
  }
  library(spatialreg)

  # Projekcja na EPSG:2180 (metryczny uklad PL) - kNN wymaga metrow, nie stopni
  voronoi_proj <- st_transform(voronoi_sf, 2180)
  coords <- st_coordinates(st_centroid(voronoi_proj))
  Y <- voronoi_raw$spatial_risk

  cat(sprintf("  Centroidy: x range %.0f-%.0f, y range %.0f-%.0f (EPSG:2180)\n",
              min(coords[,1]), max(coords[,1]), min(coords[,2]), max(coords[,2])))

  # Efektywny zakres k (nie wiecej niz n-1)
  k_max_eff <- min(k_max, n - 1)
  k_min_eff <- min(k_min, k_max_eff)

  cat(sprintf("  Zakres k: %d - %d (efektywny)\n", k_min_eff, k_max_eff))

  # Sprawdz wariancje Y (potrzebna do estymacji)
  if (sd(Y, na.rm = TRUE) == 0 || is.na(sd(Y, na.rm = TRUE))) {
    cat("  UWAGA: Y (spatial_risk) ma zerowa wariancje.\n")
    cat("  Fallback do contiguity.\n")

    nb <- poly2nb(voronoi_sf, queen = TRUE)
    W <- nb2listw(nb, style = "W", zero.policy = TRUE)

    build_result <- list(
      listw     = W,
      nb        = nb,
      method    = "contiguity_fallback",
      k_optimal = NA_integer_,
      aic       = NA_real_
    )
  } else {
    best_k   <- k_min_eff
    best_aic <- Inf
    aic_log  <- data.frame(k = integer(), aic = numeric())
    last_err <- ""

    for (k in k_min_eff:k_max_eff) {
      nb_k <- knn2nb(knearneigh(coords, k = k))
      # Symetryzacja: kNN jest asymetryczne, spatialreg wymaga symetrii
      nb_k <- make.sym.nb(nb_k)
      W_k  <- nb2listw(nb_k, style = "W")

      # Select W on the LAG form (matches the estimated SAR in 02_spatial_models.R).
      # NOTE: intercept-only (predictors unavailable at the W-building stage) and
      # AIC-driven, so knn_aic is a sensitivity heuristic, not a substantive selector
      # - contiguity/tessW are the principled choice.
      fit <- tryCatch({
        lagsarlm(Y ~ 1, listw = W_k)
      }, error = function(e) {
        last_err <<- e$message
        NULL
      })

      if (!is.null(fit)) {
        a <- AIC(fit)
        aic_log <- rbind(aic_log, data.frame(k = k, aic = a))

        if (a < best_aic) {
          best_aic <- a
          best_k   <- k
        }
      }

      # Progress co 5 krokow
      if (k %% 5 == 0 || k == k_max_eff || k == k_min_eff) {
        current_aic <- if (!is.null(fit)) sprintf("%.2f", a) else "FAIL"
        best_marker <- if (!is.null(fit) && k == best_k) " *BEST*" else ""
        cat(sprintf("    k=%2d: AIC=%s%s\n", k, current_aic, best_marker))
      }
    }

    if (nrow(aic_log) == 0) {
      cat(sprintf("  Zaden model nie zbiegnal. Ostatni blad: %s\n", last_err))
      cat("  Proba awaryjna (lagsarlm, ponowny przebieg po k)...\n")

      # Fallback: sprobuj lagsarlm
      for (k in k_min_eff:k_max_eff) {
        nb_k <- knn2nb(knearneigh(coords, k = k))
        nb_k <- make.sym.nb(nb_k)
        W_k  <- nb2listw(nb_k, style = "W")

        fit <- tryCatch({
          lagsarlm(Y ~ 1, listw = W_k, Durbin = FALSE)
        }, error = function(e) {
          last_err <<- e$message
          NULL
        })

        if (!is.null(fit)) {
          a <- AIC(fit)
          aic_log <- rbind(aic_log, data.frame(k = k, aic = a))

          if (a < best_aic) {
            best_aic <- a
            best_k   <- k
          }
        }

        if (k %% 10 == 0 || k == k_max_eff || k == k_min_eff) {
          current_aic <- if (!is.null(fit)) sprintf("%.2f", a) else "FAIL"
          best_marker <- if (!is.null(fit) && k == best_k) " *BEST*" else ""
          cat(sprintf("    k=%2d: AIC=%s%s\n", k, current_aic, best_marker))
        }
      }
    }

    if (nrow(aic_log) == 0) {
      cat(sprintf("  Zaden model nie zbiegnal. Fallback do contiguity.\n"))
      cat(sprintf("  Ostatni blad: %s\n", last_err))
      nb <- poly2nb(voronoi_sf, queen = TRUE)
      W <- nb2listw(nb, style = "W", zero.policy = TRUE)

      build_result <- list(
        listw     = W,
        nb        = nb,
        method    = "contiguity_fallback",
        k_optimal = NA_integer_,
        aic       = NA_real_
      )
    } else {
      cat(sprintf("\n  Optymalny k=%d (AIC=%.2f)\n", best_k, best_aic))

      nb <- knn2nb(knearneigh(coords, k = best_k))
      nb <- make.sym.nb(nb)
      W  <- nb2listw(nb, style = "W")

      build_result <- list(
        listw     = W,
        nb        = nb,
        method    = "knn_aic",
        k_optimal = best_k,
        aic       = best_aic,
        aic_table = aic_log
      )
    }
  }

} else if (w_method == "tessw") {
  # tessW - contiguity z wagami proporcjonalnymi do dl. wspolnej granicy
  # Inspiracja: tessW() z spatialWarsaw
  # Dluzsze wspolne granice = silniejsza interakcja przestrzenna

  cat("  Krok 1: Queen contiguity (struktura sasiedztwa)...\n")
  nb <- poly2nb(voronoi_sf, queen = TRUE)

  cat("  Krok 2: Obliczanie dlugosci wspolnych granic via PostGIS...\n")

  # Uzywamy PostGIS zamiast R do obliczen geometrycznych (szybciej + GIST)
  shared_lengths <- dbGetQuery(conn, sprintf("
    SELECT
      a.id as id_a,
      b.id as id_b,
      ST_Length(
        ST_CollectionExtract(ST_Intersection(a.geometry, b.geometry), 2)::geography
      ) as shared_length
    FROM %s a
    JOIN %s b
      ON ST_Intersects(a.geometry, b.geometry)
         AND a.id < b.id
    WHERE a.geometry IS NOT NULL
      AND b.geometry IS NOT NULL
  ", TARGET_TABLE, TARGET_TABLE))

  cat(sprintf("  Par sasiadow: %d\n", nrow(shared_lengths)))

  if (nrow(shared_lengths) > 0) {
    cat(sprintf("  Dl. granic: min=%.1f m, max=%.1f m, avg=%.1f m\n",
                min(shared_lengths$shared_length),
                max(shared_lengths$shared_length),
                mean(shared_lengths$shared_length)))
  }

  # Buduj lookup: id -> pozycja w wektorze (order by id)
  id_to_idx <- setNames(seq_len(n), voronoi_raw$id)

  # Buduj glist z dlugosciami wspolnych granic
  # Symetryczna: jesli (a,b) ma length L, to (b,a) tez
  shared_sym <- rbind(
    shared_lengths,
    data.frame(
      id_a = shared_lengths$id_b,
      id_b = shared_lengths$id_a,
      shared_length = shared_lengths$shared_length
    )
  )

  glist <- vector("list", length(nb))

  for (i in seq_along(nb)) {
    neighbors <- nb[[i]]
    if (length(neighbors) == 1 && neighbors[1] == 0) {
      glist[[i]] <- numeric(0)
      next
    }

    my_id <- voronoi_raw$id[i]
    weights <- numeric(length(neighbors))

    for (j in seq_along(neighbors)) {
      neighbor_id <- voronoi_raw$id[neighbors[j]]

      # Znajdz dlugosc wspolnej granicy
      match_row <- shared_sym[
        shared_sym$id_a == my_id & shared_sym$id_b == neighbor_id, ]

      if (nrow(match_row) > 0 && !is.na(match_row$shared_length[1])) {
        weights[j] <- max(match_row$shared_length[1], 0.001)
      } else {
        # Fallback: minimalny weight (sasiad wg poly2nb ale brak w SQL)
        weights[j] <- 0.001
      }
    }

    glist[[i]] <- weights
  }

  W <- nb2listw(nb, glist = glist, style = "W", zero.policy = TRUE)

  build_result <- list(
    listw     = W,
    nb        = nb,
    method    = "tessw",
    k_optimal = NA_integer_,
    aic       = NA_real_
  )
}

elapsed <- (proc.time() - t0)["elapsed"]
cat(sprintf("  Czas budowy W: %.1f s\n", elapsed))

# 5. Statystyki macierzy W

cat(sprintf("\n[4] Statystyki macierzy W (%s):\n", build_result$method))

card_nb <- card(build_result$nb)

cat(sprintf("  Regionow: %d\n", length(build_result$nb)))
cat(sprintf("  Srednia sasiadow: %.1f\n", mean(card_nb)))
cat(sprintf("  Min sasiadow: %d\n", min(card_nb)))
cat(sprintf("  Max sasiadow: %d\n", max(card_nb)))
cat(sprintf("  Mediana sasiadow: %.0f\n", median(card_nb)))

n_islands <- sum(card_nb == 0)
cat(sprintf("  Wysp (0 sasiadow): %d\n", n_islands))

if (n_islands > 0) {
  island_ids <- voronoi_raw$id[card_nb == 0]
  cat(sprintf("  ID wysp: %s\n", paste(island_ids, collapse = ", ")))
}

if (!is.na(build_result$k_optimal)) {
  cat(sprintf("  Optymalny k: %d\n", build_result$k_optimal))
  cat(sprintf("  AIC (Y~1): %.2f\n", build_result$aic))
}

# Histogram sasiadow
cat("\n  Rozklad liczby sasiadow:\n")
nb_table <- table(card_nb)
for (val in names(nb_table)) {
  cat(sprintf("    %2s sasiadow: %d kafli\n", val, nb_table[val]))
}

# 6. Zapis do RDS

rds_path <- "/app/data/research_W.rds"
cat(sprintf("\n[5] Zapis do %s...\n", rds_path))

# Ensure directory exists
dir.create(dirname(rds_path), showWarnings = FALSE, recursive = TRUE)

saveRDS(build_result, file = rds_path)

file_kb <- file.size(rds_path) / 1024
cat(sprintf("Zapisano (%.0f KB).\n", file_kb))

# Weryfikacja odczytu
cat("Weryfikacja odczytu RDS...\n")
verify <- readRDS(rds_path)
if (!is.null(verify$listw) && inherits(verify$listw, "listw")) {
  cat("  OK: listw poprawnie odczytany.\n")
} else {
  cat("  BLAD: listw nie jest poprawny!\n")
  quit(status = 1)
}

# 6b. Eksport krawedzi W do GeoJSON (dla wizualizacji)

cat("\n[6] Eksport krawedzi macierzy W do GeoJSON...\n")

tryCatch({
  # Pobierz centroidy z voronoi_sf
  centroids <- st_centroid(voronoi_sf)
  coords <- st_coordinates(centroids)

  nb <- build_result$nb
  n_regions <- length(nb)

  # Buduj krawedzie (unikaj duplikatow i->j oraz j->i)
  edges <- list()
  edge_id <- 0

  for (i in 1:n_regions) {
    neighbors <- nb[[i]]
    for (j in neighbors) {
      if (j > i && j <= n_regions) {
        edge_id <- edge_id + 1
        x1 <- coords[i, 1]
        y1 <- coords[i, 2]
        x2 <- coords[j, 1]
        y2 <- coords[j, 2]
        line <- st_linestring(matrix(c(x1, x2, y1, y2), ncol = 2))
        edges[[edge_id]] <- line
      }
    }
  }

  cat(sprintf("  Utworzono %d krawedzi\n", length(edges)))

  if (length(edges) > 0) {
    edges_sfc <- st_sfc(edges, crs = 4326)
    edges_sf <- st_sf(id = 1:length(edges), geometry = edges_sfc)

    geojson_path <- "/app/data/w_matrix_edges.geojson"
    st_write(edges_sf, geojson_path, driver = "GeoJSON", delete_dsn = TRUE, quiet = TRUE)

    file_kb <- file.size(geojson_path) / 1024
    cat(sprintf("  Zapisano: %s (%.1f KB)\n", geojson_path, file_kb))
  } else {
    cat("  UWAGA: Brak krawedzi do eksportu.\n")
  }
}, error = function(e) {
  cat(sprintf("  UWAGA: Nie udalo sie wyeksportowac krawedzi: %s\n", e$message))
  # Non-fatal - kontynuuj pipeline
})

# 7. Podsumowanie

cat("\n============================================================\n")
cat("05_matrix_w ZAKONCZONY POMYSLNIE\n")
cat("============================================================\n")
cat(sprintf("Metoda: %s\n", build_result$method))
cat(sprintf("Regionow: %d\n", length(build_result$nb)))
cat(sprintf("Srednia sasiadow: %.1f\n", mean(card_nb)))
cat(sprintf("Wysp: %d\n", n_islands))
if (!is.na(build_result$k_optimal)) {
  cat(sprintf("Optymalny k: %d (AIC=%.2f)\n",
              build_result$k_optimal, build_result$aic))
}
cat(sprintf("RDS: %s (%.0f KB)\n", rds_path, file_kb))
cat(sprintf("Czas: %.1f s\n", elapsed))
cat("============================================================\n")
