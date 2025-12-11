import { useState, useEffect } from 'react';

export default function Header() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const on = () => setIsOnline(true);
    const off = () => setIsOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);

  return (
    <header style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      zIndex: 100,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '8px 16px',
      background: 'rgba(15, 23, 42, 0.9)',
      backdropFilter: 'blur(8px)',
    }}>
      <span style={{ fontWeight: 700, color: '#10B981' }}>
        🐗 Dziki na Białołęce
      </span>
      {!isOnline && (
        <span style={{
          fontSize: '0.75rem',
          background: '#EF4444',
          color: '#fff',
          padding: '2px 8px',
          borderRadius: '999px',
        }}>
          Offline
        </span>
      )}
    </header>
  );
}
