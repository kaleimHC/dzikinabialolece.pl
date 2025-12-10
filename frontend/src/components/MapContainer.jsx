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
  const [mapReady, setMapReady] = useState(false);
  const { sightings } = useSightingsStore();

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: '/styles/dark-wildlife.json',
      center: [20.98, 52.33],
      zoom: 12,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.addControl(
      new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: true } }),
      'top-right'
    );
    map.on('load', () => {
      // Boundary
      map.addSource('boundary', {
        type: 'geojson',
        data: '/api/analytics/boundaries/',
      });
      map.addLayer({
        id: 'boundary-outline',
        type: 'line',
        source: 'boundary',
        paint: { 'line-color': '#10B981', 'line-width': 2, 'line-opacity': 0.8 },
      });

      // Encounters GeoJSON source with clustering
      map.addSource('encounters', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
        cluster: true,
        clusterMaxZoom: 14,
        clusterRadius: 50,
      });

      // Ryjowisko GeoJSON source with clustering
      map.addSource('ryjowisko', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
        cluster: true,
        clusterMaxZoom: 14,
        clusterRadius: 50,
      });

      setMapReady(true);
    });
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
}
