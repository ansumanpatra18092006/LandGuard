import { useState } from 'react';
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Pencil, MapPin, ClipboardList, Scale, Clock3, Hourglass, Map } from 'lucide-react';
import { api } from '../services/api';
import { ErrorState, Loading, pretty, Progress, PageHeader, SectionCard } from '../components/common';
import { useResource } from '../hooks/useResource';
import { useTabIndicator } from '../hooks/useTabIndicator';
import { safeReturnTo, scopeLabel } from '../utils/projectScope';
import IntelligencePanel from '../components/projects/IntelligencePanel';
import ProjectDigitalTwin from '../components/projects/ProjectDigitalTwin';
import InterventionLedger from '../components/projects/InterventionLedger';

export default function ProjectDetails() {
  const { projectId } = useParams();
  const location = useLocation();
  const [params,setParams] = useSearchParams();
  const [retry,setRetry] = useState(0);
  const { data:project,error } = useResource(projectId,signal => api('/projects/' + projectId,{ signal }),retry);
  const returnTo = safeReturnTo(location.state?.returnTo);
  const tabs = [['overview','Overview'],['progress','Acquisition Progress'],['issues','Administrative Issues'],['twin','Process Twin'],['ai','AI Intelligence'],['interventions','Interventions'],['gis','GIS'],['history','History']];
  const tab = tabs.some(([id]) => id === params.get('tab')) ? params.get('tab') : 'overview';
  function selectTab(id) {
    const next = new URLSearchParams(params);
    if (id === 'overview') next.delete('tab'); else next.set('tab',id);
    setParams(next,{ replace:true,state:location.state });
  }
  function tabKey(event,index) {
    const directions = { ArrowRight:(index + 1) % tabs.length,ArrowLeft:(index + tabs.length - 1) % tabs.length,Home:0,End:tabs.length - 1 };
    if (directions[event.key] === undefined) return;
    event.preventDefault();
    const next = directions[event.key];
    selectTab(tabs[next][0]);
    event.currentTarget.parentElement.querySelectorAll('[role="tab"]')[next].focus();
  }
  const tabList = useTabIndicator(tab);
  if (error) return <ErrorState message={error} retry={() => setRetry(n => n + 1)}/>;
  if (!project) return <Loading variant="detail"/>;
  const p = project;
  return <>
    <div className="context-breadcrumb"><Link className="back" to={returnTo}><ArrowLeft size={15}/> Back to results</Link>{scopeLabel(returnTo) && <span>{scopeLabel(returnTo)} / {p.project_id}</span>}</div>
    <PageHeader eyebrow="PROJECT COMMAND CENTER" title={p.project_name} description={p.district + ', ' + p.state} action={<Link className="button primary" to={'/projects/' + projectId + '/edit'} state={{ returnTo }}><Pencil size={15}/> Edit project</Link>}>
      <div className="meta-chips"><span className="badge neutral">{p.project_id}</span><span className="badge neutral">{pretty(p.project_type)}</span><span className="badge neutral">{p.state}</span><span className="badge neutral">{p.district}</span><span className="badge">{pretty(p.acquisition_stage)}</span><span className="badge neutral">{pretty(p.data_source)} data</span></div>
    </PageHeader>
    <div className="detail-tabs" ref={tabList} role="tablist" aria-label="Project sections">{tabs.map(([id,label],index) => <button key={id} id={'tab-' + id} role="tab" aria-selected={tab === id} aria-controls={'panel-' + id} tabIndex={tab === id ? 0 : -1} onClick={() => selectTab(id)} onKeyDown={event => tabKey(event,index)}>{label}</button>)}</div>
    <div role="tabpanel" id={'panel-' + tab} aria-labelledby={'tab-' + tab} tabIndex={0} key={tab} className="content-enter">
    {tab === 'overview' && <section className="panel overview-grid" aria-label="Project overview">
      <div><span>Land area</span><strong>{p.land_area.toLocaleString()} <small>hectares</small></strong></div>
      <div><span>Affected families</span><strong>{p.affected_families.toLocaleString()}</strong><small>Recorded project total</small></div>
      <div><span>Elapsed acquisition</span><strong>{p.elapsed_acquisition_days} <small>days</small></strong></div>
      <div><span>Project location</span><strong>{p.district}</strong><small>{p.state}</small></div>
      <div><span>Original approved cost</span><strong>{p.original_cost_crore != null ? `₹${p.original_cost_crore.toLocaleString()} cr` : 'Not recorded'}</strong><small>PAIMANA-baseline input</small></div>
      <div><span>Cumulative expenditure</span><strong>{p.expenditure_crore != null ? `₹${p.expenditure_crore.toLocaleString()} cr` : 'Not recorded'}</strong><small>PAIMANA-baseline input</small></div>
      <div><span>Original completion date</span><strong>{p.original_end_date ? new Date(`${p.original_end_date}T00:00:00`).toLocaleDateString() : 'Not recorded'}</strong><small>PAIMANA-baseline input</small></div>
    </section>}
    <div className="detail-grid">
      {['overview','progress'].includes(tab) && <SectionCard title="Acquisition progress" description="Current completion across the acquisition workflow">
        <div className="progress-section"><Progress label="Compensation completed" value={p.compensation_completion_pct}/><Progress label="Land possession" value={p.possession_pct}/><Progress label="Rehabilitation completed" value={p.rehabilitation_completion_pct}/></div>
      </SectionCard>}
      {tab === 'issues' && <SectionCard title="Administrative bottlenecks" description="Recorded observations for official review">
        <div className="admin-indicators">{[[ClipboardList,p.pending_approvals,'Pending approvals'],[Scale,p.legal_disputes,'Legal disputes'],[Clock3,p.stakeholder_response_days,'Stakeholder response time (days)'],[Hourglass,p.elapsed_acquisition_days,'Elapsed acquisition duration (days)']].map(([Icon,value,label]) => <div key={label}><Icon size={20}/><strong>{value}</strong><span>{label}</span></div>)}</div>
        <p className="panel-footnote">These observations are not a model-derived risk assessment.</p>
      </SectionCard>}
    </div>
    {tab === 'twin' && <ProjectDigitalTwin project={p}/>}
    {tab === 'ai' && <IntelligencePanel project={p}/>}
    {tab === 'interventions' && <InterventionLedger project={p}/>}
    <div className="detail-grid">
      {tab === 'gis' && <SectionCard title="Geographic context" description={'Latitude ' + p.latitude + ' · Longitude ' + p.longitude} action={<MapPin size={18}/>}>
        <div className="geographic-placeholder"><div><Map size={30}/><strong>Coordinates connected to GIS workspace</strong><p>This project can now be opened in the geographic intelligence view.</p><Link className="button secondary" to="/map">Open GIS workspace</Link></div></div>
      </SectionCard>}
      {tab === 'history' && <SectionCard title="Record history" description="Project record timestamps">
        <div className="timeline"><div><strong>Record last updated</strong><p>{new Date(p.updated_at).toLocaleString()}</p></div><div><strong>Record created</strong><p>{new Date(p.created_at).toLocaleString()}</p></div></div>
        <p className="panel-footnote">Authentication and intervention events are persisted. Full project-field change history remains a future hardening step.</p>
      </SectionCard>}
    </div>
    {tab === 'overview' && <details className="panel metadata-details"><summary>Project metadata</summary><dl className="quick-facts"><div><dt>Data source</dt><dd>{pretty(p.data_source)}</dd></div><div><dt>Record ID</dt><dd>{p.project_id}</dd></div><div><dt>Coordinates</dt><dd>{p.latitude}, {p.longitude}</dd></div></dl></details>}
    </div><div className="notice"><span>i</span><p>AI recommends; authorized officials decide. Illustrative records are fictional development data.</p></div>
  </>;
}
