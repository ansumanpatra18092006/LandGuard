import { useCallback, useLayoutEffect, useRef, useState } from 'react';

// Measures the selected tab and publishes its offset and a unitless width scale to CSS, so a
// single underline can slide between tabs instead of one border blinking off and another on.
// Keeping width as a scale factor means the indicator moves on `transform` alone.
//
// The indicator is drawn as a pseudo-element on the tablist, which keeps the ARIA structure
// clean — a tablist should contain tabs and nothing else.
//
// Returns a callback ref, not an object ref: the tablist only mounts once the project record
// has loaded, and a callback ref is what tells us the node finally exists.
export function useTabIndicator(activeKey, baseWidth = 100) {
  const [element, setElement] = useState(null);
  const positioned = useRef(false);

  const measure = useCallback(() => {
    const active = element?.querySelector('[role="tab"][aria-selected="true"]');
    if (!element || !active) return false;
    element.style.setProperty('--tab-x', active.offsetLeft + 'px');
    element.style.setProperty('--tab-scale', active.offsetWidth / baseWidth);
    return true;
  }, [element, baseWidth]);

  useLayoutEffect(() => {
    if (!measure() || positioned.current) return;
    // The first measurement places the indicator; it must not slide in from the left edge on
    // mount, so transitions only switch on once it is already sitting under a tab.
    positioned.current = true;
    const frame = requestAnimationFrame(() => element?.setAttribute('data-ready', 'true'));
    return () => cancelAnimationFrame(frame);
  }, [activeKey, measure, element]);

  useLayoutEffect(() => {
    if (!element || typeof ResizeObserver === 'undefined') return;
    // Labels reflow on resize and when the webfont swaps in; both change the geometry.
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    for (const tab of element.querySelectorAll('[role="tab"]')) observer.observe(tab);
    return () => observer.disconnect();
  }, [element, measure]);

  return setElement;
}
