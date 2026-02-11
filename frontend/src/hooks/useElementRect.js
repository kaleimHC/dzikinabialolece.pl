import { useState, useLayoutEffect } from "react";

export function useElementRect(selector) {
  const [rect, setRect] = useState(null);

  useLayoutEffect(() => {
    const el = document.querySelector(selector);
    if (!el) return;

    const update = () => {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) return;
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    };

    update();

    // Re-measure after Framer Motion entry animations settle (~300-500ms)
    const t1 = setTimeout(update, 350);
    const t2 = setTimeout(update, 700);

    const ro = new ResizeObserver(update);
    ro.observe(el);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      ro.disconnect();
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [selector]);

  return rect;
}
