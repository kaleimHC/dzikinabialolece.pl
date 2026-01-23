/**
 * CodeTab.jsx - Wartościowe snippety kodu RESEARCH pipeline
 * Źródła: ścieżki i numery linii do plików repo
 */

import React, { useState } from "react";

const FileRef = ({ path, lines }) => (
  <div className="flex items-center gap-2 mb-2 text-xs text-gray-500">
    <span className="font-mono">{path}</span>
    {lines && <span className="text-gray-600">:{lines}</span>}
  </div>
);

const Code = ({ children }) => (
  <pre className="bg-gray-950 rounded p-3 text-xs overflow-x-auto my-2 leading-relaxed">
    <code className="text-green-400 font-mono">{children}</code>
  </pre>
);

const LangBadge = ({ lang }) => {
  const styles = {
    py: "bg-blue-900/50 text-blue-300 border-blue-700",
    r: "bg-emerald-900/50 text-emerald-300 border-emerald-700",
    js: "bg-yellow-900/50 text-yellow-300 border-yellow-700",
  };
  return (
    <span
      className={`inline-block px-1.5 py-0.5 rounded text-xs border font-mono ${styles[lang]}`}
    >
      {lang.toUpperCase()}
    </span>
  );
};


const OrchestratorSection = () => (
  <div className="space-y-6 text-gray-300 text-sm">
    <h2 className="text-xl font-bold text-white">
      Python: Orkiestrator & Celery
    </h2>

    {/* PIPELINE_STEPS */}
    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        PIPELINE_STEPS - definicja 8 kroków
      </h3>
      <FileRef path="src/analytics/orchestrator_research.py" lines="66-115" />
      <p className="text-gray-400 mb-2">
        Lista kroków iterowana przez orchestrator. Każdy krok: name,
        description, type (R/Python), script.
      </p>
      <Code>{`PIPELINE_STEPS = [
    { 'name': '01_geometry',     'description': 'Generate spatial units (Voronoi / grid)',
      'type': StepType.R,        'script': '01_generate_voronoi.R' },
    { 'name': '02_population',   'description': 'Assign population to spatial units',
      'type': StepType.R,        'script': 'research/02_population.R' },
    { 'name': '03_osm_features', 'description': 'Calculate OSM environmental features',
      'type': StepType.R,        'script': 'research/03_osm_features.R' },
    { 'name': '04_variable_y',   'description': 'Compute dependent variable Y',
      'type': StepType.R,        'script': 'research/04_variable_y.R' },
    { 'name': '05_matrix_w',     'description': 'Build spatial weights matrix W',
      'type': StepType.R,        'script': 'research/05_matrix_w.R' },
    { 'name': '06_model',        'description': 'Fit spatial model (SAR/SEM/SDM/probit/logit)',
      'type': StepType.R,        'script': '02_spatial_models.R' },
    { 'name': '07_diagnostics',  'description': "Run diagnostics (Moran's I, LM tests, LISA)",
      'type': StepType.R,        'script': 'research/07_diagnostics.R' },
    { 'name': '08_results',      'description': 'Ensemble prediction and final risk map',
      'type': StepType.R,        'script': '05_ensemble_prediction.R' },
]`}</Code>
    </div>

    {/* run_r_script */}
    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        run_r_script() - Docker runner
      </h3>
      <FileRef path="src/analytics/orchestrator_research.py" lines="136-217" />
      <p className="text-gray-400 mb-2">
        Uruchamia skrypt R jako kontener Docker. Zwraca (exit_code, stdout,
        stderr). Klucz: wolumeny RDS przez{" "}
        <code className="font-mono text-gray-300">dziki_r_data</code> (shared
        między krokami), R scripts montowane jako read-only.
      </p>
      <Code>{`def run_r_script(
    script_name: str,
    extra_env: Optional[dict] = None,
    image: str = 'dziki-worker-r:latest',
    timeout: int = 600,
) -> tuple[int, str, str]:

    client = docker.from_env()
    env = {**_build_db_env(), **(extra_env or {})}

    try:
        container_output = client.containers.run(
            image,
            command=['Rscript', '--vanilla', f'/app/r_scripts/{script_name}'],
            environment=env,
            network='dziki_dziki-internal',
            volumes={
                'dziki_r_data':  {'bind': '/app/data',      'mode': 'rw'},
                r_scripts_host:  {'bind': '/app/r_scripts',  'mode': 'ro'},
            },
            remove=True,
            mem_limit='4g',
        )
        output = container_output.decode('utf-8')
        return (0, output, '')               # sukces

    except docker.errors.ContainerError as e:
        stderr = e.stderr.decode('utf-8')[:2000] if e.stderr else str(e)
        exit_code = e.exit_status if hasattr(e, 'exit_status') else 1
        return (exit_code, '', stderr)       # fail-fast -> orchestrator raise PipelineError
    except docker.errors.ImageNotFound:
        return (1, '', f'Docker image not found: {image}')

# Exit codes: 0=sukces, 1=błąd wejścia, 2=timeout, 3=błąd obliczeniowy, 137=OOM`}</Code>
    </div>

    {/* Celery task */}
    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        Celery task - run_research_pipeline
      </h3>
      <FileRef path="src/analytics/tasks_research.py" lines="59-113" />
      <p className="text-gray-400 mb-2">
        Asynchroniczne opakowanie orkiestratora. Queue{" "}
        <code className="font-mono text-gray-300">q_cpu</code>, soft limit 5
        min, hard 6 min, zero retries.
      </p>
      <Code>{`@shared_task(
    bind=True,
    queue='q_cpu',
    soft_time_limit=300,   # 5 min soft
    time_limit=360,        # 6 min hard
    max_retries=0,
)
def run_research_pipeline(self, run_id: str):
    run = ResearchRun.objects.select_related('config').get(pk=run_id)

    orchestrator = ResearchOrchestrator(run.config, run=run)
    result = orchestrator.execute()

    return {
        'run_id': str(result.id),
        'status': result.status,
        'config_name': run.config.name,
        'n_cells': result.n_cells,
        'error': result.error_message,
    }`}</Code>
    </div>

    {/* to_env_dict */}
    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        ResearchConfig.to_env_dict() - konfiguracja jako ENV
      </h3>
      <FileRef path="src/analytics/models_research.py" lines="359-390" />
      <p className="text-gray-400 mb-2">
        Cała konfiguracja research → flat dict stringów → zmienne środowiskowe
        dla R scripts. Jedyne miejsce mapowania Python config → R runtime.
      </p>
      <Code>{`def to_env_dict(self):
    env = {
        'RESEARCH_GEOMETRY_TYPE':       self.geometry_type,
        'RESEARCH_POPULATION_METHOD':   self.population_method,
        'RESEARCH_Y_FORMULA':           self.y_formula,
        'RESEARCH_W_METHOD':            self.w_method,
        'RESEARCH_K_RANGE_MIN':         str(self.k_range_min),
        'RESEARCH_K_RANGE_MAX':         str(self.k_range_max),
        'RESEARCH_MODEL_TYPE':          self.model_type,
        'RESEARCH_ACTIVE_PREDICTORS':   ','.join(self.active_predictors or []),
        'RESEARCH_RUN_MORAN':           '1' if self.run_moran else '0',
        'RESEARCH_RUN_LM_TESTS':        '1' if self.run_lm_tests else '0',
        'RESEARCH_RUN_LISA':            '1' if self.run_lisa else '0',
        'RESEARCH_RUN_ETA':             '1' if self.run_eta else '0',
        'RESEARCH_VIF_THRESHOLD':       str(self.vif_threshold),
        'RESEARCH_ALPHA':               str(self.alpha),
        'RESEARCH_SEED':                str(self.seed),
        'RESEARCH_USE_REGIME':          '1' if self.use_regime_model else '0',
        'RESEARCH_REGIME_TYPE':         self.regime_type,
        'RESEARCH_REGIME_THRESHOLD':    str(self.regime_threshold),
        'RESEARCH_REGIME_THRESHOLD_URBAN': str(self.regime_threshold_urban),
        # + RESEARCH_DATE_FROM / RESEARCH_DATE_TO jeśli ustawione
    }
    return env`}</Code>
    </div>
  </div>
);


