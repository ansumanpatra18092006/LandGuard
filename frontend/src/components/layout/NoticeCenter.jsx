import { toast } from './Toasts';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import Modal from '../common/Modal';
import { useResource } from '../../hooks/useResource';
import { useLocalPreference } from '../../hooks/useLocalPreference';
import { api } from '../../services/api';
import { ErrorState, Loading } from '../common';

function Notices({ onClose,returnTo }) {
  const [refresh,setRefresh] = useState(0);
  const [storedRead,setRead] = useLocalPreference('landguard:read-alerts',[]);
  const read = Array.isArray(storedRead) ? storedRead : [];
  const { data,loading,error,updatedAt } = useResource('alerts',signal => api('/alerts',{signal}),refresh,0);
  const alerts = data || [];
  const mark = ids => { setRead([...new Set([...read,...ids])].slice(-500)); toast(ids.length > 1 ? 'Shown alerts marked as read' : 'Alert marked as read'); };
  return <div className="notice-content"><p className="notice-explainer"><strong>Administrative alert inbox</strong>Operational and workflow-automation alerts. Due reminders and overdue escalations come from tracked interventions; these are not ML predictions.</p>
    <div className="notice-controls"><button onClick={() => setRefresh(n => n + 1)} disabled={loading}>Refresh alerts</button><button disabled={!alerts.length} onClick={() => mark(alerts.map(a=>a.id))}>Mark shown as read</button></div>
    {loading ? <Loading/> : error ? <ErrorState message={error} retry={() => setRefresh(n => n + 1)}/> : <><p className="muted">{alerts.filter(a => !read.includes(a.id)).length} unread shown · {alerts.length} administrative alert{alerts.length===1?'':'s'} · Checked {updatedAt?.toLocaleTimeString()}</p>{!alerts.length && <p>No projects currently trigger an operational alert.</p>}<div className="review-list">{alerts.map(a => <article key={a.id} className={read.includes(a.id) ? 'is-read' : 'is-unread'}><span className="notice-read">{read.includes(a.id) ? 'Read' : a.severity}</span><Link to={'/projects/' + a.project_id + (a.source==='AUTOMATION'?'?tab=interventions':'')} state={{returnTo}} onClick={() => { mark([a.id]); onClose(); }}>{a.title} · {a.project_id}</Link><p>{a.message}</p><small>Project record updated {new Date(a.created_at).toLocaleString()} · {a.source.replaceAll('_',' ')}</small>{!read.includes(a.id) && <button className="ghost" onClick={() => mark([a.id])}>Mark as read</button>}</article>)}</div></>}
  </div>;
}
export default function NoticeCenter({open,onClose,returnTo}) {
  return <Modal open={open} onClose={onClose} title="Administrative alerts" className="notice-center"><Notices {...{onClose,returnTo}}/></Modal>;
}
