import { useEffect, useRef } from "react";

const GLYPHS = "アカサタナハマヤラワ0123456789ABCDEFXZ$#@%&*+=<>";

/** Classic falling-glyph background, tinted by the active theme. */
export function MatrixRain() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current!;
    const ctx = canvas.getContext("2d")!;
    let raf = 0;
    let cols: number[] = [];
    const fontSize = 15;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      cols = Array(Math.ceil(canvas.width / fontSize)).fill(0)
        .map(() => Math.floor(Math.random() * -60));
    };
    resize();
    window.addEventListener("resize", resize);

    let frame = 0;
    const draw = () => {
      frame++;
      if (frame % 3 === 0) {  // slow the fall to a calm ambient pace
        const styles = getComputedStyle(document.documentElement);
        const rgb = styles.getPropertyValue("--core-rgb").trim() || "0, 255, 102";
        const bg = styles.getPropertyValue("--bg").trim() || "#010804";
        ctx.fillStyle = bg;
        ctx.globalAlpha = 0.16;               // fade trail
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.globalAlpha = 1;
        ctx.font = `${fontSize}px monospace`;
        for (let i = 0; i < cols.length; i++) {
          const char = GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
          const y = cols[i] * fontSize;
          if (y > 0) {
            // bright head glyph with a dimmer trail behind it
            ctx.fillStyle = `rgba(${rgb}, 0.85)`;
            ctx.fillText(char, i * fontSize, y);
            ctx.fillStyle = `rgba(${rgb}, 0.35)`;
            ctx.fillText(GLYPHS[(i + frame) % GLYPHS.length], i * fontSize, y - fontSize);
          }
          if (y > canvas.height && Math.random() > 0.975) cols[i] = 0;
          else cols[i]++;
        }
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