const TessellationSection = () => (
  <div className="space-y-6 text-gray-300 text-sm">
    <h2 className="text-xl font-bold text-white">R: Tessellacja Voronoi</h2>
    <p className="text-gray-400">
      Krok 1 pipeline. Dwie ścieżki geometrii w jednym skrypcie.
    </p>

    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        Voronoi tessellation (ścieżka voronoi)
      </h3>
      <FileRef path="r_scripts/01_generate_voronoi.R" lines="132-200" />
      <p className="text-gray-400 mb-2">
        Jitter punktów przed tessellacją (duplikaty GPS → zdegenerowane
        komórki). Następnie Voronoi, clip do granicy Białołęki, wykluczenie
        Wisły.
      </p>
      <Code>{`# Jitter dla duplikatów GPS (±~1m, set.seed(42))
crds$X_coord <- crds$X_coord + rnorm(n_sightings, 0, sd(crds$X_coord) / 1000)
crds$Y_coord <- crds$Y_coord + rnorm(n_sightings, 0, sd(crds$Y_coord) / 1000)

# Voronoi tessellation (EPSG:3857 → 4326 po przycinaniu)
crds_union   <- st_union(st_geometry(sightings_jittered))
voronoi_raw  <- st_voronoi(crds_union, region_sfc)
voronoi_cast <- st_cast(voronoi_raw)

# Clip do granicy Białołęki
voronoi_clipped <- st_intersection(voronoi_cast, st_union(region_sfc))
voronoi_4326    <- st_transform(voronoi_clipped, 4326)

# Wykluczenie Wisły (jeśli dostępna)
if (!is.null(wisla_buffered)) {
  voronoi_4326 <- st_difference(voronoi_4326, st_union(wisla_buffered))
  voronoi_4326 <- voronoi_4326[!st_is_empty(voronoi_4326)]
}

# Spatial join - liczba obserwacji per komórka
grid_cells <- st_sf(
  grid_id = sprintf("VORONOI_%04d", seq_along(voronoi_4326)),
  geometry = voronoi_4326, sighting_count = 0L, district = "Bialoleka"
)
grid_cells$sighting_count <- lengths(st_intersects(grid_cells, sightings))`}</Code>
    </div>

    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        Grid 500m (ścieżka grid_500)
      </h3>
      <FileRef path="r_scripts/01_generate_voronoi.R" lines="201-258" />
      <p className="text-gray-400 mb-2">
        Reużywa siatki GUS 500m zamiast generować nową - bezpośredni JOIN z
        bazą. Efekt: 342 komórki w granicach Białołęki (siatka GUS 500m, niezależna od próby).
      </p>
      <Code>{`# grid_500 - reużywamy siatki GUS (1:1 alignment z population grid)
} else if (geometry_type == "grid_500") {

  # SQL pobiera TYLKO geometrię + populację GUS (zliczanie NIE w SQL):
  gus_raw <- dbGetQuery(conn, "
    SELECT g.id   AS gus_id,
           g.code AS gus_code,
           g.tot  AS population,
           ST_AsText(g.geom) AS wkt
    FROM gus_population_grid_500m g, boundaries b
    WHERE b.name = 'bialoleka'
      AND ST_Intersects(g.geom, b.geom)
    ORDER BY g.id
  ")

  grid_sf <- st_as_sf(gus_raw, wkt = "wkt", crs = 4326)

  # sighting_count liczony w R (NIE w SQL):
  grid_sf$sighting_count <- lengths(st_intersects(grid_sf, sightings))`}</Code>
    </div>
  </div>
);


