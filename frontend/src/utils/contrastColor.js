/**
 * Pick a readable text color (dark or light) for a given background.
 * Uses the perceived-luminance (YIQ) formula.
 */
export function contrastColor(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 > 128 ? "#1a1a1a" : "#ffffff";
}

/**
 * Same as contrastColor but for an "rgb(r g b)" / "rgb(r, g, b)" string.
 */
export function contrastColorRgb(rgbStr) {
  const clean = rgbStr.replace(/^rgb\(\s*|\s*\)$/g, "");
  const [r, g, b] = clean.trim().split(/\s+/).map(Number);
  return (r * 299 + g * 587 + b * 114) / 1000 > 128 ? "#1a1a1a" : "#ffffff";
}
