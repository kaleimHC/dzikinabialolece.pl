#!/usr/bin/env Rscript
# 05_matrix_w.R
# Budowanie macierzy wag przestrzennych W
#
# Metody:
#   contiguity — Queen contiguity (poly2nb)
#   knn_aic    — k-NN z optymalizacja AIC (errorsarlm Y~1)
#   tessw      — tessW style: contiguity z wagami dl. wspolnej granicy
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
cat("05_matrix_w.R — Macierz wag przestrzennych W\n")
cat("============================================================\n")

# 1. Parametry z ENV

TARGET_TABLE <- Sys.getenv("RESEARCH_TARGET_TABLE", "sightings_gridcell_voronoi")
w_method <- Sys.getenv("RESEARCH_W_METHOD", "contiguity")
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
  cat(sprintf("k range: %d — %d\n", k_min, k_max))
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
  # ==========================================================================
  # Queen contiguity — sasiedzi dziela krawedz lub wierzcholek
  # ==========================================================================

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
  # ==========================================================================
  # k-NN z optymalizacja AIC
  # Fitujemy errorsarlm(Y ~ 1) dla kazdego k i wybieramy najlepszy AIC
  # ==========================================================================

  if (!requireNamespace("spatialreg", quietly = TRUE)) {
    cat("  Instalacja spatialreg...\n")
    install.packages("spatialreg", repos = "https://cloud.r-project.org")
  }
  library(spatialreg)

  # Projekcja na EPSG:2180 (metryczny uklad PL) — kNN wymaga metrow, nie stopni
  voronoi_proj <- st_transform(voronoi_sf, 2180)
  coords <- st_coordinates(st_centroid(voronoi_proj))
  Y <- voronoi_raw$spatial_risk

  cat(sprintf("  Centroidy: x range %.0f—%.0f, y range %.0f—%.0f (EPSG:2180)\n",
              min(coords[,1]), max(coords[,1]), min(coords[,2]), max(coords[,2])))

  # Efektywny zakres k (nie wiecej niz n-1)
  k_max_eff <- min(k_max, n - 1)
  k_min_eff <- min(k_min, k_max_eff)

  cat(sprintf("  Zakres k: %d — %d (efektywny)\n", k_min_eff, k_max_eff))

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

      fit <- tryCatch({
        errorsarlm(Y ~ 1, listw = W_k, Durbin = FALSE)
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
      cat("  Proba z lagsarlm (SAR) zamiast errorsarlm (SEM)...\n")

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
  # ==========================================================================
  # tessW — contiguity z wagami proporcjonalnymi do dl. wspolnej granicy
  # Inspiracja: tessW() z spatialWarsaw
  # Dluzsze wspolne granice = silniejsza interakcja przestrzenna
  # ==========================================================================

  cat("  Krok 1: Queen contiguity (struktura sasiedztwa)...\n")
  nb <- poly2nb(voronoi_sf, queen = TRUE)

  cat("  Krok 2: Obliczanie dlugosci wspolnych granic via PostGIS...\n")

  # Uzywamy PostGIS zamiast R do obliczen geometrycznych (szybciej + GIST)
  shared_lengths <- dbGetQuery(conn, sprintf("
    SELECT
      a.id as id_a,
      b.id as id_b,
