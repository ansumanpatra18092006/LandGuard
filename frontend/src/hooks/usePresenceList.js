import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from './useReducedMotion';

// React unmounts a removed item immediately, which leaves no frame in which to animate it
// out. This keeps departed entries in the rendered list, flagged `exiting`, until their
// animation has had time to finish — then drops them for real.
//
// Exiting entries hold their previous index so a chip collapses where it stood instead of
// jumping to the end of the row on its way out.
//
// Callers almost always pass a freshly built array, so the effect runs off a signature of
// the keys rather than array identity; otherwise every render would queue another pass.
export function usePresenceList(items, getKey, duration = 160) {
  const reduced = useReducedMotion();
  const latest = useRef({ items, getKey });
  latest.current = { items, getKey };

  const [rendered, setRendered] = useState(() => items.map(item => ({ key: getKey(item), item, exiting: false })));
  const timers = useRef(new Map());
  const signature = items.map(getKey).join('\u0000');

  useEffect(() => () => { timers.current.forEach(clearTimeout); timers.current.clear(); }, []);

  useEffect(() => {
    const { items: current, getKey: key } = latest.current;
    const incoming = current.map(item => ({ key: key(item), item, exiting: false }));

    // An item that returned before its exit finished should stop exiting.
    for (const entry of incoming) {
      const timer = timers.current.get(entry.key);
      if (timer) { clearTimeout(timer); timers.current.delete(entry.key); }
    }

    if (reduced || !duration) { setRendered(incoming); return; }

    setRendered(previous => {
      const liveKeys = new Set(incoming.map(entry => entry.key));
      const next = [...incoming];
      previous.forEach((entry, index) => {
        if (liveKeys.has(entry.key)) return;
        if (!entry.exiting) {
          timers.current.set(entry.key, setTimeout(() => {
            timers.current.delete(entry.key);
            setRendered(list => list.filter(candidate => candidate.key !== entry.key));
          }, duration));
        } else if (!timers.current.has(entry.key)) return;
        next.splice(Math.min(index, next.length), 0, { ...entry, exiting: true });
      });
      return next;
    });
  }, [signature, duration, reduced]);

  return rendered;
}