const VariableYSection = () => (
  <div className="space-y-6 text-gray-300 text-sm">
    <h2 className="text-xl font-bold text-white">R: Zmienna zależna Y</h2>

    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        Zapewnienie kolumn Y w DB
      </h3>
      <FileRef path="r_scripts/research/04_variable_y.R" lines="112-117" />
      <p className="text-gray-400 mb-2">
        Krok 4 dodaje kolumny idempotentnie (ADD COLUMN IF NOT EXISTS).
        Wszystkie 6 kolumn Y zawsze istnieje w tabeli - tylko aktywna formula
        jest obliczana.
      </p>
      <Code>{`# Idempotentne tworzenie kolumn Y
for (col in c("y_log_intensity", "y_count_pop", "y_inv_pop", "y_log_pop", "y_log_count", "y_binary")) {
  dbExecute(conn, sprintf("
    ALTER TABLE %s
    ADD COLUMN IF NOT EXISTS %s DOUBLE PRECISION DEFAULT 0
  ", TARGET_TABLE, col))
}`}</Code>
    </div>

    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        Formuły Y jako SQL expressions
      </h3>
      <FileRef path="r_scripts/research/04_variable_y.R" lines="124-132" />
      <p className="text-gray-400 mb-2">
        Obliczenia w SQL (nie R) - bezpośredni UPDATE per formuła.
        <code className="font-mono text-gray-300">
          {" "}
          switch(y_formula, ...)
        </code>{" "}
        mapuje na SQL expression wykonywany przez PostgreSQL. Default to{" "}
        <code className="font-mono text-gray-300">log_intensity</code> = log
        intensywności zgłoszeń na powierzchnię (nie populacja). Warianty
        populacyjne (inv_pop / log_pop) są opt-in proxy hipotezy unikania
        zabudowy.
      </p>
      <Code>{`# SQL expression dobierany przez switch()
y_sql <- switch(y_formula,
  # DEFAULT: sighting intensity per area with +1 continuity (matches 02_spatial_models.R).
  "log_intensity" = "ln((sighting_count + 1.0) / GREATEST(ST_Area(geometry::geography) / 1000000.0, 1e-6))",
  "count_pop" = "sighting_count::double precision / population",
  "inv_pop"   = "1.0 / population",
  "log_pop"   = "-ln(population)",
  "log_count" = "ln(sighting_count + 1)",
  "binary"    = "CASE WHEN sighting_count > 0 THEN 1.0 ELSE 0.0 END"
)
# fallback do log_intensity dla nieznanej formuly
# → UPDATE $TARGET_TABLE SET y_<formula> = <y_sql>, spatial_risk = ...`}</Code>
    </div>

    <div className="bg-gray-800/40 rounded p-3 text-xs text-gray-400">
      <strong className="text-white">Dlaczego SQL zamiast R?</strong> Dane są w
      PostgreSQL. Obliczenie Y w SQL = zero transferu danych do R, zero
      wektoryzacji w R. UPDATE per komórka na poziomie bazy - szybsze i
      prostsze. Uwaga: model (02_spatial_models.R) i tak liczy Y samodzielnie z
      tej samej formuły; kolumny y_* w bazie są poglądowe.
    </div>
  </div>
);


