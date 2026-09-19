import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, LoaderCircle } from 'lucide-react';
import { api } from '../services/api';

export default function AcceptInvitation() {
  const [invitation,setInvitation] = useState(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    return {token_hash:params.get('token_hash') || '',type:params.get('type') || ''};
  });
  useEffect(() => {
    const receive = () => {
      if (!window.location.hash) return;
      const params = new URLSearchParams(window.location.hash.slice(1));
      setInvitation({token_hash:params.get('token_hash') || '',type:params.get('type') || ''});
      setPassword('');setConfirm('');setError('');setDone(false);
      window.history.replaceState(null,'',window.location.pathname);
    };
    window.history.replaceState(null,'',window.location.pathname);
    window.addEventListener('hashchange',receive);
    return () => window.removeEventListener('hashchange',receive);
  },[]);
  const [password,setPassword] = useState('');
  const [confirm,setConfirm] = useState('');
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [done,setDone] = useState(false);
  const validLink = invitation.token_hash && ['invite','recovery'].includes(invitation.type);
  async function submit(event) {
    event.preventDefault();
    if(password!==confirm) { setError('The passwords do not match.'); return; }
    setBusy(true); setError('');
    try { await api('/auth/accept-invitation',{method:'POST',body:JSON.stringify({...invitation,password})}); setPassword('');setConfirm('');setDone(true); }
    catch(err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <main className="login-shell">
    <section className="login-brand"><ShieldCheck size={38}/><p className="eyebrow">LANDGUARD AI</p><h1>Your workspace<br/>starts here.</h1><p>Your administrator has assigned your role and project scope. Set your own password to activate your account.</p></section>
    <section className="login-card">
      {done ? <><ShieldCheck size={32}/><h2>Your account is active</h2><p>Sign in with the email that received this invitation and your new password.</p><Link className="button primary" to="/login">Continue to sign in</Link></> :
      !validLink ? <><h2>Open your invitation email</h2><p>Use the complete invitation link sent by your administrator. If you refreshed this page, reopen the email link.</p><Link to="/login">Back to sign in</Link></> :
      <form onSubmit={submit} aria-busy={busy}><p className="eyebrow">ACTIVATE YOUR ACCOUNT</p><h2>Choose your password</h2><p>Use at least 12 characters. A long, unique passphrase works well.</p>
        <label htmlFor="new-password">New password</label><input id="new-password" type="password" minLength={12} maxLength={128} required autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} disabled={busy}/>
        <label htmlFor="confirm-password">Confirm password</label><input id="confirm-password" type="password" minLength={12} maxLength={128} required autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} disabled={busy}/>
        <p aria-live="polite">{password.length>0 ? password.length<12 ? `${12-password.length} more characters needed` : confirm && password!==confirm ? 'Passwords do not match yet.' : 'Password length meets the requirement.' : 'Your password is stored securely by Supabase Auth.'}</p>
        {error && <p role="alert" className="form-error">{error}</p>}
        <button className="button primary login-submit" disabled={busy || password.length<12 || password!==confirm}>{busy?<><LoaderCircle size={16} className="busy-spinner"/> Activatingâ€¦</>:'Activate account'}</button>
        <small>If activation fails after opening a valid link, ask the administrator to resend your invitation.</small>
      </form>}
    </section>
  </main>;
}
