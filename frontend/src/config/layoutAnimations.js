/**
 * Variants dla koordynowanych animacji Desktop ↔ Mobile
 *
 * Używane z AnimatePresence mode="wait"
 * Wszystkie elementy wewnątrz fazy animują się RAZEM
 */

// Czas trwania animacji (spójny z resztą projektu)
const DURATION = 0.3;
const EASE = "easeOut";

/**
 * Container variants - wrapper dla całego layoutu
 * Używa when: "beforeChildren" / "afterChildren" dla kontroli sekwencji
 */
export const containerVariants = {
  initial: {
    opacity: 0,
  },
  animate: {
    opacity: 1,
    transition: {
      duration: DURATION,
      ease: EASE,
      when: "beforeChildren", // Container pojawia się przed dziećmi
    },
  },
  exit: {
    opacity: 0,
    transition: {
      duration: DURATION,
      ease: EASE,
      when: "afterChildren", // Container znika po dzieciach
    },
  },
};

/**
 * Desktop child variants - slide z odpowiednich kierunków
 */
export const desktopChildVariants = {
  // RecalcPanel - slide z lewej
  left: {
    initial: { opacity: 0, x: -50 },
    animate: {
      opacity: 1,
      x: 0,
      transition: { duration: DURATION, ease: EASE },
    },
    exit: {
      opacity: 0,
      x: -50,
      transition: { duration: DURATION, ease: EASE },
    },
  },
  // ModeToggle - slide z prawej
  right: {
    initial: { opacity: 0, x: 50 },
    animate: {
      opacity: 1,
      x: 0,
      transition: { duration: DURATION, ease: EASE },
    },
    exit: {
      opacity: 0,
      x: 50,
      transition: { duration: DURATION, ease: EASE },
    },
  },
  // FAB - scale + fade
  fab: {
    initial: { opacity: 0, scale: 0.8 },
    animate: {
      opacity: 1,
      scale: 1,
      transition: { duration: DURATION, ease: EASE },
    },
    exit: {
      opacity: 0,
      scale: 0.8,
      transition: { duration: DURATION, ease: EASE },
    },
  },
};

