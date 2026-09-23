import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Modal from '../common/Modal';
import { useResource } from '../../hooks/useResource';
import { api } from '../../services/api';

function Commands({ onClose }) {
  const [query,setQuery] = useState('');
  const [active,setActive] = useState(0);
  const input = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => { input.current?.focus(); },[]);
  const { data,loading,error } = useResource(query,async signal => {
    const [projects,districts] = await Promise.all([api('/projects?page_size=8&search=' + encodeURIComponent(query.trim()),{signal}),api('/dashboard/district-summary',{signal})]);
    return { projects:projects.items,districts };
  });
  const lower = query.trim().toLowerCase();
  const items = [
    ...[['Dashboard','/dashboard'],['Projects','/projects'],['GIS Map','/map'],['Analytics','/analytics'],['Route analysis','/route-analysis'],['Why LandGuard','/why-landguard']].filter(([label]) => label.toLowerCase().includes(lower)).map(([label,url]) => ({label,url,kind:'Page'})),
    ...(data?.projects || []).map(p => ({label:p.project_id + ' · ' + p.project_name,url:'/projects/' + p.project_id,kind:'Project'})),
    ...(data?.districts || []).filter(d => (d.district + ' ' + d.state).toLowerCase().includes(lower)).slice(0,8).map(d => ({label:d.district + ', ' + d.state,url:'/projects?' + new URLSearchParams({district:d.district,state:d.state}),kind:'District'})),
  ];
  function choose(item) { if (!item) return; navigate(item.url,{state:{returnTo:location.pathname + location.search}}); onClose(); }
  useEffect(() => { setActive(0); },[query,data]);
  function key(event) {
    if (['ArrowDown','ArrowUp','Enter'].includes(event.key)) event.preventDefault();
    if (event.key === 'ArrowDown') setActive(n => items.length ? (n + 1) % items.length : 0);
    if (event.key === 'ArrowUp') setActive(n => items.length ? (n + items.length - 1) % items.length : 0);
    if (event.key === 'Enter') choose(items[active]);
  }
  useEffect(() => { document.getElementById('command-' + active)?.scrollIntoView({block:'nearest'}); },[active]);
  return <><input ref={input} className="command-input" role="combobox" aria-label="Search commands, projects and districts" aria-expanded="true" aria-controls="command-results" aria-activedescendant={items[active] ? 'command-' + active : undefined} autoComplete="off" placeholder="Search projects, districts, or pages…" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={key}/>
    <div role="status" className="command-status">{loading ? 'Searching current records…' : error ? 'Project search unavailable: ' + error : items.length + ' results'}</div>
    <div id="command-results" role="listbox" aria-label="Search results" className="command-results">{items.map((item,i) => <div role="option" aria-selected={active === i} id={'command-' + i} key={item.url} onMouseMove={() => setActive(i)} onMouseDown={e => e.preventDefault()} onClick={() => choose(item)}><small>{item.kind}</small><span>{item.label}</span><span aria-hidden="true">↵</span></div>)}</div>
    <p className="command-help">↑ ↓ to navigate · Enter to open · Esc to close</p></>;
}
export default function CommandPalette({ open,onClose }) {
  return <Modal open={open} onClose={onClose} title="Go to anything" className="command-palette"><Commands onClose={onClose}/></Modal>;
}
