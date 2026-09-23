import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Crosshair, Database, ExternalLink, FileUp, Filter, Layers3, LocateFixed, MapPinned, Radar, RotateCcw, Search, ShieldAlert, ShieldCheck, Sparkles, Trash2 } from 'lucide-react';
import { api } from '../services/api';
import { ErrorState, Loading, PageHeader, SectionCard, pretty } from '../components/common';
import { useResource } from '../hooks/useResource';
import LeafletProjectMap from '../components/gis/LeafletProjectMap';
import InterventionSimulator from '../components/projects/InterventionSimulator';

const BHUNAKSHA_URL='https://bhunakshaodisha.nic.in/bhunaksha/';
const BHULEKH_URL='https://bhulekh.ori.nic.in/';

function severity(project) {
  if (project?.risk_category) return project.risk_category.toLowerCase();
  if (project?.legal_disputes >= 2 || project?.pending_approvals >= 3) return 'high';
  if (project?.legal_disputes || project?.pending_approvals) return 'medium';
  return 'low';
}

function ownershipStatusMeta(status) {
  if (status === 'AUTHORITY_VERIFIED') return {label:'Authority verified', icon:ShieldCheck, tone:'verified'};
  if (status === 'IMPORTED_DATASET') return {label:'Imported dataset', icon:Database, tone:'imported'};
  return {label:'No cadastral data', icon:ShieldAlert, tone:'unavailable'};
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
  const [showOwnership,setShowOwnership]=useState(true);
  const [showRiskHeat,setShowRiskHeat]=useState(true);
  const [ownershipParcels,setOwnershipParcels]=useState([]);
  const [ownershipSummary,setOwnershipSummary]=useState(null);
  const [ownershipError,setOwnershipError]=useState('');
  const [ownershipRevision,setOwnershipRevision]=useState(0);
  const [authorityVerified,setAuthorityVerified]=useState(false);
  const [importBusy,setImportBusy]=useState(false);
  const [importMessage,setImportMessage]=useState('');
  const fileInputRef=useRef(null);

  const states=useMemo(()=>[...new Set((data||[]).map(p=>p.state))].sort(),[data]);
  const districts=useMemo(()=>[...new Set((data||[]).filter(p=>!state||p.state===state).map(p=>p.district))].sort(),[data,state]);
  const stages=useMemo(()=>[...new Set((data||[]).map(p=>p.acquisition_stage))].sort(),[data]);
  const filtered=useMemo(()=>{
    const q=query.trim().toLowerCase();
    return (data||[]).filter(p=>(!state||p.state===state)&&(!district||p.district===district)&&(!stage||p.acquisition_stage===stage)&&(!q||[p.project_id,p.project_name,p.district,p.state,p.project_type].join(' ').toLowerCase().includes(q)));
  },[data,query,state,district,stage]);
  const active=filtered.find(p=>p.project_id===selected?.project_id) || filtered[0] || null;

  useEffect(()=>{
    let cancelled=false;
    if(!active?.project_id){ setOwnershipParcels([]); setOwnershipSummary(null); return ()=>{}; }
    setOwnershipError('');
    setOwnershipParcels([]);
    setOwnershipSummary(null);
    setImportMessage('');
    setAuthorityVerified(false);
    Promise.all([
      api(`/gis/ownership/parcels?project_id=${encodeURIComponent(active.project_id)}`),
      api(`/gis/ownership/summary/${encodeURIComponent(active.project_id)}`),
    ]).then(([parcels,summary])=>{
      if(cancelled) return;
      setOwnershipParcels(parcels);
      setOwnershipSummary(summary);
    }).catch(err=>{
      if(cancelled) return;
      setOwnershipParcels([]); setOwnershipSummary(null); setOwnershipError(err.message);
    });
    return ()=>{cancelled=true;};
  },[active?.project_id,ownershipRevision]);

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

  async function importCadastralFile(event) {
    const file=event.target.files?.[0];
    event.target.value='';
    if(!file||!active) return;
    setImportBusy(true); setOwnershipError(''); setImportMessage('');
    try {
      if(!/\.(geojson|json)$/i.test(file.name)) throw new Error('Import a GeoJSON (.geojson or .json) cadastral export in WGS84 / EPSG:4326.');
      const parsed=JSON.parse(await file.text());
      const features=parsed?.type==='FeatureCollection' ? parsed.features : parsed?.type==='Feature' ? [parsed] : null;
      if(!Array.isArray(features)||!features.length) throw new Error('The selected file is not a GeoJSON FeatureCollection with parcel polygons.');
      const result=await api('/gis/ownership/import',{
        method:'POST',
        body:JSON.stringify({
          project_id:active.project_id,
          state:active.state,
          district:active.district,
          source_name:`CADASTRAL_GEOJSON:${file.name}`.slice(0,120),
          ror_verified:authorityVerified,
          crs_epsg:4326,
          replace_project_dataset:true,
          features,
        }),
      });
      setImportMessage(`${result.imported} parcels imported${result.rejected?` · ${result.rejected} rejected`:''}.`);
      setOwnershipRevision(n=>n+1);
    } catch(err) {
      setOwnershipError(err.message || 'Cadastral import failed.');
    } finally {
      setImportBusy(false);
    }
  }

  async function clearCadastralData() {
    if(!active||!ownershipParcels.length) return;
    if(!window.confirm(`Remove the imported cadastral dataset from ${active.project_id}?`)) return;
    setImportBusy(true); setOwnershipError(''); setImportMessage('');
    try {
      await api(`/gis/ownership/parcels/${encodeURIComponent(active.project_id)}`,{method:'DELETE'});
      setImportMessage('Cadastral dataset removed. No synthetic parcels will replace it.');
      setOwnershipRevision(n=>n+1);
    } catch(err) { setOwnershipError(err.message); }
    finally { setImportBusy(false); }
  }

  const status=ownershipStatusMeta(ownershipSummary?.data_status || 'UNAVAILABLE');
  const StatusIcon=status.icon;

  return <>
    <PageHeader eyebrow="GEOGRAPHIC INTELLIGENCE" title="Predictive risk map" description="See where schedule-slip risk is concentrated, inspect predictive hotspots, and move from geography directly into intervention simulation."/>
    <section className="gis-toolbar panel" aria-label="GIS controls">
      <label className="gis-search"><Search size={16}/><input aria-label="Search map projects" placeholder="Search project, district, state…" value={query} onChange={e=>setQuery(e.target.value)}/></label>
      <label><span>State</span><select aria-label="Map state filter" value={state} onChange={e=>{setState(e.target.value);setDistrict('');}}><option value="">All states</option>{states.map(v=><option key={v}>{v}</option>)}</select></label>
      <label><span>District</span><select aria-label="Map district filter" value={district} onChange={e=>setDistrict(e.target.value)}><option value="">All districts</option>{districts.map(v=><option key={v}>{v}</option>)}</select></label>
      <label><span>Stage</span><select aria-label="Map stage filter" value={stage} onChange={e=>setStage(e.target.value)}><option value="">All stages</option>{stages.map(v=><option key={v} value={v}>{pretty(v)}</option>)}</select></label>
      <button className="button secondary" onClick={()=>setFitRequest(n=>n+1)}><MapPinned size={16}/> Fit projects</button>
      <button className={`button ${showRiskHeat?'primary':'secondary'}`} onClick={()=>setShowRiskHeat(v=>!v)}><Radar size={16}/> ML heatmap {showRiskHeat?'on':'off'}</button>
      <button className={`button ${showOwnership&&ownershipParcels.length?'primary':'secondary'}`} onClick={()=>setShowOwnership(v=>!v)} disabled={!ownershipParcels.length}><Layers3 size={16}/> Parcels {showOwnership&&ownershipParcels.length?'on':'off'}</button>
      <button className="button secondary" onClick={()=>setLocateRequest(n=>n+1)}><Crosshair size={16}/> My location</button>
      <button className="button ghost" onClick={clearFilters}><RotateCcw size={16}/> Reset</button>
    </section>

    <div className="gis-risk-strip"><div><Radar size={16}/><strong>ML delay-risk heatmap</strong><small>PAIMANA 3-month schedule-slip probability</small></div><span className="high">{predictiveCounts.high} high</span><span className="medium">{predictiveCounts.medium} medium</span><span className="low">{predictiveCounts.low} low</span>{predictiveCounts.unscored>0&&<span>{predictiveCounts.unscored} unscored</span>}</div>
    <div className="gis-status-row"><span><Filter size={14}/> {filtered.length} matching projects</span><span>{visibleCount} currently in map viewport</span><div className="gis-legend" aria-label="Predictive marker legend"><i className="low"/> Low <i className="medium"/> Medium <i className="high"/> High / alert</div></div>
    {showRiskHeat&&<div className="ml-heat-legend" aria-label="ML delay risk heatmap legend"><strong><Radar size={14}/> ML delay-risk intensity</strong><span className="risk-0">0–30%</span><span className="risk-1">31–50%</span><span className="risk-2">51–70%</span><span className="risk-3">71–85%</span><span className="risk-4">86–100%</span><small>Background intensity uses only ML delay probabilities; unscored projects do not create heat.</small></div>}
    {showOwnership&&ownershipParcels.length>0&&<div className="ownership-legend"><strong><Layers3 size={14}/> Imported cadastral ownership</strong><span><i className="government"/>Government</span><span><i className="private"/>Private</span><span><i className="leasehold"/>Govt leasehold</span><span><i className="institutional"/>Institutional</span><span><i className="unknown"/>Unknown / unclassified</span></div>}

    <section className="gis-layout">
      <SectionCard title="Predictive project map" description="OpenTopoMap base + PAIMANA ML delay-risk intensity + imported cadastral geometry · ownership comes only from source attributes">
        {filtered.length ? <LeafletProjectMap projects={filtered} selected={active} onSelect={setSelected} onBoundsChange={setViewport} locateRequest={locateRequest} fitRequest={fitRequest} ownershipParcels={ownershipParcels} showOwnership={showOwnership} showRiskHeat={showRiskHeat}/> : <div className="gis-empty"><MapPinned size={30}/><strong>No projects match these GIS filters.</strong><button className="button secondary" onClick={clearFilters}>Clear filters</button></div>}
      </SectionCard>
      <aside className="panel gis-inspector">{active ? <><p className="eyebrow">SELECTED PROJECT</p><div className="gis-title-row"><span className={`gis-risk-dot ${severity(active)}`}/><div><h2>{active.project_name}</h2><p className="muted">{active.project_id} · {active.district}, {active.state}</p></div></div>
        {active.delay_probability != null ? <div className={`gis-predictive-card ${severity(active)}`}><span>3-month schedule-slip risk</span><strong>{Math.round(active.delay_probability*100)}%</strong><small>{active.risk_category} · {active.slip_alert?'ALERT TRIGGERED':'No alert'}</small></div> : <div className="gis-predictive-card unscored"><span>Predictive risk</span><strong>Not scored</strong><small>Add model baseline fields in the project record.</small></div>}
        <div className="gis-facts"><div><span>Stage</span><strong>{pretty(active.acquisition_stage)}</strong></div><div><span>Project type</span><strong>{pretty(active.project_type)}</strong></div><div><span>Pending approvals</span><strong>{active.pending_approvals}</strong></div><div><span>Legal disputes</span><strong>{active.legal_disputes}</strong></div><div><span>Compensation</span><strong>{active.compensation_completion_pct}%</strong></div><div><span>Possession</span><strong>{active.possession_pct}%</strong></div><div><span>Rehabilitation</span><strong>{active.rehabilitation_completion_pct}%</strong></div><div><span>Coordinates</span><strong>{active.latitude.toFixed(4)}, {active.longitude.toFixed(4)}</strong></div></div>

        <div className={`ownership-summary-card ${status.tone}`}>
          <div className="ownership-summary-head"><span>Land record layer</span><strong className={`ownership-status ${status.tone}`}><StatusIcon size={13}/>{status.label}</strong></div>
          {ownershipSummary?.breakdown?.length ? <div className="ownership-breakdown">{ownershipSummary.breakdown.map(row=><div key={row.ownership_type}><span>{pretty(row.ownership_type)}</span><strong>{row.area_pct}%</strong><small>{row.area_acres} ac · {row.parcel_count} plots</small></div>)}</div> : <div className="ownership-empty-state"><Database size={20}/><strong>No parcel geometry loaded</strong><p>LandGuard will not draw fake cadastral plots. Load a real WGS84 cadastral GeoJSON export for this project.</p></div>}
          {ownershipSummary?.total_parcels>0&&<p className="ownership-source">{ownershipSummary.total_parcels} parcels · {ownershipSummary.total_area_acres} acres · Source: {ownershipSummary.source_names.join(', ') || 'unspecified'} · {ownershipSummary.verified_parcels}/{ownershipSummary.total_parcels} authority-verified</p>}
          {ownershipSummary?.disclaimer&&<p className="ownership-disclaimer">{ownershipSummary.disclaimer}</p>}

          <div className="cadastral-import-panel">
            <input ref={fileInputRef} type="file" accept=".geojson,.json,application/geo+json,application/json" hidden onChange={importCadastralFile}/>
            <label className="authority-check"><input type="checkbox" checked={authorityVerified} onChange={e=>setAuthorityVerified(e.target.checked)}/><span><strong>Authority-verified export</strong><small>Enable only if the file came from the competent land-record authority or an approved departmental export.</small></span></label>
            <div className="cadastral-actions">
              <button className="button secondary" disabled={importBusy} onClick={()=>fileInputRef.current?.click()}><FileUp size={15}/>{importBusy?'Importing…':ownershipParcels.length?'Replace cadastral GeoJSON':'Import cadastral GeoJSON'}</button>
              {ownershipParcels.length>0&&<button className="button ghost danger" disabled={importBusy} onClick={clearCadastralData}><Trash2 size={15}/>Remove dataset</button>}
            </div>
            <small className="cadastral-hint">Expected: Polygon/MultiPolygon GeoJSON, EPSG:4326. Recommended attributes: plot_no, khata_no, ownership_type, kisam, unique_plot_id. Missing ownership stays UNKNOWN.</small>
            {importMessage&&<p className="form-success cadastral-message">{importMessage}</p>}
            {ownershipError&&<p className="form-error cadastral-message">{ownershipError}</p>}
          </div>

          {active.state?.toLowerCase()==='odisha' ? <div className="official-land-links"><span>Official Odisha references</span><a href={BHUNAKSHA_URL} target="_blank" rel="noreferrer">BhuNaksha cadastral map <ExternalLink size={12}/></a><a href={BHULEKH_URL} target="_blank" rel="noreferrer">Bhulekh RoR / plot records <ExternalLink size={12}/></a></div> : <div className="official-land-links"><span>Authority reference</span><small>Validate cadastral geometry and RoR attributes against the competent land-record authority for {active.state} before marking an import as verified.</small></div>}
        </div>

        <Link className="button primary" to={`/projects/${active.project_id}?tab=ai`}><LocateFixed size={16}/> Open intelligence</Link>
        {active.delay_probability != null && <button className="button simulator-map-button" onClick={launchSimulator} disabled={simBusy}><Sparkles size={16}/>{simBusy?'Loading simulator…':'Simulate intervention'}</button>}
        <a className="button secondary" href={`https://www.openstreetmap.org/?mlat=${active.latitude}&mlon=${active.longitude}#map=13/${active.latitude}/${active.longitude}`} target="_blank" rel="noreferrer"><ExternalLink size={16}/> Open in OSM</a>
        {simError&&<p className="form-error">{simError}</p>}
      </> : <p>No project selected.</p>}</aside>
    </section>
    <div className="notice"><span>i</span><p>Cadastral ownership is shown only when a real dataset is imported. Bhuvan/imagery can provide geographic context, but LandGuard never infers legal ownership from imagery or land-use appearance.</p></div>
    <InterventionSimulator open={simulatorOpen} onClose={()=>setSimulatorOpen(false)} project={simProject} prediction={simPrediction}/>
  </>;
}
