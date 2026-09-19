import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ShieldCheck, ArrowRight, LockKeyhole, Eye, EyeOff, LoaderCircle, Check } from 'lucide-react';
import { api } from '../services/api';
import { setAuth } from '../services/auth';

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from;
  const destination = typeof from === 'string' && /^\/(dashboard|analytics|projects|map|admin)(\/|\?|$)/.test(from) ? from : '/dashboard';
  const [email,setEmail] = useState('');
  const [password,setPassword] = useState('');
  const [showPassword,setShowPassword] = useState(false);
  const [capsLock,setCapsLock] = useState(false);
  const [focused,setFocused] = useState('');
  const [step,setStep] = useState(0);
  const steps = [['Review the portfolio','Start with administrative bottlenecks and the projects behind them.'],['Investigate a project','Inspect acquisition progress, recorded issues, and model provenance.'],['Compare districts','Explore differences in compensation, possession, and acquisition stage.']];
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const result = await api('/auth/login',{method:'POST',body:JSON.stringify({email,password})});
      setAuth(result);
      const target = result.user?.role === 'SYSTEM_ADMIN' ? (destination.startsWith('/admin') ? destination : '/admin') : (destination.startsWith('/admin') ? '/dashboard' : destination);
      navigate(target,{replace:true});
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <main className="login-shell">
    <section className="login-brand"><span className="brand-symbol"><ShieldCheck size={30}/></span><p className="eyebrow">LAND ACQUISITION INTELLIGENCE</p><h1>LANDGUARD <b>AI</b></h1><p>Predict delays early. Explain the drivers. Support authorized intervention.</p><div className="login-journey"><p className="eyebrow">INSIDE YOUR WORKSPACE</p><div aria-label="Explore workspace tasks">{steps.map(([title],i)=><button type="button" key={title} aria-pressed={step===i} onClick={()=>setStep(i)}><span>0{i+1}</span>{title}<ArrowRight size={14}/></button>)}</div><p key={step} className="login-step-copy">{steps[step][1]}</p></div></section>
    <form className={"login-card" + (busy ? " is-submitting" : "")} onSubmit={submit} aria-busy={busy}><div className="login-icon"><LockKeyhole size={22}/></div><p className="eyebrow">AUTHORIZED ACCESS</p><h2>Sign in to the workspace</h2><p className="muted">Use your invited email address and the password you chose during activation.</p>
      <div className="login-field" data-focused={focused==='email'}><label htmlFor="login-email">Email {email.trim() && <Check size={13} aria-hidden="true"/>}</label><input id="login-email" type="email" maxLength={254} value={email} onChange={e=>{setEmail(e.target.value);setError('');}} onFocus={()=>setFocused('email')} onBlur={()=>setFocused('')} required autoComplete="username" disabled={busy}/></div>
      <div className="login-field" data-focused={focused==='password'}><label htmlFor="login-password">Password</label><div className="password-control"><input id="login-password" type={showPassword?'text':'password'} value={password} onChange={e=>{setPassword(e.target.value);setError('');}} onFocus={()=>setFocused('password')} onBlur={()=>{setFocused('');setCapsLock(false);}} onKeyUp={e=>setCapsLock(e.getModifierState('CapsLock'))} required autoComplete="current-password" disabled={busy}/><button type="button" aria-label={showPassword?'Hide password':'Show password'} aria-pressed={showPassword} onClick={()=>setShowPassword(!showPassword)} disabled={busy}>{showPassword?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></div>
      <div className="login-feedback" aria-live="polite">{capsLock ? 'Caps Lock is on.' : focused==='email' ? 'Use the email address that received your invitation.' : focused==='password' ? 'Your password is hidden unless you choose to reveal it.' : 'Enter your account credentials to continue.'}</div>
      {error && <p className="form-error login-error" role="alert">{error}</p>}
      <button className="button primary login-submit" disabled={busy || !email.trim() || !password}>{busy ? <><LoaderCircle size={17} className="busy-spinner"/> Signing in…</> : <>Enter workspace <ArrowRight size={16}/></>}</button>
      <small>Accounts are invitation-only. Your administrator assigns your role and project scope.</small><p><Link to="/access">Need access? Read the onboarding guidance</Link></p><Link className="back" to="/">← Back to LandGuard AI</Link>
    </form>
  </main>;
}
