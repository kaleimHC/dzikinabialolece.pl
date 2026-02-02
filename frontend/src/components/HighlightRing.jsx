import { motion } from 'framer-motion'
import { useElementRect } from '../hooks/useElementRect'

const PADDING = 6

export function HighlightRing({ selector, delay = 0 }) {
  const rect = useElementRect(selector)
  if (!rect) return null

  const isRound = Math.abs(rect.width - rect.height) < 4 && rect.width <= 80

  return (
    <motion.div
      className="onboarding-ring"
      style={{
        position: 'fixed',
        top: rect.top - PADDING,
        left: rect.left - PADDING,
        width: rect.width + PADDING * 2,
        height: rect.height + PADDING * 2,
        borderRadius: isRound ? '50%' : '14px',
        animationDelay: `${delay + 0.25}s`,
      }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay, duration: 0.25 }}
      aria-hidden="true"
    />
  )
}
