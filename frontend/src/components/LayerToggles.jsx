import { motion, AnimatePresence } from "framer-motion";
import { useSightingsStore } from "../stores/sightingsStore";
import { getTokens } from "../tokens/colors";

function contrastColor(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 > 128 ? "#1a1a1a" : "#ffffff";
}

const LAYERS = [
  { key: "forests", label: "Lasy", description: "Siedliska" },
  { key: "scrub", label: "Zarośla", description: "Gęsta roślinność" },
  { key: "meadows", label: "Łąki", description: "Tereny trawiaste" },
  { key: "parks", label: "Parki", description: "Tereny zielone" },
  { key: "water", label: "Zbiorniki", description: "Jeziora, stawy" },
  { key: "waterways", label: "Cieki", description: "Rzeki, strumienie" },
  { key: "farmland", label: "Pola", description: "Tereny rolnicze" },
  { key: "allotments", label: "Działki", description: "Ogrody działkowe" },
  { key: "buildings", label: "Budynki", description: "Zabudowa" },
  { key: "barriers", label: "Bariery", description: "Ogrodzenia, mury" },
  { key: "roads", label: "Drogi", description: "Sieć drogowa" },
  { key: "railway", label: "Kolej", description: "Linie kolejowe" },
];

function LayerGrid({ columns = 2 }) {
  const { visibleLayers, toggleLayer } = useSightingsStore();
  const currentTheme = useSightingsStore((s) => s.currentTheme);
  const osmColors = getTokens(currentTheme).osm;

  const gridCols = columns === 3 ? "1fr 1fr 1fr" : "1fr 1fr";

  return (
    <div style={{ display: "grid", gridTemplateColumns: gridCols, gap: "6px" }}>
      {LAYERS.map(({ key, label, description }) => {
        const isActive = visibleLayers?.[key] ?? false;
        const color = osmColors[key] || "#6B7280";

        return (
          <button
            key={key}
            data-qa={`layers.toggle-${key}`}
            onClick={() => {
              toggleLayer(key);
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 8px",
              borderRadius: "6px",
              backgroundColor: isActive
                ? color
                : "rgb(var(--color-gray-700) / 0.8)",
              border: `1px solid ${isActive ? color : "rgb(var(--color-gray-600) / 0.5)"}`,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
            title={description}
          >
            {/* Color indicator */}
            <div
              style={{
                width: "12px",
                height: "12px",
                borderRadius: "3px",
                backgroundColor: isActive
                  ? "rgba(255,255,255,0.3)"
                  : "rgb(var(--color-gray-600))",
                border: `2px solid ${isActive ? "rgba(255,255,255,0.5)" : "rgb(var(--color-gray-500))"}`,
                transition: "all 0.15s ease",
              }}
            />

            {/* Label */}
            <span
              style={{
                fontSize: "10px",
                fontWeight: isActive ? "600" : "400",
                color: isActive ? contrastColor(color) : "rgb(156 163 175)",
                transition: "all 0.15s ease",
              }}
            >
              {label}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export default function LayerToggles({
  isExpanded = false,
  onToggle,
  bare = false,
  columns = 2,
}) {
  // bare mode: tylko grid bez nagłówka i accordion
  if (bare) {
    return <LayerGrid columns={columns} />;
  }

  return (
    <div>
      {/* Klikalny nagłówek */}
      <div
        data-qa="layers.accordion-toggle"
        onClick={() => {
          onToggle();
        }}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          cursor: "pointer",
          paddingBottom: isExpanded ? "8px" : "0",
          transition: "padding-bottom 0.5s ease-out",
        }}
      >
        <span
          style={{
            fontSize: "12px",
            fontWeight: 500,
            color: "rgb(var(--color-text))",
          }}
        >
          Warstwy © OpenStreetMap
        </span>
        <span style={{ color: "rgb(var(--color-muted))", fontSize: "11px" }}>
          {isExpanded ? "▲" : "▼"}
        </span>
      </div>

      {/* Animowana zawartość */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            style={{ overflow: "hidden" }}
          >
            <div style={{ paddingBottom: "8px" }}>
              <LayerGrid />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
