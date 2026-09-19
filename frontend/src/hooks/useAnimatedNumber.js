import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from './useReducedMotion';

// Counts from the previously displayed value to the new one. Re-running on every target
// change means a KPI that shifts because the user changed a filter animates from where it
// was, rather than restarting from zero and implying the figure fell to nothing first.
export function useAnimatedNumber(target, duration = 500) {
  const reduced = useReducedMotion();
  const [value, setValue] = useState(() => (reduced ? target : 0));
  const current = useRef(value);
  const mounted = useRef(false);

  useEffect(() => {
    // First paint counts up from zero; later changes tween from the figure already on screen.
    const from = mounted.current ? current.current : 0;
    mounted.current = true;

    if (reduced) { current.current = target; setValue(target); return; }

    // The clock starts on the first frame that actually runs, not when the effect fired.
    // A frame timestamp can predate `performance.now()` taken moments earlier, which drove
    // progress negative and briefly rendered -1; anchoring here also means a counter whose
    // mount coincides with a busy main thread still animates its full length instead of
    // losing the first few hundred milliseconds to work it was queued behind.
    let start = null;
    let frame = requestAnimationFrame(function tick(now) {
      if (start === null) start = now;
      const progress = Math.min(1, Math.max(0, (now - start) / duration));
      current.current = from + (target - from) * (1 - (1 - progress) ** 3);
      setValue(progress === 1 ? target : current.current);
      if (progress < 1) frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  }, [target, duration, reduced]);

  return value;
}
