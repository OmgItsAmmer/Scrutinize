import { useEffect } from "react";

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

/**
 * Adds eased/inertial momentum to wheel-driven scrolling by intercepting
 * wheel deltas and lerping window.scrollTo toward the accumulated target,
 * rather than faking scroll with a transformed fixed layer. Real document
 * scroll keeps moving, so scrollIntoView, anchor links, IntersectionObserver,
 * and browser scroll restoration all keep working correctly. Touch scroll is
 * left untouched — mobile OSes already apply their own momentum.
 */
export function useInertialScroll() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let target = window.scrollY;
    let current = window.scrollY;
    let raf = 0;
    let running = false;

    const maxScroll = () => Math.max(0, document.documentElement.scrollHeight - window.innerHeight);

    const loop = () => {
      current = lerp(current, target, 0.12);
      if (Math.abs(target - current) < 0.5) {
        current = target;
        window.scrollTo(0, current);
        running = false;
        return;
      }
      window.scrollTo(0, current);
      raf = requestAnimationFrame(loop);
    };

    const onWheel = (e: WheelEvent) => {
      // Let horizontal-intent gestures (e.g. the filmstrip's overflow-x) pass through natively.
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
      e.preventDefault();
      target = Math.min(Math.max(target + e.deltaY, 0), maxScroll());
      if (!running) {
        running = true;
        raf = requestAnimationFrame(loop);
      }
    };

    const onNativeScroll = () => {
      // Keyboard / scrollbar-drag / programmatic scroll should stay authoritative.
      if (!running) {
        target = window.scrollY;
        current = window.scrollY;
      }
    };

    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("scroll", onNativeScroll, { passive: true });
    return () => {
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("scroll", onNativeScroll);
      cancelAnimationFrame(raf);
    };
  }, []);
}
