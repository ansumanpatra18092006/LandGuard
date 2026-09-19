import { useEffect, useMemo, useState } from 'react';
import { BrainCircuit, Gauge, ShieldAlert, ClipboardCheck, Play, TriangleAlert, Database, History, SlidersHorizontal, TrendingUp, Sparkles, ChevronDown, Target, Activity, Route, Layers3 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { SectionCard } from '../common';
import { api } from '../../services/api';
import InterventionSimulator from './InterventionSimulator';

const readinessLabel = score => score >= 80 ? 'READY' : score < 50 ? 'BLOCKED' : 'PARTIALLY READY';

export default function IntelligencePanel({project}) {
  const projectId = project.project_id;
  const [status,setStatus]=useState(null);
  const [prediction,setPrediction]=useState(null);
  const [scenario,setScenario]=useState(null);
  const [busy,setBusy]=useState(false);
  const [scenarioBusy,setScenarioBusy]=useState(false);
  const [simulatorOpen,setSimulatorOpen]=useState(false);
  const [error,setError]=useState('');
  const initialRatio = useMemo(() => project.original_cost_crore > 0 && project.expenditure_crore != null
    ? Math.max(0, Math.min(150, Math.round((project.expenditure_crore/project.original_cost_crore)*100))) : 50,
    [project.original_cost_crore,project.expenditure_crore]);
  const [scenarioRatio,setScenarioRatio]=useState(initialRatio);
  const initialDays = useMemo(() => {
    if (!project.original_end_date) return 180;
    const ms = new Date(project.original_end_date).getTime() - Date.now();
    if (!Number.isFinite(ms)) return 180;
    return Math.max(-365, Math.min(730, Math.round(ms/86400000)));
  }, [project.original_end_date]);
  const [scenarioDays,setScenarioDays]=useState(initialDays);
  useEffect(() => { setScenarioRatio(initialRatio); setScenarioDays(initialDays); setScenario(null); }, [projectId, initialRatio, initialDays]);

  const missing = [['original_cost_crore','original approved cost'],['expenditure_crore','cumulative expenditure'],['original_end_date','original completion date']]
    .filter(([key]) => project[key] == null || project[key] === '');

  async function run() {
    setBusy(true); setError(''); setScenario(null);
    try {
      const model = await api('/model/status'); setStatus(model);
      if (!model.available) return;
      setPrediction(await api(`/projects/${projectId}/predict`,{method:'POST'}));
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function runScenario() {
    setScenarioBusy(true); setError('');
    try {
      setScenario(await api(`/projects/${projectId}/scenario`,{
        method:'POST', body:JSON.stringify({ expenditure_to_original_cost_pct:Number(scenarioRatio), days_to_original_deadline:Number(scenarioDays) })
      }));
    } catch (err) { setError(err.message); }
    finally { setScenarioBusy(false); }
  }

  const unavailable = status && !status.available;
  const cannotRun = missing.length > 0;
  const slippedCount = prediction?.similar_cases?.filter(c=>c.slipped_within_3_months).length ?? 0;
  const sameSectorCount = prediction?.similar_cases?.filter(c=>c.same_sector).length ?? 0;
  const maxContribution = Math.max(...(prediction?.factors?.map(f=>Number(f.contribution)||0) ?? [0]), 0.0001);
  const impactLabel = value => {
    const share = Number(value)/maxContribution;
    return share >= 0.65 ? 'Strong' : share >= 0.30 ? 'Moderate' : 'Smaller';
  };
  const frictionComponents = prediction?.acquisition_friction?.components || [];
  const topFriction = [...frictionComponents].sort((a,b)=>(b.score*b.weight)-(a.score*a.weight)).slice(0,3);

  return <SectionCard
    title="Land acquisition intelligence"
    description="Acquisition-specific operational risk first; independent PAIMANA ML schedule evidence second."
    action={<button className="button secondary" onClick={run} disabled={busy || cannotRun}><Play size={14}/>{busy?'Running…':prediction?'Refresh intelligence':'Run intelligence'}</button>}
    className="intelligence intelligence-v2"
  >
    {cannotRun && <div className="model-disclaimer"><Database size={17}/><p><strong>PAIMANA baseline incomplete.</strong> Add {missing.map(([,label])=>label).join(', ')} to activate the independent ML schedule signal. The acquisition-specific operational layer remains separate. <Link to={`/projects/${projectId}/edit`}>Edit project</Link></p></div>}
    {!prediction && <div className="intelligence-intro"><BrainCircuit size={27}/><div><h3>{unavailable?'No trained schedule model loaded':cannotRun?'Acquisition intelligence available; ML baseline incomplete':'Run the complete evidence view'}</h3><p>{unavailable ? status.disclaimer : cannotRun ? 'LandGuard can still reason over acquisition conditions, while the real-data PAIMANA model needs its own schedule/cost inputs.' : 'Run intelligence to combine acquisition-specific operational risk with an independent three-month PAIMANA schedule signal.'}</p>{error && <p className="form-error">{error}</p>}</div></div>}

    {prediction ? <>
      <section className="la-command-hero">
        <div className="la-command-main">
          <span className="eyebrow"><Target size={14}/> PRIMARY DECISION SIGNAL</span>
          <div className="la-risk-number"><strong>{prediction.acquisition_delay_risk?.score ?? '—'}</strong><span>/100</span></div>
          <h2>{prediction.acquisition_delay_risk?.label || '—'} acquisition delay risk</h2>
          <p>{prediction.acquisition_delay_risk?.methodology?.split('. ')[0]}.</p>
          <div className="la-primary-actions"><button className="button primary" onClick={()=>setSimulatorOpen(true)}><Sparkles size={15}/>Simulate intervention</button><Link className="button secondary" to={`/projects/${projectId}?tab=interventions`}><ClipboardCheck size={15}/>Track action</Link></div>
        </div>
        <div className="la-command-side">
          <article><span>Intervention priority</span><strong>{prediction.intervention_priority_score}/100</strong><small>{prediction.intervention_priority_category} · LA risk establishes the base; schedule evidence can only escalate it</small></article>
          <article><span>Acquisition readiness</span><strong>{prediction.acquisition_readiness_score}/100</strong><small>{readinessLabel(prediction.acquisition_readiness_score)}</small></article>
          <article className="blocker-card"><span>Primary bottleneck</span><strong>{prediction.acquisition_friction?.dominant_blocker || '—'}</strong><small>{prediction.acquisition_delay_risk?.stage_attention || 'Review recorded acquisition conditions.'}</small></article>
        </div>
      </section>

      <section className="la-why-card">
        <div className="advanced-ai-heading"><Route size={18}/><div><h3>Why this acquisition needs attention</h3><p>Recorded operational factors, not ML attribution.</p></div></div>
        <div className="la-factor-rail">
          {topFriction.map((c,i)=><article key={c.key}><span className="rank-dot">{i+1}</span><div><strong>{c.label}</strong><small>{c.note}</small></div><b>{c.score}/100</b></article>)}
        </div>
        <div className="la-state-strip">
          <span>Compensation <strong>{Math.round(project.compensation_completion_pct || 0)}%</strong></span>
          <span>Possession <strong>{Math.round(project.possession_pct || 0)}%</strong></span>
          <span>R&amp;R <strong>{Math.round(project.rehabilitation_completion_pct || 0)}%</strong></span>
          <span>Pending approvals <strong>{project.pending_approvals || 0}</strong></span>
          <span>Legal disputes <strong>{project.legal_disputes || 0}</strong></span>
        </div>
      </section>

      <section className="ml-support-card">
        <div className="ml-support-heading"><div><span className="eyebrow"><Activity size={14}/> INDEPENDENT ML EARLY WARNING</span><h3>PAIMANA 3-month schedule signal</h3></div><div className={`ml-signal-pill ${(prediction.risk_category||'low').toLowerCase()}`}><strong>{Math.round(prediction.delay_probability*100)}%</strong><span>{prediction.risk_category}</span></div></div>
        <p>Trained on real longitudinal MoSPI PAIMANA project histories. This signal does not use compensation, possession, R&amp;R, approvals, legal disputes or stakeholder response.</p>
        <div className="ml-support-meta"><span>{prediction.metadata.data_period}</span><span>{prediction.metadata.target_definition}</span><span>{prediction.metadata.calibration_method || 'Raw model probability'}</span></div>
      </section>

      <div className="intervention-launch-strip"><div><Sparkles size={20}/><span><strong>Intervention Simulator</strong><small>Test administrative actions against acquisition risk, friction, readiness and priority. PAIMANA model sensitivity remains a separate lane.</small></span></div><button className="button primary" onClick={()=>setSimulatorOpen(true)}>Launch full-screen simulator</button></div>

      <div className="intelligence-results intelligence-results-v2">
        <div><h3>Why the PAIMANA schedule signal is {prediction.risk_category?.toLowerCase()}</h3>{prediction.factors.length ? prediction.factors.map(f=><article key={f.feature}><span className={`factor-direction ${f.direction}`}>{f.direction==='increases_risk'?'↑':'↓'}</span><div><strong>{f.display_name}</strong><small>{impactLabel(f.contribution)} {f.direction==='increases_risk'?'upward':'downward'} influence · relative SHAP contribution, not probability points</small></div></article>) : <p className="muted">No dominant model contribution detected.</p>}</div>
        <div><h3>Recommended administrative review</h3>{prediction.recommendations.map((r,i)=><article key={i}><ClipboardCheck size={17}/><div><strong>{r.action}</strong><small>{r.rationale}</small></div></article>)}<Link className="button secondary intervention-track-link" to={`/projects/${projectId}?tab=interventions`}>Track these actions</Link></div>
      </div>

      <div className="advanced-intelligence-grid">
        <section className="advanced-ai-block">
          <div className="advanced-ai-heading"><History size={18}/><div><h3>Historical analogues</h3><p>Nearest PAIMANA cases in model-feature space. The similarity value is a closeness score, not a probability.</p></div></div>
          {prediction.similar_cases?.length ? <>
            <div className="analogue-summary"><strong>{slippedCount}/{prediction.similar_cases.length}</strong><span>nearest historical cases slipped within 3 months · {sameSectorCount}/{prediction.similar_cases.length} same sector</span></div>
            <div className="analogue-list">{prediction.similar_cases.map(c=><article key={`${c.project_code}-${c.snapshot_month}`}>
              <div><strong>PAIMANA {c.project_code}</strong><small>{c.sector_name} · {c.snapshot_month} · {c.same_sector?'Same-sector precedent':'Cross-sector fallback'}</small></div>
              <div className="analogue-metrics"><span>Similarity score {(c.similarity_pct/100).toFixed(2)}</span><span className={`analogue-outcome ${c.slipped_within_3_months?'slipped':'stable'}`}>{c.slipped_within_3_months?'Slipped':'Stable'}</span></div>
            </article>)}</div>
          </> : <p className="muted">Historical analogue data unavailable.</p>}
        </section>

        <section className="advanced-ai-block">
          <div className="advanced-ai-heading"><SlidersHorizontal size={18}/><div><h3>PAIMANA model sensitivity</h3><p>Optional two-variable sensitivity test. Not an administrative intervention and not a causal promise.</p></div></div>
          <label className="scenario-control"><span>Hypothetical expenditure progress <strong>{scenarioRatio}%</strong> <small>(current ≈ {initialRatio}%)</small></span><input type="range" min="0" max="120" step="1" value={scenarioRatio} onChange={e=>setScenarioRatio(e.target.value)}/></label>
          <label className="scenario-control"><span>Assumed days to original deadline <strong>{scenarioDays}</strong> <small>(current ≈ {initialDays})</small></span><input type="range" min="-365" max="730" step="5" value={scenarioDays} onChange={e=>setScenarioDays(e.target.value)}/></label>
          <button className="button secondary scenario-button" onClick={runScenario} disabled={scenarioBusy}>{scenarioBusy?'Simulating…':'Run model sensitivity'}</button>
          {scenario && <div className="scenario-result"><TrendingUp size={18}/><div><span>PAIMANA schedule signal</span><strong>{Math.round(scenario.base_probability*100)}% → {Math.round(scenario.scenario_probability*100)}%</strong><small>{scenario.probability_change>0?'+':''}{Math.round(scenario.probability_change*100)} pts · {scenario.base_risk_category} → {scenario.scenario_risk_category}</small></div></div>}
          {scenario && <p className="scenario-note">{scenario.note}</p>}
        </section>
      </div>

      <details className="evidence-disclosure">
        <summary><Layers3 size={16}/> Evidence & methodology <ChevronDown size={16}/></summary>
        <div className="evidence-disclosure-body">
          <div className="model-card-honesty">
            <div><span className="eyebrow">MODEL EVIDENCE CARD</span><h3>{prediction.metadata.model_role || 'PAIMANA central-infrastructure schedule-slip baseline'}</h3></div>
            <div className="model-card-grid"><span><small>ML uses LA operational factors?</small><strong>{prediction.metadata.land_acquisition_features_used ? 'YES' : 'NO'}</strong></span><span><small>ML role</small><strong>Early-warning schedule signal</strong></span><span><small>LA factors</small><strong>Separate operational lane</strong></span><span><small>Decision authority</small><strong>Authorized officer</strong></span></div>
            <p>{prediction.metadata.operational_lane_note}</p><p className="model-validity-caveat">{prediction.metadata.validation_caveat}</p>
          </div>
          <div className="friction-breakdown acquisition-risk-breakdown"><div className="advanced-ai-heading"><ShieldAlert size={18}/><div><h3>Acquisition Delay Risk methodology</h3><p>{prediction.acquisition_delay_risk?.methodology}</p></div></div><div className="friction-component-grid">{prediction.acquisition_delay_risk?.drivers?.map(c=><article key={c.key}><span>{c.label}</span><strong>{c.score}/100</strong><small>{Math.round(c.weight*100)}% weight · {c.note}</small></article>)}</div></div>
          <div className="friction-breakdown"><div className="advanced-ai-heading"><ShieldAlert size={18}/><div><h3>Land-Acquisition Friction methodology</h3><p>{prediction.acquisition_friction?.methodology}</p></div></div><div className="friction-component-grid">{frictionComponents.map(c=><article key={c.key}><span>{c.label}</span><strong>{c.score}/100</strong><small>{Math.round(c.weight*100)}% weight · {c.note}</small></article>)}</div></div>
          {prediction.delay_outlook && <div className="advanced-impact-estimate"><TriangleAlert size={17}/><div><strong>Advanced conditional severity estimate</strong><p>Rough extension if a schedule slip occurs: ~{prediction.delay_outlook.expected_extension_days} days, with a wide {prediction.delay_outlook.likely_range_low_days}–{prediction.delay_outlook.likely_range_high_days} day uncertainty range.</p><small>{prediction.delay_outlook.conditional_note}</small></div></div>}
          <div className="model-disclaimer"><TriangleAlert size={17}/><p><strong>{prediction.metadata.training_data_kind}</strong> · {prediction.metadata.disclaimer}<br/><small>{prediction.metadata.test_split} · {prediction.metadata.explanation_method}</small></p></div>
        </div>
      </details>

      {error && <p className="form-error intelligence-error">{error}</p>}
      <InterventionSimulator open={simulatorOpen} onClose={()=>setSimulatorOpen(false)} project={project} prediction={prediction}/>
    </> : !unavailable && !cannotRun && <div className="intelligence-slots">{[[ShieldAlert,'Acquisition delay risk','Transparent land-acquisition-specific operational risk index.'],[Gauge,'PAIMANA schedule signal','Independent three-month schedule early-warning signal.'],[ClipboardCheck,'Intervention priority','Acquisition risk establishes the base; schedule evidence can escalate it.'],[History,'Evidence trail','Explanations, historical analogues and tracked actions remain separate and auditable.']].map(([Icon,title,description])=><div key={title}><Icon size={21}/><strong>{title}</strong><p>{description}</p><small>Run to inspect</small></div>)}</div>}
  </SectionCard>;
}
