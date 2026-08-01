import { useEffect, useMemo, useRef } from "react";

/**
 * Infinite zoom-quilt canvas gallery. Ported from the OriginKit "Infinity Canvas"
 * component (docs/ui/images_section.md) — same scatter/octave-swap engine, but
 * driven by a tiny ref-based motion value (no framer-motion dependency) and
 * rendering palette-driven placeholder tiles instead of hotlinked images, since
 * we don't have real asset URLs to embed.
 */

type Tile = {
  wx: number;
  wy: number;
  cx: number;
  cy: number;
  slot: number;
  octave: number;
  colorIdx: number;
  w: number;
  h: number;
  bakedScale: number;
};

type MotionValue = { get: () => number; set: (v: number) => void };
function useMV(initial: number): MotionValue {
  const ref = useRef(initial);
  return useMemo(
    () => ({
      get: () => ref.current,
      set: (v: number) => {
        ref.current = v;
      },
    }),
    [],
  );
}

function hash3(cx: number, cy: number, cz: number, salt: number) {
  let h = (cx | 0) * 0x8da6b343;
  h ^= Math.imul(cy | 0, 0xd8163841);
  h ^= Math.imul(cz | 0, 0xcb1ab31f);
  h ^= salt | 0;
  h ^= h >>> 16;
  h = Math.imul(h, 0x7feb352d);
  h ^= h >>> 15;
  h = Math.imul(h, 0x846ca68b);
  h ^= h >>> 16;
  return h >>> 0;
}

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

const PX_PER_UNIT = 6;
const CELL_SIZE = 110;
const MAX_RANGE = 20;
const SCALE_MIN = 0.45;
const SCALE_MAX = 1.6;

// App-consistent palette: modality accents + neutral glass tones.
const TILE_PALETTE = [
  "linear-gradient(135deg, #0ea5e9, #38bdf8)",
  "linear-gradient(135deg, #10b981, #34d399)",
  "linear-gradient(135deg, #f59e0b, #fbbf24)",
  "linear-gradient(135deg, #8b5cf6, #a78bfa)",
  "linear-gradient(135deg, #e2e8f0, #cbd5e1)",
  "linear-gradient(135deg, #050505, #27272a)",
];

type InfiniteGalleryProps = {
  className?: string;
  density?: number;
  imageWidth?: number;
  imageHeight?: number;
  rounded?: number;
  dragSpeed?: number;
  driftAmount?: number;
  friction?: number;
  style?: React.CSSProperties;
};