const MatrixWSection = () => (
  <div className="space-y-6 text-gray-300 text-sm">
    <h2 className="text-xl font-bold text-white">
      R: Macierz wag przestrzennych W
    </h2>

    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        contiguity - queen
      </h3>
      <FileRef path="r_scripts/research/05_matrix_w.R" lines="114-129" />
      <p className="text-gray-400 mb-2">
        Najprostsza metoda. Sąsiedzi = komórki dzielące krawędź lub narożnik.
        Row-standardized: W_ij = 1/n_i dla sąsiadów.
      </p>
      <Code>{`if (w_method == "contiguity") {
  nb <- poly2nb(voronoi_sf, queen = TRUE)
  W  <- nb2listw(nb, style = "W", zero.policy = TRUE)

  build_result <- list(
    listw     = W,
    nb        = nb,
    method    = "contiguity",
    k_optimal = NA_integer_,
    aic       = NA_real_
  )
}`}</Code>
    </div>

    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        knn_aic - k-NN z AIC
      </h3>
      <FileRef path="r_scripts/research/05_matrix_w.R" lines="130-278" />
      <p className="text-gray-400 mb-2">
        Operacyjny default (<code className="font-mono text-gray-300">RESEARCH_W_METHOD</code>
        ) - tym policzono wszystkie dotychczasowe wyniki. Iteruje k od RESEARCH_K_RANGE_MIN (domyślnie 2) do
        RESEARCH_K_RANGE_MAX. Dla każdego k: fituje formę LAG{" "}
        <code className="font-mono text-gray-300">lagsarlm(Y~1, listw)</code> i
        zapisuje AIC. Wybiera k z najniższym AIC. Selekcja na lag-form zgadza się
        z estymowanym SAR (02_spatial_models.R). contiguity/tessW są dostępne i
        metodologicznie zasadne, ale nie są shipowanym defaultem i nie były dotąd
        uruchamiane. Fallback do contiguity jeśli Y ma zerową wariancję.
      </p>
      <Code>{`} else if (w_method == "knn_aic") {

  # Projekcja na EPSG:2180 (metryczny) - kNN wymaga metrów
  voronoi_proj <- st_transform(voronoi_sf, 2180)
  coords <- st_coordinates(st_centroid(voronoi_proj))
  Y <- voronoi_raw$spatial_risk

  # Fallback jeśli Y bez wariancji
  if (sd(Y, na.rm = TRUE) == 0) {
    nb <- poly2nb(voronoi_sf, queen = TRUE)
    W  <- nb2listw(nb, style = "W", zero.policy = TRUE)
    # → build_result method = "contiguity_fallback"
  } else {
    # Iteracja k, wybór wg AIC na formie LAG lagsarlm(Y~1)
    for (k in k_min_eff:k_max_eff) {
      nb_k <- knn2nb(knearneigh(coords, k = k))
      nb_k <- make.sym.nb(nb_k)   # kNN asymetryczne, spatialreg wymaga symetrii
      W_k  <- nb2listw(nb_k, style = "W")
      fit  <- lagsarlm(Y ~ 1, listw = W_k)
      aic_k <- AIC(fit)
      # zapisz k z min(AIC)
    }
  }
}`}</Code>
    </div>
  </div>
);


