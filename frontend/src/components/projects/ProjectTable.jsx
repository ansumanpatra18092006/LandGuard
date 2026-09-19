import { Link } from 'react-router-dom';
import { ArrowUp, ArrowUpDown, ArrowDown, ArrowUpRight } from 'lucide-react';
import { pretty, Progress } from '../common';
import ProjectActions from './ProjectActions';

const columns = [
  ['project_id','Project ID'],['project_name','Project name'],['district','District'],['project_type','Type'],
  ['acquisition_stage','Acquisition stage'],['compensation_completion_pct','Compensation'],['possession_pct','Possession'],
  ['pending_approvals','Approvals'],['legal_disputes','Disputes'],
];

export default function ProjectTable({ projects, onInspect, selectedId, returnTo, sortBy, sortDir, onSort }) {
  // Re-keying on the visible set remounts the rows, which is what restarts the staggered
  // entrance when the page, sort or filter changes. Reordering alone would not.
  const scopeKey = projects.map(p => p.id).join(',');
  function rowKey(event,project) {
    if (event.target !== event.currentTarget) return;
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onInspect(project); }
  }
  return <>
    <div className="table-wrap project-table-wrap" tabIndex={0} aria-label="Project records; scroll horizontally for all columns"><table className="project-table"><caption className="sr-only">Project acquisition records. Select a row to open quick view.</caption>
      <thead><tr>{columns.map(([key,label]) => {
        const active = sortBy === key;
        const Icon = active ? (sortDir === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown;
        return <th scope="col" key={key} aria-sort={active ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}>
          <button type="button" className={'sort-header' + (active ? ' active-sort' : '')} onClick={() => onSort(key)}>{label}<Icon size={11} className="sort-indicator"/></button>
        </th>;
      })}<th scope="col"><span className="sr-only">Action</span></th></tr></thead>
      <tbody key={scopeKey}>{projects.map((p, index) => <tr key={p.id} style={{ '--index': index }} tabIndex={0} className={'interactive-row' + (selectedId === p.id ? ' selected-row' : '')} aria-label={'Inspect ' + p.project_id} onKeyDown={e => rowKey(e,p)} onClick={e => { if (!e.target.closest('a,button,summary,details')) onInspect(p); }}>
        <td className="id-text">{p.project_id}</td><td className="project-name"><Link className="project-link" to={'/projects/' + p.project_id} state={{ returnTo }}>{p.project_name}</Link><small>{pretty(p.data_source)} record</small></td><td>{p.district}<small>{p.state}</small></td><td>{pretty(p.project_type)}</td><td><span className="badge">{pretty(p.acquisition_stage)}</span></td>
        <td><Progress compact value={p.compensation_completion_pct} label={p.project_id + ' compensation'}/></td><td><Progress compact value={p.possession_pct} label={p.project_id + ' possession'}/></td><td><span className="count-badge" title="Pending approvals">{p.pending_approvals}</span></td><td><span className="count-badge" title="Legal disputes">{p.legal_disputes}</span></td>
        <td><div className="row-action-group"><button className="view-link ghost" onClick={() => onInspect(p)} aria-label={'Quick view ' + p.project_id}>Quick view</button><ProjectActions project={p} returnTo={returnTo} onInspect={onInspect}/></div></td>
      </tr>)}</tbody>
    </table></div>
    <div className="project-cards" key={scopeKey}>{projects.map((p, index) => <article key={p.id} style={{ '--index': index }} tabIndex={0} aria-label={'Inspect ' + p.project_id} className={'project-mobile-card interactive-row' + (selectedId === p.id ? ' selected-row' : '')} onKeyDown={e => rowKey(e,p)} onClick={e => { if (!e.target.closest('a,button,summary,details')) onInspect(p); }}><div className="mobile-project-meta"><span className="id-text">{p.project_id}</span><span className="badge">{pretty(p.acquisition_stage)}</span></div><Link className="project-link" to={'/projects/' + p.project_id} state={{ returnTo }}>{p.project_name}</Link><p>{p.district}, {p.state} · {pretty(p.project_type)}<br/>{pretty(p.data_source)} record</p><div className="mobile-progress"><Progress label="Compensation" value={p.compensation_completion_pct}/><Progress label="Possession" value={p.possession_pct}/></div><div className="mobile-project-actions"><div><span>{p.pending_approvals} pending approvals</span><span>{p.legal_disputes} legal disputes</span></div><button className="view-link ghost" onClick={() => onInspect(p)} aria-label={'Quick view ' + p.project_id}>Quick view <ArrowUpRight size={14}/></button><ProjectActions project={p} returnTo={returnTo} onInspect={onInspect}/></div></article>)}</div>
  </>;
}
