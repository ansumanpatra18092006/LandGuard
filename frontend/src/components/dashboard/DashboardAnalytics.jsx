import { Link } from 'react-router-dom';
import { filterQuery } from '../../services/dashboard';
import { useEffect } from 'react';
import { FolderOpen, ClipboardList, Scale, CircleCheck, Database } from 'lucide-react';
import { useResource } from '../../hooks/useResource';
import { loadDashboard } from '../../services/dashboard';
import { ErrorState, Loading, MetricCard, EmptyState } from '../common';
import BottleneckCard from './BottleneckCard';
import AnalyticsIntelligence from './AnalyticsIntelligence';

export default function DashboardAnalytics({ filters, refresh, onDrill, onStatus, onClear, mode = 'dashboard' }) {
  const analysis = mode === 'analytics';
  const resource = useResource(JSON.stringify({ filters, mode }), signal => loadDashboard(filters, signal, analysis), refresh, 0);
  const { data:result,error,loading,updatedAt } = resource;
  useEffect(() => { onStatus({ loading,updatedAt,total:result?.summary.total_projects }); },[loading,updatedAt,result,onStatus]);
  // Keep dashboard intelligence near-real-time even when the officer leaves the page open.
  // Data-entry/API mutations also trigger this event immediately via services/api.js.
  useEffect(() => {
    const timer = window.setInterval(() => window.dispatchEvent(new Event('landguard:data-changed')), 60000);
    return () => window.clearInterval(timer);
  }, []);
  if (error) return <section className="panel analytics-state"><h2>Dashboard data could not be loaded.</h2><ErrorState message={error} retry={() => window.dispatchEvent(new Event('landguard:data-changed'))}/></section>;
  if (!result) return <section aria-label="Loading dashboard"><Loading variant="dashboard"/></section>;
  const { summary: s, districts, stages, indicators, pulse, ledger, districtTrends, stateTrends } = result;
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
    {!analysis && <p className="data-provenance"><Database size={13}/><span>{s.illustrative_projects} illustrative prototype records <span className="separator">/</span> {s.user_entered_projects} user-entered <span className="separator">/</span> {s.integrated_projects || 0} integrated records <span className="separator">/</span> Current database observations</span></p>}
    {s.total_projects === 0 ? <section className="panel"><EmptyState title="No projects are currently available." description="Adjust your filters or add a project to see operational analytics." action={<button onClick={onClear}>Show all projects</button>}/></section> : <>
      {analysis ? <AnalyticsIntelligence summary={s} districts={districts} stages={stages} pulse={pulse} ledger={ledger} districtTrends={districtTrends} stateTrends={stateTrends}/> : <div className="primary-analytics-grid"><BottleneckCard indicators={indicators} total={s.total_projects} selected={filters.indicator} onSelect={indicator => onDrill({ indicator })}/><section className="panel dashboard-next"><div className="section-title"><div><div className="eyebrow">FROM OVERVIEW TO ACTION</div><h2>Choose the next step</h2></div></div><div className="dashboard-next-grid"><div className="dashboard-next-card"><p>Select a bottleneck above, then open a project to inspect or update its observations.</p><Link className="button primary" to={scoped('/projects')}>Open project registry</Link></div><div className="dashboard-next-card"><p>Compare districts and acquisition stages without losing this scope.</p><Link className="button" to={scoped('/analytics')}>Compare in Analytics</Link></div></div></section></div>}
    </>}
  </section>;
}
