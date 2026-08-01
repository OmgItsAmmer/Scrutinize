import { useId } from "react";

/**
 * The Wispr Flow hero signature: a loose gray line of handwritten-feeling
 * text curling in from the left, "spoken into" a circular voice bubble, and
 * continuing as a bold black marquee bar — the same sentence now inverted
 * (white on black), sliding continuously left-to-right.
 */
export function VoiceMarquee({
  text = "so no one really knows what's going on, can you check in with them and see if the notes from yesterday's meeting were sent out, or if they're still waiting",
  accent = "#10b981",
  className,
}: {
  text?: string;
  accent?: string;
  className?: string;
}) {
  const pathId = useId();

  return (
    <div className={className} style={{ width: "100%" }}>
      <style>{`
        @keyframes vm-marquee {
          from { transform: translateX(-50%); }
          to { transform: translateX(0%); }
        }
        @keyframes vm-bar-1 { 0%,100% { height: 30%; } 50% { height: 90%; } }
        @keyframes vm-bar-2 { 0%,100% { height: 70%; } 50% { height: 35%; } }
        @keyframes vm-bar-3 { 0%,100% { height: 45%; } 50% { height: 100%; } }
        .vm-track {
          display: flex;
          width: 200%;
          animation: vm-marquee 13s linear infinite;
        }
        .vm-seg {
          flex: 0 0 50%;
          display: flex;
          align-items: center;
          white-space: nowrap;
          padding-right: 3ch;
        }
        .vm-bubble-bar span { display:inline-block; width: 3px; border-radius: 2px; background: #1a1a1a; }
      `}</style>

      <svg
        viewBox="0 0 320 150"
        style={{ width: "100%", maxWidth: 420, height: "auto", display: "block", marginBottom: -8 }}
        aria-hidden="true"
      >
        <path
          id={pathId}
          d="M 300 20 C 220 -10, 140 5, 90 45 C 40 85, 60 130, 105 128 C 145 126, 150 92, 118 82 C 92 74, 78 96, 95 108"
          fill="none"
          stroke="none"
        />
        <text fontSize="13" fill="var(--app-text-faint)" fontStyle="italic" letterSpacing="0.2">
          <textPath href={`#${pathId}`} startOffset="0%">
            {text}
          </textPath>
        </text>
      </svg>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: -18,
          position: "relative",
        }}
      >
        <div
          className="vm-bubble-bar"
          style={{
            width: 56,
            height: 56,
            borderRadius: 9999,
            background: "var(--app-bg)",
            border: "2px solid #1a1a1a",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 3,
            flex: "0 0 auto",
            zIndex: 2,
            marginRight: -20,
          }}
        >
          <span style={{ height: "40%", animation: "vm-bar-1 1.1s ease-in-out infinite" }} />
          <span style={{ height: "70%", animation: "vm-bar-2 1.1s ease-in-out infinite" }} />
          <span style={{ height: "50%", animation: "vm-bar-3 1.1s ease-in-out infinite" }} />
          <span style={{ height: "65%", animation: "vm-bar-1 1.1s ease-in-out infinite 0.2s" }} />
        </div>

        <div
          style={{
            flex: 1,
            minWidth: 0,
            height: 56,
            borderRadius: 9999,
            background: "#050505",
            overflow: "hidden",
            paddingLeft: 32,
            display: "flex",
            alignItems: "center",
          }}
        >
          <div className="vm-track">
            <span className="vm-seg" style={{ color: "#f5f5f7", fontWeight: 600, fontSize: 16 }}>
              {text}
            </span>
            <span className="vm-seg" style={{ color: accent, fontWeight: 600, fontSize: 16 }}>
              {text}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
