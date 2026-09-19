import { useCallback, useEffect, useRef, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { MailPlus, RefreshCw, UsersRound } from 'lucide-react';
import { api } from '../services/api';
import { getUser } from '../services/auth';
import '../styles/accounts.css';

const empty = {email:'',display_name:'',role:'DISTRICT_OFFICER',state:'',district:'',project_ids:''};
const roles = {SYSTEM_ADMIN:'System administrator',STATE_OFFICER:'State officer',DISTRICT_OFFICER:'District officer',IMPLEMENTING_AGENCY:'Implementing agency'};
const assignableRoles = Object.entries(roles).filter(([value]) => value !== 'SYSTEM_ADMIN');

export default function Users() {
  const admin = getUser()?.role==='SYSTEM_ADMIN';
  const location = useLocation();
  const inviteName = useRef(null);
  useEffect(() => {
    if (admin && location.hash === '#invite-user') inviteName.current?.focus();
  },[admin,location.hash]);
  const [form,setForm] = useState(empty);
  const [users,setUsers] = useState([]);
  const [loading,setLoading] = useState(true);
  const [busy,setBusy] = useState('');
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [search,setSearch] = useState('');
  const [status,setStatus] = useState('all');
  const reload = useCallback(async () => {
    setLoading(true);
    try { setUsers(await api('/auth/users')); }
    catch(err) { setError(err.message); }
    finally { setLoading(false); }
  },[]);
  useEffect(()=>{if(admin) reload();},[admin,reload]);
  if(!admin) return <Navigate to="/dashboard" replace/>;
  const change = e => setForm({...form,[e.target.name]:e.target.value});
  async function invite(e) {
    e.preventDefault();setBusy('invite');setError('');setNotice('');
    try {
      await api('/auth/invitations',{method:'POST',body:JSON.stringify({...form,project_ids:form.project_ids.split(',').map(v=>v.trim()).filter(Boolean)})});
      setNotice('Invitation accepted by Brevo. The recipient can activate their account from the email.');setForm(empty);
    } catch(err) {setError(err.message);}
    finally {await reload();setBusy('');}
  }
  async function act(user,action) {
    setBusy(user.id);setError('');setNotice('');
    try {
      if(action==='resend') await api(`/auth/users/${user.id}/resend`,{method:'POST'});
      else await api(`/auth/users/${user.id}`,{method:'PATCH',body:JSON.stringify({status:action})});
      setNotice(action==='resend'?'New invitation accepted by Brevo.':action==='disabled'?'Account disabled and sessions revoked.':'Account enabled. The user can sign in again.');
    } catch(err) {setError(err.message);}
    finally {await reload();setBusy('');}
  }
  const filtered = users.filter(u=>(status==='all'||u.status===status)&&[u.email,u.display_name,u.state,u.district].join(' ').toLowerCase().includes(search.toLowerCase()));
  return <div className="accounts-page">
    <header className="accounts-heading"><div><p className="eyebrow">SYSTEM ADMINISTRATION</p><h1>Users & access</h1><p>Invite authorized operational users, assign their scope, and control account status.</p></div><UsersRound size={30}/></header>
    {error&&<p role="alert" className="form-error">{error}</p>}{notice&&<p role="status" className="accounts-notice">{notice}</p>}
    <div className="accounts-grid"><section className="panel" id="invite-user"><h2><MailPlus size={20}/> Invite an operational user</h2><p className="muted">System administrators manage access only. Operational users receive the project scope assigned below.</p><form className="accounts-form" onSubmit={invite}>
      <label>Full name<input ref={inviteName} name="display_name" value={form.display_name} onChange={change} minLength={2} maxLength={100} required disabled={!!busy}/></label>
      <label>Work email<input name="email" type="email" value={form.email} onChange={change} maxLength={254} required disabled={!!busy}/></label>
      <label>Role<select name="role" value={form.role} onChange={change} disabled={!!busy}>{assignableRoles.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
      {['STATE_OFFICER','DISTRICT_OFFICER'].includes(form.role)&&<label>Assigned state<input name="state" value={form.state} onChange={change} required maxLength={100} disabled={!!busy} placeholder="Exact state name in project records"/></label>}
      {form.role==='DISTRICT_OFFICER'&&<label>Assigned district<input name="district" value={form.district} onChange={change} required maxLength={100} disabled={!!busy} placeholder="Exact district name in project records"/></label>}
      {form.role==='IMPLEMENTING_AGENCY'&&<label>Assigned project IDs<input name="project_ids" value={form.project_ids} onChange={change} required disabled={!!busy} placeholder="P1042, P1043"/><small>Separate project IDs with commas.</small></label>}
      <p className="muted">The backend limits project records, analytics, maps, alerts, and AI intelligence to the recipient's assigned operational scope.</p>
      <button className="button primary" disabled={!!busy}>{busy==='invite'?'Sending invitation…':'Send invitation'}</button><small>The recipient chooses their own password. No password is sent by email.</small>
    </form></section>
    <section className="panel accounts-directory"><div className="accounts-heading"><h2>Account directory</h2><button className="button secondary" onClick={()=>{setError('');reload();}} disabled={loading||!!busy}><RefreshCw size={15}/> Refresh</button></div>
      <div className="accounts-filters"><input aria-label="Search accounts" placeholder="Search name, email, or jurisdiction" value={search} onChange={e=>setSearch(e.target.value)}/><select aria-label="Account status" value={status} onChange={e=>setStatus(e.target.value)}><option value="all">All statuses</option><option value="invited">Invited</option><option value="active">Active</option><option value="disabled">Disabled</option></select></div>
      <p className="muted" aria-live="polite">{loading?'Loading accounts…':`${filtered.length} matching accounts`}</p>
      {!loading&&!filtered.length&&<p>No accounts match. Invite a colleague or adjust your filters.</p>}
      <ul className="account-list">{filtered.map(user=><li key={user.id}><div><strong>{user.display_name}</strong><span>{user.email}</span><small>{roles[user.role] || user.role} · {user.role==='SYSTEM_ADMIN'?'System administration only':user.role==='IMPLEMENTING_AGENCY'?user.project_ids.join(', '):[user.state,user.district].filter(Boolean).join(' / ')}</small></div><div className="account-actions"><span className={`account-status ${user.status}`}>{user.status}</span>
        {user.status==='invited'?<><small>{user.invitation_delivery==='accepted_by_brevo'?'Email accepted by Brevo':user.invitation_delivery==='failed'?'Email failed — resend available':'Email not sent'}</small>{user.role!=='SYSTEM_ADMIN'&&<button className="button secondary" disabled={!!busy} onClick={()=>act(user,'resend')}>{busy===user.id?'Sending…':'Resend invitation'}</button>}</>:user.role!=='SYSTEM_ADMIN'?<button className="button secondary" disabled={!!busy} onClick={()=>act(user,user.status==='active'?'disabled':'active')}>{busy===user.id?'Updating…':user.status==='active'?'Disable account':'Enable account'}</button>:<small>Deployment-owner managed</small>}
      </div></li>)}</ul><small>Shows up to 1,000 most recent accounts. Email acceptance is not proof of inbox delivery.</small>
    </section></div>
  </div>;
}
