import { useCallback, useEffect, useRef } from 'react';
import { useReducedMotion } from './useReducedMotion';

// Subtle pointer-following tilt, meant to run alongside useSpotlight on the same card so
// the highlight and the tilt read as one effect rather than two competing ones. Rotation
// is capped small on purpose — a few degrees reads as polish, more reads as a toy.
//
// Same narrow gating as useSpotlight: fine pointers only, nothing under reduced motion,
// writes batched to one animation frame.
export function useTilt(max = 6) {
  const node = useRef(null);
  const frame = useRef(0);
  const reduced = useReducedMotion();

  const enabled = !reduced && typeof window !== 'undefined'
    && window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  const write = useCallback((x, y) => {
    frame.current = 0;
    const element = node.current;
    if (!element) return;
    element.style.setProperty('--tilt-x', (y * -max).toFixed(2) + 'deg');
    element.style.setProperty('--tilt-y', (x * max).toFixed(2) + 'deg');
  }, [max]);

  const onPointerMove = useCallback(event => {
    if (!enabled || !node.current) return;
    const rect = node.current.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const x = ((event.clientX - rect.left) / rect.width) - 0.5;
    const y = ((event.clientY - rect.top) / rect.height) - 0.5;
    if (!frame.current) frame.current = requestAnimationFrame(() => write(x, y));
  }, [enabled, write]);

  // Settle back to flat on exit rather than freezing at the last tilt angle.
  const onPointerLeave = useCallback(() => {
    if (!enabled) return;
    cancelAnimationFrame(frame.current);
    frame.current = 0;
    node.current?.style.setProperty('--tilt-x', '0deg');
    node.current?.style.setProperty('--tilt-y', '0deg');
  }, [enabled]);

  if (!enabled) return { ref: node };
  return { ref: node, onPointerMove, onPointerLeave, 'data-tilt': 'on' };
}