const ModelSection = () => (
  <div className="space-y-6 text-gray-300 text-sm">
    <h2 className="text-xl font-bold text-white">
      R: Model SAR/SEM - auto-selekcja
    </h2>

    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        Logika wyboru modelu
      </h3>
      <FileRef path="r_scripts/02_spatial_models.R" lines="351-588" />
      <p className="text-gray-400 mb-2">
        Przy <code className="font-mono text-gray-300">model_type=auto</code>:
        decyzja przez porównanie AIC -{" "}
        <code className="font-mono text-green-400">
          if (sar_result$AIC {"<"} sem_result$AIC)
        </code>{" "}
        → SAR, else SEM. Przy wymuszonej wartości (sar/sem/sdm) - bezpośrednia
        estymacja.
      </p>
      <Code>{`# Które modele estymować?
fit_sar <- model_type %in% c("auto", "sar")
fit_sem <- model_type %in% c("auto", "sem")
fit_sdm <- (model_type == "sdm")

# SAR: y = ρWy + Xβ + ε
if (fit_sar) {
  model <- lagsarlm(eq, data = gridcells_raw, listw = listw, method = "LU")
  # model$rho - parametr autokorelacji
  # AIC(model) - kryterium wyboru
}

# SEM: y = Xβ + u,   u = λWu + ε
if (fit_sem) {
  model <- errorsarlm(eq, data = gridcells_raw, listw = listw, method = "LU", Durbin = FALSE)
  # model$lambda - parametr autokorelacji błędów
}

# SDM: y = ρWy + Xβ + WXγ + ε  (lagsarlm type="mixed")
if (fit_sdm) {
  model <- lagsarlm(eq, data = gridcells_raw, listw = listw,
                    type = "mixed", method = "LU")
}

# Auto-selekcja (model_type == "auto")
# → wybór przez min(AIC) spośród SAR, SEM

# Wynik: saveRDS(model_for_diag, "/app/data/research_model.rds")`}</Code>
    </div>

    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        Regime model (opcjonalnie)
      </h3>
      <FileRef path="r_scripts/02_spatial_models.R" lines="299-342" />
      <p className="text-gray-400 mb-2">
        Opt-in (default pooled, use_regime=0). Regime (forest/urban/mixed) jest
        WYPROWADZONY z forest_cover + building_density (krok 04), więc interakcja
        regime z tymi samymi predyktorami byłaby samo-kolinearna. Dlatego
        forests_z / buildings_z zostają jako pooled main effects, a regime
        interaguje TYLKO z predyktorami nie-definiującymi. Formula z "0 +" usuwa
        intercept globalny: każdy regime ma swój.
      </p>
      <Code>{`# Regime model - interakcje TYLKO z predyktorami nie-definiujacymi
if (use_regime && regime_type %in% c("binary", "trinary")) {
  gridcells_raw$regime <- factor(gridcells_raw$regime,
                                  levels = c("urban", "mixed", "forest"))
  # regime jest pochodna forest/building -> nie interaguj z nimi (kolinearnosc)
  regime_defining <- c("forests_z", "buildings_z")
  interact_z <- setdiff(z_names, regime_defining)   # interakcje regime:(...)
  maineff_z  <- intersect(z_names, regime_defining)  # pooled main effects
  terms <- "0 + regime"
  if (length(interact_z) > 0)
    terms <- paste(terms, sprintf("regime:(%s)", paste(interact_z, collapse = " + ")), sep = " + ")
  if (length(maineff_z) > 0)
    terms <- paste(terms, paste(maineff_z, collapse = " + "), sep = " + ")
  eq_str <- paste("Y ~", terms)
} else {
  eq_str <- paste("Y ~", paste(z_names, collapse = " + "))
}
eq <- as.formula(eq_str)`}</Code>
    </div>
  </div>
);


