import { useMemo, useState } from 'react';
import { AlertTriangle, Bot, CalendarClock, CheckCircle2, ClipboardCheck, History, PlayCircle, Plus, RefreshCw, UserRound, Zap, ListChecks } from 'lucide-react';
import { api } from '../../services/api';
import { useResource } from '../../hooks/useResource';

function isoIn(days){ const d=new Date(); d.setDate(d.getDate()+days); return d.toISOString().slice(0,10); }
function suggestedActions(p){
  const out=[];
  if(Number(p.pending_approvals||0)>0) out.push('Clear pending approval chain');
  if(Number(p.legal_disputes||0)>0) out.push('Escalate authorized legal review');
  if(Number(p.compensation_completion_pct||0)<80) out.push('Review compensation processing');
  if(Number(p.possession_pct||0)<80) out.push('Review possession / handover readiness');
  if(Number(p.rehabilitation_completion_pct||0)<80) out.push('Review rehabilitation obligations');
  return out.length?out:['Continue routine monitoring'];
}

export default function InterventionLedger({project}){
  const [refresh,setRefresh]=useState(0); const [busy,setBusy]=useState(false); const [error,setError]=useState(''); const [automationResult,setAutomationResult]=useState(null);
  const {data,error:loadError}=useResource(`interventions-${project.project_id}`,signal=>api(`/projects/${project.project_id}/interventions`,{signal}),refresh);
  const actions=useMemo(()=>suggestedActions(project),[project]);
  const [action,setAction]=useState(actions[0]); const [assignedTo,setAssignedTo]=useState('District Acquisition Cell'); const [dueDate,setDueDate]=useState(isoIn(7)); const [priority,setPriority]=useState('HIGH');
  async function create(){setBusy(true);setError('');try{await api(`/projects/${project.project_id}/interventions`,{method:'POST',body:JSON.stringify({action,assigned_to:assignedTo,due_date:dueDate,priority,source:'RECOMMENDATION'})});setRefresh(x=>x+1);}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function runAutomation(){setBusy(true);setError('');try{const result=await api(`/projects/${project.project_id}/automation/evaluate`,{method:'POST'});setAutomationResult(result);setRefresh(x=>x+1);}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function status(row,next){setBusy(true);setError('');try{let resolution_note=undefined;if(next==='RESOLVED'){resolution_note=window.prompt('Resolution note (required for the audit trail):','Reviewed and closed by authorized officer.');if(!resolution_note)return;}await api(`/projects/${project.project_id}/interventions/${row.id}`,{method:'PATCH',body:JSON.stringify({status:next,resolution_note})});setRefresh(x=>x+1);}catch(e){setError(e.message);}finally{setBusy(false);}}
  const rows=data||[]; const open=rows.filter(x=>x.status!=='RESOLVED').length; const overdue=rows.filter(x=>x.overdue).length; const automated=rows.filter(x=>x.source==='AUTOMATION'&&x.status!=='RESOLVED').length;
  return <section className="intervention-ledger">
    <div className="ledger-hero"><div><span className="eyebrow">INTERVENTION AUTOMATION + LEDGER</span><h2>Turn intelligence into accountable action.</h2><p>Operational triggers can create actions automatically, assign an owner and due date, generate reminders, and escalate overdue work. Authorized officers verify and resolve every action.</p></div><div className="ledger-counters"><div><strong>{open}</strong><span>open</span></div><div><strong>{automated}</strong><span>automated</span></div><div className={overdue?'danger':''}><strong>{overdue}</strong><span>overdue</span></div></div></div>
    <section className="ledger-block automation-block">
      <div className="ledger-section-head"><div className="ledger-section-icon"><Zap size={17}/></div><div><span className="eyebrow">AUTOMATION</span><h3>Policy-aware workflow checks</h3><p>Turn recorded bottlenecks into trackable workflow actions while keeping the final decision with the officer.</p></div></div>
      <div className="automation-strip panel"><div><Bot size={20}/><div><strong>Evaluate this project</strong><p>Checks approvals, disputes, compensation, possession, R&amp;R, response time and critical acquisition risk.</p></div></div><button className="button secondary" onClick={runAutomation} disabled={busy}><RefreshCw size={14}/>{busy?'Checking…':'Refresh automation'}</button></div>
      {automationResult&&<p className="automation-result">Automation checked this project · {automationResult.created} action(s) created · {automationResult.reminded} reminder(s) · {automationResult.escalated} escalation(s).</p>}
    </section>

    <section className="ledger-block create-block">
      <div className="ledger-section-head"><div className="ledger-section-icon"><Plus size={17}/></div><div><span className="eyebrow">NEW ACTION</span><h3>Create an intervention</h3><p>Assign one clear action, owner, due date and priority.</p></div></div>
      <div className="ledger-create panel">
        <div className="ledger-field wide"><label>Manual / recommended action</label><select value={action} onChange={e=>setAction(e.target.value)}>{actions.map(x=><option key={x}>{x}</option>)}</select></div>
        <div className="ledger-field"><label>Owner</label><input value={assignedTo} onChange={e=>setAssignedTo(e.target.value)} /></div>
        <div className="ledger-field"><label>Due date</label><input type="date" value={dueDate} min={new Date().toISOString().slice(0,10)} onChange={e=>setDueDate(e.target.value)} /></div>
        <div className="ledger-field"><label>Priority</label><select value={priority} onChange={e=>setPriority(e.target.value)}><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select></div>
        <button className="button primary" onClick={create} disabled={busy||!action||!assignedTo||!dueDate}><Plus size={15}/>{busy?'Saving…':'Create intervention'}</button>
      </div>
    </section>
    {(error||loadError)&&<p className="form-error">{error||loadError}</p>}

    <section className="ledger-block tracked-block">
      <div className="ledger-section-head ledger-section-head-row"><div className="ledger-section-head-copy"><div className="ledger-section-icon"><ListChecks size={17}/></div><div><span className="eyebrow">ACCOUNTABILITY</span><h3>Tracked interventions</h3><p>Open, in-progress and resolved actions with their audit history.</p></div></div><span className="ledger-total">{rows.length} total</span></div>
      <div className="ledger-list">{rows.length?rows.map(row=><article className={`ledger-item ${row.overdue?'overdue':''}`} key={row.id}>
      <div className="ledger-item-main"><div className="ledger-icon">{row.status==='RESOLVED'?<CheckCircle2 size={18}/>:row.overdue?<AlertTriangle size={18}/>:row.source==='AUTOMATION'?<Bot size={18}/>:<ClipboardCheck size={18}/>}</div><div><div className="ledger-title"><strong>{row.action}</strong>{row.source==='AUTOMATION'&&<span className="badge automation-badge">AUTO</span>}<span className={`badge ${row.priority==='HIGH'?'risk-high':'neutral'}`}>{row.priority}</span><span className="badge neutral">{row.status.replace('_',' ')}</span>{row.overdue&&<span className="badge risk-high">OVERDUE</span>}</div><p><UserRound size={13}/>{row.assigned_to}<CalendarClock size={13}/>Due {new Date(`${row.due_date}T00:00:00`).toLocaleDateString()}</p><small>Created by {row.created_by} · {new Date(row.created_at).toLocaleString()}</small></div></div>
      <div className="ledger-actions">{row.status==='OPEN'&&<button className="button ghost" disabled={busy} onClick={()=>status(row,'IN_PROGRESS')}><PlayCircle size={14}/>Start</button>}{row.status!=='RESOLVED'&&<button className="button secondary" disabled={busy} onClick={()=>status(row,'RESOLVED')}><CheckCircle2 size={14}/>Verify & resolve</button>}</div>
      {!!row.events?.length&&<details className="ledger-events"><summary><History size={13}/>Audit events ({row.events.length})</summary>{row.events.map(ev=><div key={ev.id}><strong>{ev.event_type.replaceAll('_',' ')}</strong><span>{ev.detail}</span><small>{ev.actor} · {new Date(ev.created_at).toLocaleString()}</small></div>)}</details>}
    </article>):<div className="empty-state small"><ClipboardCheck size={22}/><strong>No interventions yet</strong><p>Refresh automation or create an action from the project's recorded bottlenecks.</p></div>}</div>
    </section>
  </section>;
}
