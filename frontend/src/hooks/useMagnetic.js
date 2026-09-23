import { useCallback, useEffect, useRef } from 'react';
import { useReducedMotion } from './useReducedMotion';

// Nudges an element a few pixels toward the pointer while it's within range, then eases
// back on release — the "magnetic button" pattern. Deliberately reserved for a single
// primary call-to-action; sprinkled across every button it stops reading as attentive and
// starts reading as jitter.
//
// Fine pointers only, inert under reduced motion, writes batched to one animation frame —
// same gating discipline as useSpotlight and useTilt.
export function useMagnetic(strength = 0.3, max = 12) {
  const node = useRef(null);
  const frame = useRef(0);
  const reduced = useReducedMotion();

  const enabled = !reduced && typeof window !== 'undefined'
    && window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  const write = useCallback((x, y) => {
    frame.current = 0;
    node.current?.style.setProperty('--magnet-x', x.toFixed(1) + 'px');
    node.current?.style.setProperty('--magnet-y', y.toFixed(1) + 'px');
  }, []);

  const onPointerMove = useCallback(event => {
    if (!enabled || !node.current) return;
    const rect = node.current.getBoundingClientRect();
    const x = clamp((event.clientX - (rect.left + rect.width / 2)) * strength, max);
    const y = clamp((event.clientY - (rect.top + rect.height / 2)) * strength, max);
    if (!frame.current) frame.current = requestAnimationFrame(() => write(x, y));
  }, [enabled, strength, max, write]);

  const onPointerLeave = useCallback(() => {
    if (!enabled) return;
    cancelAnimationFrame(frame.current);
    frame.current = 0;
    node.current?.style.setProperty('--magnet-x', '0px');
    node.current?.style.setProperty('--magnet-y', '0px');
  }, [enabled]);

  if (!enabled) return { ref: node };
  return { ref: node, onPointerMove, onPointerLeave, 'data-magnetic': 'on' };
}

function clamp(value, max) { return Math.max(-max, Math.min(max, value)); }
