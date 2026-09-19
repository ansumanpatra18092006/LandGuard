import { useCallback, useEffect, useRef, useState } from 'react';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import { useReveal } from '../../hooks/useReveal';

const steps = ['Predict', 'Explain', 'Recommend', 'Alert', 'Intervene'];
const RUN_MS = steps.length * 110 + 620;

// The decision-support chain, animated once: the signal passes from stage to stage, drawing
// each connector as it goes, then stops. Pointing at the strip replays it — which is the
// whole point of putting it here, since the sequence *is* the explanation of the product.
export default function ProcessStrip() {
  const reduced = useReducedMotion();
  const [revealRef, revealed] = useReveal({ threshold: 0.35 });
  const [run, setRun] = useState(0);
  const playing = useRef(false);
  const timer = useRef(0);

  useEffect(() => () => clearTimeout(timer.current), []);

  const replay = useCallback(() => {
    if (reduced || playing.current) return;
    playing.current = true;
    setRun(n => n + 1);
    timer.current = setTimeout(() => { playing.current = false; }, RUN_MS);
  }, [reduced]);

  const animate = !reduced && revealed;

  return <div className="process-strip" ref={revealRef} data-animate={animate} onPointerEnter={replay}>
    <span className="process-caption">DECISION-SUPPORT VISION</span>
    {/* Remounting on replay restarts the staggered keyframes without a second code path. */}
    <ol className="process-track" key={run} aria-label="Decision support stages">
      {steps.map((step, index) => <li key={step} style={{ '--step': index }}>
        <span className="process-node" aria-hidden="true"><i/></span>
        <span className="process-label">{step}</span>
      </li>)}
    </ol>
    <span className="process-state">Operational analytics available · ML not connected</span>
  </div>;
}
