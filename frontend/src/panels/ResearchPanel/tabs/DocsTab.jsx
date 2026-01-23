/**
 * DocsTab.jsx - Metodologia Trybu Badawczego (RESEARCH)
 * Dokumentuje 8-step pipeline: orchestrator_research.py + R scripts
 */

import React, { useState } from "react";

const Code = ({ children }) => (
  <pre className="bg-gray-950 rounded p-3 text-sm overflow-x-auto my-2">
    <code className="text-green-400 font-mono">{children}</code>
  </pre>
);

const Formula = ({ children }) => (
  <div className="bg-gray-800/50 rounded p-2 my-2 font-mono text-blue-300 text-sm">
    {children}
  </div>
);

const Tag = ({ children, color = "blue" }) => {
  const colors = {
    blue: "bg-blue-900/40 text-blue-300 border-blue-700",
    green: "bg-green-900/40 text-green-300 border-green-700",
    yellow: "bg-yellow-900/40 text-yellow-300 border-yellow-700",
    purple: "bg-purple-900/40 text-purple-300 border-purple-700",
    gray: "bg-gray-800/60 text-gray-400 border-gray-600",
  };
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs border font-mono ${colors[color]}`}
    >
      {children}
    </span>
  );
};


const PipelineOverview = () => (
  <div className="space-y-4 text-gray-300 text-sm">
    <h2 className="text-xl font-bold text-white">
      RESEARCH Mode - Pipeline 8 kroków
    </h2>
    <p className="text-gray-400">
      Orkiestrator:{" "}
      <code className="font-mono text-green-400">
        src/analytics/orchestrator_research.py
      </code>{" "}
      - klasa{" "}
      <code className="font-mono text-gray-300">ResearchOrchestrator</code>.
      Każdy krok uruchamia skrypt R w izolowanym kontenerze Docker (
      <code className="font-mono text-gray-300">dziki-worker-r:latest</code>).
      Fail-fast: błąd kroku zatrzymuje cały pipeline.
    </p>

    <div className="overflow-x-auto mt-4">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left py-2 pr-3 text-gray-500 font-medium">
              Krok
            </th>
            <th className="text-left py-2 pr-3 text-gray-500 font-medium">
              Nazwa
            </th>
            <th className="text-left py-2 pr-3 text-gray-500 font-medium">
              Skrypt R
            </th>
            <th className="text-left py-2 text-gray-500 font-medium">Output</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/60">
          {[
            [
              "01",
              "geometry",
              "01_generate_voronoi.R",
              "tabela w DB (Voronoi lub grid_500)",
            ],
            [
              "02",
              "population",
              "research/02_population.R",
              "UPDATE population",
            ],
            [
              "03",
              "osm_features",
              "research/03_osm_features.R",
              "UPDATE do 11 predyktorów OSM",
            ],
            [
              "04",
              "variable_y",
              "research/04_variable_y.R",
              "UPDATE y_<formula>, spatial_risk",
            ],
            [
              "05",
              "matrix_w",
              "research/05_matrix_w.R",
              "research_W.rds + w_matrix_edges.geojson",
            ],
            ["06", "model", "02_spatial_models.R", "research_model.rds"],
            [
              "07",
              "diagnostics",
              "research/07_diagnostics.R",
              "INSERT → analytics_researchdiagnostics (34 kol.)",
            ],
            [
              "08",
              "results",
              "05_ensemble_prediction.R",
              "WebSocket pipeline_complete + mapa ryzyka",
            ],
          ].map(([n, name, script, output]) => (
            <tr key={n} className="hover:bg-gray-800/30">
              <td className="py-2 pr-3 font-mono text-gray-600">{n}</td>
              <td className="py-2 pr-3 font-semibold text-white">{name}</td>
              <td className="py-2 pr-3 font-mono text-green-400">{script}</td>
              <td className="py-2 text-gray-400">{output}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>

    <h3 className="text-lg font-semibold text-white mt-6">Przepływ danych</h3>
    <Code>{`sightings (punkty, status=verified)
  ↓ 01_geometry   - Voronoi tessellation lub grid 500m → DB
  ↓ 02_population - JOIN z GUS 500m grid → population per komórka
  ↓ 03_osm        - do 11 predyktorów OSM (default: wszystkie) → forest, buildings, roads, water, parks, meadow...
  ↓ 04_variable_y - Y continuous (default log_intensity) → y_<formula> w DB
  ↓ 05_matrix_w   - macierz W → /app/data/research_W.rds
  ↓ 06_model      - SAR/SEM/SDM → /app/data/research_model.rds
  ↓ 07_diagnostics- Moran, LM, LISA, ETA, VIF → analytics_researchdiagnostics
  ↓ 08_results    - ensemble_risk → WebSocket pipeline_complete → mapa`}</Code>

    <h3 className="text-lg font-semibold text-white mt-2">
      Wymiana danych między krokami
    </h3>
    <p className="text-gray-400">
      Pliki RDS przekazywane przez filesystem kontenera (
      <code className="font-mono text-gray-300">/app/data/</code>):
    </p>
    <ul className="list-disc list-inside space-y-1 text-gray-400 mt-1">
      <li>
        <code className="font-mono text-green-400">research_W.rds</code> -
        macierz W (krok 5 → kroki 6, 7)
      </li>
      <li>
        <code className="font-mono text-green-400">research_model.rds</code> -
        wyestymowany model (krok 6 → krok 7)
      </li>
      <li>
        <code className="font-mono text-green-400">w_matrix_edges.geojson</code>{" "}
        - wizualizacja W w MapLibre (krok 5 → endpoint)
      </li>
    </ul>
    <p className="text-gray-500 mt-2 text-xs">
      Każdy krok tworzy <code className="font-mono">ResearchStepLog</code> z
      stdout, stderr, exit_code, duration. Kody wyjścia: 0=sukces, 1=błąd
      wejścia, 2=timeout/brak danych, 3=błąd obliczeniowy, 137=OOM.
    </p>
  </div>
);


const VariableYNotes = () => (
  <div className="space-y-4 text-gray-300 text-sm">
    <h2 className="text-xl font-bold text-white">Krok 4: Zmienna zależna Y</h2>
    <p className="text-gray-500">
      Skrypt:{" "}
      <code className="font-mono text-green-400">
        r_scripts/research/04_variable_y.R
      </code>
    </p>

    <h3 className="text-lg font-semibold text-white mt-4">
      Dlaczego RESEARCH {"≠"} PUB
    </h3>
    <p>
      W trybie PUB (Voronoi 1:1) każda komórka ma dokładnie 1 obserwację -{" "}
      <code className="font-mono text-gray-300">count = 1</code> zawsze → brak
      wariancji w Y → SAR/SEM niemożliwy.
    </p>
    <p className="mt-2">
      W trybie RESEARCH zmienna Y jest tworzona explicite jako{" "}
      <strong className="text-white">continuous variable</strong> przez krok 4.
      Wariancja istnieje → SAR/SEM działa metodologicznie.
    </p>

    <h3 className="text-lg font-semibold text-white mt-4">6 formuł Y</h3>
    <div className="space-y-3">
      {[
        {
          name: "log_intensity",
          formula: "Y = log((sighting_count + 1) / area_km2)",
          desc: "Default. Intensywność zgłoszeń na powierzchnię (sygnał ryzyka, NIE populacja). Korekta +1 trzyma puste kafle skończone (log(1/area)). Na grid_500 (area ~stała) zbiega do log(count+1); na Voronoi (count=1) do -log(area). Liczona w 02_spatial_models.R.",
          color: "green",
        },
        {
          name: "count_pop",
          formula: "Y = sighting_count / population",
          desc: "Rate na mieszkańca. Normalizuje przez gęstość zaludnienia.",
          color: "blue",
        },
        {
          name: "inv_pop",
          formula: "Y = 1 / population",
          desc: "Proxy unikania populacji (opt-in, jawna hipoteza - nie miara ryzyka). Wyższe Y tam gdzie mniej ludzi.",
          color: "blue",
        },
        {
          name: "log_pop",
          formula: "Y = -log(population)",
          desc: "Proxy unikania populacji (opt-in). Modeluje -log(population), nie zgłoszenia. Logarytmiczny efekt populacji.",
          color: "blue",
        },
        {
          name: "log_count",
          formula: "Y = log(sighting_count + 1)",
          desc: "Dla grid_500, gdzie count > 1 jest możliwy. Nie zalecane dla Voronoi (count=1 zawsze).",
          color: "yellow",
        },
        {
          name: "binary",
          formula: "Y = 1 jeśli count > 0, else 0",
          desc: "Presence/absence. Wymaga modelu probit/logit - nie SAR/SEM (Gaussian).",
          color: "purple",
        },
      ].map((f) => (
        <div key={f.name} className="border-l-2 border-gray-700 pl-4">
          <div className="flex items-center gap-2 mb-1">
            <Tag color={f.color}>{f.name}</Tag>
          </div>
          <Formula>{f.formula}</Formula>
          <p className="text-gray-400 text-xs">{f.desc}</p>
        </div>
      ))}
    </div>

    <h3 className="text-lg font-semibold text-white mt-4">
      Walidacja konfiguracji
    </h3>
    <p className="text-gray-400">
      <code className="font-mono text-green-400">ResearchConfig.clean()</code>{" "}
      odrzuca: Voronoi + count_pop oraz Voronoi + binary (count=1 per komórka
      Voronoi - brak wariancji w Y) oraz SAR/SEM/SDM + binary (wymaga continuous
      Y). Waliduje też k_range i zakres dat. Źródło:{" "}
      <code className="font-mono text-gray-300">
        src/analytics/models_research.py
      </code>
      .
    </p>
  </div>
);


const MatrixWNotes = () => (
  <div className="space-y-4 text-gray-300 text-sm">
    <h2 className="text-xl font-bold text-white">
      Krok 5: Macierz wag przestrzennych W
    </h2>
    <p className="text-gray-500">
      Skrypt:{" "}
      <code className="font-mono text-green-400">
        r_scripts/research/05_matrix_w.R
      </code>
    </p>
    <p>
      Macierz W definiuje "sąsiedztwo" - które komórki wpływają na które w
      modelu SAR/SEM. Output:{" "}
      <code className="font-mono text-green-400">/app/data/research_W.rds</code>{" "}
      (obiekt <code className="font-mono text-gray-300">listw</code> z pakietu
      spdep).
    </p>

    <h3 className="text-lg font-semibold text-white mt-4">
      Trzy metody (RESEARCH_W_METHOD)
    </h3>
    <div className="space-y-4">
      <div className="border-l-4 border-blue-500 pl-4">
        <div className="flex items-center gap-2 mb-1">
          <Tag color="blue">contiguity</Tag>
          <span className="text-gray-500 text-xs">queen contiguity</span>
        </div>
        <p className="text-gray-400">
          Sąsiedzi = komórki dzielące krawędź lub narożnik. Zbudowana przez{" "}
          <code className="font-mono text-gray-300">poly2nb(queen=TRUE)</code> +{" "}
          <code className="font-mono text-gray-300">nb2listw(style="W")</code>.
        </p>
      </div>

      <div className="border-l-4 border-green-500 pl-4">
        <div className="flex items-center gap-2 mb-1">
          <Tag color="green">knn_aic</Tag>
          <span className="text-gray-500 text-xs">
            k-nearest neighbours z AIC
          </span>
        </div>
        <p className="text-gray-400">
          Operacyjny default - tym policzono wszystkie dotychczasowe wyniki
          (60/60 runów; contiguity i tessw są dostępne i principled, ale nie
          domyślne i nieuruchamiane). Iteruje k od{" "}
          <code className="font-mono text-gray-300">RESEARCH_K_RANGE_MIN</code>{" "}
          (default 2) do{" "}
          <code className="font-mono text-gray-300">RESEARCH_K_RANGE_MAX</code>,
          dla każdego k buduje W (kNN symetryzowane) i estymuje{" "}
          <code className="font-mono text-gray-300">lagsarlm(Y~1)</code> (forma
          lag, zgodna z SAR w kroku 6). Wybiera k z najniższym AIC. Selekcja
          intercept-only, więc to heurystyka wrażliwości, nie selektor
          merytoryczny. Inspiracja: funkcja{" "}
          <code className="font-mono text-gray-300">bestW()</code> wg
          metodologii Kopczewskiej - własna impl. (05_matrix_w.R).
        </p>
      </div>

      <div className="border-l-4 border-purple-500 pl-4">
        <div className="flex items-center gap-2 mb-1">
          <Tag color="purple">tessw</Tag>
          <span className="text-gray-500 text-xs">
            wagi proporcjonalne do wspólnej granicy
          </span>
        </div>
        <p className="text-gray-400">
          Queen contiguity z wagami proporcjonalnymi do długości wspólnej
          krawędzi. Bezpośrednio inspirowany funkcją{" "}
          <code className="font-mono text-gray-300">tessW()</code> wg
          metodologii Kopczewskiej - własna impl. (05_matrix_w.R:279-369).
        </p>
      </div>
    </div>

    <h3 className="text-lg font-semibold text-white mt-4">
      Wzory (row-standardized)
    </h3>
    <Formula>W_ij = 1/nᵢ jeśli i, j są sąsiadami</Formula>
    <Formula>W_ij = 0 w przeciwnym razie</Formula>
    <p className="text-gray-400 text-xs">
      nᵢ = liczba sąsiadów komórki i. Każdy wiersz sumuje się do 1.
    </p>

    <h3 className="text-lg font-semibold text-white mt-4">Wymóg CRS</h3>
    <p className="text-gray-400">
      <code className="font-mono text-gray-300">poly2nb()</code> (contiguity) jest
      topologiczna - działa na dowolnym CRS i w skrypcie liczona jest wprost na
      geometrii WGS84 (EPSG:4326). Metrów wymaga dopiero k-NN:{" "}
      <code className="font-mono text-gray-300">05_matrix_w.R</code> rzutuje na
      EPSG:2180 (<code className="font-mono text-gray-300">st_transform(voronoi_sf, 2180)</code>)
      tylko dla k-NN (odległości centroidów), nie dla contiguity.
    </p>
  </div>
);


const ModelNotes = () => (
  <div className="space-y-4 text-gray-300 text-sm">
    <h2 className="text-xl font-bold text-white">
      Krok 6: Model przestrzenny SAR/SEM/SDM
    </h2>
    <p className="text-gray-500">
      Skrypt:{" "}
      <code className="font-mono text-green-400">
        r_scripts/02_spatial_models.R
      </code>
    </p>
    <p className="text-gray-500 text-xs">
      Tylko RESEARCH - krok 6 nie ma zastosowania w PUB (brak wariancji Y,
      Voronoi 1:1 daje <code className="font-mono">count=1</code> zawsze).
      W RESEARCH czyta{" "}
      <code className="font-mono">research_W.rds</code> z kroku 5, zapisuje{" "}
      <code className="font-mono">research_model.rds</code> i{" "}
      <code className="font-mono">model_fitted</code> do tabeli. Diagnostyki w
      kroku 7.
    </p>

    <h3 className="text-lg font-semibold text-white mt-4">
      Auto-selekcja (RESEARCH_MODEL_TYPE=auto)
    </h3>
    <p className="text-gray-400">
      Krok 6 fituje SAR i SEM przez MLE ({" "}
      <code className="font-mono">lagsarlm</code>,{" "}
      <code className="font-mono">errorsarlm</code> z pakietu spatialreg).
      Auto-selekcja przez porównanie AIC:{" "}
      <code className="font-mono text-green-400">
        if (sar_result$AIC {"<"} sem_result$AIC)
      </code>{" "}
      → SAR, else SEM. Fallback do drugiego modelu jeśli jeden zawiedzie.
    </p>
    <p className="text-gray-400 mt-2 text-xs">
      LM testy (Elhorst 2010) obliczane w kroku 7 ({" "}
      <code className="font-mono">07_diagnostics.R</code>) jako post-hoc
      diagnostics - nie kryterium wyboru modelu.
    </p>

    <h3 className="text-lg font-semibold text-white mt-4">Modele</h3>
    <div className="space-y-3">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Tag color="blue">SAR</Tag>
          <span className="text-gray-500 text-xs">
            Spatial Autoregressive / Lag Model
          </span>
        </div>
        <Formula>y = ρWy + Xβ + ε</Formula>
        <p className="text-gray-400 text-xs">
          ρ (rho) - autokorelacja przestrzenna odpowiedzi. Sąsiedzi wpływają na
          wartość Y.
        </p>
      </div>
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Tag color="green">SEM</Tag>
          <span className="text-gray-500 text-xs">Spatial Error Model</span>
        </div>
        <Formula>y = Xβ + u, u = λWu + ε</Formula>
        <p className="text-gray-400 text-xs">
          λ (lambda) - autokorelacja przestrzenna błędów. Pominięte zmienne
          przestrzenne.
        </p>
      </div>
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Tag color="purple">SDM</Tag>
          <span className="text-gray-500 text-xs">Spatial Durbin Model</span>
        </div>
        <Formula>y = ρWy + Xβ + WXγ + ε</Formula>
        <p className="text-gray-400 text-xs">
          Ogólniejszy model - przestrzenny lag zarówno Y jak i X.
        </p>
      </div>
    </div>

    <h3 className="text-lg font-semibold text-white mt-4">Predyktory OSM</h3>
    <p className="text-gray-400">
      Zmienne niezależne X (z kroku 3, standaryzowane z-score). Default aktywny
      zestaw to 4 predyktory: forest_cover, building_density, road_density,
      distance_to_water. Krok 3 liczy do 11 cech OSM (m.in. parks, meadow,
      farmland, scrub, railway, barrier_resistance); aktywny podzbiór
      konfigurowalny przez{" "}
      <code className="font-mono text-gray-300">
        RESEARCH_ACTIVE_PREDICTORS
      </code>
      .
    </p>

    <Code>{`# r_scripts/02_spatial_models.R:559-588
# --- auto: wybor przez AIC ---
if (!sar_result$success && !sem_result$success) {
  # oba modele przestrzenne zawiodly -> fallback OLS
  best_result <- list(model = lm(eq, data = gridcells_raw), type = "OLS", ...)
} else if (!sar_result$success) {
  best_result <- sem_result    # SAR nieudany -> SEM
} else if (!sem_result$success) {
  best_result <- sar_result    # SEM nieudany -> SAR
} else if (sar_result$AIC < sem_result$AIC) {
  best_result <- sar_result    # WYBRANO: SAR (nizsze AIC)
} else {
  best_result <- sem_result    # WYBRANO: SEM (nizsze AIC)
}
# LM testy (lm.RStests) -> krok 7, post-hoc diagnostics, nie selekcja`}</Code>
  </div>
);


