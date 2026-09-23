import { Activity, Database, History, RefreshCw } from 'lucide-react';
import { api } from '../../services/api';
import { useResource } from '../../hooks/useResource';
import { ErrorState, Loading, SectionCard, pretty } from '../common';

function eventLabel(value='') {
  return pretty(value.replace(/^INTEGRATION_/, 'INTEGRATION '));
}

export default function ProjectHistoryPanel({ projectId }) {
  const { data, loading, error } = useResource(`project-history:${projectId}`, signal => api(`/projects/${projectId}/history`, { signal }));
  if (loading && !data) return <Loading variant="detail"/>;
  if (error) return <ErrorState message={error}/>;
  const events = data?.events || [];
  const snapshots = data?.snapshots || [];
  return <div className="project-history-grid">
    <SectionCard title="Project audit trail" description="Persisted create, update and integration events for this project" action={<Activity size={18}/>}>
      {!events.length ? <p className="muted">No project-field audit events have been recorded yet.</p> : <ol className="project-audit-list">{events.map(event => <li key={event.id}>
        <span><Activity size={14}/></span>
        <div><strong>{eventLabel(event.event_type)}</strong><p>{event.detail}</p><small>{event.changed_fields?.length ? `Changed: ${event.changed_fields.map(pretty).join(', ')} · ` : ''}{event.actor_email || event.actor_role || 'System'} · {new Date(event.created_at).toLocaleString()}</small></div>
      </li>)}</ol>}
    </SectionCard>
    <SectionCard title="Historical project snapshots" description="Risk and acquisition-state observations captured when the record changes" action={<History size={18}/>}>
      {!snapshots.length ? <p className="muted">No snapshots are available yet.</p> : <div className="project-snapshot-list">{snapshots.slice(0,20).map(snapshot => <article key={snapshot.id}>
        <div><strong>{new Date(snapshot.captured_at).toLocaleString()}</strong><span>{pretty(snapshot.acquisition_stage)}</span></div>
        <dl><div><dt>Acquisition risk</dt><dd>{snapshot.acquisition_risk_score ?? '—'}/100</dd></div><div><dt>Compensation</dt><dd>{Math.round(snapshot.compensation_completion_pct)}%</dd></div><div><dt>Possession</dt><dd>{Math.round(snapshot.possession_pct)}%</dd></div><div><dt>Approvals</dt><dd>{snapshot.pending_approvals}</dd></div><div><dt>Disputes</dt><dd>{snapshot.legal_disputes}</dd></div><div><dt>ML schedule</dt><dd>{snapshot.delay_probability == null ? '—' : `${Math.round(snapshot.delay_probability*100)}%`}</dd></div></dl>
      </article>)}</div>}
      <p className="panel-footnote"><Database size={13}/> Snapshots support district/state trend analysis and do not overwrite prior observations.</p>
    </SectionCard>
  </div>;
}
