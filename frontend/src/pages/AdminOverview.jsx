import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, UserCheck, UserPlus, UsersRound, UserX, Clock3, ShieldCheck, DatabaseZap, RefreshCw, BrainCircuit, CheckCircle2 } from 'lucide-react';
import { api } from '../services/api';
import { ErrorState, Loading, PageHeader, SectionCard } from '../components/common';
import { useResource } from '../hooks/useResource';
import '../styles/accounts.css';

const roleLabels = {
  SYSTEM_ADMIN: 'System administrator',
  STATE_OFFICER: 'State officer',
  DISTRICT_OFFICER: 'District officer',
  IMPLEMENTING_AGENCY: 'Implementing agency',
};

function eventLabel(event) {
  return ({
    session_created: 'Signed in',
    user_invited: 'User invited',
    invitation_resent: 'Invitation resent',
    invitation_accepted: 'Invitation accepted',
    account_active: 'Account enabled',
    account_disabled: 'Account disabled',
  })[event] || event.replaceAll('_', ' ');
}

export default function AdminOverview() {
  const [retry,setRetry] = useState(0);
  const [checkingPipeline,setCheckingPipeline] = useState(false);
  const [pipelineError,setPipelineError] = useState('');
  const usersRes = useResource('admin-users', signal => api('/auth/users',{signal}), retry);
  const auditRes = useResource('admin-audit', signal => api('/auth/audit',{signal}), retry);
  const pipelineRes = useResource('admin-pipeline', signal => api('/pipeline/status',{signal}), retry);
  const users = usersRes.data || [];
  const audit = auditRes.data || [];
  const pipeline = pipelineRes.data || null;
  const byId = useMemo(() => Object.fromEntries(users.map(u => [u.id,u])),[users]);
  const stats = useMemo(() => ({
    total: users.filter(u => u.role !== 'SYSTEM_ADMIN').length,
    active: users.filter(u => u.role !== 'SYSTEM_ADMIN' && u.status === 'active').length,
    invited: users.filter(u => u.role !== 'SYSTEM_ADMIN' && u.status === 'invited').length,
    disabled: users.filter(u => u.role !== 'SYSTEM_ADMIN' && u.status === 'disabled').length,
  }),[users]);
  if ((usersRes.loading && !usersRes.data) || (auditRes.loading && !auditRes.data) || (pipelineRes.loading && !pipelineRes.data)) return <Loading variant="dashboard"/>;
  const error = usersRes.error || auditRes.error || pipelineRes.error;
  if (error) return <ErrorState message={error} retry={() => setRetry(n => n + 1)}/>;
  async function checkPipelineNow() {
    setCheckingPipeline(true); setPipelineError('');
    try { await api('/pipeline/check',{method:'POST'}); setRetry(n => n + 1); }
    catch (err) { setPipelineError(err.message); }
    finally { setCheckingPipeline(false); }
  }

  return <div className="accounts-page admin-overview">
    <PageHeader eyebrow="SYSTEM ADMINISTRATION" title="Access & account overview" description="Manage who can use LandGuard AI and monitor account activity. Project records, GIS, analytics, and AI intelligence are intentionally outside the system-administrator role." action={<Link className="button primary" to="/admin/users#invite-user"><UserPlus size={16}/> Invite user</Link>}/>
    <section className="admin-kpis" aria-label="Account summary">
      <div className="admin-kpi"><UsersRound size={20}/><span>Managed users</span><strong>{stats.total}</strong><small>Operational accounts</small></div>
      <div className="admin-kpi"><UserCheck size={20}/><span>Active</span><strong>{stats.active}</strong><small>Can sign in now</small></div>
      <div className="admin-kpi"><Clock3 size={20}/><span>Invited</span><strong>{stats.invited}</strong><small>Awaiting activation</small></div>
      <div className="admin-kpi"><UserX size={20}/><span>Disabled</span><strong>{stats.disabled}</strong><small>Access revoked</small></div>
    </section>
    <section className="pipeline-card" aria-label="PAIMANA continuous learning pipeline">
      <div className="pipeline-card-head"><div><p className="eyebrow">DATA INTELLIGENCE PIPELINE</p><h2>PAIMANA source monitor</h2><p>Detects new official monthly snapshots, refreshes the longitudinal dataset, and retrains a challenger only after 3-month outcomes mature.</p></div><button className="button secondary" onClick={checkPipelineNow} disabled={checkingPipeline}><RefreshCw size={16} className={checkingPipeline?'spin':''}/>{checkingPipeline?'Checking…':'Check now'}</button></div>
      <div className="pipeline-flow">
        <div><DatabaseZap size={18}/><span>Source</span><strong>{pipeline?.latest_published_month || 'Awaiting check'}</strong><small>Latest published month</small></div>
        <i>→</i>
        <div><CheckCircle2 size={18}/><span>Dataset</span><strong>{pipeline?.dataset_rows?.toLocaleString?.() || '—'}</strong><small>Fully-labelled project-month rows</small></div>
        <i>→</i>
        <div><BrainCircuit size={18}/><span>Model</span><strong>{pipeline?.current_model_name || '—'}</strong><small>Temporal test: {pipeline?.latest_model_test_month || '—'}</small></div>
      </div>
      <div className="pipeline-status-strip"><span className={`pipeline-pill ${pipeline?.retraining_status || 'idle'}`}>{pipeline?.retraining_status?.replaceAll('_',' ') || 'idle'}</span><span>Downloaded: <b>{pipeline?.latest_downloaded_month || '—'}</b></span><span>Labels mature through: <b>{pipeline?.latest_labelled_month || '—'}</b></span><span>Promotion: <b>{pipeline?.model_promotion_status?.replaceAll('_',' ') || '—'}</b></span></div>
      {(pipelineError || pipeline?.message) && <p className={pipelineError?'pipeline-message error':'pipeline-message'}>{pipelineError || pipeline.message}</p>}
      <small className="pipeline-footnote">New data is never promoted blindly: the challenger must pass ROC-AUC, recall, and incumbent-tolerance quality gates before replacing the current model.</small>
    </section>
    <div className="admin-overview-grid">
      <SectionCard title="Recent account activity" description="Latest authentication and account-management events">
        {!audit.length ? <p className="muted">No account activity has been recorded yet.</p> : <ol className="admin-activity">{audit.slice(0,12).map(item => {
          const subject = item.subject_id ? byId[item.subject_id] : null;
          const actor = item.actor_id ? byId[item.actor_id] : null;
          return <li key={item.id}><span className="activity-icon"><Activity size={15}/></span><div><strong>{eventLabel(item.event)}</strong><p>{subject?.display_name || subject?.email || 'Account'}{actor && actor.id !== item.subject_id ? ` · by ${actor.display_name}` : ''}</p><small>{new Date(item.created_at).toLocaleString()}</small></div></li>;
        })}</ol>}
      </SectionCard>
      <SectionCard title="Role boundaries" description="System administration is separated from land-acquisition operations">
        <div className="admin-boundaries"><div><ShieldCheck size={18}/><span><strong>System administrator</strong><small>Users, invitations, account status, account audit activity</small></span></div><div><UsersRound size={18}/><span><strong>Operational roles</strong><small>State officers, district officers, and implementing agencies access project data according to assigned scope</small></span></div></div>
        <Link className="button secondary" to="/admin/users">Open user directory</Link>
      </SectionCard>
    </div>
    <section className="panel"><div className="section-title"><div><p className="eyebrow">RECENT ACCOUNTS</p><h2>Latest managed users</h2><p>System administrator accounts are deployment-owner managed and are not part of the operational directory.</p></div><Link className="button secondary" to="/admin/users">View all users</Link></div>
      <ul className="admin-recent-users">{users.filter(u => u.role !== 'SYSTEM_ADMIN').slice(0,6).map(user => <li key={user.id}><span className={`account-status ${user.status}`}>{user.status}</span><div><strong>{user.display_name}</strong><small>{user.email} · {roleLabels[user.role]}</small></div></li>)}</ul>
      {!users.filter(u => u.role !== 'SYSTEM_ADMIN').length && <p className="muted">No operational users have been added yet.</p>}
    </section>
  </div>;
}