const DiagnosticsNotes = () => (
  <div className="space-y-4 text-gray-300 text-sm">
    <h2 className="text-xl font-bold text-white">Krok 7: Diagnostyki</h2>
    <p className="text-gray-500">
      Skrypt:{" "}
      <code className="font-mono text-green-400">
        r_scripts/research/07_diagnostics.R
      </code>
    </p>
    <p className="text-gray-400">
      Jedyne miejsce zapisu do tabeli{" "}
      <code className="font-mono text-green-400">
        analytics_researchdiagnostics
      </code>{" "}
      (34 kolumny). Odczytuje{" "}
      <code className="font-mono text-gray-300">research_W.rds</code> i{" "}
      <code className="font-mono text-gray-300">research_model.rds</code> z
      kroków 5 i 6.
    </p>

    <div className="space-y-5 mt-4">
      <div className="border-l-4 border-blue-500 pl-4">
        <div className="flex items-center gap-2 mb-1">
          <h3 className="font-bold text-white">Moran I</h3>
          <Tag color="blue">domyślnie włączony</Tag>
        </div>
        <p className="text-gray-400 mt-1">
          Globalna autokorelacja przestrzenna reszt modelu.
        </p>
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono">
          <span className="text-green-400">moran_i</span>
          <span className="text-gray-400">statystyka I ∈ [-1, +1]</span>
          <span className="text-green-400">moran_expected</span>
          <span className="text-gray-400">wartość oczekiwana E[I]</span>
          <span className="text-green-400">moran_z</span>
          <span className="text-gray-400">standaryzowana z-statystyka</span>
          <span className="text-green-400">moran_p</span>
          <span className="text-gray-400">p-value (jednostronne, H1: dodatnia autokorelacja)</span>
        </div>
      </div>

      <div className="border-l-4 border-yellow-500 pl-4">
        <div className="flex items-center gap-2 mb-1">
          <h3 className="font-bold text-white">LM / Robust LM testy</h3>
          <Tag color="blue">domyślnie włączone</Tag>
        </div>
        <p className="text-gray-400 mt-1">
          Lagrange Multiplier tests (lm.RStests z pakietu spdep, test="all").
          Post-hoc diagnostyka - auto-selekcja SAR vs SEM idzie po AIC (krok 6),
          nie po LM. LM dają tylko tekstową rekomendację w logu kroku 7.
        </p>
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono">
          <span className="text-green-400">lm_lag_stat / lm_lag_p</span>
          <span className="text-gray-400">test dla SAR (lag)</span>
          <span className="text-green-400">lm_error_stat / lm_error_p</span>
          <span className="text-gray-400">test dla SEM (error)</span>
          <span className="text-green-400">rlm_lag_stat / rlm_lag_p</span>
          <span className="text-gray-400">Robust LM lag</span>
          <span className="text-green-400">rlm_error_stat / rlm_error_p</span>
          <span className="text-gray-400">Robust LM error</span>
        </div>
      </div>

      <div className="border-l-4 border-purple-500 pl-4">
        <div className="flex items-center gap-2 mb-1">
          <h3 className="font-bold text-white">LISA</h3>
          <Tag color="yellow">opcjonalne</Tag>
        </div>
        <p className="text-gray-400 mt-1">
          Local Indicators of Spatial Association (Local Moran I). Klasyfikuje
          komórki do klastrów przestrzennych.
        </p>
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono">
          <span className="text-green-400">lisa_hh_count</span>
          <span className="text-gray-400">
            High-High - skupisko wysokiego ryzyka
          </span>
          <span className="text-green-400">lisa_ll_count</span>
          <span className="text-gray-400">
            Low-Low - skupisko niskiego ryzyka
          </span>
          <span className="text-green-400">lisa_hl_count</span>
          <span className="text-gray-400">High-Low - outlier</span>
          <span className="text-green-400">lisa_lh_count</span>
          <span className="text-gray-400">Low-High - outlier</span>
          <span className="text-green-400">lisa_ns_count</span>
          <span className="text-gray-400">Not Significant</span>
        </div>
      </div>

      <div className="border-l-4 border-green-500 pl-4">
        <div className="flex items-center gap-2 mb-1">
          <h3 className="font-bold text-white">ETA - entropia globalna</h3>
          <Tag color="yellow">opcjonalne</Tag>
        </div>
        <p className="text-gray-400 mt-1">
          Relative Shannon entropy - własna impl. (07_diagnostics.R:451-502).
          Wartość globalna dla całej tessellacji - nie per komórka.
        </p>
        <Formula>ETA = H / H_max = -Σ(rᵢ × ln(rᵢ)) / ln(n)</Formula>
        <p className="text-gray-400 text-xs">
          0 = silna aglomeracja, 1 = rozkład równomierny
        </p>
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono">
          <span className="text-green-400">eta_h_emp</span>
          <span className="text-gray-400">surowa entropia H</span>
          <span className="text-green-400">eta_h_max</span>
          <span className="text-gray-400">H_max = ln(n)</span>
          <span className="text-green-400">eta_h_rel</span>
          <span className="text-gray-400">ETA = H/H_max ∈ [0,1]</span>
        </div>
      </div>

      <div className="border-l-4 border-gray-600 pl-4">
        <div className="flex items-center gap-2 mb-1">
          <h3 className="font-bold text-white">VIF + współczynniki</h3>
          <Tag color="gray">zawsze</Tag>
        </div>
        <p className="text-gray-400 mt-1">
          Variance Inflation Factor per predyktor. Próg z konfiguracji (
          <code className="font-mono text-gray-300">
            RESEARCH_VIF_THRESHOLD
          </code>
          , domyślnie 5.0). VIF jest INFORMACYJNY - nic nie jest usuwane z
          modelu. Predyktory powyżej progu są jedynie oznaczane (
          <code className="font-mono text-green-400">predictors_dropped</code>),
          z pominięciem kolumn strukturalnych (regime, interakcje).
        </p>
        <p className="text-gray-400 mt-2">
          Spatial impacts tylko dla pooled SAR/SDM: direct/indirect/total
          effects wg LeSage {"&"} Pace (2009), R=500 symulacji. Pomijane dla
          modeli z interakcją regime (efekty różne per regime - jeden wiersz
          byłby nieważny) oraz dla SEM/OLS (β jak w OLS). Liczone w kroku 6,
          dostępne przez{" "}
          <code className="font-mono text-green-400">
            /api/research/impacts/
          </code>
          .
        </p>
      </div>
    </div>
  </div>
);


const SECTIONS = [
  { id: "pipeline", label: "Pipeline 8 kroków" },
  { id: "variable_y", label: "Zmienna Y" },
  { id: "matrix_w", label: "Macierz W" },
  { id: "model", label: "Model SAR/SEM" },
  { id: "diagnostics", label: "Diagnostyki" },
];

const CONTENT = {
  pipeline: <PipelineOverview />,
  variable_y: <VariableYNotes />,
  matrix_w: <MatrixWNotes />,
  model: <ModelNotes />,
  diagnostics: <DiagnosticsNotes />,
};

export default function DocsTab() {
  const [activeSection, setActiveSection] = useState("pipeline");

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
                  ${
                    activeSection === section.id
                      ? "bg-blue-600/30 text-blue-400"
                      : "text-gray-400 hover:text-white hover:bg-gray-700/50"
                  }
                `}
              >
                {i + 1}. {section.label}
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
