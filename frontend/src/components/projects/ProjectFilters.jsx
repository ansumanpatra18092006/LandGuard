import { useEffect, useId, useRef, useState } from 'react';
import { Search, SlidersHorizontal, X } from 'lucide-react';
import { pretty } from '../common';
import { indicatorLabels } from '../../utils/projectScope';
import Modal from '../common/Modal';
import ProjectSortMenu from './ProjectSortMenu';
import FilterChips from './FilterChips';

export default function ProjectFilters({ filters, onChange, onClear, sortBy, sortDir, onSortField, onSortDirToggle }) {
  const [open,setOpen] = useState(false);
  const searchRef = useRef(null);
  useEffect(() => {
    function shortcut(event) {
      if (event.key !== '/' || event.target.closest('input,select,textarea,[contenteditable]')) return;
      event.preventDefault();
      searchRef.current?.focus();
    }
    window.addEventListener('keydown',shortcut);
    return () => window.removeEventListener('keydown',shortcut);
  },[]);
  const [mobile,setMobile] = useState(() => window.matchMedia('(max-width: 600px)').matches);
  const id = useId();
  useEffect(() => {
    const media = window.matchMedia('(max-width: 600px)');
    const change = () => { setMobile(media.matches); setOpen(false); };
    media.addEventListener('change',change);
    return () => media.removeEventListener('change',change);
  },[]);
  const active = Object.entries(filters).filter(([,value]) => value.trim());
  const labels = { state:'State',district:'District',project_type:'Type',acquisition_stage:'Stage',search:'Search',indicator:'Indicator' };
  const fields = <div className="filter-fields" id={id}>
    <label>State<input aria-label="State filter" placeholder="Exact state name" value={filters.state} onChange={e => onChange('state',e.target.value)}/></label>
    <label>District<input aria-label="District filter" placeholder="Exact district name" value={filters.district} onChange={e => onChange('district',e.target.value)}/></label>
    <label>Project type<select aria-label="Project type" value={filters.project_type} onChange={e => onChange('project_type',e.target.value)}><option value="">All types</option>{['ROAD','RAILWAY','IRRIGATION','INDUSTRIAL','URBAN'].map(x => <option key={x} value={x}>{pretty(x)}</option>)}</select></label>
    <label>Acquisition stage<select aria-label="Acquisition stage" value={filters.acquisition_stage} onChange={e => onChange('acquisition_stage',e.target.value)}><option value="">All stages</option>{['NOTIFICATION','SURVEY','VALUATION','COMPENSATION','REHABILITATION','POSSESSION','COMPLETED'].map(x => <option key={x} value={x}>{pretty(x)}</option>)}</select></label>
    <label>Operational indicator<select aria-label="Operational indicator" value={filters.indicator} onChange={e => onChange('indicator',e.target.value)}><option value="">All indicators</option>{Object.entries(indicatorLabels).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label>
  </div>;
  return <div className="filters" id="project-filters">
    <label className="search"><Search size={17}/><input ref={searchRef} aria-label="Search projects" placeholder="Search projects by name or ID…" value={filters.search} onChange={e => onChange('search',e.target.value)}/>{filters.search ? <button type="button" className="search-clear" aria-label="Clear search" onClick={() => onChange('search','')}><X size={13}/></button> : <kbd className="search-kbd" aria-hidden="true">/</kbd>}</label>
    <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}><SlidersHorizontal size={16}/> Filters {active.length > 0 && <span className="filter-count">{active.length}</span>}</button>
    {onSortField && <ProjectSortMenu sortBy={sortBy} sortDir={sortDir} onFieldChange={onSortField} onDirToggle={onSortDirToggle}/>}
    {active.length > 0 && <button className="ghost" onClick={onClear}><X size={14}/> Clear filters</button>}
    {open && !mobile && fields}
    {mobile && <Modal open={open} onClose={() => setOpen(false)} title="Project filters" className="filter-sheet">{fields}<p className="muted">Filters update the results immediately.</p><button className="primary" onClick={() => setOpen(false)}>Show results</button></Modal>}
    <FilterChips active={active} labels={labels} onRemove={key => onChange(key,'')} describe={(key,value) => key === 'indicator' ? indicatorLabels[value] || value : value}/>
  </div>;
}
