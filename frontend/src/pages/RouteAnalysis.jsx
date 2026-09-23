import { useMemo, useState } from 'react';
import {
  Activity, ArrowLeftRight, BrainCircuit, Building2, CheckCircle2, Database,
  ExternalLink, FileDown, Gauge, Info, Landmark, Layers3, MapPinned, Mountain,
  Navigation, Route as RouteIcon, Ruler, ShieldAlert, Sparkles, Trees, Waves,
} from 'lucide-react';
import { PageHeader } from '../components/common';
import RouteAnalysisMap from '../components/gis/RouteAnalysisMap';
import '../styles/route-analysis.css';

const apiBase = `${import.meta.env.VITE_API_URL || ''}/api/v1`;

async function routeRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...options,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-LandGuard-Request': '1', ...options.headers },
    });
  } catch {
    throw new Error('LandGuard could not reach the route-analysis service. Check internet connectivity and the backend terminal.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || 'Route analysis could not be completed.');
  }
  return response.json();
}

function fmt(value, digits = 1, fallback = '—') {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return fallback;
  return Number(value).toFixed(digits);
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 0;
  return Math.max(0, Math.min(100, Number(value)));
}

function coverageLabel(status) {
  if (status === 'GOOD') return 'Good live-data coverage';
  if (status === 'PARTIAL') return 'Partial live-data coverage';
  return 'Limited live-data coverage';
}

function constructionLabel(value) {
  return ({ ROAD: 'Road / highway', RAILWAY: 'Railway', CANAL: 'Canal', PIPELINE: 'Pipeline', OTHER: 'Other infrastructure' })[value] || value;
}

function splitLead(text, fallback) {
  const raw = String(text || '').trim();
  for (const token of [':', ' — ']) {
    const index = raw.indexOf(token);
    if (index > 2 && index < 72) {
      return { title: raw.slice(0, index).trim(), body: raw.slice(index + token.length).trim() };
    }
  }
  return { title: fallback, body: raw };
}

function summaryPoints(text) {
  const raw = String(text || '').trim();
  if (!raw) return [];
  const sentences = raw.split(/(?<=[.!?])\s+(?=[A-Z])/g);
  return sentences.map(item => item.trim()).filter(Boolean).slice(0, 4);
}

function trimWords(text, maxWords = 18) {
  const words = String(text || '').replace(/\s+/g, ' ').trim().split(' ').filter(Boolean);
  if (!words.length) return '—';
  if (words.length <= maxWords) return words.join(' ');
  return `${words.slice(0, maxWords).join(' ')}…`;
}

function compactPoint(text) {
  return trimWords(String(text || '').replace(/^LandGuard recommends\s+/i, ''), 20);
}

function compactSource(source) {
  const raw = String(source || '');
  if (/openstreetmap|overpass/i.test(raw)) return 'OSM / Overpass mapped features';
  if (/srtm|opentopo/i.test(raw)) return 'SRTM terrain screening';
  if (/nominatim/i.test(raw)) return 'Scoped place resolution';
  if (/deterministic concept-alignment/i.test(raw)) return 'Deterministic corridor generator';
  if (/google maps/i.test(raw)) return 'Google Maps endpoint reference';
  return trimWords(raw, 6);
}

function ImpactRow({ label, value }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}

function ResultMetric({ icon: Icon, label, value, caption }) {
  return <article className="route-result-metric">
    <span className="route-result-icon"><Icon size={17}/></span>
    <div><span>{label}</span><strong>{value}</strong><small>{caption}</small></div>
  </article>;
}

