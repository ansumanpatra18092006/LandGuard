import { lazy, Suspense, useCallback, useMemo, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { Plus, ArrowUp, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import { filterQuery } from '../services/dashboard';
import { defaultSortDir, filterKeys, pageSizeOptions, sortLabels } from '../utils/projectScope';
import { useResource } from '../hooks/useResource';
import { ErrorState, Loading, EmptyState, PageHeader, Pagination, ProcessIndicator } from '../components/common';
import ProjectFilters from '../components/projects/ProjectFilters';
import ProjectTable from '../components/projects/ProjectTable';
import ScopeDock from '../components/projects/ScopeDock';
import ProjectQuickView from '../components/projects/ProjectQuickView';
import RiskPulse from '../components/dashboard/RiskPulse';

const DashboardAnalytics = lazy(() => import('../components/dashboard/DashboardAnalytics'));

export default function Projects({ overview = false }) {
  const [params,setParams] = useSearchParams();
  const location = useLocation();
  const filters = useMemo(() => Object.fromEntries(filterKeys.map(key => [key,params.get(key) || ''])), [params]);
  const pageNumber = Number(params.get('page') || 1);
  const page = Number.isSafeInteger(pageNumber) && pageNumber > 0 ? pageNumber : 1;
  const pageSizeParam = Number(params.get('page_size'));
  const pageSize = pageSizeOptions.includes(pageSizeParam) ? pageSizeParam : 6;
  const sortBy = sortLabels[params.get('sort_by')] ? params.get('sort_by') : 'project_id';
  const sortDir = params.get('sort_dir') === 'desc' ? 'desc' : 'asc';
  const [refresh,setRefresh] = useState(0);
  const [selected,setSelected] = useState(null);
  const [quickOpen,setQuickOpen] = useState(false);
  const [analyticsStatus,setAnalyticsStatus] = useState({ loading: true, updatedAt: null });
  const reportStatus = useCallback(status => setAnalyticsStatus(status), []);
  const query = filterQuery(filters); query.set('page',page); query.set('page_size',pageSize); query.set('sort_by',sortBy); query.set('sort_dir',sortDir);
  const resource = useResource(query.toString(),signal => api('/projects?' + query,{ signal }),refresh);
  const { data,error,loading,updatedAt } = resource;
  const returnTo = location.pathname + location.search;
  const activeProject = data?.items.find(p => p.id === selected?.id) || selected;
  const busy = loading || (overview && analyticsStatus.loading);
  const lastUpdated = updatedAt && (!overview || analyticsStatus.updatedAt) ? new Date(Math.min(+updatedAt, overview ? +analyticsStatus.updatedAt : +updatedAt)) : null;
  function scope(values,replace = true) {
    const next = new URLSearchParams(params);
    for (const [key,value] of Object.entries(values)) { if (value) next.set(key,value); else next.delete(key); }
    next.delete('page'); setParams(next,{ replace }); setSelected(null); setQuickOpen(false);
  }
  const update = (key,value) => scope({ [key]: value });
  const clear = () => { setParams({}, { replace: true }); setSelected(null); setQuickOpen(false); };
  function drill(values) { scope(values,false); }
  function setPage(value) {
    const next = new URLSearchParams(params);
    if (value > 1) next.set('page',value); else next.delete('page');
    setParams(next); setSelected(null); setQuickOpen(false);
  }
  function setPageSize(value) {
    const next = new URLSearchParams(params);
    if (value !== 6) next.set('page_size',value); else next.delete('page_size');
    next.delete('page'); setParams(next); setSelected(null); setQuickOpen(false);
  }
  // Clicking a column header (or picking a field from the sort menu) toggles direction if it's
  // already the active field, otherwise switches field and falls back to that field's sensible default.
  function sortByField(field) {
    const next = new URLSearchParams(params);
    let dir;
    if (field === sortBy) {
      dir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      if (field === 'project_id') next.delete('sort_by'); else next.set('sort_by',field);
      dir = defaultSortDir(field);
    }
    if (dir === 'asc') next.delete('sort_dir'); else next.set('sort_dir','desc');
    next.delete('page'); setParams(next); setSelected(null); setQuickOpen(false);
  }
  function toggleSortDir() {
    const next = new URLSearchParams(params);
    const flipped = sortDir === 'asc' ? 'desc' : 'asc';
    if (flipped === 'asc') next.delete('sort_dir'); else next.set('sort_dir','desc');
    next.delete('page'); setParams(next); setSelected(null); setQuickOpen(false);
  }
  function inspect(project) { setSelected(project); setQuickOpen(true); }
  return <>
    <PageHeader eyebrow={overview ? 'OPERATIONAL INTELLIGENCE' : 'PROJECT WORKSPACE'} title={overview ? 'Operational dashboard' : 'Project registry'} description={overview ? 'Review portfolio status, identify administrative bottlenecks, and inspect the projects needing attention.' : 'Search, filter, and inspect acquisition records without losing your place.'} action={<div className="header-actions"><button onClick={() => setRefresh(n => n + 1)} disabled={busy} aria-label="Refresh project data"><RefreshCw size={15}/> {busy ? 'Updating…' : 'Refresh'}</button><Link className="button primary" to="/projects/new" state={{ returnTo }}><Plus size={16}/> Add project</Link></div>}/>
    <div className="refresh-status" role="status">{busy ? 'Updating current scope…' : lastUpdated ? 'Last refreshed: ' + lastUpdated.toLocaleTimeString() : 'Some data could not be refreshed.'}</div>
    
    <div className="scope-toolbar"><ProjectFilters filters={filters} onChange={update} onClear={clear} sortBy={sortBy} sortDir={sortDir} onSortField={sortByField} onSortDirToggle={toggleSortDir}/>{overview && <p className="scope-caption">Select a KPI or bottleneck to filter the project queue. Use Analytics for district and stage comparisons.</p>}</div>
    {overview && <RiskPulse filters={filters} refresh={refresh}/>}
    {overview && <Suspense fallback={<Loading variant="dashboard"/>}><DashboardAnalytics filters={filters} refresh={refresh} onDrill={drill} onStatus={reportStatus} onClear={clear}/></Suspense>}
    <section className="panel" id="project-monitor" tabIndex={-1} aria-busy={loading}><div className="section-title"><div><div className="eyebrow">PROJECT RECORDS</div><h2>{overview ? 'Project monitor' : 'All projects'}</h2><p aria-live="polite">{error ? 'These records could not be loaded.' : loading || !data ? 'Loading the selected project scope…' : data.total + ' projects found. Select a row for quick view.'}</p></div><a className="button ghost" href="#project-filters"><ArrowUp size={14}/> Adjust scope</a></div>
      {loading && !data ? <Loading/> : error ? <ErrorState message={error} retry={() => setRefresh(n => n + 1)}/> : data?.items.length ? <ProjectTable projects={data.items} onInspect={inspect} selectedId={selected?.id} returnTo={returnTo} sortBy={sortBy} sortDir={sortDir} onSort={sortByField}/> : <EmptyState action={<><button onClick={clear}>Clear filters</button>{page > 1 && <button onClick={() => setPage(1)}>First page</button>}</>}/>}
      <div className="pagination">
        <span>{data && !loading && !error ? data.total + ' matching records · Page ' + page + ' of ' + Math.max(1,Math.ceil(data.total / pageSize)) : 'Project registry'}</span>
        <div className="pagination-tools">
          <label className="page-size-select"><span className="sr-only">Rows per page</span>
            <select aria-label="Rows per page" value={pageSize} disabled={loading || !!error} onChange={e => setPageSize(Number(e.target.value))}>
              {pageSizeOptions.map(size => <option key={size} value={size}>{size} / page</option>)}
            </select>
          </label>
          {data && !loading && !error ? <Pagination page={page} pageSize={pageSize} total={data.total} onPage={setPage}/> :
            <div className="pagination-controls"><button disabled>Previous</button><button disabled>Next</button></div>}
        </div>
      </div>
    </section>
    <ScopeDock count={data?.total} filters={filters} onClear={clear}/>
    <ProjectQuickView project={quickOpen ? activeProject : null} returnTo={returnTo} onClose={() => setQuickOpen(false)}/>
    <div className="notice"><span>i</span><p><strong>Transparent by design.</strong> Operational indicators describe recorded conditions, not predicted delays. Seed records are illustrative prototype data. AI predictions are available only when a labelled model artifact is loaded; synthetic-demo results are explicitly labelled.</p></div>
  </>;
}
