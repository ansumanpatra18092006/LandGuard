import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { ShieldCheck, LayoutDashboard, FolderOpen, Map, Bell, ChartNoAxesCombined, UsersRound, PanelLeftClose, PanelLeftOpen, Menu, X, Search, ChevronDown, ArrowUpRight, Activity, MapPinned } from 'lucide-react';

import CommandPalette from './CommandPalette';
import NoticeCenter from './NoticeCenter';
import Toasts from './Toasts';
import { useLocalPreference } from '../../hooks/useLocalPreference';
import { useDialogTransition } from '../../hooks/useDialogTransition';
import { clearAuth, getUser } from '../../services/auth';
import { api } from '../../services/api';

function Navigation({ close, notices, user }) {
  if (user?.role === 'SYSTEM_ADMIN') return <><p className="nav-caption">SYSTEM ADMINISTRATION</p><nav className="app-nav" aria-label="System administration">
    <NavLink to="/admin" end onClick={close} title="Administration overview"><Activity size={19}/><span>Overview</span></NavLink>
    <NavLink to="/admin/users" onClick={close} title="Users & access"><UsersRound size={19}/><span>Users & access</span></NavLink>
  </nav></>;
  return <><p className="nav-caption">OPERATIONAL WORKSPACE</p><nav className="app-nav" aria-label="Main navigation">
    <NavLink to="/dashboard" end onClick={close} title="Dashboard"><LayoutDashboard size={19}/><span>Dashboard</span></NavLink>
    <NavLink to="/projects" onClick={close} title="Projects"><FolderOpen size={19}/><span>Projects</span></NavLink>
    <NavLink to="/map" onClick={close} title="GIS Map"><Map size={19}/><span>GIS Map</span></NavLink>
    <button onClick={() => { close?.(); notices(); }} title="Review notices"><Bell size={19}/><span>Review notices</span></button>
    <NavLink to="/analytics" onClick={close} title="Analytics"><ChartNoAxesCombined size={19}/><span>Analytics</span></NavLink>
    <NavLink to="/route-analysis" onClick={close} title="Route feasibility"><MapPinned size={19}/><span>Route analysis</span></NavLink>
  </nav></>;
}
function Brand() {
  return <Link className="brand" to="/" aria-label="LandGuard AI home"><span className="brand-symbol"><ShieldCheck size={25}/></span><span>LANDGUARD <b>AI</b><small>LAND ACQUISITION INTELLIGENCE</small></span></Link>;
}
export default function AppShell({ children }) {
  const [collapsed, setCollapsed] = useLocalPreference('landguard:sidebar-collapsed',false);
  const [paletteOpen,setPaletteOpen] = useState(false);
  const [noticesOpen,setNoticesOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [query, setQuery] = useState('');
  const { ref: drawer, phase: drawerPhase } = useDialogTransition(drawerOpen);
  const opener = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const user = getUser();
  const systemAdmin = user?.role === 'SYSTEM_ADMIN';
  const [signingOut,setSigningOut] = useState(false);
  const [logoutError,setLogoutError] = useState('');
  async function signOut() {
    setSigningOut(true);setLogoutError('');
    try { await api('/auth/logout',{method:'POST'});clearAuth();navigate('/login',{replace:true}); }
    catch(err) {setLogoutError(err.message);}
    finally {setSigningOut(false);}
  }
  const context = location.pathname === '/admin' ? 'Administration overview' : location.pathname === '/admin/users' ? 'Users & access' : location.pathname === '/dashboard' ? 'Dashboard' : location.pathname === '/analytics' ? 'Analytics' : location.pathname === '/route-analysis' ? 'Route analysis' : location.pathname === '/map' ? 'GIS Map' : location.pathname.endsWith('/edit') ? 'Edit project' : location.pathname.endsWith('/new') ? 'New project' : location.pathname === '/projects' ? 'Project registry' : location.pathname.startsWith('/projects/') ? 'Project details' : systemAdmin ? 'Administration' : 'Workspace';

  useEffect(() => { setDrawerOpen(false); }, [location.pathname]);
  useEffect(() => {
    const media = window.matchMedia('(min-width: 901px)');
    const closeOnDesktop = () => { if (media.matches) setDrawerOpen(false); };
    media.addEventListener('change', closeOnDesktop);
    return () => media.removeEventListener('change', closeOnDesktop);
  }, []);
  function closeDrawer() { setDrawerOpen(false); }
  useEffect(() => {
    if (systemAdmin) return undefined;
    const shortcut = event => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k' && !document.querySelector('dialog[open]')) { event.preventDefault(); setPaletteOpen(true); } };
    window.addEventListener('keydown',shortcut);
    return () => window.removeEventListener('keydown',shortcut);
  },[systemAdmin]);
  function search(event) {
    event.preventDefault();
    if (systemAdmin) return;
    navigate('/projects?search=' + encodeURIComponent(query.trim()));
    setQuery('');
  }
  return <div className={'app-shell' + (collapsed ? ' is-collapsed' : '')}>
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <aside className="sidebar desktop-sidebar"><Brand/><Navigation notices={() => setNoticesOpen(true)} user={user}/>
      <div className="sidebar-note"><span className="sidebar-status"><i/> PROTOTYPE WORKSPACE</span><strong>{systemAdmin ? 'Access administration only.' : 'Visibility before intervention.'}</strong><p>{systemAdmin ? <>Manage users and account access.<br/>Project data is intentionally restricted.</> : <>AI recommends.<br/>Authorized officials decide.</>}</p></div>
      <div className="sidebar-footer"><span>Smart India Hackathon 2026<small>Brief reference · SIH26017</small></span></div>
      <button className="collapse-button" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed}>{collapsed ? <PanelLeftOpen size={18}/> : <PanelLeftClose size={18}/>}<span>Collapse sidebar</span></button>
    </aside>
    <dialog className="nav-drawer" ref={drawer} data-phase={drawerPhase} onClick={event => { if (event.target.closest('a')) closeDrawer(); }} onCancel={event => { event.preventDefault(); setDrawerOpen(false); }} aria-label="Navigation drawer">
      <div className="drawer-heading"><Brand/><button className="icon-button" onClick={closeDrawer} aria-label="Close navigation"><X size={20}/></button></div><Navigation close={closeDrawer} notices={() => setNoticesOpen(true)} user={user}/><p className="drawer-note">{systemAdmin ? 'System administration does not include project-data access.' : 'AI recommends; authorized officials decide.'}</p>
    </dialog>
    <div className="workspace"><header className="topbar"><button ref={opener} className="icon-button mobile-menu" onClick={() => setDrawerOpen(true)} aria-label="Toggle navigation" aria-expanded={drawerOpen}><Menu size={21}/></button>
      <div className="breadcrumb"><span>{systemAdmin ? 'Administration' : 'Workspace'}</span><span>/</span><strong>{context}</strong></div>
      {!systemAdmin && <form role="search" className="global-search" onSubmit={search}><Search size={17}/><input aria-label="Global project search" placeholder="Find a project…" value={query} onChange={e => setQuery(e.target.value)}/><button className="icon-button ghost" aria-label="Search all projects"><ArrowUpRight size={16}/></button></form>}
      {!systemAdmin && <button className="icon-button command-launch" onClick={() => setPaletteOpen(true)} aria-label="Open command palette"><Search size={18}/><kbd>Ctrl K</kbd></button>}
      {!systemAdmin && <button className="icon-button" aria-label="Notification status" title="Review notices" onClick={() => setNoticesOpen(true)}><Bell size={19}/></button>}
      <details className="header-menu profile-menu"><summary><span className="avatar">{user?.display_name?.split(" ").map(x=>x[0]).join("").slice(0,2) || "LG"}</span><span>{user?.display_name || "Prototype user"}<small>{user?.role?.replaceAll("_"," ") || "Authenticated"}</small></span><ChevronDown size={14}/></summary><div className="header-popover"><strong>Your account</strong><p>Role: {user?.role?.replaceAll("_"," ")}</p><p>{user?.email}</p>{logoutError && <p role="alert">{logoutError}</p>}<button className="button secondary" disabled={signingOut} onClick={signOut}>{signingOut ? "Signing out…" : "Sign out"}</button></div></details>
    </header>
    {!systemAdmin && <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)}/>} {!systemAdmin && <NoticeCenter open={noticesOpen} onClose={() => setNoticesOpen(false)} returnTo={location.pathname + location.search}/>}<Toasts/>
    <main id="main-content" tabIndex={-1}><div className="workspace-page" key={location.pathname}>{children}</div></main><footer><span><ShieldCheck size={14}/> {systemAdmin ? 'System administration · project data restricted.' : 'AI recommends; authorized officials decide.'}</span><span>LANDGUARD AI <span className="footer-dot">·</span> PROTOTYPE</span></footer></div>
  </div>;
}
