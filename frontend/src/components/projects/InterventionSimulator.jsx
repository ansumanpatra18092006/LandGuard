import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, CheckCircle2, Gauge, ShieldAlert, Sparkles, X, Activity, Target } from 'lucide-react';
import { api } from '../../services/api';

function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }
function priorityClass(value) { return String(value || 'ROUTINE').toLowerCase(); }

function ScoreRing({ value, label, sublabel, kind='priority' }) {
  const pct = clamp(Math.round(Number(value || 0)), 0, 100);
  return <div className={`intervention-gauge ${kind}`} style={{'--risk-pct':`${pct * 3.6}deg`}}>
    <div><span>{label}</span><strong>{pct}</strong><small>{sublabel}</small></div>
  </div>;
}

export default function InterventionSimulator({ open, onClose, project, prediction }) {
  const originalCost = Number(project?.original_cost_crore || 0);
  const currentExpenditure = Number(project?.expenditure_crore || 0);
  const currentRatio = originalCost > 0 ? clamp(Math.round(currentExpenditure / originalCost * 100), 0, 150) : 0;
  const currentDays = useMemo(() => {
    if (!project?.original_end_date) return 0;
    return Math.round((new Date(`${project.original_end_date}T00:00:00`) - new Date()) / 86400000);
  }, [project?.original_end_date]);

  const currentComp = Math.round(Number(project?.compensation_completion_pct || 0));
  const currentPoss = Math.round(Number(project?.possession_pct || 0));
  const currentRr = Math.round(Number(project?.rehabilitation_completion_pct || 0));
  const currentResponse = Math.round(Number(project?.stakeholder_response_days || 0));

  const [ratio,setRatio] = useState(currentRatio);
  const [days,setDays] = useState(currentDays);
  const [clearApprovals,setClearApprovals] = useState(false);
  const [resolveLegal,setResolveLegal] = useState(false);
  const [compTarget,setCompTarget] = useState(currentComp);
  const [possTarget,setPossTarget] = useState(currentPoss);
  const [rrTarget,setRrTarget] = useState(currentRr);
  const [responseTarget,setResponseTarget] = useState(currentResponse);
  const [scenario,setScenario] = useState(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setRatio(currentRatio); setDays(currentDays);
    setClearApprovals(false); setResolveLegal(false);
    setCompTarget(currentComp); setPossTarget(currentPoss); setRrTarget(currentRr); setResponseTarget(currentResponse);
    setScenario(null); setError('');
  }, [open, currentRatio, currentDays, currentComp, currentPoss, currentRr, currentResponse, project?.project_id]);

  if (!open || !project || !prediction) return null;

  async function simulate() {
    setBusy(true); setError('');
    try {
      setScenario(await api(`/projects/${project.project_id}/scenario`, {
        method:'POST',
        body:JSON.stringify({
          expenditure_to_original_cost_pct:Number(ratio),
          days_to_original_deadline:Number(days),
          clear_pending_approvals:clearApprovals,
          resolve_legal_disputes:resolveLegal,
          compensation_target_pct:Number(compTarget),
          possession_target_pct:Number(possTarget),
          rehabilitation_target_pct:Number(rrTarget),
          stakeholder_response_target_days:Number(responseTarget),
        })
      }));
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  const basePriority = scenario?.base_priority_score ?? prediction.intervention_priority_score;
  const basePriorityCategory = scenario?.base_priority_category ?? prediction.intervention_priority_category;
  const nextPriority = scenario?.scenario_priority_score ?? basePriority;
  const nextPriorityCategory = scenario?.scenario_priority_category ?? basePriorityCategory;
  const baseFriction = scenario?.base_friction?.score ?? prediction.acquisition_friction?.score ?? 0;
  const nextFriction = scenario?.scenario_friction?.score ?? baseFriction;
  const baseAcquisitionRisk = scenario?.base_acquisition_delay_risk?.score ?? prediction.acquisition_delay_risk?.score ?? 0;
  const nextAcquisitionRisk = scenario?.scenario_acquisition_delay_risk?.score ?? baseAcquisitionRisk;
  const baseReadiness = scenario?.base_readiness_score ?? prediction.acquisition_readiness_score ?? 0;
  const nextReadiness = scenario?.scenario_readiness_score ?? baseReadiness;
  const scenarioProbability = scenario?.scenario_probability ?? prediction.delay_probability;

  return <div className="intervention-simulator" role="dialog" aria-modal="true" aria-label="Intervention priority simulator">
    <div className="intervention-topbar">
      <div><span className="eyebrow">LANDGUARD INTERVENTION PRIORITY SIMULATOR</span><h1>{project.project_name}</h1><p>{project.project_id} · {project.district}, {project.state}</p></div>
      <button className="simulator-close" onClick={onClose} aria-label="Close intervention simulator"><X size={22}/></button>
    </div>

    <div className="intervention-stage priority-stage">
      <section className="intervention-comparison current">
        <span className="intervention-label">CURRENT ADMINISTRATIVE STATE</span>
        <div className={`priority-hero ${priorityClass(basePriorityCategory)}`}><strong>{basePriority}</strong><span>/100</span><small>{basePriorityCategory} intervention priority</small></div>
        <div className="intervention-facts"><span>Acquisition delay risk <strong>{baseAcquisitionRisk}/100</strong></span><span>Schedule signal <strong>{Math.round(prediction.delay_probability*100)}%</strong></span><span>LA friction <strong>{baseFriction}/100</strong></span><span>Readiness <strong>{baseReadiness}/100</strong></span></div>
      </section>

      <div className="intervention-arrow"><Sparkles size={22}/><ArrowRight size={34}/><span>TEST ACTIONS</span></div>

      <section className="intervention-comparison scenario">
        <span className="intervention-label">SCENARIO ADMINISTRATIVE STATE</span>
        <div className={`priority-hero ${priorityClass(nextPriorityCategory)}`}><strong>{nextPriority}</strong><span>/100</span><small>{nextPriorityCategory} intervention priority</small></div>
        <div className="intervention-facts"><span>Acquisition delay risk <strong>{nextAcquisitionRisk}/100</strong></span><span>Schedule signal <strong>{Math.round(scenarioProbability*100)}%</strong></span><span>Readiness <strong>{nextReadiness}/100</strong></span><span>Change in priority <strong>{scenario ? `${nextPriority-basePriority > 0 ? '+' : ''}${nextPriority-basePriority}` : '—'}</strong></span></div>
      </section>
    </div>

    <div className="intervention-controls-grid">
      <section className="intervention-control-panel operational intervention-primary-lane">
        <div className="intervention-section-heading"><ShieldAlert size={18}/><div><h2>Administrative action lane</h2><p>These controls change acquisition-delay risk, friction, readiness and officer priority — not the PAIMANA ML probability.</p></div></div>
        <div className="intervention-actions">
          {(project.pending_approvals || 0) > 0 && <label className={clearApprovals?'selected':''}><input type="checkbox" checked={clearApprovals} onChange={e=>setClearApprovals(e.target.checked)}/><CheckCircle2 size={17}/><span>Clear {project.pending_approvals} pending approval{project.pending_approvals===1?'':'s'}</span></label>}
          {(project.legal_disputes || 0) > 0 && <label className={resolveLegal?'selected':''}><input type="checkbox" checked={resolveLegal} onChange={e=>setResolveLegal(e.target.checked)}/><CheckCircle2 size={17}/><span>Resolve {project.legal_disputes} recorded legal dispute{project.legal_disputes===1?'':'s'}</span></label>}
        </div>
        <label><span>Compensation target <strong>{compTarget}%</strong> <small>current {currentComp}%</small></span><input type="range" min={currentComp} max="100" value={compTarget} onChange={e=>setCompTarget(Number(e.target.value))}/></label>
        <label><span>Possession target <strong>{possTarget}%</strong> <small>current {currentPoss}%</small></span><input type="range" min={currentPoss} max="100" value={possTarget} onChange={e=>setPossTarget(Number(e.target.value))}/></label>
        <label><span>R&amp;R target <strong>{rrTarget}%</strong> <small>current {currentRr}%</small></span><input type="range" min={currentRr} max="100" value={rrTarget} onChange={e=>setRrTarget(Number(e.target.value))}/></label>
        <label><span>Stakeholder response target <strong>{responseTarget}d</strong> <small>current {currentResponse}d</small></span><input type="range" min="0" max={Math.max(45,currentResponse)} value={responseTarget} onChange={e=>setResponseTarget(Number(e.target.value))}/></label>
      </section>

      <section className="intervention-control-panel model-lane">
        <div className="intervention-section-heading"><Gauge size={18}/><div><h2>Separate model-sensitivity lane</h2><p>Optional. These are PAIMANA model inputs, not administrative promises.</p></div></div>
        <label><span>Expenditure progress <strong>{ratio}%</strong></span><input type="range" min="0" max="120" value={ratio} onChange={e=>setRatio(Number(e.target.value))}/></label>
        <label><span>Days to original deadline <strong>{days}</strong></span><input type="range" min="-365" max="730" step="5" value={days} onChange={e=>setDays(Number(e.target.value))}/></label>
        <div className="intervention-separation"><strong>Evidence stays separate</strong><span><Activity size={14}/> ML schedule signal: {Math.round(prediction.delay_probability*100)}% → {Math.round(scenarioProbability*100)}%</span><span><Target size={14}/> Acquisition delay risk: {baseAcquisitionRisk} → {nextAcquisitionRisk}</span><span>Acquisition friction: {baseFriction} → {nextFriction}</span><span>Administrative actions never masquerade as learned causal effects.</span></div>
      </section>
    </div>

    <div className="simulator-run-row"><button className="button primary intervention-run" onClick={simulate} disabled={busy}>{busy ? 'Recalculating…' : 'Recalculate acquisition priority'}</button>{scenario && <div className={`priority-delta ${nextPriority <= basePriority ? 'improved' : 'worsened'}`}><strong>{basePriority} → {nextPriority}</strong><span>{basePriorityCategory} → {nextPriorityCategory}</span></div>}</div>
    {error && <p className="form-error">{error}</p>}
    {scenario && <div className="scenario-method-notes"><p>{scenario.operational_note}</p><p>{scenario.note}</p></div>}
    <footer className="intervention-footer"><span>Acquisition delay risk, friction and readiness are transparent prototype indices, not trained probabilities or government-standard scores.</span><strong>AI recommends; authorized officials decide.</strong></footer>
  </div>;
}
