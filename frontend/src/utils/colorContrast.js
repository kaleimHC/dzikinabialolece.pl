/**
 * WCAG contrast ratio helper for theme text validation.
 * @param {string} rgb1 - "R G B" triplet (0-255)
 * @param {string} rgb2 - "R G B" triplet (0-255)
 */
export function contrastRatio(rgb1, rgb2) {
  const lum = (rgb) => {
    const c = rgb.split(" ").map((v) => {
      const s = parseInt(v) / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  };
  const l1 = lum(rgb1),
    l2 = lum(rgb2);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

export function meetsWCAG(rgb1, rgb2, level = "AA") {
  const ratio = contrastRatio(rgb1, rgb2);
  return level === "AAA" ? ratio >= 7 : ratio >= 4.5;
}
