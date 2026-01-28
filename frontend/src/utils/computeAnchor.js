const GAP = 16;
const CALLOUT_W = 264;
const CALLOUT_H = 145;
const MARGIN = 10;

export function computeAnchor(rect, anchor, offsetY = 0) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;

  let top, left;

  switch (anchor) {
    case "left-of":
      top = rect.top + rect.height / 2 - CALLOUT_H / 2;
      left = rect.left - CALLOUT_W - GAP;
      break;
    case "right-of":
      top = rect.top + rect.height / 2 - CALLOUT_H / 2;
      left = rect.left + rect.width + GAP;
      break;
    case "below-left":
      top = rect.top + rect.height + GAP;
      left = rect.left;
      break;
    case "above-right":
      top = rect.top - CALLOUT_H - GAP;
      left = rect.left + rect.width - CALLOUT_W;
      break;
    default:
      top = rect.top;
      left = rect.left;
  }

  top += offsetY;
  top = Math.max(MARGIN, Math.min(vh - CALLOUT_H - MARGIN, top));
  left = Math.max(MARGIN, Math.min(vw - CALLOUT_W - MARGIN, left));

  return { top, left };
}
