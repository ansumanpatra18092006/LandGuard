import { ClipboardList, Scale, Banknote, MapPinned, Clock3, ArrowDown } from 'lucide-react';
import { SectionCard } from '../common';

export default function BottleneckCard({ indicators: op, total, selected, onSelect }) {
  const t = op.thresholds;
  const keys = ['pending_approvals','legal_disputes','compensation_lag','possession_lag','slow_response'];
  const rows = [
    ['Pending approvals',op.projects_with_pending_approvals,ClipboardList,'At least one approval pending'],
    ['Legal disputes',op.projects_with_legal_disputes,Scale,'At least one recorded dispute'],
    ['Compensation lag',op.projects_below_compensation_threshold,Banknote,'Below ' + t.compensation_below_pct + '% completed'],
    ['Possession lag',op.projects_below_possession_threshold,MapPinned,'Below ' + t.possession_below_pct + '% completed'],
    ['Slow response',op.projects_with_slow_stakeholder_response,Clock3,'Above ' + t.response_above_days + ' response days'],
  ];
  return <SectionCard title="Administrative bottlenecks" description="Operational indicators · projects affected" className="bottleneck-panel">
    <div className="bottleneck-list">{rows.map(([label,count,Icon,context],i) => {
      const pct = total ? Math.round(count / total * 100) : 0;
      const severity = pct >= 50 ? 'high' : pct >= 25 ? 'medium' : 'low';
      return <button className={'bottleneck-row' + (selected === keys[i] ? ' active-indicator' : '')} data-severity={severity} key={label} aria-label={'Filter by ' + label} aria-pressed={selected === keys[i]} onClick={() => onSelect(selected === keys[i] ? '' : keys[i])}><span className="bottleneck-icon"><Icon size={17}/></span><div><strong>{label}</strong><small>{context}</small><div className="indicator-track"><span style={{ width: pct + '%' }}/></div></div><span className="bottleneck-count">{count}<small>{pct}%</small></span></button>;
    })}</div>
    <div className="bottleneck-foot"><p>Indicators overlap. Prototype thresholds describe recorded conditions, not ML risk.</p><a href="#project-monitor">Review project records <ArrowDown size={14}/></a></div>
  </SectionCard>;
}