export function InfiniteGallery({
  className,
  density = 4,
  imageWidth = 130,
  imageHeight = 130,
  rounded = 10,
  dragSpeed = 1,
  driftAmount = 6,
  friction = 0.4,
  style,
}: InfiniteGalleryProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<HTMLDivElement | null>(null);

  const safeDensity = Math.max(1, Math.min(15, Math.floor(density)));
  const safeFriction = 1 - Math.max(0.05, Math.min(0.95, friction)) * 0.3 + 0.7;

  const targetX = useMV(0);
  const targetY = useMV(0);
  const camX = useMV(0);
  const camY = useMV(0);
  const velX = useMV(0);
  const velY = useMV(0);
  const targetLogZoom = useMV(0);
  const logZoom = useMV(0);
  const velLogZoom = useMV(0);
  const driftTX = useMV(0);
  const driftTY = useMV(0);
  const driftX = useMV(0);
  const driftY = useMV(0);

  const subN = Math.max(1, Math.ceil(Math.sqrt(safeDensity)));
  const subSize = CELL_SIZE / subN;
  const SUBCELL_INNER_PAD = 0.1;
  const effectivePerCell = Math.min(safeDensity, subN * subN);

  const generateCell = useMemo(() => {
    return (gx: number, gy: number, octave: number): Tile[] => {
      const seed = hash3(gx, gy, octave | 0, 0x9e3779b1);
      const rand = mulberry32(seed);

      const totalSubs = subN * subN;
      const subs = new Array<number>(totalSubs);
      for (let i = 0; i < totalSubs; i++) subs[i] = i;
      for (let i = totalSubs - 1; i > 0; i--) {
        const j = Math.floor(rand() * (i + 1));
        const tmp = subs[i];
        subs[i] = subs[j];
        subs[j] = tmp;
      }

      const tiles: Tile[] = [];
      const count = Math.min(effectivePerCell, totalSubs);
      const pad = subSize * SUBCELL_INNER_PAD;
      const innerRange = Math.max(0, subSize - pad * 2);
      const cellX0 = gx * CELL_SIZE;
      const cellY0 = gy * CELL_SIZE;
      const wWorld = imageWidth / PX_PER_UNIT;
      const hWorld = imageHeight / PX_PER_UNIT;

      for (let slot = 0; slot < count; slot++) {
        const subIdx = subs[slot];
        const sx = subIdx % subN;
        const sy = Math.floor(subIdx / subN);
        const wx = cellX0 + sx * subSize + pad + rand() * innerRange;
        const wy = cellY0 + sy * subSize + pad + rand() * innerRange;
        const bakedScale = SCALE_MIN + rand() * (SCALE_MAX - SCALE_MIN);
        const colorIdx = Math.floor(rand() * TILE_PALETTE.length) % TILE_PALETTE.length;

        tiles.push({
          wx,
          wy,
          cx: gx,
          cy: gy,
          slot,
          octave,
          colorIdx,
          w: wWorld,
          h: hWorld,
          bakedScale,
        });
      }
      return tiles;
    };
  }, [subN, subSize, effectivePerCell, imageWidth, imageHeight]);

  useEffect(() => {
    const scene = sceneRef.current;
    const container = containerRef.current;
    if (!scene) return;

    let cW = container ? container.clientWidth || 900 : 900;
    let cH = container ? container.clientHeight || 600 : 600;
    const ro = new ResizeObserver(() => {
      if (container) {
        cW = container.clientWidth || cW;
        cH = container.clientHeight || cH;
      }
    });
    if (container) ro.observe(container);

    const layerPools = new Map<number, { tileEls: Map<string, HTMLDivElement> }>();
    const getPool = (octave: number) => {
      let pool = layerPools.get(octave);
      if (!pool) {
        pool = { tileEls: new Map() };
        layerPools.set(octave, pool);
      }
      return pool;
    };
    const disposeLayer = (octave: number) => {
      const pool = layerPools.get(octave);
      if (!pool) return;
      pool.tileEls.forEach((el) => {
        if (el.parentNode === scene) scene.removeChild(el);
      });
      pool.tileEls.clear();
      layerPools.delete(octave);
    };
    const removeTile = (octave: number, key: string) => {
      const pool = layerPools.get(octave);
      if (!pool) return;
      const el = pool.tileEls.get(key);
      if (el && el.parentNode === scene) scene.removeChild(el);
      pool.tileEls.delete(key);
    };

    const ensureTile = (t: Tile): HTMLDivElement => {
      const pool = getPool(t.octave);
      const key = `${t.cx},${t.cy},${t.slot}`;
      let el = pool.tileEls.get(key);
      if (!el) {
        el = document.createElement("div");
        el.style.position = "absolute";
        el.style.left = "50%";
        el.style.top = "50%";
        el.style.transformOrigin = "0 0";
        el.style.willChange = "transform, opacity";
        el.style.pointerEvents = "none";
        el.style.background = TILE_PALETTE[t.colorIdx];
        el.style.boxShadow = "0 8px 24px rgba(5, 5, 5, 0.12)";
        scene.appendChild(el);
        pool.tileEls.set(key, el);
      }
      return el;
    };

    const projectLayer = (
      octave: number,
      layerScale: number,
      layerAlpha: number,
      layerZBase: number,
      cx: number,
      cy: number,
    ) => {
      const pool = getPool(octave);
      const camCellX = Math.floor(cx / CELL_SIZE);
      const camCellY = Math.floor(cy / CELL_SIZE);
      const worldHalfX = cW / 2 / (PX_PER_UNIT * layerScale);
      const worldHalfY = cH / 2 / (PX_PER_UNIT * layerScale);
      const rangeX = Math.min(MAX_RANGE, Math.ceil(worldHalfX / CELL_SIZE) + 1);
      const rangeY = Math.min(MAX_RANGE, Math.ceil(worldHalfY / CELL_SIZE) + 1);

      const visibleKeys = new Set<string>();
      const tilesThisFrame: Tile[] = [];
      for (let dy = -rangeY; dy <= rangeY; dy++) {
        for (let dx = -rangeX; dx <= rangeX; dx++) {
          const tiles = generateCell(camCellX + dx, camCellY + dy, octave);
          for (let i = 0; i < tiles.length; i++) tilesThisFrame.push(tiles[i]);
        }
      }

      const orderKeys: string[] = new Array(tilesThisFrame.length);
      const orderScale: number[] = new Array(tilesThisFrame.length);

      for (let i = 0; i < tilesThisFrame.length; i++) {
        const t = tilesThisFrame[i];
        const key = `${t.cx},${t.cy},${t.slot}`;
        visibleKeys.add(key);

        const dxPx = (t.wx - cx) * layerScale * PX_PER_UNIT;
        const dyPx = (t.wy - cy) * layerScale * PX_PER_UNIT;
        const s = t.bakedScale * layerScale;
        const el = ensureTile(t);
        const wPx = t.w * PX_PER_UNIT;
        const hPx = t.h * PX_PER_UNIT;

        el.style.transform = `translate3d(${dxPx}px, ${dyPx}px, 0) scale(${s}) translate(${-wPx / 2}px, ${-hPx / 2}px)`;
        el.style.width = `${wPx}px`;
        el.style.height = `${hPx}px`;
        el.style.opacity = String(layerAlpha);
        el.style.borderRadius = `${(rounded / 20) * (Math.min(wPx, hPx) / 2)}px`;

        orderKeys[i] = key;
        orderScale[i] = t.bakedScale;
      }

      for (const key of Array.from(pool.tileEls.keys())) {
        if (!visibleKeys.has(key)) removeTile(octave, key);
      }

      const idxs = orderKeys.map((_, i) => i);
      idxs.sort((a, b) => orderScale[a] - orderScale[b]);
      for (let k = 0; k < idxs.length; k++) {
        const el = pool.tileEls.get(orderKeys[idxs[k]]);
        if (el) el.style.zIndex = String(layerZBase + k);
      }
    };

    let lastOctaves: Set<number> = new Set();
    const project = () => {
      const cx = camX.get();
      const cy = camY.get();
      const lz = logZoom.get();
      const octave = Math.floor(lz);
      const frac = lz - octave;
      const scaleCurrent = Math.pow(2, frac);
      const scaleNext = Math.pow(2, frac - 1);
      const alphaCurrent = 1 - frac;
      const alphaNext = frac;

      projectLayer(octave, scaleCurrent, alphaCurrent, 0, cx, cy);
      projectLayer(octave + 1, scaleNext, alphaNext, 100000, cx, cy);

      const nowOctaves = new Set<number>([octave, octave + 1]);
      for (const o of Array.from(lastOctaves)) if (!nowOctaves.has(o)) disposeLayer(o);
      for (const o of Array.from(layerPools.keys())) if (!nowOctaves.has(o)) disposeLayer(o);
      lastOctaves = nowOctaves;
    };

    project();
    let raf = 0;
    const loop = () => {
      const tx = targetX.get() + velX.get();
      const ty = targetY.get() + velY.get();
      targetX.set(tx);
      targetY.set(ty);
      velX.set(velX.get() * safeFriction);
      velY.set(velY.get() * safeFriction);

      const vlz = velLogZoom.get();
      if (vlz !== 0) {
        targetLogZoom.set(targetLogZoom.get() + vlz);
        velLogZoom.set(vlz * safeFriction);
      }

      driftX.set(lerp(driftX.get(), driftTX.get() * driftAmount, 0.08));
      driftY.set(lerp(driftY.get(), driftTY.get() * driftAmount, 0.08));
      camX.set(lerp(camX.get(), targetX.get() + driftX.get(), 0.18));
      camY.set(lerp(camY.get(), targetY.get() + driftY.get(), 0.18));
      logZoom.set(lerp(logZoom.get(), targetLogZoom.get(), 0.18));

      project();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      Array.from(layerPools.keys()).forEach(disposeLayer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [generateCell, safeFriction, driftAmount, rounded]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    let dragging = false;
    let lastPX = 0;
    let lastPY = 0;
    let lastT = 0;
    let pid: number | null = null;

    const onDown = (e: PointerEvent) => {
      if (e.button !== 0 && e.pointerType === "mouse") return;
      dragging = true;
      pid = e.pointerId;
      lastPX = e.clientX;
      lastPY = e.clientY;
      lastT = e.timeStamp;
      try {
        el.setPointerCapture(e.pointerId);
      } catch {
        /* noop */
      }
      el.style.cursor = "grabbing";
    };

    const onMove = (e: PointerEvent) => {
      const rect = el.getBoundingClientRect();
      const nx = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const ny = ((e.clientY - rect.top) / rect.height) * 2 - 1;
      driftTX.set(Math.max(-1, Math.min(1, nx)));
      driftTY.set(Math.max(-1, Math.min(1, ny)));

      if (!dragging || e.pointerId !== pid) return;
      const dpx = e.clientX - lastPX;
      const dpy = e.clientY - lastPY;
      const lz = logZoom.get();
      const frac = lz - Math.floor(lz);
      const effScale = (1 - frac) * Math.pow(2, frac) + frac * Math.pow(2, frac - 1);
      const dWorldX = (-dpx / (PX_PER_UNIT * effScale)) * dragSpeed;
      const dWorldY = (-dpy / (PX_PER_UNIT * effScale)) * dragSpeed;
      targetX.set(targetX.get() + dWorldX);
      targetY.set(targetY.get() + dWorldY);

      const dt = Math.max(1, e.timeStamp - lastT);
      const k = 16 / dt;
      velX.set(dWorldX * k);
      velY.set(dWorldY * k);

      lastPX = e.clientX;
      lastPY = e.clientY;
      lastT = e.timeStamp;
    };

    const onUp = (e: PointerEvent) => {
      if (!dragging || e.pointerId !== pid) return;
      dragging = false;
      pid = null;
      try {
        el.releasePointerCapture(e.pointerId);
      } catch {
        /* noop */
      }
      el.style.cursor = "grab";
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      let delta = e.deltaY;
      if (e.deltaMode === 1) delta *= 16;
      else if (e.deltaMode === 2) delta *= 400;
      const step = -delta * 0.0015 * dragSpeed;
      velLogZoom.set(velLogZoom.get() + step);
    };

    const onLeave = () => {
      driftTX.set(0);
      driftTY.set(0);
    };

    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
    el.addEventListener("wheel", onWheel, { passive: false });
    el.addEventListener("pointerleave", onLeave);
    el.style.cursor = "grab";

    return () => {
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onUp);
      el.removeEventListener("wheel", onWheel);
      el.removeEventListener("pointerleave", onLeave);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dragSpeed]);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        overflow: "hidden",
        touchAction: "none",
        userSelect: "none",
        cursor: "grab",
        ...style,
      }}
    >
      <div ref={sceneRef} style={{ position: "absolute", inset: 0 }} />
    </div>
  );
}
