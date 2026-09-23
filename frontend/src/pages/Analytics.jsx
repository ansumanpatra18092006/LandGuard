import { lazy, Suspense, useCallback, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { RefreshCw, ArrowRight } from 'lucide-react';
import { PageHeader, Loading } from '../components/common';
import ScopeDock from '../components/projects/ScopeDock';
import ProjectFilters from '../components/projects/ProjectFilters';
import { filterKeys } from '../utils/projectScope';
import { filterQuery } from '../services/dashboard';
const DashboardAnalytics = lazy(() => import('../components/dashboard/DashboardAnalytics'));

export default function Analytics() {
  const [params,setParams] = useSearchParams();
  const filters = useMemo(() => Object.fromEntries(filterKeys.map(key => [key,params.get(key) || ''])),[params]);
  const [refresh,setRefresh] = useState(0);
  const [status,setStatus] = useState({loading:true,updatedAt:null});
  const report = useCallback(value => setStatus(value),[]);
  const query = filterQuery(filters).toString();
  function drill(values) {
    const next = new URLSearchParams(query);
    for (const [key,value] of Object.entries(values)) { if (value) next.set(key,value); else next.delete(key); }
    setParams(next);
  }
  return <><PageHeader eyebrow="DISTRICT INTELLIGENCE" title="Acquisition command analytics" description="See where acquisition risk concentrates, why it exists, and which intervention needs officer attention next." action={<div className="header-actions"><button aria-label="Refresh analytics" disabled={status.loading} onClick={() => setRefresh(n => n + 1)}><RefreshCw size={15}/> Refresh</button><Link className="button primary" to={'/projects' + (query ? '?' + query : '')}>Explore matching projects <ArrowRight size={15}/></Link></div>}/>
    <div className="refresh-status" role="status">{status.loading ? 'Updating analysis…' : status.updatedAt ? 'Last refreshed: ' + status.updatedAt.toLocaleTimeString() : 'Analysis could not be refreshed.'}</div>
    <div className="scope-toolbar"><ProjectFilters filters={filters} onChange={(key,value) => drill({[key]:value})} onClear={() => setParams({})}/><p className="scope-caption">Filter the current portfolio by district, stage or project attributes. Analytics uses current recorded observations; PAIMANA schedule evidence remains a separate supporting ML signal.</p></div>
    <Suspense fallback={<Loading variant="dashboard"/>}><DashboardAnalytics mode="analytics" filters={filters} refresh={refresh} onDrill={drill} onStatus={report} onClear={() => setParams({})}/></Suspense>
    <ScopeDock count={status.total} filters={filters} onClear={()=>setParams({})} projectUrl={'/projects' + (query ? '?' + query : '')}/>
  </>;
}
