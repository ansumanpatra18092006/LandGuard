import { useId } from 'react';
import { useAnimatedNumber } from '../hooks/useAnimatedNumber';
import { useReveal } from '../hooks/useReveal';
import { useSpotlight } from '../hooks/useSpotlight';
import ProcessStrip from './common/ProcessStrip';
import { AlertCircle, ChevronLeft, ChevronRight, FolderOpen, Info, RotateCcw } from 'lucide-react';

// Kept under the original name so callers do not need to care that it grew a timeline.
export const ProcessIndicator = ProcessStrip;

export const pretty = value => value?.toLowerCase().replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());

export function PageHeader({ eyebrow, title, description, action, children }) {
  return <div className="page-title"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{description && <p>{description}</p>}{children}</div>{action}</div>;
}
export function MetricCard({ label, value, caption, icon: Icon, onClick, active = false, tone = 'neutral', index = 0 }) {
  const numeric = typeof value === 'number' ? value : value.endsWith('%') ? parseFloat(value) : null;
  const animated = useAnimatedNumber(numeric ?? 0);
  const display = numeric === null ? value : typeof value === 'number' ? Math.round(animated) : Number(animated.toFixed(2)) + '%';
  const Tag = onClick ? 'button' : 'article';
  // `index` drives the entrance stagger; the spotlight props are inert on coarse pointers.
  const spotlight = useSpotlight();
  return <Tag {...spotlight} style={{ '--index': index }} className={'stat' + (onClick ? ' clickable-stat' : '') + (active ? ' active-indicator' : '')} data-testid={label} data-tone={tone} onClick={onClick} aria-label={onClick ? 'Filter projects with ' + label.toLowerCase() : undefined} aria-pressed={onClick ? active : undefined}><div className="stat-heading"><span>{label}</span>{Icon && <span className="metric-icon"><Icon size={18}/></span>}</div><strong aria-label={String(value)} data-value={value} className={value === 'Unavailable' ? 'metric-unavailable' : undefined}>{display}</strong><small>{caption}{onClick && <span className="metric-action">{active ? 'Selected · click to clear' : 'Click to explore projects'}</span>}</small></Tag>;
}
export function SectionCard({ title, description, action, children, className = '', reveal = true }) {
  const [revealRef, revealed] = useReveal();
  const classes = ['panel', className, reveal ? 'reveal' : '', reveal && revealed ? 'is-revealed' : ''];
  return <section ref={reveal ? revealRef : undefined} className={classes.filter(Boolean).join(' ')}><div className="section-title"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{action}</div>{children}</section>;
}
export function ErrorState({ message, retry }) {
  return <div className="error" role="alert"><AlertCircle size={25}/><div><strong>We couldn’t complete that request.</strong><p>{message || 'Check your connection and try again.'}</p>{retry && <button onClick={retry}><RotateCcw size={15}/>Try again</button>}</div></div>;
}
export function EmptyState({ title = 'No projects match your filters.', description, action }) {
  return <div className="empty"><span className="empty-icon"><FolderOpen size={26}/></span><h2>{title}</h2><p>{description || 'Try a different search or clear your filters to explore all projects.'}</p>{action}</div>;
}
export function Loading({ variant = 'table' }) {
  return <div className={'loading skeleton-' + variant} role="status" aria-label={'Loading ' + variant}>
    <span className="sr-only">Loading project records…</span>
    {['dashboard','detail'].includes(variant) ? <><div className="skeleton-metrics">{[1,2,3,4].map(n => <div key={n} className="skeleton-card"><i/><b/><i/></div>)}</div><div className="skeleton-charts"><div/><div/></div></> :
    [1,2,3,4].map(n => <div className="skeleton-row" key={n}><i/><i/><i/></div>)}
  </div>;
}
export function Progress({ label, value, compact = false }) {
  const tone = value >= 75 ? 'high' : value >= 40 ? 'medium' : 'low';
  return <div className={compact ? 'progress compact' : 'progress'} data-tone={tone} title={label + ': ' + value + '% complete in the current project record.'}><div><span className={compact ? 'sr-only' : ''}>{label}</span><strong>{value}%</strong></div><progress className="sr-only" value={value} max="100" aria-label={label}/><span className="progress-track" aria-hidden="true"><i style={{width:value + '%'}}/></span></div>;
}
// Builds a compact page-number window with gaps, e.g. [1, '…', 4, 5, 6, '…', 12].
function paginationWindow(page, pages) {
  if (pages <= 7) return Array.from({ length: pages },(_,i) => i + 1);
  const keep = new Set([1,2,pages - 1,pages,page - 1,page,page + 1].filter(p => p >= 1 && p <= pages));
  const ordered = [...keep].sort((a,b) => a - b);
  return ordered.flatMap((p,i) => i > 0 && p - ordered[i - 1] > 1 ? ['…',p] : [p]);
}
export function Pagination({ page, pageSize, total, onPage, disabled = false }) {
  const pages = Math.max(1,Math.ceil(total / pageSize));
  if (disabled) return <nav className="pagination-controls" aria-label="Project pages"/>;
  return <nav className="pagination-controls" aria-label="Project pages">
    <button disabled={page === 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft size={15}/></button>
    {paginationWindow(page,pages).map((p,i) => p === '…' ? <span key={'gap' + i} className="pagination-gap" aria-hidden="true">…</span> :
      <button key={p} className={p === page ? 'active-page' : ''} aria-current={p === page ? 'page' : undefined} aria-label={'Page ' + p} onClick={() => onPage(p)}>{p}</button>)}
    <button disabled={page === pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight size={15}/></button>
  </nav>;
}
export function InfoTooltip({ text }) {
  const id = useId();
  return <span className="info-tooltip"><button type="button" className="icon-button ghost" aria-label="About this metric" aria-describedby={id}><Info size={15}/></button><span role="tooltip" id={id}>{text}</span></span>;
}

