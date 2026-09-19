import { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { getAuth, setAuth } from '../../services/auth';
import { api } from '../../services/api';

export default function AuthGate({children}) {
  const [session,setSession] = useState({loading:true, auth:null, error:''});
  const [retry,setRetry] = useState(0);
  const location = useLocation();
  useEffect(() => {
    let alive = true;
    const controller = new AbortController();
    const update = () => { if (alive) setSession({loading:false,auth:getAuth(),error:''}); };
    const check = async () => {
      try {
        const user = await api('/auth/me',{signal:controller.signal});
        if (alive) setAuth({user});
      } catch (error) {
        if (alive && error.name !== 'AbortError') setSession({loading:false,auth:null,error:error.status===401?'':error.message});
      }
    };
    window.addEventListener('landguard:auth-changed',update);
    window.addEventListener('focus',check);
    check();
    return () => { alive=false; controller.abort(); window.removeEventListener('landguard:auth-changed',update); window.removeEventListener('focus',check); };
  },[retry]);
  if (session.loading) return <main className="login-shell"><section className="login-card" role="status">Verifying your session…</section></main>;
  if (session.error) return <main className="login-shell"><section className="login-card"><h1>Unable to verify access</h1><p role="alert">{session.error}</p><button className="button primary" onClick={()=>{setSession({loading:true,auth:null,error:''});setRetry(n=>n+1);}}>Try again</button></section></main>;
  if (!session.auth?.user) return <Navigate to="/login" replace state={{from:location.pathname + location.search}}/>;
  return children;
}
