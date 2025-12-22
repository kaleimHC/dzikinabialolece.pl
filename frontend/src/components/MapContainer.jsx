import { useEffect, useRef, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useSightingsStore } from "../stores/sightingsStore";
import {
  getRadiusExpression,
  getStrokeWidth,
  getPointRadius,
} from "../utils/clusterConfig";
import { useGridTransition } from "../hooks/useGridTransition";
import { useOsmLayerTransition } from "../hooks/useOsmLayerTransition";
import { getTokens } from "../tokens/colors";

const MAP_STYLE = "/styles/dark-wildlife.json?v=1766865415694";

const riskOpacity = (lowTransparent) =>
  lowTransparent
    ? ["interpolate", ["linear"], ["get", "risk"],
        0.0, 0.12, 0.08, 0.68, 1.0, 0.85]
    : 0.65;

export default function MapContainer() {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);
  const [currentZoom, setCurrentZoom] = useState(12);
  const {
    sightings,
    updateMapView,
    setSelectedSighting,
    isAddMode,
    setPendingLocation,
    showFastGrid,
    showHeatmap,
    showResearchGrid,
    displayMode,
    visibleLayers,
    researchGeometry,
  } = useSightingsStore();
  const currentTheme = useSightingsStore((s) => s.currentTheme);

  // Grid transition (crossfade animation FAST <-> PUB <-> RESEARCH)
  useGridTransition(
    mapRef,
    mapReady,
    displayMode,
    showFastGrid,
    showHeatmap,
    showResearchGrid,
    researchGeometry,
  );

  // OSM layer transition (fade in/out animation)
  useOsmLayerTransition(mapRef, mapReady, visibleLayers);

  const updateCircleSizes = useCallback((map, n, zoom) => {
    if (!map || n === 0) return;

    const radiusExpr = getRadiusExpression(n);
    const baseRadius = getPointRadius(n, zoom);
    const strokeWidth = getStrokeWidth(baseRadius);

    ["encounters-point", "ryjowisko-point"].forEach((layer) => {
      if (map.getLayer(layer)) {
        map.setPaintProperty(layer, "circle-radius", radiusExpr);
        map.setPaintProperty(layer, "circle-stroke-width", strokeWidth);
      }
    });

    ["encounters-hover-ring", "ryjowisko-hover-ring"].forEach((layer) => {
      if (map.getLayer(layer)) {
        const hoverRadius = getPointRadius(n, zoom) * 2.5;
        map.setPaintProperty(layer, "circle-radius", hoverRadius);
      }
    });
  }, []);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [20.98, 52.33],
      zoom: 12,
      attributionControl: false,
      fadeDuration: 0,
    });
    mapRef.current = map;

    map.on("load", () => {
      const tk = getTokens(currentTheme);

      map.addSource("boundaries", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      map.addSource("forests", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "forests-fill",
        type: "fill",
        source: "forests",
        paint: { "fill-color": tk.osm.forests, "fill-opacity": 0.5 },
      });

      map.addSource("water", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "water-fill",
        type: "fill",
        source: "water",
        paint: { "fill-color": tk.osm.water, "fill-opacity": 0.6 },
      });

      map.addSource("waterways", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "waterways-line",
        type: "line",
        source: "waterways",
        paint: {
          "line-color": tk.osm.waterways,
          "line-width": 2,
          "line-opacity": 0.8,
        },
      });

      map.addSource("buildings", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "buildings-fill",
        type: "fill",
        source: "buildings",
        paint: { "fill-color": tk.osm.buildings, "fill-opacity": 0.7 },
      });

      map.addSource("roads", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      setMapReady(true);
    });

    map.on("zoom", () => {
      setCurrentZoom(map.getZoom());
    });

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "100%" }}
    />
  );
}
