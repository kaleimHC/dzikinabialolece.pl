import { useEffect, useRef, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useSightingsStore } from "../stores/sightingsStore";
import { getRadiusExpression, getStrokeWidth, getPointRadius } from "../utils/clusterConfig";
import { useGridTransition } from "../hooks/useGridTransition";
import { useOsmLayerTransition } from "../hooks/useOsmLayerTransition";
import { getTokens } from "../tokens/colors";

const MAP_STYLE = "/styles/dark-wildlife.json?v=1766865415694";

export default function MapContainer() {
  const containerRef = useRef(null);
  const mapRef = useRef(null);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
}
