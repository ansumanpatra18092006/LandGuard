import { useMemo, useState } from 'react';
import { Activity, ArrowDown, Check, CircleDot, ClipboardCopy, FileText, Gauge, Play, Printer, Sparkles, TriangleAlert } from 'lucide-react';
import { api } from '../../services/api';
import { useResource } from '../../hooks/useResource';

const STAGES = ['NOTIFICATION','SURVEY','VALUATION','COMPENSATION','REHABILITATION','POSSESSION','COMPLETED'];
const LABELS = {
  NOTIFICATION:'Notification', SURVEY:'Survey', VALUATION:'Valuation / award',
  COMPENSATION:'Compensation', REHABILITATION:'Rehabilitation', POSSESSION:'Possession', COMPLETED:'Handover ready'
};

function pct(v){ return Math.max(0,Math.min(100,Math.round(Number(v)||0))); }
function issueCount(p){ return Number(p.pending_approvals||0)+Number(p.legal_disputes||0); }
function deriveBottleneck(p){
  if (Number(p.legal_disputes||0)>0) return {name:'Legal resolution', detail:`${p.legal_disputes} recorded dispute${p.legal_disputes===1?'':'s'} may constrain downstream clearance.`, cascade:['Legal resolution','Compensation / possession','Site handover']};
  if (Number(p.pending_approvals||0)>0) return {name:'Approval clearance', detail:`${p.pending_approvals} approval${p.pending_approvals===1?' is':'s are'} still pending.`, cascade:['Administrative clearance','Acquisition progression','Site handover']};
  if (pct(p.compensation_completion_pct)<70) return {name:'Compensation', detail:`Compensation is ${pct(p.compensation_completion_pct)}% complete.`, cascade:['Compensation','Possession readiness','Site handover']};
  if (pct(p.possession_pct)<70) return {name:'Possession', detail:`Possession is ${pct(p.possession_pct)}% complete.`, cascade:['Possession','Site handover','Execution readiness']};
  if (pct(p.rehabilitation_completion_pct)<70) return {name:'Rehabilitation', detail:`Rehabilitation is ${pct(p.rehabilitation_completion_pct)}% complete.`, cascade:['Rehabilitation','Handover readiness','Execution readiness']};
  return {name:'No dominant recorded bottleneck', detail:'Recorded acquisition indicators are comparatively advanced.', cascade:['Acquisition controls','Handover readiness','Execution readiness']};
}

function stageState(project, stage){
  const current = STAGES.indexOf(project.acquisition_stage);
  const index = STAGES.indexOf(stage);
  if (stage==='COMPENSATION') return pct(project.compensation_completion_pct)>=100?'done':pct(project.compensation_completion_pct)>0?'active':index<current?'done':'pending';
  if (stage==='REHABILITATION') return pct(project.rehabilitation_completion_pct)>=100?'done':pct(project.rehabilitation_completion_pct)>0?'active':index<current?'done':'pending';
  if (stage==='POSSESSION') return pct(project.possession_pct)>=100?'done':pct(project.possession_pct)>0?'active':index<current?'done':'pending';
  if (index<current || project.acquisition_stage==='COMPLETED') return 'done';
  if (index===current) return 'active';
  return 'pending';
}

function stageValue(project, stage){
  if(stage==='COMPENSATION') return `${pct(project.compensation_completion_pct)}%`;
  if(stage==='REHABILITATION') return `${pct(project.rehabilitation_completion_pct)}%`;
  if(stage==='POSSESSION') return `${pct(project.possession_pct)}%`;
  return stageState(project,stage)==='done'?'Complete':stageState(project,stage)==='active'?'Current stage':'Pending';
}

function buildBrief(project,prediction,bottleneck){
  if(!prediction) return '';
  const prob=Math.round(prediction.delay_probability*100);
  const outlook=prediction.delay_outlook;
  const analogues=prediction.similar_cases||[];
  const slipped=analogues.filter(x=>x.slipped_within_3_months).length;
  const top=prediction.factors?.[0]?.display_name;
  const recommendations=(prediction.recommendations||[]).slice(0,3).map(x=>x.action).join('; ');
  return `${project.project_name} (${project.project_id}) — Officer Review Brief\n\nLandGuard estimates a ${prob}% probability of a reported schedule extension within the next three months (${prediction.risk_category} predictive risk). ${outlook?`If slippage occurs, the duration model estimates an indicative extension of approximately ${outlook.expected_extension_days} days, with expected delay exposure of about ${outlook.expected_delay_exposure_days} days. `:''}${top?`The strongest local model influence is ${top}. `:''}${analogues.length?`${slipped} of ${analogues.length} retrieved historical PAIMANA analogues experienced schedule slippage within the prediction horizon. `:''}\n\nAcquisition process attention point: ${bottleneck.name}. ${bottleneck.detail}\n\nRecorded operational indicators: ${project.pending_approvals} pending approvals; ${project.legal_disputes} legal disputes; compensation ${pct(project.compensation_completion_pct)}%; possession ${pct(project.possession_pct)}%; rehabilitation ${pct(project.rehabilitation_completion_pct)}%.${recommendations?`\n\nRecommended administrative review: ${recommendations}.`:''}\n\nDecision-support note: predictive outputs are model estimates; operational indicators are separately recorded project conditions. Authorized officials decide.`;
}

