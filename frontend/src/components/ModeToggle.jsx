import { useState } from "react";
import { useSightingsStore } from "../stores/sightingsStore";
import LayerToggles from "./LayerToggles";

export default function ModeToggle({ embedded = false }) {
  const { displayMode } = useSightingsStore();
  const [expandedPanel, setExpandedPanel] = useState(null);

  const content = (
    <>
      {/* Layer toggles */}
      <LayerToggles
        isExpanded={expandedPanel === "layers"}
        onToggle={() =>
          setExpandedPanel((prev) => (prev === "layers" ? null : "layers"))
        }
      />
    </>
  );

  if (embedded) {
    return <div>{content}</div>;
  }

  return (
    <div
      className="rounded-lg p-3"
      style={{
        background: "rgb(var(--color-surface) / 0.95)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        border: "1px solid rgb(var(--color-border))",
        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
      }}
    >
      {content}
    </div>
  );
}
