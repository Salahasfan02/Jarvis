import { useEffect, useRef } from "react";
import mapData from "./worldmap.json";

interface Arc {
  from: [number, number];
  to: [number, number];
  progress: number;      // 0..1 of the pulse along the curve
  speed: number;
  alive: number;         // remaining life in frames after arrival
}

interface Ping { x: number; y: number; r: number; alpha: number; }

const CITY_LIST = Object.values(mapData.cities) as [number, number][];

/** Command-center world map: dotted continents with data streams arcing
 *  between cities. Tinted by the active theme via --core-rgb. */
export function WorldMap() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current!;
    const ctx = canvas.getContext("2d")!;
    let raf = 0;
    let arcs: Arc[] = [];
    let pings: Ping[] = [];

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const project = ([mx, my]: [number, number]) => {
      // fit the map into the viewport, centered, with margin
      const scale = Math.min(canvas.width / mapData.w, canvas.height / mapData.h) * 0.86;
      const ox = (canvas.width - mapData.w * scale) / 2;
      const oy = (canvas.height - mapData.h * scale) / 2;
      return [ox + mx * scale, oy + my * scale] as [number, number];
    };

    const bezier = (a: [number, number], b: [number, number], t: number) => {
      const [ax, ay] = project(a);
      const [bx, by] = project(b);
      const mx = (ax + bx) / 2;
      const my = (ay + by) / 2 - Math.hypot(bx - ax, by - ay) * 0.25; // arc height
      const u = 1 - t;
      return [
        u * u * ax + 2 * u * t * mx + t * t * bx,
        u * u * ay + 2 * u * t * my + t * t * by,
      ] as [number, number];
    };

    const spawnArc = () => {
      const from = CITY_LIST[Math.floor(Math.random() * CITY_LIST.length)];
      let to = CITY_LIST[Math.floor(Math.random() * CITY_LIST.length)];
      if (to === from) to = CITY_LIST[(CITY_LIST.indexOf(from) + 3) % CITY_LIST.length];
      arcs.push({ from, to, progress: 0, speed: 0.004 + Math.random() * 0.006, alive: 30 });
    };

    let frame = 0;
    const draw = () => {
      frame++;
      const rgb = getComputedStyle(document.documentElement)
        .getPropertyValue("--core-rgb").trim() || "0, 255, 102";
      const bg = getComputedStyle(document.documentElement)
        .getPropertyValue("--bg").trim() || "#010804";

      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // continents as a dot grid
      const scale = Math.min(canvas.width / mapData.w, canvas.height / mapData.h) * 0.86;
      const dotR = Math.max(0.7, scale * 0.32);
      ctx.fillStyle = `rgba(${rgb}, 0.16)`;
      for (const d of mapData.dots as [number, number][]) {
        const [x, y] = project(d);
        ctx.beginPath();
        ctx.arc(x, y, dotR, 0, Math.PI * 2);
        ctx.fill();
      }

      // city hubs (soft pulse)
      const hubPulse = 0.35 + 0.2 * Math.sin(frame * 0.05);
      for (const c of CITY_LIST) {
        const [x, y] = project(c);
        ctx.beginPath();
        ctx.arc(x, y, dotR * 1.7, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${rgb}, ${hubPulse})`;
        ctx.fill();
      }

      // data streams
      if (arcs.length < 7 && frame % 40 === 0) spawnArc();
      arcs = arcs.filter((a) => a.alive > 0);
      for (const arc of arcs) {
        if (arc.progress < 1) arc.progress = Math.min(1, arc.progress + arc.speed);
        else arc.alive--;

        // trail: line up to current progress
        ctx.beginPath();
        const steps = 36;
        const upTo = Math.floor(arc.progress * steps);
        for (let i = 0; i <= upTo; i++) {
          const [x, y] = bezier(arc.from, arc.to, i / steps);
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        const fade = arc.progress < 1 ? 0.35 : 0.35 * (arc.alive / 30);
        ctx.strokeStyle = `rgba(${rgb}, ${fade})`;
        ctx.lineWidth = 1.2;
        ctx.stroke();

        // moving pulse head
        if (arc.progress < 1) {
          const [hx, hy] = bezier(arc.from, arc.to, arc.progress);
          ctx.beginPath();
          ctx.arc(hx, hy, 2.4, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${rgb}, 0.95)`;
          ctx.fill();
        } else if (arc.alive === 29) {
          // arrival ping
          const [px, py] = project(arc.to);
          pings.push({ x: px, y: py, r: 3, alpha: 0.6 });
        }
      }

      // expanding arrival pings
      pings = pings.filter((p) => p.alpha > 0.02);
      for (const p of pings) {
        p.r += 0.9;
        p.alpha *= 0.94;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${rgb}, ${p.alpha})`;
        ctx.lineWidth = 1.3;
        ctx.stroke();
      }

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas className="matrix-rain" ref={ref} />;
}
