import { motion, AnimatePresence, useMotionValue, useTransform } from 'framer-motion';
import RecalcPanel from './RecalcPanel';

/**
 * ProbaBottomBar - Bottom bar dla panelu Proba na mobile
 * Drag down to close (jak Google/Apple Maps)
 *
 * @param {boolean} isOpen - Czy bar jest widoczny
 * @param {Function} onClose - Handler zamknięcia
 */
export default function ProbaBottomBar({ isOpen, onClose }) {
  const y = useMotionValue(0);
  // Opacity maleje gdy przeciągamy w dół
  const opacity = useTransform(y, [0, 200], [1, 0.5]);

  const handleDragEnd = (_, info) => {
    // Zamknij jeśli przeciągnięto > 80px lub szybki swipe w dół
    if (info.offset.y > 80 || info.velocity.y > 500) {
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ y: '100%' }}
          animate={{ y: 0 }}
          exit={{ y: '100%' }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          drag="y"
          dragConstraints={{ top: 0, bottom: 0 }}
          dragElastic={{ top: 0, bottom: 0.6 }}
          onDragEnd={handleDragEnd}
          style={{
            y,
            opacity,
            paddingBottom: 'env(safe-area-inset-bottom, 0px)',
            background: 'rgb(var(--color-surface) / 0.95)',
            borderTop: '1px solid rgb(var(--color-border))'
          }}
          className="
            fixed bottom-0 left-0 right-0 z-50
            backdrop-blur-lg
            rounded-t-2xl
            shadow-2xl
            touch-none
          "
        >
          {/* Drag handle - klik lub przeciągnij zamyka */}
          <button
            onClick={onClose}
            className="w-full pt-4 pb-5 flex justify-center cursor-grab active:cursor-grabbing"
            aria-label="Zamknij"
          >
            <div className="w-10 h-1 rounded-full bg-gray-500" />
          </button>

          {/* Content */}
          <div className="px-4 pb-4">
            <RecalcPanel embedded />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
