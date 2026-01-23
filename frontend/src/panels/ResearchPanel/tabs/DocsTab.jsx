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
      RESEARCH Mode — Pipeline 8 kroków
    </h2>
    <p className="text-gray-400">
      Orkiestrator:{" "}
      <code className="font-mono text-green-400">
        src/analytics/orchestrator_research.py
      </code>{" "}
      — klasa{" "}
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
              "UPDATE population, population_density",
            ],
            [
              "03",
              "osm_features",
              "research/03_osm_features.R",
              "UPDATE 5 predyktorów OSM",
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
  ↓ 01_geometry   — Voronoi tessellation lub grid 500m → DB
  ↓ 02_population — JOIN z GUS 500m grid → population per komórka
  ↓ 03_osm        — 5 predyktorów OSM → forest, roads, buildings, water, barriers
  ↓ 04_variable_y — Y continuous → y_<formula> w DB
  ↓ 05_matrix_w   — macierz W → /app/data/research_W.rds
  ↓ 06_model      — SAR/SEM/SDM → /app/data/research_model.rds
  ↓ 07_diagnostics— Moran, LM, LISA, ETA, VIF → analytics_researchdiagnostics
  ↓ 08_results    — ensemble_risk → WebSocket pipeline_complete → mapa`}</Code>

    <h3 className="text-lg font-semibold text-white mt-2">
      Wymiana danych między krokami
    </h3>
    <p className="text-gray-400">
      Pliki RDS przekazywane przez filesystem kontenera (
      <code className="font-mono text-gray-300">/app/data/</code>):
    </p>
    <ul className="list-disc list-inside space-y-1 text-gray-400 mt-1">
      <li>
        <code className="font-mono text-green-400">research_W.rds</code> —
        macierz W (krok 5 → kroki 6, 7)
      </li>
      <li>
        <code className="font-mono text-green-400">research_model.rds</code> —
        wyestymowany model (krok 6 → krok 7)
      </li>
      <li>
        <code className="font-mono text-green-400">w_matrix_edges.geojson</code>{" "}
        — wizualizacja W w MapLibre (krok 5 → endpoint)
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
      W trybie PUB (Voronoi 1:1) każda komórka ma dokładnie 1 obserwację —{" "}
      <code className="font-mono text-gray-300">count = 1</code> zawsze → brak
      wariancji w Y → SAR/SEM niemożliwy.
    </p>
    <p className="mt-2">
      W trybie RESEARCH zmienna Y jest tworzona explicite jako{" "}
      <strong className="text-white">continuous variable</strong> przez krok 4.
      Wariancja istnieje → SAR/SEM działa metodologicznie.
    </p>

    <h3 className="text-lg font-semibold text-white mt-4">5 formuł Y</h3>
    <div className="space-y-3">
      {[
        {
          name: "count_pop",
          formula: "Y = sighting_count / population",
          desc: "Rate na mieszkańca. Normalizuje przez gęstość zaludnienia.",
          color: "blue",
        },
        {
          name: "inv_pop",
          formula: "Y = 1 / population",
          desc: "Odwrotność populacji. Wyższe ryzyko tam gdzie mniej ludzi (dziki unikają gęstej zabudowy).",
          color: "blue",
        },
        {
          name: "log_pop",
          formula: "Y = −log(population)",
          desc: "Default. Skośne rozkłady. Logarytmiczny efekt populacji.",
          color: "green",
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
          desc: "Presence/absence. Wymaga modelu probit/logit — nie SAR/SEM (Gaussian).",
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
      <code className="font-mono text-green-400">ResearchConfig</code> odrzuca
      kombinacje Voronoi + BINARY — znowu problem count=1 per komórka Voronoi
      (brak wariancji w Y binarnym). Źródło:{" "}
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
      Macierz W definiuje "sąsiedztwo" — które komórki wpływają na które w
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
          Iteruje k od{" "}
          <code className="font-mono text-gray-300">RESEARCH_K_RANGE_MIN</code>{" "}
          do{" "}
          <code className="font-mono text-gray-300">RESEARCH_K_RANGE_MAX</code>,
          dla każdego k buduje W i estymuje{" "}
