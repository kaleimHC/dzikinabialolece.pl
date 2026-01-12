import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSightingsStore } from '../stores/sightingsStore';

const SAMPLES = [
  { id: 'mala', label: 'Mała', n: 100 },
  { id: 'srednia', label: 'Średnia', n: 500 },
  { id: 'duza', label: 'Duża', n: 1500 },
  { id: 'pelna', label: 'Pełna', n: 3500 },
];

export default function SampleSlider({ isExpanded = true, onToggle }) {
  const [currentSample, setCurrentSample] = useState('pelna');
  const [sliderValue, setSliderValue] = useState(3);
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const { fetchSightings } = useSightingsStore();
  const intervalRef = useRef(null);

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, []);

  // Fetch current sample on mount
  useEffect(() => {
    fetch('/api/analytics/samples/current/')
      .then(r => r.json())
      .then(data => {
        const idx = SAMPLES.findIndex(s => s.id === data.current_sample);
        if (idx >= 0) {
          setCurrentSample(data.current_sample);
          setSliderValue(idx);
        }
      })
      .catch(err => console.warn('Failed to fetch current sample:', err));
  }, []);

  // Poll for task progress
  const pollProgress = useCallback((taskId) => {
    intervalRef.current = setInterval(() => {
      fetch(`/api/analytics/tasks/${taskId}/status/`)
        .then(r => r.json())
        .then(data => {
          setProgress(data);

          if (data.status === 'SUCCESS' || data.step === 'completed') {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
            setIsLoading(false);
            setProgress(null);
            // Refresh sightings on map
            fetchSightings();
            // Trigger voronoi refresh
            window.dispatchEvent(new Event('voronoi-refresh'));
          } else if (data.error) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
            setIsLoading(false);
            setError(data.error);
          }
        })
        .catch(err => {
          console.error('Progress poll error:', err);
          clearInterval(intervalRef.current);
          intervalRef.current = null;
          setIsLoading(false);
          setError('Polling failed');
        });
    }, 1000);

    // Cleanup after 2 minutes max
    setTimeout(() => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }, 120000);
  }, [fetchSightings]);

  const handleSliderChange = (e) => {
    const value = parseInt(e.target.value, 10);
    setSliderValue(value);
  };

  const handleApply = async () => {
    const targetSample = SAMPLES[sliderValue];
    if (targetSample.id === currentSample) return;

    setIsLoading(true);
    setError(null);
    setProgress({ percent: 0, message: 'Uruchamianie...' });

    try {
      const response = await fetch('/api/analytics/samples/switch/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sample: targetSample.id }),
      });

      const data = await response.json();

      if (response.ok) {
        setCurrentSample(targetSample.id);
        pollProgress(data.task_id);
      } else {
        setError(data.error || data.message || 'Switch failed');
        setIsLoading(false);
      }
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
    }
  };

  const selectedSample = SAMPLES[sliderValue];
  const isChanged = selectedSample.id !== currentSample;

  return (
    <div style={{ marginBottom: '12px', borderBottom: '1px solid rgb(var(--color-gray-700) / 0.4)' }}>
      {/* KLIKALNY NAGŁÓWEK */}
      <div
        onClick={() => {
          onToggle();
        }}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
          paddingBottom: '8px'
        }}
      >
        <span style={{ fontSize: '12px', fontWeight: 500, color: 'rgb(var(--color-text))' }}>
          Wielkość próby
        </span>
        <span style={{ color: 'rgb(var(--color-muted))', fontSize: '11px' }}>
          n = {selectedSample.n.toLocaleString()} {isExpanded ? '▼' : '▲'}
        </span>
      </div>

      {/* ANIMOWANA ZAWARTOŚĆ */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ paddingBottom: '12px' }}>
              {/* SLIDER */}
              <input
                type="range"
                min="0"
                max="3"
                step="1"
                value={sliderValue}
                onChange={handleSliderChange}
                disabled={isLoading}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer
                           disabled:opacity-50 disabled:cursor-not-allowed
                           [&::-webkit-slider-thumb]:appearance-none
                           [&::-webkit-slider-thumb]:w-4
                           [&::-webkit-slider-thumb]:h-4
                           [&::-webkit-slider-thumb]:bg-emerald-500
                           [&::-webkit-slider-thumb]:rounded-full
                           [&::-webkit-slider-thumb]:cursor-pointer
                           [&::-webkit-slider-thumb]:transition-all
                           [&::-webkit-slider-thumb]:hover:bg-emerald-400"
              />

              {/* LABELS */}
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                {SAMPLES.map((s, i) => (
                  <span
                    key={s.id}
                    style={{
                      fontSize: '10px',
                      color: sliderValue === i ? 'rgb(var(--color-primary))' : 'rgb(var(--color-gray-500))',
                      fontWeight: sliderValue === i ? 600 : 400
                    }}
                  >
                    {s.n}
                  </span>
                ))}
              </div>

              {/* PROGRESS BAR */}
              {isLoading && progress && (
                <div style={{ marginTop: '8px', marginBottom: '8px' }}>
                  <div style={{ height: '4px', backgroundColor: 'rgb(var(--color-gray-700))', borderRadius: '2px', overflow: 'hidden' }}>
                    <div
                      style={{
                        height: '100%',
                        backgroundColor: 'rgb(var(--color-primary))',
                        width: `${progress.percent || 0}%`,
                        transition: 'width 0.3s'
                      }}
                    />
                  </div>
                  <p style={{ fontSize: '10px', color: 'rgb(var(--color-muted))', marginTop: '4px' }}>
                    {progress.message || 'Przetwarzanie...'}
                  </p>
                </div>
              )}

              {/* ERROR */}
              {error && (
                <div style={{
                  marginTop: '8px',
                  fontSize: '10px',
                  color: '#EF4444',
                  backgroundColor: 'rgba(239,68,68,0.1)',
                  borderRadius: '4px',
                  padding: '4px 8px'
                }}>
                  {error}
                </div>
              )}

              {/* PRZYCISK */}
              <button
                onClick={handleApply}
                disabled={isLoading || !isChanged}
                style={{
                  width: '100%',
                  marginTop: '8px',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  backgroundColor: isChanged && !isLoading ? 'rgb(var(--color-primary))' : 'rgb(var(--color-gray-700))',
                  color: isChanged && !isLoading ? 'white' : 'rgb(var(--color-gray-500))',
                  border: 'none',
                  cursor: isChanged && !isLoading ? 'pointer' : 'not-allowed',
                  fontSize: '12px',
                  fontWeight: 500,
                  transition: 'all 0.2s'
                }}
              >
                {isLoading ? 'Ładowanie...' : isChanged ? 'Zastosuj' : 'Aktualna próba'}
              </button>

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
