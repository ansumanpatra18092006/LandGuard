import { ArrowDown, ArrowRight, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useReducedMotion } from '../../hooks/useReducedMotion';
export default function ScopeDock({count,filters,onClear,projectUrl}) {
  const reduced = useReducedMotion();
  const active = Object.values(filters).filter(value=>value.trim()).length;
  if (!active) return null;
  function jump() {
    const results = document.getElementById('project-monitor');
    results?.scrollIntoView({behavior:reduced ? 'instant' : 'smooth',block:'start'});
    results?.focus({preventScroll:true});
  }
  return <aside className="scope-dock" aria-label="Current selection"><span><strong>{count == null ? 'Updating selection…' : count+' matching projects'}</strong><small>{active} active filter{active===1?'':'s'}</small></span><div>{projectUrl ? <Link className="button primary" to={projectUrl}>Open records <ArrowRight size={14}/></Link> : <button className="primary" onClick={jump}>View results <ArrowDown size={14}/></button>}<button className="ghost" onClick={onClear} aria-label="Clear current selection"><X size={16}/></button></div></aside>;
}
