import { motion } from "framer-motion";
import { useSightingsStore } from "../stores/sightingsStore";

export default function CenteredPin() {
  const { isAddMode } = useSightingsStore();

  if (!isAddMode) return null;

  return (
    <div
      className="pin-primary"
      style={{
        position: "fixed",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -100%)",
        zIndex: 1000,
        pointerEvents: "none",
      }}
    >
      <motion.div
        initial={{ y: -30, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 300, damping: 20 }}
      >
        {/* Pin SVG */}
        <svg width="40" height="52" viewBox="0 0 40 52" fill="none">
          {/* Shadow */}
          <ellipse cx="20" cy="49" rx="8" ry="3" fill="rgba(0,0,0,0.4)" />
          {/* Pin body */}
          <path
            d="M20 0C8.954 0 0 8.954 0 20c0 15 20 30 20 30s20-15 20-30C40 8.954 31.046 0 20 0z"
            fill="currentColor"
          />
          {/* Inner circle */}
          <circle cx="20" cy="18" r="8" fill="white" />
          {/* Boar emoji */}
          <text x="20" y="22" textAnchor="middle" fontSize="11">
            🐗
          </text>
        </svg>
      </motion.div>
    </div>
  );
}
