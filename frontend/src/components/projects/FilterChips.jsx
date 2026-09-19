import { useCallback, useRef } from 'react';
import { X } from 'lucide-react';
import { usePresenceList } from '../../hooks/usePresenceList';

const EXIT_MS = 160;

// Active filters, each of which can be dismissed. A removed chip collapses the width it was
// holding so the rest of the row slides across instead of jumping — which means the chip's
// width has to be measured while it is still on screen, before React takes it away.
export default function FilterChips({ active, labels, describe, onRemove }) {
  const widths = useRef(new Map());
  const entries = usePresenceList(active, entry => entry[0], EXIT_MS);

  const measure = useCallback((key, node) => {
    if (node) widths.current.set(key, node.getBoundingClientRect().width);
  }, []);

  if (!entries.length) return null;

  return <div className="filter-chips" aria-label="Active filters">
    <span className="filter-summary">Filtering by:</span>
    {entries.map(({ key, item: [filterKey, value], exiting }) => <button
      key={key}
      ref={node => measure(key, node)}
      className={'chip' + (exiting ? ' is-exiting' : '')}
      style={exiting ? { '--chip-w': (widths.current.get(key) || 220) + 'px' } : undefined}
      // An exiting chip is only still here to finish its animation; it must not be tabbable.
      tabIndex={exiting ? -1 : undefined}
      aria-hidden={exiting || undefined}
      onClick={() => onRemove(filterKey)}
      aria-label={'Remove ' + labels[filterKey] + ' filter'}
    >{labels[filterKey]}: {describe(filterKey, value)}<X size={12}/></button>)}
  </div>;
}
