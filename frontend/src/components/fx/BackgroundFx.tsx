import { useEffect, useRef } from "react";

import { jitter } from "../../lib/fx";
import { useTheme } from "../../lib/theme";

/*
 * Hintergrund: ein statisches Raster mit Energiefeldern (reines CSS, `.fx-field`) und darüber ein
 * kleiner Canvas mit langsam treibenden Funkenpunkten und gelegentlich einem kurzen Blitz.
 *
 * Sparsam by design (iPhone-Akku):
 *  - kein Canvas bei `prefers-reduced-motion` (nur das statische Raster bleibt);
 *  - pausiert, wenn die Seite versteckt ist, und bei niedrigem Akku (Battery API, wo vorhanden);
 *  - höchstens ~24 Bilder je Sekunde, Auflösung 1× (weiche Punkte brauchen kein Retina);
 *  - Selbstschutz: ist ein Bild im Schnitt zu teuer, halbiert sich die Zahl der Punkte, danach stoppt es;
 *  - `document.documentElement.dataset.fx` zeigt den Zustand (running | paused | off) – für Tests.
 */

const FRAME_MS = 1000 / 24;
const BOLT_MS = 520;

type Dot = { x: number; y: number; vx: number; vy: number; r: number; phase: number; speed: number };

export function BackgroundFx() {
  const ref = useRef<HTMLCanvasElement>(null);
  const { resolved } = useTheme();

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    const root = document.documentElement;
    if (!canvas || !ctx) return;
    const motion = matchMedia("(prefers-reduced-motion: reduce)");
    const style = getComputedStyle(root);
    const arc = style.getPropertyValue("--c-arc").trim() || "#5ee7ff";
    const volt = style.getPropertyValue("--c-volt").trim() || "#ffd426";
    const dark = resolved === "dark";

    let width = 0;
    let height = 0;
    let dots: Dot[] = [];
    let count = 0;
    let raf = 0;
    let last = 0;
    let running = false;
    let lowBattery = false;
    let dead = false;
    let spent = 0;
    let frames = 0;
    let bolt: { points: [number, number][]; start: number } | null = null;
    let nextBolt = performance.now() + 5000 + Math.random() * 4000;

    const build = () => {
      width = canvas.width = Math.round(window.innerWidth);
      height = canvas.height = Math.round(window.innerHeight);
      count = Math.max(8, Math.min(26, Math.round((width * height) / 60000)));
      dots = Array.from({ length: count }, (_, i) => ({
        x: (jitter(i + 1) * 0.5 + 0.5) * width,
        y: (jitter(i + 91) * 0.5 + 0.5) * height,
        vx: jitter(i + 7) * 5,
        vy: -1.5 - (jitter(i + 13) * 0.5 + 0.5) * 4,
        r: 0.8 + (jitter(i + 21) * 0.5 + 0.5) * 1.4,
        phase: jitter(i + 33) * 6,
        speed: 0.3 + (jitter(i + 45) * 0.5 + 0.5) * 0.7,
      }));
    };

    const makeBolt = (now: number) => {
      // Zickzack zwischen zwei Rasterpunkten (Raster = 48 px)
      const cell = 48;
      const x0 = Math.round((Math.random() * width) / cell) * cell;
      const y0 = Math.round((Math.random() * height * 0.7) / cell) * cell;
      const horizontal = Math.random() < 0.5;
      const length = cell * (2 + Math.floor(Math.random() * 3));
      const steps = 6;
      const points: [number, number][] = [];
      for (let i = 0; i <= steps; i++) {
        const t = i / steps;
        const off = i === 0 || i === steps ? 0 : (Math.random() - 0.5) * 16;
        points.push(horizontal ? [x0 + t * length, y0 + off] : [x0 + off, y0 + t * length]);
      }
      bolt = { points, start: now };
    };

    const draw = (now: number) => {
      ctx.clearRect(0, 0, width, height);
      const t = now / 1000;
      ctx.fillStyle = arc;
      for (const d of dots) {
        const alpha = (0.5 + 0.5 * Math.sin(t * d.speed + d.phase)) * (dark ? 0.55 : 0.38);
        ctx.globalAlpha = alpha;
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
        ctx.fill();
      }
      if (bolt) {
        const k = (now - bolt.start) / BOLT_MS;
        if (k >= 1) bolt = null;
        else {
          ctx.globalAlpha = (1 - k) * (dark ? 0.8 : 0.6);
          ctx.strokeStyle = volt;
          ctx.lineWidth = 1.5;
          ctx.lineJoin = "round";
          ctx.shadowColor = arc;
          ctx.shadowBlur = 8;
          ctx.beginPath();
          const shown = Math.max(2, Math.ceil(bolt.points.length * Math.min(1, k * 3)));
          bolt.points.slice(0, shown).forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
          ctx.stroke();
          ctx.shadowBlur = 0;
        }
      }
      ctx.globalAlpha = 1;
    };

    const stop = (state: "paused" | "off") => {
      running = false;
      cancelAnimationFrame(raf);
      root.dataset.fx = state;
    };

    const tick = (now: number) => {
      if (!running) return;
      raf = requestAnimationFrame(tick);
      const dt = now - last;
      if (dt < FRAME_MS) return;
      last = now;
      const begin = performance.now();
      for (const d of dots) {
        d.x += (d.vx * dt) / 1000;
        d.y += (d.vy * dt) / 1000;
        if (d.y < -4) d.y = height + 4;
        if (d.x < -4) d.x = width + 4;
        if (d.x > width + 4) d.x = -4;
      }
      if (!bolt && now > nextBolt) {
        makeBolt(now);
        nextBolt = now + 7000 + Math.random() * 7000;
      }
      draw(now);
      // Selbstschutz: Kosten je Bild über 120 Bilder mitteln
      spent += performance.now() - begin;
      if (++frames === 120) {
        const avg = spent / frames;
        if (avg > 5) {
          dead = true;
          ctx.clearRect(0, 0, width, height);
          stop("off");
        } else if (avg > 2.5 && dots.length > 8) {
          dots = dots.slice(0, Math.ceil(dots.length / 2));
        }
        spent = 0;
        frames = 0;
      }
    };

    const start = () => {
      if (running || dead || motion.matches || lowBattery || document.hidden) return;
      running = true;
      last = performance.now();
      root.dataset.fx = "running";
      raf = requestAnimationFrame(tick);
    };
    const sync = () => {
      if (motion.matches) {
        ctx.clearRect(0, 0, width, height);
        stop("off");
      } else if (document.hidden || lowBattery) stop("paused");
      else start();
    };

    build();
    let resizeTimer = 0;
    const onResize = () => {
      clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(build, 200);
    };
    window.addEventListener("resize", onResize);
    document.addEventListener("visibilitychange", sync);
    motion.addEventListener("change", sync);

    let battery: { level: number; charging: boolean; addEventListener: (t: string, f: () => void) => void; removeEventListener: (t: string, f: () => void) => void } | null = null;
    const onBattery = () => {
      lowBattery = !!battery && battery.level < 0.2 && !battery.charging;
      sync();
    };
    (navigator as unknown as { getBattery?: () => Promise<NonNullable<typeof battery>> }).getBattery?.().then((b) => {
      battery = b;
      b.addEventListener("levelchange", onBattery);
      b.addEventListener("chargingchange", onBattery);
      onBattery();
    }).catch(() => {});

    sync();
    return () => {
      stop("off");
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", sync);
      motion.removeEventListener("change", sync);
      battery?.removeEventListener("levelchange", onBattery);
      battery?.removeEventListener("chargingchange", onBattery);
      clearTimeout(resizeTimer);
    };
  }, [resolved]);

  return (
    <>
      <div className="fx-field" aria-hidden="true" />
      <canvas ref={ref} className="fx-canvas" aria-hidden="true" />
    </>
  );
}
