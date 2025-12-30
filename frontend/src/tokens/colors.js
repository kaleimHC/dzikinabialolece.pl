import { themes } from "../themes/registry";

function rgb(triplet) {
  return `rgb(${triplet.trim()})`;
}

export function getTokens(themeName = "current-dark") {
  const t = themes[themeName] || themes["current-dark"];
  const p = t.palette;
  const m = t.map || {};
  return {
    encounter: m.encounter || "#10B981",
    encounterCluster: m.encounterCluster || "#059669",
    encounterLarge: m.encounterLarge || "#047857",
    ryjowisko: m.ryjowisko || "#F59E0B",
    ryjowiskoCluster: m.ryjowiskoCluster || "#D97706",
    ryjowiskoLarge: m.ryjowiskoLarge || "#B45309",
    osm: {
      forests: m.osm?.forests || "#16A34A",
      water: m.osm?.water || "#3B82F6",
      waterways: m.osm?.waterways || "#60A5FA",
      buildings: m.osm?.buildings || "#374151",
      roads: m.osm?.roads || "#6B7280",
      railway: m.osm?.railway || "#9333EA",
      barriers: m.osm?.barriers || "#EF4444",
    },
    heatmap: {
      risk: {
        s0: "#1e3a5f", s1: "#1a5276", s2: "#117a65",
        s3: "#d4ac0d", s4: "#e67e22", s5: "#d35400",
        s6: "#cb4335", s7: "#7b241c",
      },
      population: {
        s0: "#ede7f6", s1: "#d1c4e9", s2: "#b39ddb",
        s3: "#9575cd", s4: "#7e57c2", s5: "#673ab7", s6: "#4527a0",
      },
    },
    riskLowTransparent: m.riskLowTransparent ?? true,
    wmatrix: m.wmatrix || "#A78BFA",
  };
}
