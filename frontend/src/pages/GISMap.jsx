import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Crosshair, ExternalLink, Filter, LocateFixed, MapPinned, Radar, RotateCcw, Search, Sparkles } from 'lucide-react';
import { api } from '../services/api';
import { ErrorState, Loading, PageHeader, SectionCard, pretty } from '../components/common';
import { useResource } from '../hooks/useResource';
import LeafletProjectMap from '../components/gis/LeafletProjectMap';
import InterventionSimulator from '../components/projects/InterventionSimulator';

function severity(project) {
  if (project?.risk_category) return project.risk_category.toLowerCase();
  if (project?.legal_disputes >= 2 || project?.pending_approvals >= 3) return 'high';
  if (project?.legal_disputes || project?.pending_approvals) return 'medium';
  return 'low';
}

export default function GISMap() {
  const [retry,setRetry]=useState(0);
  const {data,error}=useResource('map-data',signal=>api('/map-data',{signal}),retry);
  const [selected,setSelected]=useState(null);
  const [query,setQuery]=useState('');
  const [state,setState]=useState('');
  const [district,setDistrict]=useState('');
  const [stage,setStage]=useState('');
  const [locateRequest,setLocateRequest]=useState(0);
  const [fitRequest,setFitRequest]=useState(0);
  const [viewport,setViewport]=useState(null);
  const [simulatorOpen,setSimulatorOpen]=useState(false);
  const [simProject,setSimProject]=useState(null);
  const [simPrediction,setSimPrediction]=useState(null);
  const [simBusy,setSimBusy]=useState(false);
  const [simError,setSimError]=useState('');

  const states=useMemo(()=>[...new Set((data||[]).map(p=>p.state))].sort(),[data]);
  const districts=useMemo(()=>[...new Set((data||[]).filter(p=>!state||p.state===state).map(p=>p.district))].sort(),[data,state]);
  const stages=useMemo(()=>[...new Set((data||[]).map(p=>p.acquisition_stage))].sort(),[data]);
  const filtered=useMemo(()=>{
    const q=query.trim().toLowerCase();
    return (data||[]).filter(p=>(!state||p.state===state)&&(!district||p.district===district)&&(!stage||p.acquisition_stage===stage)&&(!q||[p.project_id,p.project_name,p.district,p.state,p.project_type].join(' ').toLowerCase().includes(q)));
  },[data,query,state,district,stage]);
  const active=filtered.find(p=>p.project_id===selected?.project_id) || filtered[0] || null;
  const visibleCount=useMemo(()=>{
    if(!viewport) return filtered.length;
    return filtered.filter(p=>p.latitude>=viewport.min_lat&&p.latitude<=viewport.max_lat&&p.longitude>=viewport.min_lon&&p.longitude<=viewport.max_lon).length;
  },[filtered,viewport]);
  const predictiveCounts=useMemo(()=>filtered.reduce((acc,p)=>{ if(p.risk_category) acc[p.risk_category.toLowerCase()]++; else acc.unscored++; return acc; },{high:0,medium:0,low:0,unscored:0}),[filtered]);

  if (error) return <ErrorState message={error} retry={()=>setRetry(n=>n+1)}/>;
  if (!data) return <Loading variant="detail"/>;

  function clearFilters(){setQuery('');setState('');setDistrict('');setStage('');setSelected(null);setFitRequest(n=>n+1);}
  async function launchSimulator() {
    if (!active) return;
    setSimBusy(true); setSimError('');
    try {
      const [project,prediction]=await Promise.all([api(`/projects/${active.project_id}`),api(`/projects/${active.project_id}/predict`,{method:'POST'})]);
      setSimProject(project); setSimPrediction(prediction); setSimulatorOpen(true);
    } catch(err) { setSimError(err.message); }
    finally { setSimBusy(false); }
  }

  return <>
    <PageHeader eyebrow="GEOGRAPHIC INTELLIGENCE" title="Predictive risk map" description="See where schedule-slip risk is concentrated, inspect predictive hotspots, and move from geography directly into intervention simulation."/>
    <section className="gis-toolbar panel" aria-label="GIS controls">
      <label className="gis-search"><Search size={16}/><input aria-label="Search map projects" placeholder="Search project, district, state…" value={query} onChange={e=>setQuery(e.target.value)}/></label>
      <label><span>State</span><select aria-label="Map state filter" value={state} onChange={e=>{setState(e.target.value);setDistrict('');}}><option value="">All states</option>{states.map(v=><option key={v}>{v}</option>)}</select></label>
      <label><span>District</span><select aria-label="Map district filter" value={district} onChange={e=>setDistrict(e.target.value)}><option value="">All districts</option>{districts.map(v=><option key={v}>{v}</option>)}</select></label>
      <label><span>Stage</span><select aria-label="Map stage filter" value={stage} onChange={e=>setStage(e.target.value)}><option value="">All stages</option>{stages.map(v=><option key={v} value={v}>{pretty(v)}</option>)}</select></label>
      <button className="button secondary" onClick={()=>setFitRequest(n=>n+1)}><MapPinned size={16}/> Fit projects</button>
      <button className="button secondary" onClick={()=>setLocateRequest(n=>n+1)}><Crosshair size={16}/> My location</button>
      <button className="button ghost" onClick={clearFilters}><RotateCcw size={16}/> Reset</button>
    </section>

    <div className="gis-risk-strip"><div><Radar size={16}/><strong>Predictive map pulse</strong></div><span className="high">{predictiveCounts.high} high</span><span className="medium">{predictiveCounts.medium} medium</span><span className="low">{predictiveCounts.low} low</span>{predictiveCounts.unscored>0&&<span>{predictiveCounts.unscored} unscored</span>}</div>
    <div className="gis-status-row"><span><Filter size={14}/> {filtered.length} matching projects</span><span>{visibleCount} currently in map viewport</span><div className="gis-legend" aria-label="Predictive marker legend"><i className="low"/> Low risk <i className="medium"/> Medium risk <i className="high"/> High risk / alert</div></div>

    <section className="gis-layout">
      <SectionCard title="Predictive project map" description="OpenTopoMap basemap · marker pulse reflects current model risk when prediction inputs are available">
        {filtered.length ? <LeafletProjectMap projects={filtered} selected={active} onSelect={setSelected} onBoundsChange={setViewport} locateRequest={locateRequest} fitRequest={fitRequest}/> : <div className="gis-empty"><MapPinned size={30}/><strong>No projects match these GIS filters.</strong><button className="button secondary" onClick={clearFilters}>Clear filters</button></div>}
      </SectionCard>
      <aside className="panel gis-inspector">{active ? <><p className="eyebrow">SELECTED PROJECT</p><div className="gis-title-row"><span className={`gis-risk-dot ${severity(active)}`}/><div><h2>{active.project_name}</h2><p className="muted">{active.project_id} · {active.district}, {active.state}</p></div></div>
        {active.delay_probability != null ? <div className={`gis-predictive-card ${severity(active)}`}><span>3-month schedule-slip risk</span><strong>{Math.round(active.delay_probability*100)}%</strong><small>{active.risk_category} · {active.slip_alert?'ALERT TRIGGERED':'No alert'}</small></div> : <div className="gis-predictive-card unscored"><span>Predictive risk</span><strong>Not scored</strong><small>Add model baseline fields in the project record.</small></div>}
        <div className="gis-facts"><div><span>Stage</span><strong>{pretty(active.acquisition_stage)}</strong></div><div><span>Project type</span><strong>{pretty(active.project_type)}</strong></div><div><span>Pending approvals</span><strong>{active.pending_approvals}</strong></div><div><span>Legal disputes</span><strong>{active.legal_disputes}</strong></div><div><span>Compensation</span><strong>{active.compensation_completion_pct}%</strong></div><div><span>Possession</span><strong>{active.possession_pct}%</strong></div><div><span>Rehabilitation</span><strong>{active.rehabilitation_completion_pct}%</strong></div><div><span>Coordinates</span><strong>{active.latitude.toFixed(4)}, {active.longitude.toFixed(4)}</strong></div></div>
        <Link className="button primary" to={`/projects/${active.project_id}?tab=ai`}><LocateFixed size={16}/> Open intelligence</Link>
        {active.delay_probability != null && <button className="button simulator-map-button" onClick={launchSimulator} disabled={simBusy}><Sparkles size={16}/>{simBusy?'Loading simulator…':'Simulate intervention'}</button>}
        <a className="button secondary" href={`https://www.openstreetmap.org/?mlat=${active.latitude}&mlon=${active.longitude}#map=13/${active.latitude}/${active.longitude}`} target="_blank" rel="noreferrer"><ExternalLink size={16}/> Open in OSM</a>
        {simError&&<p className="form-error">{simError}</p>}
      </> : <p>No project selected.</p>}</aside>
    </section>
    <div className="notice"><span>i</span><p>Predictive marker colors are generated from the real PAIMANA-trained baseline when the project has the required cost/schedule inputs. Operational issues remain separate decision-support evidence.</p></div>
    <InterventionSimulator open={simulatorOpen} onClose={()=>setSimulatorOpen(false)} project={simProject} prediction={simPrediction}/>
  </>;
}
