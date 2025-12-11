import { useEffect } from 'react';
import MapContainer from './components/MapContainer';
import { useSightingsStore } from './stores/sightingsStore';

export default function App() {
  const fetchSightings = useSightingsStore(s => s.fetchSightings);

  useEffect(() => {
    fetchSightings();
  }, [fetchSightings]);

  return (
    <div style={{ width: '100vw', height: '100vh' }}>
      <MapContainer />
    </div>
  );
}
