import { ArrowRight, Crosshair, MapPinned, Radar, ShieldAlert, GaugeCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '../../services/api';
import { useResource } from '../../hooks/useResource';

function queryFor(filters) { const q=new URLSearchParams(); if(filters?.state)q.set('state',filters.state); if(filters?.district)q.set('district',filters.district); const t=q.toString(); return t?`?${t}`:''; }
export default function RiskPulse({filters,refresh=0}){
  const suffix=queryFor(filters); const {data,error}=useResource(`risk-pulse${suffix}`,signal=>api(`/risk-pulse${suffix}`,{signal}),refresh);
  const {data:ledger}=useResource(`intervention-summary${suffix}`,signal=>api('/interventions/summary',{signal}),refresh);
  if(error)return <section className="risk-pulse risk-pulse-unavailable"><div><Radar size={19}/><strong>District War Room unavailable</strong><span>{error}</span></div></section>;
  if(!data)return <section className="risk-pulse risk-pulse-loading"><div className="risk-pulse-orbit"><i/><i/><i/></div><span>Building district intervention picture…</span></section>;
  if(!data.model_available)return <section className="risk-pulse risk-pulse-unavailable"><div><Radar size={19}/><strong>War Room waiting for model</strong><span>Train the PAIMANA baseline to activate predictive prioritization.</span></div></section>;
  const total=Math.max(1,data.scored_projects); const top=data.projects?.slice(0,4)||[]; const scope=filters?.district?filters.district:filters?.state?filters.state:'Current scope';
  return <section className="war-room" aria-label="District land acquisition war room">
    <div className="war-room-hero">
      <div className="war-room-title"><div><span className="eyebrow"><Crosshair size={14}/> LAND ACQUISITION WAR ROOM</span><h2>{scope}</h2><p>Land-acquisition delay risk first, with PAIMANA schedule pressure as supporting evidence.</p></div><Link to="/map" className="button primary"><MapPinned size={15}/>Open command map</Link></div>
      <div className="war-room-metrics">
        <div className="exposure"><GaugeCircle size={20}/><span>AVG. ACQUISITION DELAY RISK</span><strong>{data.average_acquisition_delay_risk_score||0}/100</strong><small>Land-acquisition-specific index across model-ready projects</small></div>
        <div><span>Immediate intervention</span><strong>{data.intervention_candidates}</strong><small>{data.critical_priority||0} critical · {data.high_priority||0} high priority</small></div>
        <div><span>Tracked actions</span><strong>{ledger?.open_count ?? 0}</strong><small>{ledger?.overdue_count ?? 0} overdue · {ledger?.in_progress_count ?? 0} in progress</small></div>
        <div><span>ML risk bands</span><strong>{data.high_risk} / {data.medium_risk} / {data.low_risk}</strong><small>high / medium / low schedule signal</small></div>
      </div>
      <div className="risk-pulse-segments"><div className="high" style={{width:`${data.high_risk/total*100}%`}}/><div className="medium" style={{width:`${data.medium_risk/total*100}%`}}/><div className="low" style={{width:`${data.low_risk/total*100}%`}}/></div>
    </div>
    <div className="war-room-queue"><div className="risk-pulse-priority-head"><div><span className="eyebrow">TODAY'S INTERVENTION QUEUE</span><h3>Acquisition-aware priority, not probability alone.</h3></div><small>Acquisition risk sets the base · PAIMANA schedule evidence can only escalate priority</small></div>
      {top.length?<div className="risk-pulse-list">{top.map((p,i)=><Link key={p.project_id} to={`/projects/${p.project_id}?tab=twin`} className="risk-pulse-row war-row"><span className="risk-pulse-rank">0{i+1}</span><div><strong>{p.project_name}</strong><small>{p.primary_bottleneck||'Operational review'} · LA risk {p.acquisition_delay_risk_score ?? '—'}/100 · readiness {p.acquisition_readiness_score ?? '—'}/100</small></div><div className={`risk-pulse-score ${(p.intervention_priority_category||'routine').toLowerCase()}`}><strong>{p.intervention_priority_score ?? '—'}/100</strong><small>{p.intervention_priority_category || 'ROUTINE'} priority · {p.acquisition_delay_risk_label || '—'} LA risk · {Math.round(p.delay_probability*100)}% schedule signal</small></div><ArrowRight size={16}/></Link>)}</div>:<div className="risk-pulse-empty"><ShieldAlert size={20}/><span>No model-ready projects in this scope.</span></div>}
    </div>
  </section>;
}
