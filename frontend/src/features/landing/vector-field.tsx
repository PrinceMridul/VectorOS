"use client";

import * as React from "react";

/**
 * The landing background: a gradient descent field.
 *
 * Particles are released at the edges of a loss surface and follow its negative
 * gradient toward a basin, leaving fading trails. It is the literal subject of
 * the product's first curriculum, rendered as the thing you are looking at — not
 * an abstract "AI particle mesh" that would work equally well on a crypto site.
 *
 * Costs are kept honest: one canvas, capped particle count, device-pixel-ratio
 * clamped to 2, and the loop stops entirely when the tab is hidden or the user
 * has asked for reduced motion.
 */
export function VectorField({ className }: { className?: string }) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0;
    let height = 0;
    let frame = 0;
    let running = true;

    const COUNT = 90;
    type P = { x: number; y: number; vx: number; vy: number; life: number; max: number };
    const particles: P[] = [];

    /** Two basins and a saddle — the surface actually described in the course. */
    const gradient = (x: number, y: number) => {
      const nx = (x / width) * 4 - 2;
      const ny = (y / height) * 2.4 - 1.2;
      // f = (nx² − 1)² + ny²·(1 + 0.35·nx)
      const gx = 4 * nx * (nx * nx - 1) + 0.35 * ny * ny;
      const gy = 2 * ny * (1 + 0.35 * nx);
      return { gx, gy };
    };

    const spawn = (p: P) => {
      p.x = Math.random() * width;
      p.y = Math.random() * height;
      p.vx = 0;
      p.vy = 0;
      p.max = 220 + Math.random() * 320;
      p.life = Math.random() * p.max;
    };

    for (let i = 0; i < COUNT; i += 1) {
      const p: P = { x: 0, y: 0, vx: 0, vy: 0, life: 0, max: 0 };
      spawn(p);
      particles.push(p);
    }

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = () => {
      // Trails: paint the background at low alpha instead of clearing.
      ctx.fillStyle = "rgba(8, 8, 10, 0.09)";
      ctx.fillRect(0, 0, width, height);

      for (const p of particles) {
        const { gx, gy } = gradient(p.x, p.y);

        // Descent step with momentum. The learning rate is small on purpose:
        // the trails should look like careful convergence, not a scatter.
        p.vx = p.vx * 0.94 - gx * 0.22;
        p.vy = p.vy * 0.94 - gy * 0.22;

        const px = p.x;
        const py = p.y;
        p.x += p.vx;
        p.y += p.vy;
        p.life += 1;

        const speed = Math.hypot(p.vx, p.vy);
        const fade = 1 - p.life / p.max;
        const alpha = Math.max(0, Math.min(0.5, speed * 0.08)) * fade;

        ctx.strokeStyle = `rgba(124, 124, 255, ${alpha})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(p.x, p.y);
        ctx.stroke();

        if (
          p.life > p.max ||
          p.x < -20 ||
          p.x > width + 20 ||
          p.y < -20 ||
          p.y > height + 20 ||
          speed < 0.02
        ) {
          spawn(p);
        }
      }

      if (running) frame = requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);

    const onVisibility = () => {
      if (document.hidden) {
        running = false;
        cancelAnimationFrame(frame);
      } else if (!reduced) {
        running = true;
        frame = requestAnimationFrame(draw);
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    if (reduced) {
      // Render a handful of frames so the surface is visible, then stop.
      running = false;
      for (let i = 0; i < 140; i += 1) draw();
    } else {
      frame = requestAnimationFrame(draw);
    }

    return () => {
      running = false;
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden />;
}
