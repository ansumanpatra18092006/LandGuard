import { useCallback, useRef, useState } from 'react';

const supported = typeof IntersectionObserver !== 'undefined';

// Reveals an element once, the first time it scrolls into view.
//
// The hidden state lives in CSS behind `prefers-reduced-motion: no-preference`, so this hook
// only ever *adds* a class. If the observer never fires — reduced motion, an old browser, a
// print stylesheet — the element is already visible and nothing is lost.
export function useReveal({ margin = '0px 0px -8% 0px', threshold = 0.1 } = {}) {
  const [revealed, setRevealed] = useState(!supported);
  const observer = useRef(null);

  const ref = useCallback(node => {
    observer.current?.disconnect();
    if (!node || !supported) return;
    // Already on screen at mount (above the fold): reveal on the next frame so the
    // entrance keyframes have a chance to run rather than being skipped.
    observer.current = new IntersectionObserver(entries => {
      if (!entries.some(entry => entry.isIntersecting)) return;
      setRevealed(true);
      observer.current?.disconnect();
    }, { rootMargin: margin, threshold });
    observer.current.observe(node);
  }, [margin, threshold]);

  return [ref, revealed];
}

// Convenience for the common case: returns the props an element needs to reveal itself.
export function useRevealProps(className = '') {
  const [ref, revealed] = useReveal();
  return { ref, className: [className, 'reveal', revealed ? 'is-revealed' : ''].filter(Boolean).join(' ') };
}
