import { motion } from "framer-motion";
import { useElementRect } from "../hooks/useElementRect";
import { computeAnchor } from "../utils/computeAnchor";

export function CoachCallout({
  selector,
  anchor,
  n,
  label,
  title,
  body,
  delay = 0,
}) {
  const rect = useElementRect(selector);
  if (!rect) return null;

  const pos = computeAnchor(rect, anchor);

  return (
    <motion.div
      style={{
        position: "fixed",
        top: pos.top,
        left: pos.left,
        width: "min(240px, calc(40vw - 20px))",
        padding: "12px 14px",
        background: "rgba(15,23,34,0.96)",
        backdropFilter: "blur(8px)",
        border: "1px solid rgba(255,255,255,0.10)",
        borderRadius: "14px",
        boxShadow: "0 18px 50px rgba(0,0,0,0.55)",
        pointerEvents: "none",
      }}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.36, ease: "easeOut" }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: "10px",
          marginBottom: "6px",
        }}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: "22px",
            height: "22px",
            borderRadius: "999px",
            background: "rgb(var(--color-primary))",
            color: "white",
            fontWeight: 800,
            fontSize: "11px",
            flexShrink: 0,
            marginTop: "1px",
          }}
        >
          {n}
        </span>
        <strong
          style={{
            fontSize: "13px",
            fontWeight: 700,
            color: "#fff",
            lineHeight: 1.3,
          }}
        >
          {title}
        </strong>
      </div>
      <p
        style={{
          margin: "0 0 0 32px",
          fontSize: "12px",
          lineHeight: 1.5,
          color: "#8aa0b6",
        }}
      >
        {body}
      </p>
      <div
        style={{
          marginTop: "8px",
          marginLeft: "32px",
          fontSize: "10px",
          color: "#6b8197",
          fontWeight: 500,
          letterSpacing: "0.05em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
    </motion.div>
  );
}
