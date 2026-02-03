import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { useSightingsStore } from '../stores/sightingsStore'

export function OnboardingMobile() {
  const { completeOnboarding } = useSightingsStore()

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') completeOnboarding() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [completeOnboarding])

  return (
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-label="Witamy na mapie dzików"
      className="fixed inset-0 z-[500] flex flex-col items-center justify-between"
      style={{
        backgroundColor: 'rgba(5, 10, 20, 0.97)',
        paddingBottom: 'calc(2rem + env(safe-area-inset-bottom, 0px))',
      }}
      initial={{ y: '100%', opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: '100%', opacity: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
    >
      {/* Content */}
      <div className="flex-1 flex flex-col items-center justify-center px-8 gap-6 text-center">
        <span className="text-7xl select-none">🐗</span>

        <div className="flex flex-col gap-3">
          <h1 style={{ fontSize: '22px', fontWeight: 700, color: '#fff', lineHeight: 1.25 }}>
            Dziki na Białołęce
          </h1>
          <p style={{ fontSize: '14px', color: '#9CA3AF', lineHeight: 1.55 }}>
            Mapa obserwacji dzików na Białołęce.<br />
            Zgłoś spotkanie, sprawdź ryzyko w okolicy.
          </p>
        </div>

        <div className="flex flex-col gap-2 mt-2" style={{ textAlign: 'left' }}>
          {[
            'Zgłoś obserwację jednym kliknięciem',
            'Mapa ryzyka w czasie rzeczywistym',
            'Ekonometria przestrzenna na 73 km²',
          ].map((text) => (
            <div key={text} className="flex items-center gap-2">
              <span style={{ color: 'rgb(var(--color-primary))', fontWeight: 700, flexShrink: 0 }}>✓</span>
              <span style={{ fontSize: '13px', color: '#8aa0b6' }}>{text}</span>
            </div>
          ))}
        </div>

        {/* Disclaimer */}
        <div style={{
          borderTop: '1px solid rgba(255,255,255,0.06)',
          paddingTop: '16px',
          width: '100%',
          textAlign: 'center',
        }}>
          <p style={{ margin: 0, fontSize: '11px', color: '#9CA3AF', lineHeight: 1.55 }}>
            <strong style={{ color: 'rgb(var(--color-primary))', fontWeight: 700 }}>Uwaga: dane są testowe.</strong>
          </p>
        </div>
      </div>

      {/* CTA */}
      <motion.button
        onClick={completeOnboarding}
        whileTap={{ scale: 0.95 }}
        style={{
          marginLeft: '2rem',
          marginRight: '2rem',
          width: 'calc(100% - 4rem)',
          padding: '14px 0',
          borderRadius: '999px',
          background: 'linear-gradient(135deg, rgb(var(--color-primary)) 0%, rgb(var(--color-primary-dark)) 100%)',
          color: 'white',
          fontWeight: 700,
          fontSize: '15px',
          border: 'none',
          cursor: 'pointer',
          boxShadow: '0 12px 32px rgb(var(--color-primary) / 0.35)',
        }}
      >
        Zacznij →
      </motion.button>
    </motion.div>
  )
}
