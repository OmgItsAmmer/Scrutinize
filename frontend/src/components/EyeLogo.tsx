import { useEffect, useRef } from "react";

type EyeLogoProps = {
  size?: number;
  gap?: number;
  className?: string;
};

/**
 * Two-eye brand mark. Pupils track the live cursor via atan2 + lerp easing;
 * on mount they run a short scripted sweep so the mark reads immediately
 * even if the user hasn't moved the mouse yet.
 */
export function EyeLogo({ size = 48, gap, className = "" }: EyeLogoProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const eyes = Array.from(container.querySelectorAll<HTMLDivElement>(".eye-dome"));
    const mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const state = eyes.map(() => ({ x: 0, y: 0 }));

    function onMouseMove(e: MouseEvent) {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    }
    function onTouchMove(e: TouchEvent) {
      if (e.touches[0]) {
        mouse.x = e.touches[0].clientX;
        mouse.y = e.touches[0].clientY;
      }
    }
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("touchmove", onTouchMove, { passive: true });

    const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
    const introDuration = 2200;
    const startTime = performance.now();

    function introOffset(t: number) {
      const angle = t * Math.PI * 2;
      return { x: Math.sin(angle) * size * 0.19, y: Math.sin(angle * 2) * size * 0.04 };
    }

    function frame(now: number) {
      const elapsed = now - startTime;

      eyes.forEach((eye, i) => {
        const pupil = eye.querySelector<HTMLDivElement>(".pupil");
        if (!pupil) return;
        const rect = eye.getBoundingClientRect();
        let targetX: number, targetY: number;

        if (elapsed < introDuration) {
          const t = elapsed / introDuration;
          const off = introOffset(t);
          targetX = off.x;
          targetY = off.y;
        } else {
          const eyeCenterX = rect.left + rect.width / 2;
          const eyeCenterY = rect.top + rect.height * 0.75;
          const dx = mouse.x - eyeCenterX;
          const dy = mouse.y - eyeCenterY;
          const angle = Math.atan2(dy, dx);
          const maxDist = rect.width * 0.22;
          const dist = Math.min(Math.hypot(dx, dy) * 0.15, maxDist);
          targetX = Math.cos(angle) * dist;
          targetY = Math.sin(angle) * dist * 0.5;
        }

        const cur = state[i];
        cur.x = lerp(cur.x, targetX, 0.15);
        cur.y = lerp(cur.y, targetY, 0.15);
        pupil.style.transform = `translate(calc(-50% + ${cur.x}px), calc(-30% + ${cur.y}px))`;
      });

      rafRef.current = requestAnimationFrame(frame);
    }
    rafRef.current = requestAnimationFrame(frame);

    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("touchmove", onTouchMove);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [size]);

  const pupilSize = size * 0.38;
  const eyeGap = gap ?? size * 0.22;

  return (
    <div
      ref={containerRef}
      className={`flex items-center ${className}`}
      style={{ gap: eyeGap }}
    >
      {[0, 1].map((i) => (
        <div
          key={i}
          className="eye-dome"
          style={{
            width: size,
            height: size * 0.86,
            background: "#ffffff",
            borderRadius: `${size * 0.55}px ${size * 0.55}px ${size * 0.04}px ${size * 0.04}px`,
            position: "relative",
            overflow: "hidden",
            boxShadow: "0 6px 18px rgba(10,10,10,0.14)",
            animation: "eyelogo-blink 6.5s ease-in-out infinite",
            animationDelay: `${i * 0.3}s`,
          }}
        >
          <div
            className="pupil"
            style={{
              position: "absolute",
              width: pupilSize,
              height: pupilSize,
              background: "#0a0a0a",
              borderRadius: "50%",
              left: "50%",
              top: "68%",
              transform: "translate(-50%, -30%)",
              willChange: "transform",
            }}
          />
        </div>
      ))}
      <style>{`
        @keyframes eyelogo-blink {
          0%, 90%, 100% { transform: scaleY(1); }
          94% { transform: scaleY(0.17); }
        }
      `}</style>
    </div>
  );
}
