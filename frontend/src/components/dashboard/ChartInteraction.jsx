export function DrillBar({ x,y,width,height,fill,payload,onSelect,label,selected }) {
  function select(event) { event.stopPropagation(); onSelect(payload); }
  return <g role="button" tabIndex={0} aria-label={label(payload)} aria-pressed={selected?.(payload) || false}
    className="drill-bar" onClick={select} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(event); } }}>
    <rect x={x} y={y} width={Math.max(0,width)} height={Math.max(0,height)} rx={3} fill={fill} stroke={selected?.(payload) ? 'var(--text)' : 'none'} strokeWidth={1.5}/>
  </g>;
}
export function AnalyticsTooltip({ active,payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const isComparison = row.avg_compensation_pct != null && row.avg_possession_pct != null;
  return <div className="analytics-tooltip">
    <strong>{row.name || row.label}</strong>
    {isComparison ? <dl>
      <div><dt><i className="tooltip-dot" style={{ background:'var(--primary)' }}/>Compensation</dt><dd>{row.avg_compensation_pct}%</dd></div>
      <div><dt><i className="tooltip-dot" style={{ background:'var(--slate)' }}/>Possession</dt><dd>{row.avg_possession_pct}%</dd></div>
      <div><dt>Pending approvals</dt><dd>{row.projects_with_pending_approvals}</dd></div>
      <div><dt>Legal disputes</dt><dd>{row.projects_with_legal_disputes}</dd></div>
    </dl> : <p className="tooltip-count">{row.project_count ?? row.count} <span>projects</span></p>}
    <small>Select to filter project records</small>
  </div>;
}
