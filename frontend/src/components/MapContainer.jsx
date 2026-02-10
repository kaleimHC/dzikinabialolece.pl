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
        // Hover ring is ~2.5x the point radius
        const hoverRadius = baseRadius * 2.5;
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

    // Attribution in Header, zoom buttons removed - scroll zoom is enough

    map.on("load", () => {
      const tk = getTokens(currentTheme);
      // Boundaries layer (Białołęka district + Wisła river)
      map.addSource("boundaries", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      // OSM Layers - UNDER grid (order matters!)
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
      map.addLayer({
        id: "roads-line",
        type: "line",
        source: "roads",
        paint: {
          "line-color": tk.osm.roads,
          "line-width": 2,
          "line-opacity": 0.8,
        },
      });

      map.addSource("barriers", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "barriers-line",
        type: "line",
        source: "barriers",
        paint: {
          "line-color": tk.osm.barriers,
          "line-width": 2,
          "line-opacity": 0.8,
        },
      });

      map.addSource("allotments", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "allotments-fill",
        type: "fill",
        source: "allotments",
        paint: { "fill-color": tk.osm.allotments, "fill-opacity": 0.5 },
      });

      map.addSource("meadows", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "meadows-fill",
        type: "fill",
        source: "meadows",
        paint: { "fill-color": tk.osm.meadows, "fill-opacity": 0.5 },
      });

      map.addSource("farmland", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "farmland-fill",
        type: "fill",
        source: "farmland",
        paint: { "fill-color": tk.osm.farmland, "fill-opacity": 0.4 },
      });

      map.addSource("parks", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "parks-fill",
        type: "fill",
        source: "parks",
        paint: { "fill-color": tk.osm.parks, "fill-opacity": 0.5 },
      });

      map.addSource("scrub", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "scrub-fill",
        type: "fill",
        source: "scrub",
        paint: { "fill-color": tk.osm.scrub, "fill-opacity": 0.5 },
      });

      map.addSource("railway", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "railway-line",
        type: "line",
        source: "railway",
        paint: {
          "line-color": tk.osm.railway,
          "line-width": 3,
          "line-opacity": 0.8,
        },
      });

      // GUS Population grid (subtle violet choropleth)
      map.addSource("population", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "population-fill",
        type: "fill",
        source: "population",
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "tot"],
            0,
            tk.heatmap.population.s0,
            10,
            tk.heatmap.population.s1,
            100,
            tk.heatmap.population.s2,
            300,
            tk.heatmap.population.s3,
            700,
            tk.heatmap.population.s4,
            1500,
            tk.heatmap.population.s5,
            3000,
            tk.heatmap.population.s6,
          ],
          "fill-opacity": [
            "interpolate",
            ["linear"],
            ["get", "tot"],
            0,
            0.3,
            10,
            0.4,
            100,
            0.5,
            300,
            0.55,
            700,
            0.6,
            1500,
            0.65,
            3000,
            0.7,
          ],
        },
      });
      map.addLayer({
        id: "population-outline",
        type: "line",
        source: "population",
        paint: {
          "line-color": "rgba(124, 58, 237, 0.2)",
          "line-width": 0.5,
          "line-opacity": 1,
        },
      });

      // W Matrix edges (spatial neighbor connections)
      map.addSource("w-matrix", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "w-matrix-lines",
        type: "line",
        source: "w-matrix",
        paint: {
          "line-color": tk.wmatrix,
          "line-width": 1,
          "line-opacity": 0.6,
        },
      });

      // Risk heatmap (ON TOP)
      map.addSource("risk", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "risk-fill",
        type: "fill",
        source: "risk",
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "risk"],
            0.0,
            tk.heatmap.risk.s0,
            0.1,
            tk.heatmap.risk.s1,
            0.25,
            tk.heatmap.risk.s2,
            0.4,
            tk.heatmap.risk.s3,
            0.55,
            tk.heatmap.risk.s4,
            0.7,
            tk.heatmap.risk.s5,
            0.85,
            tk.heatmap.risk.s6,
            1.0,
            tk.heatmap.risk.s7,
          ],
          "fill-opacity": riskOpacity(tk.riskLowTransparent),
        },
      });
      map.addLayer({
        id: "risk-outline",
        type: "line",
        source: "risk",
        paint: {
          "line-color": "#ffffff",
          "line-width": 0.5,
          "line-opacity": 0.3,
        },
      });

      // TRAJECTORY LAYER (migration corridors)
      map.addSource("trajectories", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "trajectory-lines",
        type: "line",
        source: "trajectories",
        layout: { visibility: "none" },
        paint: {
          "line-color": [
            "match",
            ["get", "trajectory_type"],
            "riparian",
            "#0066ff",
            "forest_edge",
            "#00aa00",
            "urban_green",
            "#ff9900",
            "#E879F9",
          ],
          "line-width": 3,
          "line-opacity": 0.8,
        },
      });

      map.addSource("encounters", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
        cluster: true,
        clusterMaxZoom: 14,
        clusterRadius: 50,
      });
      map.addSource("ryjowisko", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
        cluster: true,
        clusterMaxZoom: 14,
        clusterRadius: 50,
      });

      map.addLayer({
        id: "encounters-clusters",
        type: "circle",
        source: "encounters",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": [
            "step",
            ["get", "point_count"],
            tk.encounter,
            5,
            tk.encounterCluster,
            15,
            tk.encounterLarge,
          ],
          "circle-radius": ["step", ["get", "point_count"], 18, 5, 25, 15, 35],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });
      map.addLayer({
        id: "encounters-cluster-count",
        type: "symbol",
        source: "encounters",
        filter: ["has", "point_count"],
        layout: {
          "text-field": ["to-string", ["get", "point_count"]],
          "text-size": 12,
          "text-allow-overlap": true,
          "text-ignore-placement": true,
        },
        paint: {
          "text-color": "#ffffff",
          "text-opacity-transition": { duration: 0, delay: 0 },
        },
      });
      map.addLayer({
        id: "encounters-point",
        type: "circle",
        source: "encounters",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": tk.encounter,
          "circle-radius": 6,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });
      map.addLayer({
        id: "encounters-hover-ring",
        type: "circle",
        source: "encounters",
        filter: ["==", ["get", "id"], ""],
        paint: {
          "circle-radius": 16,
          "circle-color": "transparent",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });

      map.addLayer({
        id: "ryjowisko-clusters",
        type: "circle",
        source: "ryjowisko",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": [
            "step",
            ["get", "point_count"],
            tk.ryjowisko,
            5,
            tk.ryjowiskoCluster,
            15,
            tk.ryjowiskoLarge,
          ],
          "circle-radius": ["step", ["get", "point_count"], 18, 5, 25, 15, 35],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });
      map.addLayer({
        id: "ryjowisko-cluster-count",
        type: "symbol",
        source: "ryjowisko",
        filter: ["has", "point_count"],
        layout: {
          "text-field": ["to-string", ["get", "point_count"]],
          "text-size": 12,
          "text-allow-overlap": true,
          "text-ignore-placement": true,
        },
        paint: {
          "text-color": "#ffffff",
          "text-opacity-transition": { duration: 0, delay: 0 },
        },
      });
      map.addLayer({
        id: "ryjowisko-point",
        type: "circle",
        source: "ryjowisko",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": tk.ryjowisko,
          "circle-radius": 6,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });
      map.addLayer({
        id: "ryjowisko-hover-ring",
        type: "circle",
        source: "ryjowisko",
        filter: ["==", ["get", "id"], ""],
        paint: {
          "circle-radius": 16,
          "circle-color": "transparent",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });

      // Boundaries on top of everything
      map.addLayer({
        id: "bialoleka-outline",
        type: "line",
        source: "boundaries",
        filter: ["==", ["get", "name"], "bialoleka"],
        paint: {
          "line-color": "#60a5fa",
          "line-width": 3,
          "line-dasharray": [4, 2],
          "line-opacity": 0.9,
        },
      });
      map.addLayer({
        id: "wisla-line",
        type: "line",
        source: "boundaries",
        filter: ["==", ["get", "name"], "wisla"],
        paint: {
          "line-color": "#3b82f6",
          "line-width": 5,
          "line-opacity": 0.8,
        },
      });

      // Hide base map buildings (overlap with grid)
      if (map.getLayer("building"))
        map.setLayoutProperty("building", "visibility", "none");

      setMapReady(true);
    });

    const clusterClick = (src) => (e) => {
      const f = map.queryRenderedFeatures(e.point, {
        layers: [src + "-clusters"],
      });
      if (f.length) {
        map
          .getSource(src)
          .getClusterExpansionZoom(f[0].properties.cluster_id, (err, z) => {
            if (!err)
              map.flyTo({
                center: f[0].geometry.coordinates,
                zoom: z,
                speed: 0.8,
              });
          });
      }
    };
    map.on("click", "encounters-clusters", clusterClick("encounters"));
    map.on("click", "ryjowisko-clusters", clusterClick("ryjowisko"));

    const pointClick = (e) => {
      if (e.features && e.features.length) {
        setSelectedSighting(e.features[0].properties);
      }
    };
    map.on("click", "encounters-point", pointClick);
    map.on("click", "ryjowisko-point", pointClick);

    ["encounters-clusters", "ryjowisko-clusters"].forEach((l) => {
      map.on("mouseenter", l, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", l, () => (map.getCanvas().style.cursor = ""));
    });
    map.on("mouseenter", "encounters-point", (e) => {
      map.getCanvas().style.cursor = "pointer";
      if (e.features && e.features[0])
        map.setFilter("encounters-hover-ring", [
          "==",
          ["get", "id"],
          e.features[0].properties.id || "",
        ]);
    });
    map.on("mouseleave", "encounters-point", () => {
      map.getCanvas().style.cursor = "";
      map.setFilter("encounters-hover-ring", ["==", ["get", "id"], ""]);
    });
    map.on("mouseenter", "ryjowisko-point", (e) => {
      map.getCanvas().style.cursor = "pointer";
      if (e.features && e.features[0])
        map.setFilter("ryjowisko-hover-ring", [
          "==",
          ["get", "id"],
          e.features[0].properties.id || "",
        ]);
    });
    map.on("mouseleave", "ryjowisko-point", () => {
      map.getCanvas().style.cursor = "";
      map.setFilter("ryjowisko-hover-ring", ["==", ["get", "id"], ""]);
    });

    map.on("moveend", () => {
      const c = map.getCenter();
      const z = map.getZoom();
      updateMapView([c.lng, c.lat], z);
      setCurrentZoom(z);
    });
    map.on("zoom", () => setCurrentZoom(map.getZoom()));
    return () => {
      mapRef.current = null;
      map.remove();
    };
  }, []);

  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const enc = sightings.filter(
      (f) => f.properties && f.properties.sighting_type === "encounter",
    );
    const ryk = sightings.filter(
      (f) => f.properties && f.properties.sighting_type === "ryjowisko",
    );
    const encSrc = mapRef.current.getSource("encounters");
    const rykSrc = mapRef.current.getSource("ryjowisko");
    if (encSrc) encSrc.setData({ type: "FeatureCollection", features: enc });
    if (rykSrc) rykSrc.setData({ type: "FeatureCollection", features: ryk });

    updateCircleSizes(mapRef.current, sightings.length, currentZoom);
  }, [mapReady, sightings, currentZoom, updateCircleSizes]);
  // Fetch boundaries (Białołęka + Wisła)
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    fetch("/api/analytics/boundaries/")
      .then((r) => r.json())
      .then((data) => {
        const src = mapRef.current?.getSource("boundaries");
        if (src) src.setData(data);
      })
      .catch((err) => console.warn("Boundaries fetch failed:", err));
  }, [mapReady]);

  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const m = mapRef.current;
    const tk = getTokens(currentTheme);
    if (m.getLayer("encounters-point"))
      m.setPaintProperty("encounters-point", "circle-color", tk.encounter);
    if (m.getLayer("encounters-clusters"))
      m.setPaintProperty("encounters-clusters", "circle-color", [
        "step",
        ["get", "point_count"],
        tk.encounter,
        5,
        tk.encounterCluster,
        15,
        tk.encounterLarge,
      ]);
    if (m.getLayer("ryjowisko-point"))
      m.setPaintProperty("ryjowisko-point", "circle-color", tk.ryjowisko);
    if (m.getLayer("ryjowisko-clusters"))
      m.setPaintProperty("ryjowisko-clusters", "circle-color", [
        "step",
        ["get", "point_count"],
        tk.ryjowisko,
        5,
        tk.ryjowiskoCluster,
        15,
        tk.ryjowiskoLarge,
      ]);

    const paintCalls = [
      // OSM custom (12)
      ["forests-fill", "fill-color", tk.osm.forests],
      ["water-fill", "fill-color", tk.osm.water],
      ["waterways-line", "line-color", tk.osm.waterways],
      ["buildings-fill", "fill-color", tk.osm.buildings],
      ["roads-line", "line-color", tk.osm.roads],
      ["barriers-line", "line-color", tk.osm.barriers],
      ["allotments-fill", "fill-color", tk.osm.allotments],
      ["meadows-fill", "fill-color", tk.osm.meadows],
      ["farmland-fill", "fill-color", tk.osm.farmland],
      ["parks-fill", "fill-color", tk.osm.parks],
      ["scrub-fill", "fill-color", tk.osm.scrub],
      ["railway-line", "line-color", tk.osm.railway],
      // Basemap fills (9)
      ["background", "background-color", tk.basemap.background],
      ["water", "fill-color", tk.basemap.water],
      ["landcover-grass", "fill-color", tk.basemap.landcoverGrass],
      ["landcover-wood", "fill-color", tk.basemap.landcoverWood],
      ["landuse-park", "fill-color", tk.basemap.landusePark],
      ["landuse-residential", "fill-color", tk.basemap.landuseResidential],
      ["building", "fill-color", tk.basemap.building],
      ["building-3d", "fill-extrusion-color", tk.basemap.building],
      // Basemap lines (8)
      ["waterway", "line-color", tk.basemap.waterway],
      ["road-service", "line-color", tk.basemap.roadService],
      ["road-minor", "line-color", tk.basemap.roadMinor],
      ["road-secondary", "line-color", tk.basemap.roadSecondary],
      ["road-primary", "line-color", tk.basemap.roadPrimary],
      ["road-trunk", "line-color", tk.basemap.roadTrunk],
      ["road-motorway", "line-color", tk.basemap.roadMotorway],
      ["railway", "line-color", tk.basemap.railway],
      // Basemap admin boundary (1)
      ["boundary-country", "line-color", tk.basemap.boundaryCountry],
      // Basemap symbols - text-color (5)
      ["place-city", "text-color", tk.basemap.placeText],
      ["place-town", "text-color", tk.basemap.placeText],
      ["place-village", "text-color", tk.basemap.placeText],
      ["place-suburb", "text-color", tk.basemap.placeSuburbText],
      ["road-label", "text-color", tk.basemap.roadLabelText],
      // Basemap symbols - text-halo-color (5)
      ["place-city", "text-halo-color", tk.basemap.placeHalo],
      ["place-town", "text-halo-color", tk.basemap.placeHalo],
      ["place-village", "text-halo-color", tk.basemap.placeHalo],
      ["place-suburb", "text-halo-color", tk.basemap.placeHalo],
      ["road-label", "text-halo-color", tk.basemap.roadLabelHalo],
      // W-matrix (1)
      ["w-matrix-lines", "line-color", tk.wmatrix],
      // Boundaries (2)
      ["bialoleka-outline", "line-color", tk.boundary],
      ["wisla-line", "line-color", tk.river],
    ];
    paintCalls.forEach(([id, prop, val]) => {
      if (m.getLayer(id)) m.setPaintProperty(id, prop, val);
    });

    if (m.getLayer("risk-fill")) {
      m.setPaintProperty("risk-fill", "fill-color", [
        "interpolate",
        ["linear"],
        ["get", "risk"],
        0.0,
        tk.heatmap.risk.s0,
        0.1,
        tk.heatmap.risk.s1,
        0.25,
        tk.heatmap.risk.s2,
        0.4,
        tk.heatmap.risk.s3,
        0.55,
        tk.heatmap.risk.s4,
        0.7,
        tk.heatmap.risk.s5,
        0.85,
        tk.heatmap.risk.s6,
        1.0,
        tk.heatmap.risk.s7,
      ]);
      // Guard: don't overwrite opacity=0 managed by useGridTransition when toggle is OFF.
      // Population-fill has the same guard (see below). Both: colour can always change,
      // opacity must not resurrect a layer the user explicitly hid.
      if (m.getPaintProperty("risk-fill", "fill-opacity") !== 0) {
        m.setPaintProperty("risk-fill", "fill-opacity", riskOpacity(tk.riskLowTransparent));
      }
    }

    if (m.getLayer("population-fill")) {
      m.setPaintProperty("population-fill", "fill-color", [
        "interpolate",
        ["linear"],
        ["get", "tot"],
        0,
        tk.heatmap.population.s0,
        10,
        tk.heatmap.population.s1,
        100,
        tk.heatmap.population.s2,
        300,
        tk.heatmap.population.s3,
        700,
        tk.heatmap.population.s4,
        1500,
        tk.heatmap.population.s5,
        3000,
        tk.heatmap.population.s6,
      ]);
      // Only restore data-driven opacity expression when layer is visible.
      // If toggle is OFF, scalar 0 set by useOsmLayerTransition must not be overwritten.
      if (visibleLayers?.population) {
        m.setPaintProperty("population-fill", "fill-opacity", [
          "interpolate",
          ["linear"],
          ["get", "tot"],
          0,
          0.3,
          10,
          0.4,
          100,
          0.5,
          300,
          0.55,
          700,
          0.6,
          1500,
          0.65,
          3000,
          0.7,
        ]);
      }
    }

  }, [currentTheme, mapReady]);

  // NOTE: Grid fetch moved to useGridTransition hook (with crossfade animation)
  // NOTE: OSM layer fetch + animation moved to useOsmLayerTransition hook

  // Toggle base map visibility based on displayMode
  // NOTE: Risk layers (risk-fill, risk-outline) controlled by useGridTransition via opacity
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const map = mapRef.current;

    const isPubMode = displayMode === "publication";

    // Hide base map buildings when in PUB mode with heatmap on
    const buildingVis = isPubMode && showHeatmap ? "none" : "visible";
    if (map.getLayer("building"))
      map.setLayoutProperty("building", "visibility", buildingVis);
  }, [mapReady, showHeatmap, displayMode]);

  useEffect(() => {
    if (!mapReady || !mapRef.current || !isAddMode) return;
    const update = () => {
      const c = mapRef.current.getCenter();
      setPendingLocation(c.lat, c.lng);
    };
    update();
    mapRef.current.on("moveend", update);
    return () => {
      if (mapRef.current) mapRef.current.off("moveend", update);
    };
  }, [mapReady, isAddMode]);

  return <div ref={containerRef} className="absolute inset-0" />;
}
