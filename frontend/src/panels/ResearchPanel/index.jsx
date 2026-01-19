/**
 * ResearchPanel - Tryb Badawczy
 *
 * Fullscreen modal dokumentujący metodologię spatialModel.
 *
 *
 * Integracja:
 * - Store: useSightingsStore().showResearchPanel
 * - Toggle: useSightingsStore().toggleResearchPanel()
 */

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSightingsStore } from "../../stores/sightingsStore";
import DocsTab from "./tabs/DocsTab";
import PipelineTab from "./tabs/PipelineTab";
import CodeTab from "./tabs/CodeTab";
import LiteratureTab from "./tabs/LiteratureTab";

const SHOW_LITERATURE_TAB = true;

const TABS = [
  { id: "pipeline", label: "Konfiguracja", icon: "⚙️" },
  { id: "docs", label: "Dokumentacja", icon: "📚" },
  { id: "code", label: "Kod", icon: "💻" },
  ...(SHOW_LITERATURE_TAB ? [{ id: "literature", label: "Literatura", icon: "📖" }] : []),
];

const ResearchPanel = () => {
  const { showResearchPanel, toggleResearchPanel } = useSightingsStore();
  const [activeTab, setActiveTab] = useState("pipeline");

  // Nie renderuj jeśli panel zamknięty
  if (!showResearchPanel) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-gray-900 text-white flex flex-col"
      >
        {/* HEADER */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-gray-700 bg-gray-800">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🔬</span>
            <div>
              <h1 className="text-xl font-bold">Tryb Badawczy</h1>
              <p className="text-sm text-gray-400">
                Metodologia: spatialModel
              </p>
            </div>
          </div>

          <button
            data-qa="research.panel-close"
            onClick={toggleResearchPanel}
            className="text-3xl text-gray-400 hover:text-white transition-colors p-2"
            aria-label="Zamknij panel badawczy"
          >
            ✕
          </button>
        </header>

        {/* TABS NAVIGATION */}
        <nav className="flex border-b border-gray-700 bg-gray-800/50">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              data-qa={`research.tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={`
                flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors
                ${
                  activeTab === tab.id
                    ? "bg-gray-700 text-white border-b-2 border-blue-500"
                    : "text-gray-400 hover:text-white hover:bg-gray-700/50"
                }
              `}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>

        {/* CONTENT AREA */}
        <main className="flex-1 overflow-auto p-6">
          {activeTab === "pipeline" && <PipelineTab />}
          {activeTab === "docs" && <DocsTab />}
          {activeTab === "code" && <CodeTab />}
          {activeTab === "literature" && <LiteratureTab />}
        </main>
      </motion.div>
    </AnimatePresence>
  );
};

export default ResearchPanel;
