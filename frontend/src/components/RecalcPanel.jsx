import { useState } from 'react';
import { useSightingsStore } from '../stores/sightingsStore';

export default function RecalcPanel() {
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState(null);

  const handleFastCompute = async () => {
    setIsLoading(true);
    setStatus('computing');
    try {
      const res = await fetch('/api/analytics/recalculate/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'fast' }),
      });
      if (!res.ok) throw new Error('Recalculation failed');
      const data = await res.json();
      setStatus(data.task_id ? 'queued' : 'done');
    } catch (err) {
      setStatus('error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ padding: '16px' }}>
      <h3 style={{ margin: '0 0 12px', fontSize: '0.875rem', fontWeight: 700 }}>
        Przelicz ryzyko
      </h3>
      <button
        onClick={handleFastCompute}
        disabled={isLoading}
        style={{
          width: '100%',
          padding: '8px 16px',
          borderRadius: '8px',
          border: 'none',
          background: '#10B981',
          color: '#fff',
          fontWeight: 600,
          cursor: isLoading ? 'wait' : 'pointer',
          opacity: isLoading ? 0.7 : 1,
        }}
      >
        {isLoading ? 'Przeliczanie...' : 'FAST — Przelicz'}
      </button>
      {status && (
        <p style={{ marginTop: '8px', fontSize: '0.75rem', color: '#9CA3AF' }}>
          Status: {status}
        </p>
      )}
    </div>
  );
}
