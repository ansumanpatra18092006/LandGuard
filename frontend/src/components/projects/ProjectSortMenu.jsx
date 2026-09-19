import { ArrowDownWideNarrow, ArrowUpWideNarrow } from 'lucide-react';
import { sortOptions } from '../../utils/projectScope';

export default function ProjectSortMenu({ sortBy, sortDir, onFieldChange, onDirToggle }) {
  return <div className="sort-menu">
    <label className="sr-only" htmlFor="project-sort-field">Sort projects by</label>
    <select id="project-sort-field" value={sortBy} onChange={e => onFieldChange(e.target.value)}>
      {sortOptions.map(o => <option key={o.value} value={o.value}>Sort: {o.label}</option>)}
    </select>
    <button type="button" className="icon-button ghost" onClick={onDirToggle}
      aria-label={sortDir === 'asc' ? 'Sorted ascending. Click to sort descending.' : 'Sorted descending. Click to sort ascending.'}>
      {sortDir === 'asc' ? <ArrowUpWideNarrow size={16}/> : <ArrowDownWideNarrow size={16}/>}
    </button>
  </div>;
}