const DiagnosticsSection = () => (
  <div className="space-y-6 text-gray-300 text-sm">
    <h2 className="text-xl font-bold text-white">
      R: Diagnostyki - Moran I, LM, VIF
    </h2>

    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        Moran's I - autokorelacja reszt
      </h3>
      <FileRef path="r_scripts/research/07_diagnostics.R" lines="287-319" />
      <p className="text-gray-400 mb-2">
        Test na resztach modelu (nie na Y). Jeśli reszty mają autokorelację →
        model nie wyczyścił zależności przestrzennej.
      </p>
      <Code>{`if (run_moran) {
  # Test na resztach modelu (lub Y jeśli reszty niedostępne)
  moran_input <- if (!is.null(resids)) resids else Y

  moran_result <- moran.test(moran_input, listw = listw, zero.policy = TRUE)

  diag$moran_i        <- round(moran_result$estimate["Moran I statistic"], 6)
  diag$moran_expected <- round(moran_result$estimate["Expectation"], 6)
  diag$moran_variance <- round(moran_result$estimate["Variance"], 6)
  diag$moran_z        <- round(moran_result$statistic, 4)
  diag$moran_p        <- round(moran_result$p.value, 6)

  sig <- if (diag$moran_p < alpha) "ISTOTNY" else "nieistotny"
  # ISTOTNY → model nie wyczyścił autokorelacji
  # nieistotny → OK, model dobrze uchwycił strukturę przestrzenną
}`}</Code>
    </div>

    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        LM testy - selekcja SAR vs SEM
      </h3>
      <FileRef path="r_scripts/research/07_diagnostics.R" lines="327-360" />
      <p className="text-gray-400 mb-2">
        Lagrange Multiplier tests z pakietu spdep.{" "}
        <code className="font-mono text-gray-300">lm.RStests</code> (następca
        deprecated <code className="font-mono text-gray-300">lm.LMtests</code>).
        Wyniki: RSlag (dla SAR), RSerr (dla SEM), adjRSlag/adjRSerr (Robust LM).
      </p>
      <Code>{`if (run_lm_tests && !is.null(ols_model)) {
  lm_result <- lm.RStests(
    ols_model, listw = listw, zero.policy = TRUE,
    test = "all"   # RSlag, RSerr, adjRSlag, adjRSerr, SARMA
  )

  # Ekstraktuj statystyki
  diag$lm_lag_stat   <- lm_result[["RSlag"]]$statistic
  diag$lm_lag_p      <- lm_result[["RSlag"]]$p.value
  diag$lm_error_stat <- lm_result[["RSerr"]]$statistic
  diag$lm_error_p    <- lm_result[["RSerr"]]$p.value
  diag$rlm_lag_stat  <- lm_result[["adjRSlag"]]$statistic
  diag$rlm_error_stat<- lm_result[["adjRSerr"]]$statistic
  # → zapisane do analytics_researchdiagnostics
}`}</Code>
    </div>

    <div>
      <h3 className="text-base font-semibold text-white mb-1">
        VIF - współczynniki inflacji wariancji
      </h3>
      <FileRef path="r_scripts/research/07_diagnostics.R" lines="234-279" />
      <p className="text-gray-400 mb-2">
        Ręczna implementacja VIF (bez pakietu car) przez{" "}
        <code className="font-mono text-gray-300">
          R² regresji każdego predyktora na pozostałe
        </code>
        . VIF jest WYŁĄCZNIE informacyjny - nic nie jest usuwane z modelu.
        Predyktory powyżej{" "}
        <code className="font-mono text-gray-300">RESEARCH_VIF_THRESHOLD</code>{" "}
        (domyślnie 5.0) są tylko oznaczane i zapisywane do JSON{" "}
        <code className="font-mono text-gray-300">predictors_dropped</code>{" "}
        (mimo nazwy: flaga, nie usunięcie). Kolumny strukturalne (regime, regime:x)
        są pomijane.
      </p>
      <Code>{`# VIF = 1 / (1 - R²_j) gdzie R²_j z lm(X_j ~ X_-j)
X <- model.matrix(ols_model)[, -1, drop = FALSE]  # bez interceptu
vif_vals <- numeric(ncol(X))
names(vif_vals) <- colnames(X)

for (j in seq_len(ncol(X))) {
  r2 <- summary(lm(X[, j] ~ X[, -j]))$r.squared
  vif_vals[j] <- 1 / (1 - r2)
}
# VIF > vif_threshold → flag *** WYSOKI! (INFORMACYJNIE, nic nie usuwamy)
# Pomijaj kolumny strukturalne (regime, ":") - GVIF Fox-Monette wymagany
# Oznaczone predyktory → predictors_dropped JSON (tylko flaga)`}</Code>
    </div>
  </div>
);