export default function ProjectDigitalTwin({project}){
  const [prediction,setPrediction]=useState(null); const [busy,setBusy]=useState(false); const [error,setError]=useState(''); const [copied,setCopied]=useState(false);
  const {data:readiness}=useResource(`readiness-${project.project_id}`,signal=>api(`/projects/${project.project_id}/readiness`,{signal}),project.updated_at);
  const missing=['original_cost_crore','expenditure_crore','original_end_date'].filter(k=>project[k]==null||project[k]==='');
  const bottleneck=useMemo(()=>deriveBottleneck(project),[project]);
  const fallbackReadiness = pct(project.possession_pct)<60 || pct(project.compensation_completion_pct)<60 ? 'BLOCKED' : issueCount(project)>0 || pct(project.possession_pct)<90 ? 'CONSTRAINED' : 'READY';
  const readinessLabel = readiness?.readiness_label || fallbackReadiness;
  const brief=buildBrief(project,prediction,bottleneck);
  async function run(){setBusy(true);setError('');try{setPrediction(await api(`/projects/${project.project_id}/predict`,{method:'POST'}));}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function copy(){try{await navigator.clipboard.writeText(brief);setCopied(true);setTimeout(()=>setCopied(false),1800);}catch{setError('Could not copy the brief in this browser.');}}
  function printBrief(){const w=window.open('','_blank','width=850,height=900'); if(!w)return; w.document.write(`<html><head><title>${project.project_id} Officer Brief</title><style>body{font:15px/1.6 system-ui;padding:42px;white-space:pre-wrap;color:#14211d}h1{font-size:22px}</style></head><body><h1>LandGuard Officer Review Brief</h1>${brief.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')}</body></html>`);w.document.close();w.print();}
  return <section className="digital-twin-shell">
    <div className="digital-twin-head"><div><span className="eyebrow">LAND ACQUISITION PROCESS TWIN</span><h2>See the process, the bottleneck and what may break next.</h2><p>A live acquisition-process view built from the project record. Dependency logic is operational workflow logic; predictive risk comes separately from the PAIMANA-trained models.</p></div><button className="button primary" onClick={run} disabled={busy||missing.length>0}><Play size={15}/>{busy?'Computing…':prediction?'Refresh outlook':'Activate predictive twin'}</button></div>
    {missing.length>0&&<div className="twin-warning"><TriangleAlert size={17}/> Add the PAIMANA model baseline fields before predictive outlook can be overlaid.</div>}
    <div className="digital-twin-grid">
      <div className="twin-process">
        {STAGES.map((stage,index)=>{const state=stageState(project,stage);return <div className={`twin-stage ${state}`} key={stage}><div className="twin-node">{state==='done'?<Check size={15}/>:state==='active'?<CircleDot size={15}/>:<span>{index+1}</span>}</div><div><strong>{LABELS[stage]}</strong><small>{stageValue(project,stage)}</small></div>{index<STAGES.length-1&&<div className="twin-line"/>}</div>})}
      </div>
      <div className="twin-intelligence">
        {readiness&&<div className={`readiness-card ${readiness.readiness_label.toLowerCase()}`}><div className="readiness-score"><strong>{readiness.readiness_score}</strong><span>/100</span></div><div><span className="eyebrow">ACQUISITION READINESS</span><h3>{readiness.readiness_label}</h3><p><b>Primary blocker:</b> {readiness.primary_blocker}</p><p><b>Next milestone:</b> {readiness.next_milestone}</p></div><div className="readiness-components">{readiness.components.map(c=><div key={c.key}><span>{c.label}</span><strong>{c.score}%</strong><i><em style={{width:`${c.score}%`}}/></i></div>)}</div><small>{readiness.methodology}</small></div>}
        <div className="twin-bottleneck"><span>PRIMARY ATTENTION POINT</span><strong>{bottleneck.name}</strong><p>{bottleneck.detail}</p></div>
        <div className="cascade-card"><span className="eyebrow">WHAT BREAKS NEXT?</span>{bottleneck.cascade.map((x,i)=><div key={x} className="cascade-step"><strong>{x}</strong>{i<bottleneck.cascade.length-1&&<ArrowDown size={16}/>}</div>)}<div className={`handover-status ${readinessLabel.toLowerCase()}`}>Handover readiness <strong>{readinessLabel}</strong></div><small>Deterministic workflow heuristic — not an ML prediction.</small></div>
        {prediction?<div className={`twin-outlook ${prediction.risk_category.toLowerCase()}`}><div><span>3-month slip risk</span><strong>{Math.round(prediction.delay_probability*100)}%</strong><small>{prediction.risk_category}</small></div><div><span>Possible extension</span><strong>{prediction.delay_outlook?`~${prediction.delay_outlook.expected_extension_days}d`:'—'}</strong><small>{prediction.delay_outlook?.severity||'Impact model unavailable'}</small></div><div><span>Delay exposure</span><strong>{prediction.delay_outlook?`~${prediction.delay_outlook.expected_delay_exposure_days}d`:'—'}</strong><small>likelihood × conditional impact</small></div></div>:<div className="twin-outlook-placeholder"><Gauge size={24}/><strong>Predictive overlay not active</strong><span>Activate the twin to add schedule-risk and delay-impact estimates.</span></div>}
      </div>
    </div>
    {prediction&&<div className="officer-brief"><div className="officer-brief-head"><div><FileText size={18}/><span><strong>Officer Brief</strong><small>Generated only from the current project record and model output.</small></span></div><div><button className="button ghost" onClick={copy}><ClipboardCopy size={14}/>{copied?'Copied':'Copy brief'}</button><button className="button ghost" onClick={printBrief}><Printer size={14}/>Print review note</button></div></div><pre>{brief}</pre></div>}
    {error&&<p className="form-error">{error}</p>}
  </section>;
}
