import { Route, Routes, Link, Navigate } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import AuthGate from './components/auth/AuthGate';
import { EmptyState } from './components/common';
import { getUser } from './services/auth';
import Projects from './pages/Projects';
import ProjectDetails from './pages/ProjectDetails';
import ProjectForm from './pages/ProjectForm';
import GISMap from './pages/GISMap';
import Login from './pages/Login';
import Landing from './pages/Landing';
import WhyLandGuard from './pages/WhyLandGuard';
import AccessGuide from './pages/AccessGuide';
import Analytics from './pages/Analytics';
import Users from './pages/Users';
import AdminOverview from './pages/AdminOverview';
import AcceptInvitation from './pages/AcceptInvitation';

const isSystemAdmin = () => getUser()?.role === 'SYSTEM_ADMIN';
function RoleHome() { return isSystemAdmin() ? <Navigate to="/admin" replace/> : <Projects overview/>; }
function OperationalOnly({children}) { return isSystemAdmin() ? <Navigate to="/admin" replace/> : children; }
function SystemAdminOnly({children}) { return isSystemAdmin() ? children : <Navigate to="/dashboard" replace/>; }

function WorkspaceRoutes() {
  return <AppShell><Routes>
    <Route path="/admin" element={<SystemAdminOnly><AdminOverview/></SystemAdminOnly>}/>
    <Route path="/admin/users" element={<SystemAdminOnly><Users/></SystemAdminOnly>}/>
    <Route path="/dashboard" element={<RoleHome/>}/>
    <Route path="/analytics" element={<OperationalOnly><Analytics/></OperationalOnly>}/>
    <Route path="/projects" element={<OperationalOnly><Projects/></OperationalOnly>}/>
    <Route path="/projects/new" element={<OperationalOnly><ProjectForm/></OperationalOnly>}/>
    <Route path="/projects/:projectId/edit" element={<OperationalOnly><ProjectForm/></OperationalOnly>}/>
    <Route path="/projects/:projectId" element={<OperationalOnly><ProjectDetails/></OperationalOnly>}/>
    <Route path="/map" element={<OperationalOnly><GISMap/></OperationalOnly>}/>
    <Route path="*" element={<section className="panel"><h1 className="sr-only">Page not found</h1><EmptyState title="This page could not be found." description="Return to your authorized home area." action={<Link className="button primary" to="/dashboard">Return home</Link>}/></section>}/>
  </Routes></AppShell>;
}

export default function App() {
  return <Routes>
    <Route path="/" element={<Landing/>}/>
    <Route path="/why-landguard" element={<WhyLandGuard/>}/>
    <Route path="/access" element={<AccessGuide/>}/>
    <Route path="/accept-invitation" element={<AcceptInvitation/>}/>
    <Route path="/login" element={<Login/>}/>
    <Route path="/*" element={<AuthGate><WorkspaceRoutes/></AuthGate>}/>
  </Routes>;
}