const SECTIONS = [
  { id: "orchestrator", label: "Orkiestrator", lang: "py" },
  { id: "tessellation", label: "Tessellacja", lang: "r" },
  { id: "variable_y", label: "Zmienna Y", lang: "r" },
  { id: "matrix_w", label: "Macierz W", lang: "r" },
  { id: "model", label: "Model SAR/SEM", lang: "r" },
  { id: "diagnostics", label: "Diagnostyki", lang: "r" },
];

const CONTENT = {
  orchestrator: <OrchestratorSection />,
  tessellation: <TessellationSection />,
  variable_y: <VariableYSection />,
  matrix_w: <MatrixWSection />,
  model: <ModelSection />,
  diagnostics: <DiagnosticsSection />,
};

export default function CodeTab() {
  const [activeSection, setActiveSection] = useState("orchestrator");

  return (
    <div className="h-full flex">
      <nav className="w-44 flex-shrink-0 border-r border-gray-700 pr-4">
        <ul className="space-y-1">
          {SECTIONS.map((section, i) => (
            <li key={section.id}>
              <button
                onClick={() => setActiveSection(section.id)}
                className={`
                  w-full text-left px-3 py-2 rounded text-sm transition-colors
                  flex items-center gap-2
                  ${
                    activeSection === section.id
                      ? "bg-blue-600/30 text-blue-400"
                      : "text-gray-400 hover:text-white hover:bg-gray-700/50"
                  }
                `}
              >
                <LangBadge lang={section.lang} />
                <span>{section.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <main className="flex-1 pl-6 overflow-y-auto">
        {CONTENT[activeSection]}
      </main>
    </div>
  );
}
