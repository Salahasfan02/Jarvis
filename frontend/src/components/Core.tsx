import { useEffect, useRef } from "react";
import { voiceBus } from "../lib/voice";

export type CoreMode = "idle" | "thinking" | "speaking" | "listening";

/** The JARVIS core: orbiting particles, energy rings and a glowing nucleus.
 *  Idle: slow drift. Thinking: fast orbit. Speaking: audio-reactive pulse
 *  rings driven by voiceBus amplitude events. */
export function Core({ mode, size = 420 }: { mode: CoreMode; size?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const modeRef = useRef<CoreMode>(mode);
  const ampRef = useRef(0);
  const speakingRef = useRef(false);
  modeRef.current = mode;

  useEffect(() => {
    const onAmp = (e: Event) => (ampRef.current = (e as CustomEvent).detail);
    const onSpeak = (e: Event) => (speakingRef.current = (e as CustomEvent).detail);
    voiceBus.addEventListener("amplitude", onAmp);
    voiceBus.addEventListener("speaking", onSpeak);
    return () => {
      voiceBus.removeEventListener("amplitude", onAmp);
      voiceBus.removeEventListener("speaking", onSpeak);
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current!;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);
    const cx = size / 2;
    const cy = size / 2;

    const particles = Array.from({ length: 90 }, (_, i) => ({
      angle: (Math.PI * 2 * i) / 90 + Math.random(),
      radius: 70 + Math.random() * 110,
      speed: 0.0015 + Math.random() * 0.004,
      size: 0.8 + Math.random() * 1.8,
      wobble: Math.random() * Math.PI * 2,
    }));

    interface Ring { r: number; alpha: number; }
    let rings: Ring[] = [];
    let raf = 0;
    let t = 0;
    let smoothing = 0;

    const draw = () => {
      t += 1;
      const m = modeRef.current;
      const speaking = speakingRef.current;
      const target = speaking ? ampRef.current : 0;
      smoothing += (target - smoothing) * 0.25;
      const amp = smoothing;

      const speedMul = m === "thinking" ? 4 : m === "listening" ? 2 : 1;
      const breath = Math.sin(t * 0.02) * 0.5 + 0.5;
      const coreR = 44 + breath * 4 + amp * 26;

      ctx.clearRect(0, 0, size, size);

      // spawn expanding energy rings while speaking
      if (speaking && t % 9 === 0 && amp > 0.08) {
        rings.push({ r: coreR + 6, alpha: 0.5 * Math.min(1, amp + 0.3) });
      }
      rings = rings.filter((ring) => ring.alpha > 0.01);
      for (const ring of rings) {
        ring.r += 2.4;
        ring.alpha *= 0.955;
        ctx.beginPath();
        ctx.arc(cx, cy, ring.r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(99, 150, 255, ${ring.alpha})`;
        ctx.lineWidth = 1.6;
        ctx.stroke();
      }

      // static orbital guides
      for (const gr of [92, 132, 168]) {
        ctx.beginPath();
        ctx.arc(cx, cy, gr + amp * 10, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(99, 150, 255, 0.07)";
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // rotating arc accents
      for (let i = 0; i < 3; i++) {
        const base = t * 0.004 * speedMul + (i * Math.PI * 2) / 3;
        ctx.beginPath();
        ctx.arc(cx, cy, 110 + i * 26, base, base + 0.9);
        ctx.strokeStyle = `rgba(120, 170, 255, ${0.22 + amp * 0.4})`;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // particles
      for (const p of particles) {
        p.angle += p.speed * speedMul;
        const wob = Math.sin(t * 0.01 + p.wobble) * 6;
        const r = p.radius + wob + amp * 18;
        const x = cx + Math.cos(p.angle) * r;
        const y = cy + Math.sin(p.angle) * r * 0.92;
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(140, 180, 255, ${0.25 + amp * 0.5})`;
        ctx.fill();
      }

      // nucleus glow
      const grad = ctx.createRadialGradient(cx, cy, 4, cx, cy, coreR * 2.2);
      grad.addColorStop(0, `rgba(190, 215, 255, ${0.95})`);
      grad.addColorStop(0.35, `rgba(99, 150, 255, ${0.55 + amp * 0.4})`);
      grad.addColorStop(1, "rgba(99, 150, 255, 0)");
      ctx.beginPath();
      ctx.arc(cx, cy, coreR * 2.2, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(cx, cy, coreR * 0.62, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(235, 244, 255, ${0.85 + amp * 0.15})`;
      ctx.fill();

      // waveform strip while speaking
      if (speaking) {
        const w = size * 0.5;
        ctx.beginPath();
        for (let x = 0; x <= w; x += 4) {
          const y = cy + size * 0.36 +
            Math.sin(x * 0.09 + t * 0.25) * amp * 16 * Math.sin((x / w) * Math.PI);
          x === 0 ? ctx.moveTo(cx - w / 2 + x, y) : ctx.lineTo(cx - w / 2 + x, y);
        }
        ctx.strokeStyle = `rgba(120, 170, 255, ${0.35 + amp * 0.5})`;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [size]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: size, height: size, filter: "drop-shadow(0 0 24px rgba(79,140,255,0.35))" }}
    />
  );
}
