import { useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { MoreHorizontal, Copy, Pencil, ArrowUpRight, MapPin, PanelRightOpen } from 'lucide-react';

export default function ProjectActions({ project, returnTo, onInspect }) {
  const menu = useRef(null);
  const trigger = useRef(null);
  const id = useId();
  function toggle() {
    const rect = trigger.current.getBoundingClientRect();
    menu.current.style.left = Math.max(8,Math.min(rect.right - 218,window.innerWidth - 226)) + 'px';
    menu.current.style.top = (rect.bottom + 270 < window.innerHeight ? rect.bottom + 5 : Math.max(8,rect.top - 265)) + 'px';
    menu.current.togglePopover();
  }
  const [status,setStatus] = useState('');
  async function copy() {
    try { await navigator.clipboard.writeText(project.project_id); setStatus('Project ID copied'); }
    catch { setStatus('Copy unavailable. Project ID: ' + project.project_id); }
  }
  return <span className="row-menu" onClick={e => e.stopPropagation()}>
    <button ref={trigger} className="icon-button ghost" aria-label={'Actions for ' + project.project_id} aria-controls={id} onClick={toggle}><MoreHorizontal size={18}/></button>
    <div id={id} ref={menu} popover="auto" className="row-menu-panel" onKeyDown={e => { if (e.key === 'Escape') { menu.current.hidePopover(); trigger.current.focus(); } }}>
      <button onClick={() => { menu.current.hidePopover(); onInspect(project); }}><PanelRightOpen size={14}/> Quick view</button>
      <Link to={'/projects/' + project.project_id} state={{ returnTo }}><ArrowUpRight size={14}/> View details</Link>
      <Link to={'/projects/' + project.project_id + '/edit'} state={{ returnTo }}><Pencil size={14}/> Edit project</Link>
      <Link to={'/projects/' + project.project_id + '?tab=gis'} state={{ returnTo }}><MapPin size={14}/> Locate on map</Link>
      <button onClick={copy}><Copy size={14}/> Copy project ID</button>
      <span role="status">{status}</span>
    </div>
  </span>;
}
