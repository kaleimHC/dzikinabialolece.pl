import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { STATUS_ICON, STATUS_COLOR } from "../../../utils/pipelineHelpers.jsx";

const FACTOR_NAMES = {
  forests_z: "Lasy",
  buildings_z: "Zabudowa",
  roads_z: "Drogi",
  water_z: "Woda",
  parks_z: "Parki",
  meadow_z: "Łąki",
  farmland_z: "Pola uprawne",
  allotments_z: "Działki",
  scrub_z: "Zarośla",
  railway_z: "Kolej",
  barriers_z: "Bariery",
};

const FACTOR_ICONS = {
  forests_z: "🌲",
  buildings_z: "🏢",
  roads_z: "🛣️",
  water_z: "💧",
  parks_z: "🌳",
  meadow_z: "🌿",
  farmland_z: "🌾",
  allotments_z: "🏡",
  scrub_z: "🌿",
  railway_z: "🚂",
  barriers_z: "🚧",
};

function SimpleView({ diagnostics, configSnapshot }) {
  const model = diagnostics?.model || {};
  const coefficients = model.coefficients || {};
  const isVoronoi = configSnapshot?.geometry_type === "voronoi";

  const predictors = Object.entries(coefficients).filter(
    ([name]) => name !== "(Intercept)",
  );

  const maxEstimate =
    predictors.length > 0
      ? Math.max(...predictors.map(([, c]) => Math.abs(c.estimate)))
      : 1;

  const sorted = [...predictors].sort((a, b) => {
    const aSignificant = a[1].p < 0.05;
    const bSignificant = b[1].p < 0.05;
    if (aSignificant !== bSignificant) return aSignificant ? -1 : 1;
    return Math.abs(b[1].estimate) - Math.abs(a[1].estimate);
  });

  return (
    <div className="space-y-3">
      <div className="text-xs">
        <span className="bg-gray-800 px-2 py-1 rounded text-gray-300">
          Model:{" "}
          <span className="text-white font-medium">
            {model.selected?.toUpperCase() || "?"}
          </span>
        </span>
      </div>

      {sorted.length > 0 ? (
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-700 bg-gray-800/80">
                <th className="text-left px-3 py-2 text-gray-400 font-medium">
                  Czynnik
                </th>
                <th className="text-left px-3 py-2 text-gray-400 font-medium w-28">
                  Siła
                </th>
                <th className="text-center px-3 py-2 text-gray-400 font-medium">
                  Wpływ
                </th>
                <th className="text-center px-2 py-2 text-gray-400 font-medium w-8"></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(([name, coef]) => {
                const isSignificant = coef.p < 0.05;
                const isPositive = coef.estimate > 0;
                const displayName =
                  FACTOR_NAMES[name] || name.replace("_z", "");
                const icon = FACTOR_ICONS[name] || "";
                const strength = Math.round(
                  (Math.abs(coef.estimate) / maxEstimate) * 100,
                );
                const barColor = isPositive ? "bg-red-500" : "bg-green-500";

                return (
                  <tr
                    key={name}
                    className="border-b border-gray-700/50 last:border-0"
                  >
                    <td className="px-3 py-2 text-gray-200">
                      {icon && <span className="mr-1.5">{icon}</span>}
                      {displayName}
                    </td>
                    <td className="px-3 py-2">
                      <div className="w-20 h-2 bg-gray-700 rounded overflow-hidden">
                        <div
                          className={`h-full ${barColor}`}
                          style={{ width: `${strength}%` }}
                        />
                      </div>
                    </td>
                    <td className="text-center px-3 py-2">
                      <span
                        className={
                          isPositive ? "text-red-400" : "text-green-400"
                        }
                      >
                        {isPositive ? "↑ zwiększa" : "↓ zmniejsza"}
                      </span>
                    </td>
                    <td className="text-center px-2 py-2">
                      {isSignificant && (
                        <span className="text-yellow-400">✓</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-gray-500 text-sm p-3 bg-gray-800 rounded-lg">
          Brak danych o czynnikach ryzyka.
        </div>
      )}

      {isVoronoi && diagnostics?.eta?.h_rel != null ? (
        <div className="flex items-center gap-2 text-xs bg-gray-800 rounded-lg p-2">
          <span className="text-gray-400">Skupienie punktów:</span>
          <span
            className={`font-medium ${
              diagnostics.eta.h_rel > 0.9
                ? "text-green-400"
                : diagnostics.eta.h_rel > 0.7
                  ? "text-yellow-400"
                  : "text-red-400"
            }`}
          >
            {diagnostics.eta.h_rel > 0.9
              ? "Równomierne"
              : diagnostics.eta.h_rel > 0.7
                ? "Umiarkowane skupienie"
                : "Silne skupienie (klastry)"}
          </span>
          <span className="text-gray-600 ml-auto">
            ETA={diagnostics.eta.h_rel?.toFixed(2)}
          </span>
        </div>
      ) : (
        !isVoronoi && (
          <div className="flex items-center gap-2 text-xs bg-gray-800/50 rounded-lg p-2 opacity-50">
            <span className="text-gray-500">Skupienie punktów:</span>
            <span className="text-gray-500 italic">n/d (tylko Voronoi)</span>
          </div>
        )
      )}

      <div className="text-[10px] text-gray-500 flex gap-4">
        <span>
          <span className="text-yellow-400">✓</span> = statystycznie istotny (p
          &lt; 0.05)
        </span>
      </div>
    </div>
  );
}

function FullDebugView({ diagnostics, steps, configSnapshot }) {
  const [expandedStep, setExpandedStep] = useState(null);
  const statusIcon = STATUS_ICON;
  const statusColor = STATUS_COLOR;

  return (
    <div className="space-y-3">
      <div className="bg-gray-800 p-3 rounded text-xs">
        <h4 className="font-medium text-gray-300 mb-2">Debug info</h4>
        <ul className="space-y-1 text-gray-400">
          <li>LISA HH: {diagnostics?.lisa?.hh ?? "brak danych"}</li>
          <li>LISA LL: {diagnostics?.lisa?.ll ?? "brak danych"}</li>
          <li>VIF: {diagnostics?.vif?.results ? "dostępne" : "brak danych"}</li>
          <li>
            k_selected: {diagnostics?.w_metrics?.k_selected ?? "brak danych"}
          </li>
          <li>
            impacts:{" "}
            {diagnostics?.impacts
              ? `TAK (${Object.keys(diagnostics.impacts.direct || {}).length} predyktorów)`
              : "NIE (SEM/OLS lub brak danych)"}
          </li>
        </ul>
      </div>

      <div className="bg-gray-800 p-3 rounded text-xs">
        <h4 className="font-medium text-gray-300 mb-2">Macierz W</h4>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-gray-400">
          <span>Metoda:</span>
          <span className="text-white">{configSnapshot?.w_method || "?"}</span>
          <span>Zakres k:</span>
          <span className="text-white">
            {configSnapshot?.k_range_min || "?"} -{" "}
            {configSnapshot?.k_range_max || "?"}
          </span>
          <span>k wybrane:</span>
          <span className="text-white">
            {diagnostics?.w_metrics?.k_selected ?? "-"}
          </span>
          <span>Średnia sąsiadów:</span>
          <span className="text-white">
            {diagnostics?.w_metrics?.mean_neighbors?.toFixed(1) ?? "-"}
          </span>
        </div>
      </div>

      {steps && steps.length > 0 && (
        <div className="bg-gray-800/50 rounded-lg border border-gray-700 overflow-hidden">
          <div className="px-3 py-2 border-b border-gray-700 bg-gray-800">
            <h4 className="text-xs font-medium text-gray-300">
              Pipeline Steps ({steps.length})
            </h4>
          </div>

          {steps.map((step) => (
            <div key={step.step_order}>
              <button
                onClick={() =>
                  setExpandedStep(
                    expandedStep === step.step_order ? null : step.step_order,
                  )
                }
                className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-gray-700/50 transition-colors"
              >
                <span className="w-5 text-center font-mono text-gray-600">
                  {step.step_order}
                </span>
                <span
                  className={`w-4 text-center ${statusColor[step.status] || ""}`}
                >
                  {statusIcon[step.status] || "?"}
                </span>
                <span className="flex-1 text-left text-gray-300 font-mono truncate">
                  {step.step_name}
                </span>
                <span className="text-gray-500 text-[10px]">
                  {step.duration_seconds != null
                    ? `${step.duration_seconds.toFixed(1)}s`
                    : "-"}
                </span>
                {step.exit_code != null && step.exit_code !== 0 && (
                  <span className="text-red-400 text-[10px]">
                    exit={step.exit_code}
                  </span>
                )}
                <span
                  className={`text-gray-500 transition-transform ${expandedStep === step.step_order ? "rotate-180" : ""}`}
                >
                  ▼
                </span>
              </button>

              <AnimatePresence>
                {expandedStep === step.step_order && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    className="overflow-hidden"
                  >
                    <div className="px-3 pb-3 ml-9 space-y-2">
                      {step.stdout ? (
                        <div>
                          <div className="text-[10px] text-gray-500 mb-1">
                            stdout:
                          </div>
                          <pre className="text-xs text-green-400 bg-black p-2 rounded overflow-x-auto max-h-60 overflow-y-auto font-mono whitespace-pre-wrap">
                            {step.stdout}
                          </pre>
                        </div>
                      ) : (
                        <p className="text-xs text-gray-600 italic">
                          Brak stdout
                        </p>
                      )}
                      {step.stderr && (
                        <div>
                          <div className="text-[10px] text-gray-500 mb-1">
                            stderr:
                          </div>
                          <pre className="text-xs text-red-400 bg-red-950/30 p-2 rounded overflow-x-auto max-h-32 overflow-y-auto font-mono whitespace-pre-wrap">
                            {step.stderr}
                          </pre>
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      )}

      {(!steps || steps.length === 0) && (
        <div className="text-xs text-gray-500 italic">
          Brak kroków pipeline dla tego uruchomienia.
        </div>
      )}
    </div>
  );
}

export default function DiagnosticsReport({ diagnostics, configSnapshot, steps }) {
  const [reportMode, setReportMode] = useState("simple");

  if (!diagnostics) {
    return (
      <div className="text-xs text-gray-500 italic p-3">
        Brak diagnostyki dla tego uruchomienia.
      </div>
    );
  }

  const { model, moran, lm_tests, vif } = diagnostics;

  const formatPValue = (p, alpha = 0.05) => {
    if (p == null) return "-";
    const stars = p < 0.001 ? "***" : p < 0.01 ? "**" : p < alpha ? "*" : "";
    return `${p.toFixed(4)}${stars ? ` ${stars}` : ""}`;
  };

  const formatCoef = (val) => {
    if (val == null) return "-";
    return val >= 0 ? `+${val.toFixed(4)}` : val.toFixed(4);
  };

  return (
    <div className="space-y-3 p-3 bg-gray-900/50 rounded-lg">
      <div className="flex border-b border-gray-700 mb-2">
        {[
          { id: "simple", label: "Ogólny", desc: "dla wszystkich" },
          { id: "technical", label: "Techniczny", desc: "dla analityków" },
          { id: "full", label: "Dogłębny", desc: "dla debuggingu" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setReportMode(tab.id)}
            className={`px-3 py-2 text-xs transition-colors ${
              reportMode === tab.id
                ? "border-b-2 border-blue-500 text-white"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            <span className="block">{tab.label}</span>
            <span className="block text-[10px] text-gray-500">{tab.desc}</span>
          </button>
        ))}
      </div>

      {reportMode === "simple" && (
        <SimpleView diagnostics={diagnostics} configSnapshot={configSnapshot} />
      )}

      {reportMode === "technical" && (
        <>
          <div>
            <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">
              Model
            </h4>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-gray-800 rounded p-2">
                <span className="text-gray-500">Typ:</span>{" "}
                <span className="text-white font-mono">
                  {model?.selected?.toUpperCase() || "-"}
                </span>
              </div>
              <div className="bg-gray-800 rounded p-2">
                <span className="text-gray-500">AIC:</span>{" "}
                <span className="text-white font-mono">
                  {model?.aic?.toFixed(2) || "-"}
                </span>
              </div>
              <div className="bg-gray-800 rounded p-2">
                <span className="text-gray-500">Pseudo R²:</span>{" "}
                <span className="text-white font-mono">
                  {model?.r_squared != null
                    ? `${(model.r_squared * 100).toFixed(1)}%`
                    : "-"}
                </span>
              </div>
              <div className="bg-gray-800 rounded p-2">
                <span className="text-gray-500">
                  {model?.selected === "sem" ? "λ (SEM):" : "ρ (SAR):"}
                </span>{" "}
                <span className="text-white font-mono">
                  {(model?.selected === "sem"
                    ? model?.lambda
                    : model?.rho
                  )?.toFixed(4) || "-"}
                </span>
              </div>
            </div>
            <p className="text-[10px] text-gray-500 mt-1">
              Wybrano {model?.selected?.toUpperCase() || "?"} na podstawie
              najniższego AIC. Porównanie modeli w logach R.
            </p>
          </div>

          {model?.coefficients &&
            Object.keys(model.coefficients).length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">
                  Współczynniki
                </h4>
                <div className="bg-gray-800 rounded overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-700">
                        <th className="text-left px-2 py-1 text-gray-500 font-normal">
                          Zmienna
                        </th>
                        <th className="text-right px-2 py-1 text-gray-500 font-normal">
                          Estimate
                        </th>
                        <th className="text-right px-2 py-1 text-gray-500 font-normal">
                          Std.Err
                        </th>
                        <th className="text-right px-2 py-1 text-gray-500 font-normal">
                          p-value
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(model.coefficients).map(
                        ([name, coef]) => {
                          const isSignificant = coef.p != null && coef.p < 0.05;
                          const isPositive = coef.estimate > 0;
                          return (
                            <tr
                              key={name}
                              className="border-b border-gray-700/50 last:border-0"
                            >
                              <td className="px-2 py-1 text-gray-300 font-mono">
                                {name}
                              </td>
                              <td
                                className={`text-right px-2 py-1 font-mono ${isPositive ? "text-green-400" : "text-red-400"}`}
                              >
                                {formatCoef(coef.estimate)}
                              </td>
                              <td className="text-right px-2 py-1 text-gray-400 font-mono">
                                {coef.std_error?.toFixed(4) || "-"}
                              </td>
                              <td
                                className={`text-right px-2 py-1 font-mono ${isSignificant ? "text-yellow-400" : "text-gray-500"}`}
                              >
                                {formatPValue(coef.p)}
                              </td>
                            </tr>
                          );
                        },
                      )}
                    </tbody>
                  </table>
                </div>
                <p className="text-[10px] text-gray-600 mt-1">
                  *** p&lt;0.001, ** p&lt;0.01, * p&lt;0.05
                </p>
              </div>
            )}

          {vif?.results && Object.keys(vif.results).length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">
                VIF (prog: {configSnapshot?.vif_threshold || 5.0})
              </h4>
              <div className="flex flex-wrap gap-1">
                {Object.entries(vif.results).map(([name, val]) => {
                  const isHigh =
                    val != null && val > (configSnapshot?.vif_threshold || 5.0);
                  return (
                    <span
                      key={name}
                      className={`px-2 py-0.5 rounded text-xs font-mono ${
                        isHigh
                          ? "bg-red-900/40 text-red-400 border border-red-700/50"
                          : "bg-gray-800 text-gray-400"
                      }`}
                    >
                      {name}: {val?.toFixed(2) || "NA"}
                    </span>
                  );
                })}
              </div>
              {vif.dropped && vif.dropped.length > 0 && (
                <p className="text-xs text-amber-400 mt-1">
                  Oznaczone (informacyjnie, NIE usuwane z modelu):{" "}
                  {vif.dropped.join(", ")}
                </p>
              )}
              <p className="text-[10px] text-gray-500 mt-1">
                VIF jest informacyjny: zmienne powyżej progu są tylko oznaczane,
                nie usuwane z modelu.
              </p>
            </div>
          )}

          {moran?.i != null && (
            <div>
              <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">
                Moran's I (residua)
              </h4>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="bg-gray-800 rounded p-2">
                  <span className="text-gray-500">I:</span>{" "}
                  <span className="text-white font-mono">
                    {moran.i?.toFixed(4)}
                  </span>
                </div>
                <div className="bg-gray-800 rounded p-2">
                  <span className="text-gray-500">z:</span>{" "}
                  <span className="text-white font-mono">
                    {moran.z?.toFixed(2)}
                  </span>
                </div>
                <div className="bg-gray-800 rounded p-2">
                  <span className="text-gray-500">p:</span>{" "}
                  <span
                    className={`font-mono ${moran.p < 0.05 ? "text-red-400" : "text-green-400"}`}
                  >
                    {formatPValue(moran.p)}
                  </span>
                </div>
              </div>
              <p
                className={`text-xs mt-1 ${moran.p < 0.05 ? "text-red-400" : "text-green-400"}`}
              >
                {moran.p < 0.05
                  ? "⚠️ Istotna autokorelacja reszt - model nie wyczyścił zależności przestrzennej"
                  : "✓ Brak istotnej autokorelacji reszt"}
              </p>
            </div>
          )}

          {lm_tests &&
            (lm_tests.lm_lag?.stat != null ||
              lm_tests.lm_error?.stat != null) && (
              <div>
                <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">
                  Testy LM
                </h4>
                <div className="bg-gray-800 rounded overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-700">
                        <th className="text-left px-2 py-1 text-gray-500 font-normal">
                          Test
                        </th>
                        <th className="text-right px-2 py-1 text-gray-500 font-normal">
                          Stat
                        </th>
                        <th className="text-right px-2 py-1 text-gray-500 font-normal">
                          p-value
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { name: "LM-lag (SAR)", data: lm_tests.lm_lag },
                        { name: "LM-error (SEM)", data: lm_tests.lm_error },
                        { name: "Robust LM-lag", data: lm_tests.rlm_lag },
                        { name: "Robust LM-error", data: lm_tests.rlm_error },
                      ].map(
                        ({ name, data }) =>
                          data?.stat != null && (
                            <tr
                              key={name}
                              className="border-b border-gray-700/50 last:border-0"
                            >
                              <td className="px-2 py-1 text-gray-300">
                                {name}
                              </td>
                              <td className="text-right px-2 py-1 text-white font-mono">
                                {data.stat?.toFixed(2)}
                              </td>
                              <td
                                className={`text-right px-2 py-1 font-mono ${data.p < 0.05 ? "text-yellow-400" : "text-gray-500"}`}
                              >
                                {formatPValue(data.p)}
                              </td>
                            </tr>
                          ),
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

          {diagnostics?.impacts &&
            diagnostics.impacts.direct &&
            Object.keys(diagnostics.impacts.direct).length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">
                  Impacts (SAR/SDM)
                  <span className="text-gray-600 font-normal ml-2">
                    LeSage & Pace 2009
                  </span>
                </h4>
                <div className="bg-gray-800 rounded overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-700">
                        <th className="text-left px-2 py-1 text-gray-500 font-normal">
                          Zmienna
                        </th>
                        <th className="text-right px-2 py-1 text-gray-500 font-normal">
                          Direct
                        </th>
                        <th className="text-right px-2 py-1 text-gray-500 font-normal">
                          Indirect
                        </th>
                        <th className="text-right px-2 py-1 text-gray-500 font-normal">
                          Total
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.keys(diagnostics.impacts.direct || {}).map(
                        (name) => {
                          const direct = diagnostics.impacts.direct[name];
                          const indirect = diagnostics.impacts.indirect[name];
                          const total = diagnostics.impacts.total[name];
                          const isPositive = total > 0;
                          return (
                            <tr
                              key={name}
                              className="border-b border-gray-700/50 last:border-0"
                            >
                              <td className="px-2 py-1 text-gray-300 font-mono">
                                {name}
                              </td>
                              <td className="text-right px-2 py-1 text-gray-400 font-mono">
                                {direct?.toFixed(4) || "-"}
                              </td>
                              <td className="text-right px-2 py-1 text-blue-400 font-mono">
                                {indirect?.toFixed(4) || "-"}
                              </td>
                              <td
                                className={`text-right px-2 py-1 font-mono font-medium ${isPositive ? "text-red-400" : "text-green-400"}`}
                              >
                                {total?.toFixed(4) || "-"}
                              </td>
                            </tr>
                          );
                        },
                      )}
                    </tbody>
                  </table>
                </div>
                <p className="text-[10px] text-gray-600 mt-1">
                  Direct = wpływ X_i na Y_i (z feedbackiem) | Indirect =
                  spillover na sąsiadów | Total = Direct + Indirect
                </p>
                {model?.rho > 0.5 && (
                  <p className="text-[10px] text-amber-400 mt-1">
                    ⚠️ Wysokie ρ ({model.rho?.toFixed(3)}) - indirect effects
                    mogą dominować nad direct
                  </p>
                )}
              </div>
            )}

          {(!diagnostics?.impacts ||
            !diagnostics.impacts.direct ||
            Object.keys(diagnostics.impacts.direct).length === 0) &&
            model?.selected && (
              <div className="opacity-50">
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                  Impacts
                </h4>
                <p className="text-xs text-gray-500 italic">
                  {["sem", "ols"].includes(model.selected?.toLowerCase())
                    ? `Niedostępne dla ${model.selected.toUpperCase()}. Impacts są potrzebne tylko dla SAR/SDM (mnożnik przestrzenny (I - ρW)⁻¹).`
                    : "Brak danych - uruchom pipeline ponownie z modelem SAR lub SDM."}
                </p>
              </div>
            )}

          {configSnapshot?.geometry_type === "voronoi" &&
          diagnostics?.eta?.h_rel != null ? (
            <div>
              <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">
                ETA (Aglomeracja)
              </h4>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="bg-gray-800 rounded p-2">
                  <span className="text-gray-500">H emp:</span>{" "}
                  <span className="text-white font-mono">
                    {diagnostics.eta.h_emp?.toFixed(4)}
                  </span>
                </div>
                <div className="bg-gray-800 rounded p-2">
                  <span className="text-gray-500">H max:</span>{" "}
                  <span className="text-white font-mono">
                    {diagnostics.eta.h_max?.toFixed(4)}
                  </span>
                </div>
                <div className="bg-gray-800 rounded p-2">
                  <span className="text-gray-500">ETA:</span>{" "}
                  <span
                    className={`font-mono font-medium ${
                      diagnostics.eta.h_rel > 0.9
                        ? "text-green-400"
                        : diagnostics.eta.h_rel > 0.7
                          ? "text-yellow-400"
                          : "text-red-400"
                    }`}
                  >
                    {diagnostics.eta.h_rel?.toFixed(4)}
                  </span>
                </div>
              </div>
              <p
                className={`text-xs mt-1 ${
                  diagnostics.eta.h_rel > 0.9
                    ? "text-green-400"
                    : diagnostics.eta.h_rel > 0.7
                      ? "text-yellow-400"
                      : "text-red-400"
                }`}
              >
                {diagnostics.eta.h_rel > 0.9
                  ? "✓ Rozkład równomierny (brak aglomeracji)"
                  : diagnostics.eta.h_rel > 0.7
                    ? "~ Umiarkowane skupienie punktów"
                    : "⚠️ Silna aglomeracja (punkty w klastrach)"}
              </p>
            </div>
          ) : (
            configSnapshot?.geometry_type !== "voronoi" && (
              <div className="opacity-50">
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                  ETA (Aglomeracja)
                </h4>
                <p className="text-xs text-gray-500 italic">
                  Niedostępne dla siatki regularnej. ETA mierzy entropię
                  rozkładu powierzchni komórek - ma sens tylko dla Voronoi,
                  gdzie komórki mają różne kształty i rozmiary.
                </p>
              </div>
            )
          )}
        </>
      )}

      {reportMode === "full" && (
        <FullDebugView
          diagnostics={diagnostics}
          steps={steps}
          configSnapshot={configSnapshot}
        />
      )}
    </div>
  );
}
