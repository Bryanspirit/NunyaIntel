// Motion primitives for the broadcast-style UI (branch ui-broadcast).
//
// - useCountUp / <CountUp>: a number rolls up from 0 to its value (ease-out), like a TV stat.
// - <Reveal>: a block slides/fades in after `delay` ms, so panels arrive one after another.
//
// Accessibility: if the viewer's system asks for reduced motion (prefers-reduced-motion), numbers
// show their final value immediately and nothing slides. Never animate for its own sake.

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

export function useReducedMotion(): boolean {
  const query = "(prefers-reduced-motion: reduce)";
  const [reduced, setReduced] = useState(() => window.matchMedia?.(query).matches ?? false);
  useEffect(() => {
    const mq = window.matchMedia?.(query);
    if (!mq) return;
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/** easeOutCubic: fast at first, gently settling, the way broadcast numbers move. */
const easeOut = (t: number) => 1 - (1 - t) ** 3;

/** Animate from 0 to `target` over `duration` ms after `delay` ms. Restarts if target changes. */
export function useCountUp(target: number, duration = 900, delay = 0): number {
  const reduced = useReducedMotion();
  const [value, setValue] = useState(reduced ? target : 0);
  const frame = useRef(0);

  useEffect(() => {
    if (reduced) {
      setValue(target);
      return;
    }
    let start: number | null = null;
    const timer = window.setTimeout(() => {
      const step = (now: number) => {
        start ??= now;
        const t = Math.min(1, (now - start) / duration);
        setValue(target * easeOut(t));
        if (t < 1) frame.current = requestAnimationFrame(step);
      };
      frame.current = requestAnimationFrame(step);
    }, delay);
    return () => {
      window.clearTimeout(timer);
      cancelAnimationFrame(frame.current);
    };
  }, [target, duration, delay, reduced]);

  return value;
}

/** A number that counts up. `format` turns the in-between value into text. */
export function CountUp({
  value,
  format = (v) => v.toFixed(0),
  duration,
  delay,
}: {
  value: number;
  format?: (v: number) => string;
  duration?: number;
  delay?: number;
}) {
  const current = useCountUp(value, duration, delay);
  return <span className="countup">{format(current)}</span>;
}

/** Slide/fade a block in after `delay` ms (pure CSS; disabled for reduced motion in the CSS). */
export function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "article" | "section";
}) {
  const style = { "--delay": `${delay}ms` } as CSSProperties;
  return (
    <Tag className={`reveal ${className}`} style={style}>
      {children}
    </Tag>
  );
}
