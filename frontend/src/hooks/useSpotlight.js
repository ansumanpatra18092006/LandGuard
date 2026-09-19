import { useCallback, useEffect, useRef } from 'react';
import { useReducedMotion } from './useReducedMotion';

// Tracks the pointer across an element and publishes its position as CSS custom
// properties, so the highlight itself is drawn entirely in CSS.
//
// Deliberately narrow: fine pointers only (no phantom highlight left behind by a tap),
// and nothing at all under reduced motion. Writes are batched into one animation frame,
// so a fast pointer sweep costs at most one style write per frame.
export function useSpotlight() {
  const node = useRef(null);
  const frame = useRef(0);
  const point = useRef({ x: 0, y: 0 });
  const reduced = useReducedMotion();

  const enabled = !reduced && typeof window !== 'undefined'
    && window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  const write = useCallback(() => {
    frame.current = 0;
    const element = node.current;
    if (!element) return;
    element.style.setProperty('--spot-x', point.current.x + '%');
    element.style.setProperty('--spot-y', point.current.y + '%');
  }, []);

  const onPointerMove = useCallback(event => {
    if (!enabled || !node.current) return;
    const rect = node.current.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    point.current = {
      x: Math.round(((event.clientX - rect.left) / rect.width) * 100),
      y: Math.round(((event.clientY - rect.top) / rect.height) * 100),
    };
    if (!frame.current) frame.current = requestAnimationFrame(write);
  }, [enabled, write]);

  // Reset to centre on exit so the next hover fades up from the middle rather than
  // snapping back to wherever the pointer last left the card.
  const onPointerLeave = useCallback(() => {
    if (!enabled) return;
    cancelAnimationFrame(frame.current);
    frame.current = 0;
    node.current?.style.setProperty('--spot-x', '50%');
    node.current?.style.setProperty('--spot-y', '50%');
  }, [enabled]);

  if (!enabled) return { ref: node };
  return { ref: node, onPointerMove, onPointerLeave, 'data-spotlight': 'on' };
}
