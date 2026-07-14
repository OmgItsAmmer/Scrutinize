import type { SVGProps } from "react";

/** Placeholder project artwork — hardcoded Ronaldo-style silhouette for all project cards. */
export function RonaldoProjectIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 200 150" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden preserveAspectRatio="xMidYMid slice" {...props}>
      <defs>
        <linearGradient id="ronaldo-bg" x1="0" y1="0" x2="200" y2="150" gradientUnits="userSpaceOnUse">
          <stop stopColor="#1a1a2e" />
          <stop offset="0.5" stopColor="#16213e" />
          <stop offset="1" stopColor="#0f3460" />
        </linearGradient>
        <linearGradient id="ronaldo-silhouette" x1="50" y1="18" x2="150" y2="138" gradientUnits="userSpaceOnUse">
          <stop stopColor="#f5c518" />
          <stop offset="1" stopColor="#e8a317" />
        </linearGradient>
      </defs>
      <rect width="200" height="150" fill="url(#ronaldo-bg)" />
      <ellipse cx="100" cy="136" rx="62" ry="10" fill="rgba(0,0,0,0.38)" />
      <path
        d="M62 118c3-24 11-42 24-54 5-5 12-9 20-10-4-8-3-18 6-24 9-7 23-6 30 3 6 8 7 19 3 28 10 3 18 9 24 18 10 15 15 36 12 54"
        fill="url(#ronaldo-silhouette)"
      />
      <path
        d="M42 72c10-8 22-13 36-10M158 72c-10-8-22-13-36-10"
        stroke="#f5c518"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <circle cx="100" cy="46" r="18" fill="url(#ronaldo-silhouette)" />
      <path
        d="M84 38c5-5 13-6 20-4 7 3 11 9 10 16"
        stroke="#1a1a2e"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <text x="100" y="22" textAnchor="middle" fill="rgba(255,255,255,0.55)" fontSize="11" fontWeight="700" fontFamily="system-ui, sans-serif" letterSpacing="2.5">
        CR7
      </text>
    </svg>
  );
}