export default function RouteAnalysis() {
  const [form, setForm] = useState({
    origin: '', destination: '', construction_type: 'ROAD', alignment_mode: 'NEW_ALIGNMENT', corridor_width_m: 40, base_cost_crore_per_km: '',
  });
  const [analysis, setAnalysis] = useState(null);
  const [selectedRouteId, setSelectedRouteId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);
  const [error, setError] = useState('');

  const selected = useMemo(() => {
    if (!analysis) return null;
    return analysis.candidates.find(row => row.route_id === selectedRouteId)
      || analysis.candidates.find(row => row.route_id === analysis.recommended_route_id)
      || analysis.candidates[0];
  }, [analysis, selectedRouteId]);

  function change(name, value) {
    setForm(current => {
      const next = { ...current, [name]: value };
      if (name === 'construction_type' && value !== 'ROAD') next.alignment_mode = 'NEW_ALIGNMENT';
      return next;
    });
  }

  function swap() {
    setForm(current => ({ ...current, origin: current.destination, destination: current.origin }));
  }

  async function analyze(event) {
    event.preventDefault();
    setBusy(true); setError(''); setAnalysis(null);
    try {
      const payload = {
        origin: form.origin.trim(),
        destination: form.destination.trim(),
        construction_type: form.construction_type,
        alignment_mode: form.alignment_mode,
        corridor_width_m: Number(form.corridor_width_m),
        base_cost_crore_per_km: form.base_cost_crore_per_km === '' ? null : Number(form.base_cost_crore_per_km),
      };
      const result = await routeRequest('/route-analysis/analyze', { method: 'POST', body: JSON.stringify(payload) });
      setAnalysis(result);
      setSelectedRouteId(result.recommended_route_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function downloadReport() {
    if (!analysis) return;
    setReportBusy(true); setError('');
    try {
      const response = await fetch(`${apiBase}/route-analysis/report`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-LandGuard-Request': '1' },
        body: JSON.stringify({ analysis }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || 'Could not generate the route-analysis report.');
      }
      const blob = await response.blob();
      const href = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = href;
      a.download = 'LandGuard_Route_Feasibility_Analysis.pdf';
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(href);
    } catch (err) {
      setError(err.message);
    } finally {
      setReportBusy(false);
    }
  }

  const recommendedCandidate = analysis?.candidates.find(row => row.route_id === analysis.recommended_route_id);
  const obs = selected?.obstacle_summary;
  const terrain = selected?.terrain_summary;
  const obstacleVerified = (selected?.data_coverage_percent || 0) >= 55;
  const isNew = analysis?.alignment_mode === 'NEW_ALIGNMENT';
  const decisionPoints = summaryPoints(analysis?.executive_summary).map(compactPoint);

  const quickReview = useMemo(() => {
    if (!analysis || !selected) return [];
    const strengths = (selected.strengths || []).slice(0, 2);
    const concerns = (selected.concerns || []).slice(0, 2);
    return [
      {
        title: 'Planning mode',
        body: isNew
          ? 'Greenfield concept screening; the line is a corridor concept, not a final surveyed road.'
          : 'Existing mapped-road screening; candidates stay on the current drivable network.',
      },
      {
        title: 'Why this route ranks well',
        body: strengths.length ? trimWords(strengths.join(' · '), 18) : 'Provides a distinct corridor option for comparison.',
      },
      {
        title: 'Main watchout',
        body: !obstacleVerified
          ? 'Live mapped obstacle coverage is incomplete, so structures and utilities still need manual verification.'
          : trimWords(concerns[0] || 'Detailed engineering, RoR checks and site verification are still required.', 18),
      },
      {
        title: 'Distance & footprint',
        body: `${fmt(selected.distance_km, 2)} km selected · ${fmt(selected.screening_area_ha, 1)} ha corridor · ${fmt(analysis.corridor_width_m, 0)} m width.`,
      },
      {
        title: 'Terrain context',
        body: terrain?.available
          ? `${fmt(terrain.mean_abs_grade_percent, 2)}% mean grade · ${fmt(terrain.max_grade_percent, 2)}% max · ${fmt(terrain.elevation_range_m, 1)} m elevation range.`
          : 'Terrain provider unavailable for this run.',
      },
      {
        title: 'Data confidence',
        body: `${analysis.analysis_confidence} confidence · ${coverageLabel(analysis.mapped_data_status).toLowerCase()} · ${fmt(selected.data_coverage_percent, 0)}% corridor coverage.`,
      },
    ];
  }, [analysis, selected, isNew, obstacleVerified, terrain]);

  const readinessItems = useMemo(() => {
    if (!analysis) return [];
    return analysis.acquisition_data_readiness.slice(0, 4).map((item, index) => {
      const parsed = splitLead(item, `Required dataset ${index + 1}`);
      return { index, title: parsed.title, body: trimWords(parsed.body, 16) };
    });
  }, [analysis]);

  const providerFacts = useMemo(() => {
    const raw = String(analysis?.provider_status || '');
    return raw.split(' · ').map(item => item.trim()).filter(Boolean).slice(0, 4);
  }, [analysis]);

  const sourceChips = useMemo(() => {
    if (!analysis) return [];
    return [...new Set((analysis.data_sources || []).map(compactSource))].slice(0, 5);
  }, [analysis]);

  return <>
    <PageHeader
      eyebrow="PRE-FEASIBILITY"
      title="Route feasibility & land-impact screening"
      description="Compare practical corridor concepts using mapped constraints, terrain and acquisition signals before detailed engineering begins."
    />

    <section className="panel route-input-panel">
      <div className="route-input-heading">
        <div>
          <span className="route-section-kicker"><Navigation size={14}/> Corridor setup</span>
          <strong>Define the construction corridor</strong>
          <p>Set two endpoints, choose the infrastructure type and tell LandGuard how wide an area to screen around each candidate centreline.</p>
        </div>
        <div className="route-stage-pills" aria-label="Route analysis workflow">
          <span className="active">1 · Define</span><span>2 · Screen</span><span>3 · Compare</span>
        </div>
      </div>

      <form className="route-analysis-form route-analysis-form-v2" onSubmit={analyze}>
        <label className="route-place-field"><span>From</span><div><MapPinned size={17}/><input required minLength={2} value={form.origin} onChange={e=>change('origin',e.target.value)} placeholder="e.g. Gunupur"/></div></label>
        <button type="button" className="icon-button route-swap" onClick={swap} aria-label="Swap origin and destination"><ArrowLeftRight size={18}/></button>
        <label className="route-place-field"><span>To</span><div><MapPinned size={17}/><input required minLength={2} value={form.destination} onChange={e=>change('destination',e.target.value)} placeholder="e.g. Padmapur"/></div></label>
        <label><span>Construction type</span><select value={form.construction_type} onChange={e=>change('construction_type',e.target.value)}><option value="ROAD">Road / highway</option><option value="RAILWAY">Railway</option><option value="CANAL">Canal</option><option value="PIPELINE">Pipeline</option><option value="OTHER">Other</option></select></label>
        <label><span>Planning mode</span><select value={form.alignment_mode} onChange={e=>change('alignment_mode',e.target.value)}><option value="NEW_ALIGNMENT">New / greenfield alignment</option>{form.construction_type==='ROAD'&&<option value="EXISTING_NETWORK">Existing road corridor</option>}</select></label>
        <label><span>Screening / ROW width</span><div className="route-number-field"><input type="number" min="5" max="2000" step="5" value={form.corridor_width_m} onChange={e=>change('corridor_width_m',e.target.value)}/><b>m</b></div><small>Width around the centreline; not a distance cap.</small></label>
        <label><span>Base cost · optional</span><div className="route-number-field"><b>₹</b><input type="number" min="0.01" step="0.01" value={form.base_cost_crore_per_km} onChange={e=>change('base_cost_crore_per_km',e.target.value)} placeholder="Department estimate"/></div><small>Crore per kilometre.</small></label>
        <button className="button primary route-analyze-button" disabled={busy}><Sparkles size={17}/><span>{busy?'Screening corridor…':'Analyze route options'}</span></button>
      </form>

      <div className="route-form-note"><Info size={16}/><span><b>Planning behaviour:</b> new-alignment mode creates screening centrelines independent of existing roads. Existing-network mode is available only for road/highway upgrade analysis.</span></div>
      {error&&<div className="route-error" role="alert"><ShieldAlert size={18}/><span>{error}</span></div>}
    </section>

    {busy && <section className="panel route-loading">
      <span className="route-loading-icon"><BrainCircuit size={24}/></span>
      <div><strong>Screening candidate alignments</strong><div className="route-loading-steps"><span>Resolve endpoints</span><i/> <span>Generate geometry</span><i/> <span>Sample terrain</span><i/> <span>Query mapped constraints</span><i/> <span>Rank candidates</span></div></div>
    </section>}

    {analysis && selected && <>
      <section className="panel route-decision-hero">
        <div className="route-decision-copy">
          <div className="route-decision-meta">
            <span className="route-status-badge"><CheckCircle2 size={14}/> Screening complete</span>
            <span>{constructionLabel(analysis.construction_type)}</span>
            <span>{analysis.alignment_mode==='NEW_ALIGNMENT'?'Greenfield concepts':'Existing road corridor'}</span>
          </div>
          <p className="eyebrow">LANDGUARD SCREENING RESULT</p>
          <h2>{analysis.recommendation_title}</h2>
          <ul className="route-summary-points">
            {decisionPoints.map((point,index)=><li key={index}><span>{index+1}</span><p>{point}</p></li>)}
          </ul>
        </div>
        <div className="route-decision-actions">
          <div className="route-preferred-chip"><span>Preferred candidate</span><strong>{analysis.recommended_route_id.replace('_',' ')}</strong><small>{recommendedCandidate?.feasibility_label || 'Lower screened constraint'}</small></div>
          <a className="button secondary" href={selected.google_maps_url} target="_blank" rel="noreferrer"><ExternalLink size={16}/> Map endpoints</a>
          <button className="button primary" onClick={downloadReport} disabled={reportBusy}><FileDown size={16}/>{reportBusy?'Preparing PDF…':'Download report'}</button>
        </div>
      </section>

      <section className="route-result-grid">
        <ResultMetric icon={Database} label="Analysis confidence" value={analysis.analysis_confidence} caption={`${coverageLabel(analysis.mapped_data_status)} · ${fmt(selected.data_coverage_percent,0)}% coverage`}/>
        <ResultMetric icon={Gauge} label="Screening score" value={`${fmt(selected.feasibility_score,0)}/100`} caption={`Evidence-adjusted · burden ${fmt(selected.route_burden_score,0)}/100`}/>
        <ResultMetric icon={Ruler} label="Screening footprint" value={`${fmt(selected.screening_area_ha,1)} ha`} caption={`${fmt(analysis.corridor_width_m,0)} m ROW/screening width`}/>
        <ResultMetric icon={RouteIcon} label="Selected distance" value={`${fmt(selected.distance_km,2)} km`} caption="No route-length cap applied"/>
      </section>

      <section className="route-workbench">
        <article className="panel route-map-card route-map-card-v3">
          <div className="route-card-heading route-card-heading-spacious">
            <div><span className="route-section-kicker"><Layers3 size={14}/> Alignment workspace</span><strong>{isNew?'Concept corridor preview':'Mapped road-corridor preview'}</strong><p>{isNew?'Curved lines show corridor concepts for screening, not final engineering alignments. Select a candidate to inspect it.' :'Candidates follow the mapped drivable network. Select one to inspect its screening profile.'}</p></div>
            <span className="route-endpoint-chip">{analysis.origin.label.split(',')[0]} <b>→</b> {analysis.destination.label.split(',')[0]}</span>
          </div>

          <div className="route-candidate-switcher" role="group" aria-label="Route candidates">
            {analysis.candidates.map((candidate,index)=>{
              const active = candidate.route_id === selected.route_id;
              const recommended = candidate.route_id === analysis.recommended_route_id;
              return <button key={candidate.route_id} type="button" className={`route-candidate-tab ${active?'active':''}`} onClick={()=>setSelectedRouteId(candidate.route_id)}>
                <span className={`route-line-swatch swatch-${index+1}`}/>
                <span className="route-candidate-tab-copy"><b>{candidate.label}</b><small>{fmt(candidate.distance_km,2)} km</small></span>
                <span className="route-tab-score"><b>{fmt(candidate.feasibility_score,0)}</b><small>/100</small></span>
                {recommended&&<em>Preferred</em>}
              </button>;
            })}
          </div>

          <div className="route-resolved-endpoints" aria-label="Resolved route endpoints">
            <div className="route-resolved-point"><span>A</span><div><small>Resolved origin</small><strong>{analysis.origin.label}</strong><em>{fmt(analysis.origin.latitude,4)}, {fmt(analysis.origin.longitude,4)}</em></div></div>
            <div className="route-resolved-connector"><Navigation size={15}/><span>All candidate centrelines must begin and end at these resolved points.</span></div>
            <div className="route-resolved-point"><span>B</span><div><small>Resolved destination</small><strong>{analysis.destination.label}</strong><em>{fmt(analysis.destination.latitude,4)}, {fmt(analysis.destination.longitude,4)}</em></div></div>
          </div>

          <RouteAnalysisMap analysis={analysis} selectedRouteId={selected.route_id} onSelect={setSelectedRouteId}/>
          <div className="route-map-footer"><span><i className="route-map-dot selected"/> Selected corridor</span><span><i className="route-map-dot alternate"/> Alternative</span><span><Info size={13}/> Concept corridor preview · not final engineering geometry</span></div>
        </article>

        <aside className="panel route-route-inspector">
          <div className="route-inspector-top">
            <div><p className="eyebrow">SELECTED CANDIDATE</p><h3>{selected.label}</h3><span>{selected.route_basis}</span></div>
            <div className="route-score-ring" style={{'--route-score': `${pct(selected.feasibility_score) * 3.6}deg`}}><div><strong>{fmt(selected.feasibility_score,0)}</strong><small>/100</small></div></div>
          </div>

          <div className="route-score-label"><span>Evidence-adjusted screening score</span><b>{selected.feasibility_label}</b></div>
          <div className="route-progress"><i style={{width:`${pct(selected.feasibility_score)}%`}}/></div>

          <div className="route-inspector-metrics">
            <div><span>Distance</span><strong>{fmt(selected.distance_km,2)} <small>km</small></strong></div>
            <div><span>Burden</span><strong>{fmt(selected.route_burden_score,0)} <small>/100</small></strong></div>
            <div><span>Cost index</span><strong>{fmt(selected.comparative_cost_index,0)}</strong></div>
            <div><span>Mapped coverage</span><strong>{fmt(selected.data_coverage_percent,0)}<small>%</small></strong></div>
          </div>

          <div className="route-terrain-card route-terrain-card-v3"><Mountain size={19}/><div><span>Terrain profile</span>{terrain?.available?<><strong>{fmt(terrain.mean_abs_grade_percent,2)}% mean · {fmt(terrain.max_grade_percent,2)}% max grade</strong><small>{fmt(terrain.elevation_range_m,1)} m elevation range across {terrain.sample_count} SRTM samples</small></>:<><strong>Terrain provider unavailable</strong><small>No terrain values are being inferred.</small></>}</div></div>

          <div className={`route-data-health ${obstacleVerified?'verified':'partial'}`}><span><Activity size={16}/>{obstacleVerified?'Mapped constraint layer verified':'Constraint layer incomplete'}</span><strong>{fmt(selected.data_coverage_percent,0)}%</strong></div>
          <p className="route-google-note"><Info size={14}/><span>{selected.google_maps_note}</span></p>
        </aside>
      </section>

      <section className="panel route-impact-panel-v3">
        <div className="route-section-header">
          <div><span className="route-section-kicker"><ShieldAlert size={14}/> Corridor impact scan</span><h3>Land-acquisition & engineering signals</h3><p>Mapped objects inside the selected screening corridor. These counts describe map features, not legal ownership or final acquisition quantities.</p></div>
          <span className={`route-layer-status ${obstacleVerified?'verified':'partial'}`}>{obstacleVerified?<><CheckCircle2 size={14}/> Live OSM query verified</>:<><Database size={14}/> Live obstacle data incomplete</>}</span>
        </div>
        {obstacleVerified ? <div className="route-impact-groups route-impact-groups-v3">
          <div><span className="route-impact-icon"><Building2 size={18}/></span><h4>Structures & activity</h4><dl><ImpactRow label="Mapped structures" value={obs.mapped_buildings}/><ImpactRow label="Residential" value={obs.residential}/><ImpactRow label="Commercial" value={obs.commercial}/><ImpactRow label="Govt / public" value={obs.government_public}/><ImpactRow label="Institutional" value={obs.institutional}/><ImpactRow label="Shops / businesses" value={obs.shops_businesses}/></dl></div>
          <div><span className="route-impact-icon"><Landmark size={18}/></span><h4>Sensitive & settlement</h4><dl><ImpactRow label="Schools" value={obs.schools}/><ImpactRow label="Healthcare" value={obs.healthcare}/><ImpactRow label="Religious places" value={obs.religious}/><ImpactRow label="Settlement features" value={obs.settlements}/><ImpactRow label="Named mapped places" value={obs.named_places}/></dl></div>
          <div><span className="route-impact-icon"><Waves size={18}/></span><h4>Crossings & utilities</h4><dl><ImpactRow label="Water features" value={obs.water_crossings}/><ImpactRow label="Rail crossings" value={obs.railway_crossings}/><ImpactRow label="Power-line crossings" value={obs.powerline_crossings}/><ImpactRow label="Existing bridge segments" value={obs.existing_bridge_segments}/></dl></div>
          <div><span className="route-impact-icon"><Trees size={18}/></span><h4>Land & environment</h4><dl><ImpactRow label="Forest / protected" value={obs.forest_protected_hits}/><ImpactRow label="Farmland / related" value={obs.farmland_hits}/><ImpactRow label="Residential land-use" value={obs.residential_landuse_hits}/><ImpactRow label="Industrial / commercial" value={obs.industrial_commercial_landuse_hits}/><ImpactRow label="Legal ownership" value="Needs RoR"/></dl></div>
        </div> : <div className="route-coverage-warning"><span><Database size={20}/></span><div><strong>Mapped obstacle data could not be verified for this candidate.</strong><p>SRTM terrain is still used when available. Structure and sensitive-feature values stay blank instead of being replaced with invented zeroes.</p></div><small>Retry later or connect a managed/self-hosted OSM/Overpass source.</small></div>}
      </section>

      {analysis.official_road_reference && <section className="panel route-official-reference route-official-reference-v3">
        <span className="route-official-icon"><Landmark size={19}/></span>
        <div className="route-official-copy"><span className="route-section-kicker">Official corridor context</span><h3>{analysis.official_road_reference.road_name}</h3><p>{trimWords(analysis.official_road_reference.note, 18)}</p></div>
        <div className="route-official-stats"><span><small>Category</small><b>{analysis.official_road_reference.category}</b></span><span><small>Listed length</small><b>{analysis.official_road_reference.official_length_km.toFixed(3)} km</b></span><a className="button secondary" href={analysis.official_road_reference.source_url} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Official source</a></div>
      </section>}

      <section className="panel route-comparison-panel route-comparison-panel-v3">
        <div className="route-section-header">
          <div><span className="route-section-kicker"><Gauge size={14}/> Candidate comparison</span><h3>Compare every screened alignment</h3><p>Select any row to inspect it on the map. Lower burden and cost index are preferable within this screening model.</p></div>
          <span className="route-comparison-hint">Evidence-adjusted score · capped below 100 · missing live layers reduce confidence</span>
        </div>
        <div className="route-comparison-table-wrap"><table className="route-comparison-table route-comparison-table-v3"><thead><tr><th>Candidate</th><th>Distance</th><th>Screening score</th><th>Burden</th><th>Terrain</th><th>Structures</th><th>Sensitive</th><th>Water</th><th>Forest</th><th>Cost index</th></tr></thead><tbody>{analysis.candidates.map(candidate=>{
          const o=candidate.obstacle_summary; const t=candidate.terrain_summary; const recommended=candidate.route_id===analysis.recommended_route_id; const active=candidate.route_id===selected.route_id; const verified=(candidate.data_coverage_percent||0)>=55;
          return <tr key={candidate.route_id} className={`${recommended?'recommended':''} ${active?'active':''}`} onClick={()=>setSelectedRouteId(candidate.route_id)}><td><div className="route-table-candidate"><span/><div><strong>{candidate.label}</strong><small>{recommended?'Preferred candidate':'Alternative'}</small></div></div></td><td>{fmt(candidate.distance_km,2)} km</td><td><div className="route-table-score"><b>{fmt(candidate.feasibility_score,0)}</b><span><i style={{width:`${pct(candidate.feasibility_score)}%`}}/></span></div></td><td>{fmt(candidate.route_burden_score,0)}/100</td><td>{t?.available?`${fmt(t.mean_abs_grade_percent,2)}%`:'—'}</td><td>{verified?o.mapped_buildings:'—'}</td><td>{verified?(o.schools+o.healthcare+o.religious):'—'}</td><td>{verified?o.water_crossings:'—'}</td><td>{verified?o.forest_protected_hits:'—'}</td><td>{fmt(candidate.comparative_cost_index,0)}</td></tr>;
        })}</tbody></table></div>
      </section>

      <section className="route-information-grid route-information-grid-v3">
        <aside className="panel route-ai-brief route-ai-brief-v3">
          <div className="route-section-header"><div><span className="route-section-kicker"><BrainCircuit size={14}/> Quick review</span><h3>What deserves attention</h3><p>Short officer-ready takeaways for the selected corridor.</p></div></div>
          <div className="route-insight-list route-insight-list-compact">{quickReview.map((item,index)=><article key={index} className="route-insight"><b>{index+1}</b><div><strong>{item.title}</strong><p>{item.body}</p></div></article>)}</div>
          <div className="route-source-note route-source-note-compact">
            <div><Database size={15}/><strong>Live-data status</strong></div>
            <div className="route-provider-facts">{providerFacts.map((fact,index)=><span key={index}>{fact}</span>)}</div>
            <div className="route-source-tags">{sourceChips.map((source,index)=><small key={index}>{source}</small>)}</div>
          </div>
        </aside>

        <aside className="panel route-readiness route-readiness-v3">
          <div className="route-section-header"><div><span className="route-section-kicker"><CheckCircle2 size={14}/> Acquisition readiness</span><h3>Official data still required</h3><p>Shortlist the datasets and field checks still needed before approval.</p></div></div>
          <div className="route-readiness-list">{readinessItems.map((item,index)=><article key={index}><span>{item.index+1}</span><div><strong>{item.title}</strong><p>{item.body}</p></div></article>)}</div>
          <details className="route-limitations-details"><summary><ShieldAlert size={15}/> Show screening limitations</summary><div>{analysis.limitations.map((item,index)=><p key={index}><span>•</span>{trimWords(item, 22)}</p>)}</div></details>
        </aside>
      </section>
    </>}
  </>;
}
