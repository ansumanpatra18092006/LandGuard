import { Link } from 'react-router-dom';
import { filterQuery } from '../../services/dashboard';
import { useEffect } from 'react';
import { FolderOpen, ClipboardList, Scale, CircleCheck, Database } from 'lucide-react';
import { useResource } from '../../hooks/useResource';
import { loadDashboard } from '../../services/dashboard';
import { ErrorState, Loading, pretty, MetricCard, EmptyState } from '../common';
import DistributionChart from './DistributionChart';
import ProgressComparison from './ProgressComparison';
import BottleneckCard from './BottleneckCard';

export default function DashboardAnalytics({ filters, refresh, onDrill, onStatus, onClear, mode = 'dashboard' }) {
  const resource = useResource(JSON.stringify(filters),signal => loadDashboard(filters,signal),refresh);
  const { data:result,error,loading,updatedAt } = resource;
  useEffect(() => { onStatus({ loading,updatedAt,total:result?.summary.total_projects }); },[loading,updatedAt,result,onStatus]);
  const districtSelected = row => filters.district === row.district && filters.state === row.state;
  const districtDrill = row => onDrill(districtSelected(row) ? { state:'',district:'' } : { state:row.state,district:row.district });
  const stageDrill = row => onDrill({ acquisition_stage:filters.acquisition_stage === row.stage ? '' : row.stage });
  if (error) return <section className="panel analytics-state"><h2>Dashboard data could not be loaded.</h2><ErrorState message={error} retry={() => window.dispatchEvent(new Event('landguard:data-changed'))}/></section>;
  if (!result) return <section aria-label="Loading dashboard"><Loading variant="dashboard"/></section>;
  const { summary: s, districts, stages, indicators } = result;
  const analysis = mode === 'analytics';
  const query = filterQuery(filters).toString();
  const scoped = path => path + (query ? '?' + query : '');
  const metrics = [
    ['Total projects',s.total_projects,'Across the selected project scope',FolderOpen,'teal'],
    ['Pending approvals',s.pending_approvals,'Individual approvals awaiting action',ClipboardList,'amber'],
    ['Projects with legal disputes',s.projects_with_legal_disputes,'At least one recorded dispute',Scale,'red'],
    ['Average compensation progress',s.avg_compensation_pct === null ? 'Unavailable' : s.avg_compensation_pct + '%','Unweighted average across projects',CircleCheck,'green'],
  ];
  return <section className="analytics" aria-label="Operational dashboard">
    {!analysis && <div className="stats">{metrics.map(([label,value,caption,icon,tone],i) => <MetricCard key={label} index={i} {...{label,value,caption,icon,tone}} active={i === 1 ? filters.indicator === 'pending_approvals' : i === 2 ? filters.indicator === 'legal_disputes' : false} onClick={i === 1 || i === 2 ? () => { const indicator = i === 1 ? 'pending_approvals' : 'legal_disputes'; onDrill({ indicator:filters.indicator === indicator ? '' : indicator }); } : undefined}/>)}</div>}
    {analysis && <div className="panel analysis-scope"><strong>{s.total_projects} projects</strong> across {districts.length} districts in this scope. Averages are unweighted; indicators can overlap.</div>}
    <p className="data-provenance"><Database size={13}/><span>{s.illustrative_projects} illustrative prototype records <span className="separator">/</span> {s.user_entered_projects} user-entered records <span className="separator">/</span> Current database observations</span></p>
    {s.total_projects === 0 ? <section className="panel"><EmptyState title="No projects are currently available." description="Adjust your filters or add a project to see operational analytics." action={<button onClick={onClear}>Show all projects</button>}/></section> : <>
      {analysis ? <ProgressComparison districts={districts} onSelect={districtDrill} isSelected={districtSelected}/> : <div className="primary-analytics-grid"><BottleneckCard indicators={indicators} total={s.total_projects} selected={filters.indicator} onSelect={indicator => onDrill({ indicator })}/><section className="panel dashboard-next"><p className="eyebrow">FROM OVERVIEW TO ACTION</p><h2>Choose the next step.</h2><p>Select a bottleneck to filter the project queue below. Review the recorded issues, then open a project to inspect or update its observations.</p><Link className="button primary" to={scoped('/projects')}>Open project registry</Link><hr/><h2>Need a broader comparison?</h2><p>Analytics compares districts and acquisition stages. Carry this scope into the analysis without searching again.</p><Link className="button" to={scoped('/analytics')}>Compare in Analytics</Link></section></div>}
      {analysis && <>
      <div className="chart-grid">
        <DistributionChart title="District project distribution" subtitle="Project count by district and state" data={districts.map(row => ({ ...row, name: row.district + ', ' + row.state, count: row.project_count }))} onSelect={districtDrill} isSelected={districtSelected}/>
        <DistributionChart title="Projects by acquisition stage" subtitle="Current stage · prototype categories" data={stages.map(row => ({ ...row, name: pretty(row.stage), count: row.count }))} onSelect={stageDrill} isSelected={row => row.stage === filters.acquisition_stage}/>
      </div>
      <details className="panel district-panel"><summary><span>District acquisition progress</span><small>View detailed figures</small></summary><div className="table-wrap" tabIndex={0} aria-label="District acquisition data"><table><caption className="sr-only">Unweighted district project averages and total approval/dispute counts</caption><thead><tr><th scope="col">District / State</th><th scope="col">Projects</th><th scope="col">Avg. compensation</th><th scope="col">Avg. possession</th><th scope="col">Pending approvals</th><th scope="col">Legal disputes</th></tr></thead><tbody>{districts.map(row => <tr key={row.state + '/' + row.district}><td><button className="ghost" aria-pressed={districtSelected(row)} onClick={() => districtDrill(row)}>{row.district}</button><small>{row.state}</small></td><td>{row.project_count}</td><td>{row.avg_compensation_pct}%</td><td>{row.avg_possession_pct}%</td><td>{row.pending_approvals}</td><td>{row.legal_disputes}</td></tr>)}</tbody></table></div></details>
      </>}
    </>}
  </section>;
}
