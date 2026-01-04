import { themes } from "../themes/registry";

function rgb(triplet) {
  return `rgb(${triplet.trim()})`;
}

export function getTokens(themeName = "current-dark") {
  const t = themes[themeName] || themes["current-dark"];
  const p = t.palette;
  const m = t.map || {};
  return {
    primary: rgb(p["color-primary"]),
    primaryDark: rgb(p["color-primary-dark"]),
    layerPopulation: rgb(p["color-layer-population"]),
    layerWmatrix: rgb(p["color-layer-wmatrix"]),
    layerResearch: rgb(p["color-layer-research"]),
    linkXor: rgb(p["color-link-xor"]),
    linkSync: rgb(p["color-link-sync"]),
    encounter: m.encounter || "#10B981",
    encounterCluster: m.encounterCluster || "#059669",
    encounterLarge: m.encounterLarge || "#047857",
    ryjowisko: m.ryjowisko || "#F59E0B",
    ryjowiskoCluster: m.ryjowiskoCluster || "#D97706",
    ryjowiskoLarge: m.ryjowiskoLarge || "#B45309",
    osm: {
      forests: m.osm?.forests || "#16A34A",
      scrub: m.osm?.scrub || "#65A30D",
      meadows: m.osm?.meadows || "#84CC16",
      parks: m.osm?.parks || "#06B6D4",
      water: m.osm?.water || "#3B82F6",
      waterways: m.osm?.waterways || "#60A5FA",
      farmland: m.osm?.farmland || "#D97706",
      allotments: m.osm?.allotments || "#EC4899",
      buildings: m.osm?.buildings || "#6B7280",
      barriers: m.osm?.barriers || "#EF4444",
      roads: m.osm?.roads || "#F59E0B",
      railway: m.osm?.railway || "#8B5CF6",
    },
    heatmap: {
      risk: m.heatmap?.risk || {
        s0: "#1e3a2f",
        s1: "#22c55e",
        s2: "#84cc16",
        s3: "#eab308",
        s4: "#f97316",
        s5: "#ef4444",
        s6: "#dc2626",
        s7: "#991b1b",
      },
      population: m.heatmap?.population || {
        s0: "#1e1e28",
        s1: "#5a4678",
        s2: "#8264aa",
        s3: "#a082c8",
        s4: "#bea0dc",
        s5: "#d2beeb",
        s6: "#ebdcfa",
      },
    },
    riskLowTransparent: m.riskLowTransparent ?? false,
    boundary: m.boundary || "#60a5fa",
    river: m.river || "#3b82f6",
    wmatrix: rgb(p["color-layer-wmatrix"]),
    basemap: {
      background: m.basemap?.background || "#0F172A",
      water: m.basemap?.water || "#1E293B",
      waterway: m.basemap?.waterway || "#1E293B",
      landcoverGrass: m.basemap?.landcoverGrass || "#1a2e1f",
      landcoverWood: m.basemap?.landcoverWood || "#1a2e1f",
      landusePark: m.basemap?.landusePark || "#1a2e1f",
      landuseResidential: m.basemap?.landuseResidential || "#151d2e",
      building: m.basemap?.building || "#0F172A",
      roadService: m.basemap?.roadService || "#2d3748",
      roadMinor: m.basemap?.roadMinor || "#334155",
      roadSecondary: m.basemap?.roadSecondary || "#3d4f66",
      roadPrimary: m.basemap?.roadPrimary || "#475569",
      roadTrunk: m.basemap?.roadTrunk || "#4a5c73",
      roadMotorway: m.basemap?.roadMotorway || "#5a6b82",
      railway: m.basemap?.railway || "#4a5568",
      boundaryCountry: m.basemap?.boundaryCountry || "#64748b",
      placeText: m.basemap?.placeText || "#94a3b8",
      placeHalo: m.basemap?.placeHalo || "#0F172A",
      placeSuburbText: m.basemap?.placeSuburbText || "#7a8a9a",
      roadLabelText: m.basemap?.roadLabelText || "#64748b",
      roadLabelHalo: m.basemap?.roadLabelHalo || "#0F172A",
    },
  };
}
