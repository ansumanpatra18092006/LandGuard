import { toast } from '../components/layout/Toasts';
import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Save, Trash2 } from 'lucide-react';
import { safeReturnTo } from '../utils/projectScope';
import { api } from '../services/api';
import { getUser } from '../services/auth';
import { ErrorState, Loading, pretty } from '../components/common';

const types = ['ROAD','RAILWAY','IRRIGATION','INDUSTRIAL','URBAN'];
const stages = ['NOTIFICATION','SURVEY','VALUATION','COMPENSATION','REHABILITATION','POSSESSION','COMPLETED'];
const fields = [
  ['project_id','Project ID','text'], ['project_name','Project name','text'],
  ['project_type','Project type',types], ['state','State','text'], ['district','District','text'],
  ['acquisition_stage','Acquisition stage',stages], ['latitude','Latitude','number',-90,90],
  ['longitude','Longitude','number',-180,180], ['land_area','Land area (hectares)','number',0],
  ['affected_families','Affected families','integer',0],
  ['compensation_completion_pct','Compensation completed (%)','number',0,100],
  ['possession_pct','Possession (%)','number',0,100],
  ['rehabilitation_completion_pct','Rehabilitation completed (%)','number',0,100],
  ['pending_approvals','Pending approvals','integer',0], ['legal_disputes','Legal disputes','integer',0],
  ['stakeholder_response_days','Stakeholder response (days)','integer',0],
  ['elapsed_acquisition_days','Elapsed acquisition (days)','integer',0],
  ['original_cost_crore','Original approved cost (₹ crore)','number',0,undefined,false],
  ['expenditure_crore','Cumulative expenditure (₹ crore)','number',0,undefined,false],
  ['original_end_date','Original completion date','date',undefined,undefined,false],
];
const empty = Object.fromEntries(fields.map(([key,,type]) => [key, Array.isArray(type) ? type[0] : '']));

export default function ProjectForm() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const returnTo = safeReturnTo(location.state?.returnTo);
  const [form, setForm] = useState(empty);
  const [loading, setLoading] = useState(!!projectId);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!projectId) { setForm(empty); setLoading(false); return; }
    const controller = new AbortController();
    setLoading(true); setLoadError('');
    api(`/projects/${projectId}`, { signal: controller.signal }).then(p => {
      setForm(Object.fromEntries(fields.map(([key]) => [key, p[key] ?? ''])));
    }).catch(e => { if (e.name !== 'AbortError') setLoadError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [projectId, retry]);
  async function save(event) {
    event.preventDefault(); setBusy(true); setError('');
    const body = Object.fromEntries(fields.map(([key,,type,,,required=true]) => {
      const value = form[key];
      if (required === false && (value === '' || value == null)) return [key, null];
      if (['number','integer'].includes(type)) return [key, Number(value)];
      return [key, value];
    }));
    try {
      const p = await api(projectId ? `/projects/${projectId}` : '/projects', { method: projectId ? 'PUT' : 'POST', body: JSON.stringify(body) });
      toast(projectId ? 'Project updated successfully' : 'Project created successfully');
      navigate(`/projects/${p.project_id}`, { state:{ returnTo } });
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function remove() {
    setBusy(true); setError('');
    try { await api(`/projects/${projectId}`, { method: 'DELETE' }); toast('Project deleted successfully');
      navigate(returnTo); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  if (loading) return <Loading/>;
  if (loadError) return <ErrorState message={loadError} retry={() => setRetry(n => n + 1)}/>;
  const canDelete = getUser()?.role === 'STATE_OFFICER';
  return <><Link className="back" to={projectId ? `/projects/${projectId}` : returnTo} state={{ returnTo }}><ArrowLeft size={16}/> Back to projects</Link><div className="page-title"><div><div className="eyebrow">PROJECT REGISTRY</div><h1>{projectId ? 'Update project record' : 'Add a project'}</h1><p>Enter a project observation. Prediction-baseline fields are optional for registry use but required before running AI intelligence.</p></div></div>{error && <ErrorState message={error}/>}
    <form className="panel detail" onSubmit={save}><fieldset disabled={busy}><div className="form-grid">{fields.map(([key,label,type,min,max,required=true]) => <label key={key}>{label}{required === false && <small className="field-hint">Prediction baseline</small>}{Array.isArray(type) ? <select required={required} value={form[key]} onChange={e => setForm(f => ({...f,[key]: e.target.value}))}>{type.map(v => <option key={v} value={v}>{pretty(v)}</option>)}</select> : <input required={required} type={type === 'integer' ? 'number' : type} min={min} max={max ?? (type === 'integer' ? 2147483647 : undefined)} step={type === 'integer' ? '1' : 'any'} maxLength={key === 'project_id' ? 40 : key === 'project_name' ? 200 : 100} pattern={key === 'project_id' ? '[A-Za-z0-9_\\-]+' : undefined} value={form[key]} onChange={e => setForm(f => ({...f,[key]: e.target.value}))}/>}</label>)}</div></fieldset><div className="form-actions"><Link className="button" to={projectId ? `/projects/${projectId}` : returnTo} state={{ returnTo }}>Cancel</Link><button className="primary" disabled={busy} type="submit"><Save size={16}/>{busy ? 'Saving…' : 'Save project'}</button></div></form>
    {projectId && canDelete && <div className="delete-area">{confirmDelete ? <><p>Delete this project permanently? This cannot be undone.</p><button disabled={busy} className="danger" onClick={remove}>Confirm deletion</button><button disabled={busy} onClick={() => setConfirmDelete(false)}>Keep project</button></> : <button className="danger" onClick={() => setConfirmDelete(true)}><Trash2 size={15}/> Delete project</button>}</div>}
  </>;
}
