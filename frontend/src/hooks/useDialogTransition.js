import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from './useReducedMotion';

// A native <dialog> disappears the instant close() is called, so an overlay that animates
// in will always vanish on the way out. This holds the element open for the length of the
// exit animation, exposing a phase the caller can style against.
//
// Phases: 'closed' (not rendered), 'open', 'closing' (still in the DOM, animating out).
export function useDialogTransition(open, duration = 280) {
  const ref = useRef(null);
  const reduced = useReducedMotion();
  const [phase, setPhase] = useState(open ? 'open' : 'closed');
  const restore = useRef({ focus: null, overflow: '' });

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;

    if (open) {
      if (!dialog.open) {
        restore.current = { focus: document.activeElement, overflow: document.body.style.overflow };
        dialog.showModal();
        document.body.style.overflow = 'hidden';
      }
      setPhase('open');
      return;
    }

    if (!dialog.open) { setPhase('closed'); return; }

    setPhase('closing');
    const finish = () => {
      setPhase('closed');
      if (ref.current?.open) ref.current.close();
      document.body.style.overflow = restore.current.overflow;
      const previous = restore.current.focus;
      if (previous?.isConnected) previous.focus();
    };
    const timer = setTimeout(finish, reduced ? 0 : duration);
    return () => clearTimeout(timer);
  }, [open, duration, reduced]);

  // A dialog torn down mid-animation must not leave the page scroll-locked.
  useEffect(() => () => { document.body.style.overflow = restore.current.overflow; }, []);

  return { ref, phase };
}
