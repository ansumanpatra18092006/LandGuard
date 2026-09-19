import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, MapPin, ShieldCheck } from 'lucide-react';
import Modal from '../common/Modal';
import { pretty, Progress } from '../common';
import { api } from '../../services/api';

export default function ProjectQuickView({ project, onClose, returnTo }) {
  const [readiness,setReadiness] = useState(null);
  const [readinessError,setReadinessError] = useState('');
  useEffect(() => {
    setReadiness(null); setReadinessError('');
    if (!project) return undefined;
    const controller = new AbortController();
    api(`/projects/${project.project_id}/readiness`,{signal:controller.signal})
      .then(setReadiness)
      .catch(err => { if (err.name !== 'AbortError') setReadinessError(err.message); });
    return () => controller.abort();
  },[project?.project_id]);

  return <Modal open={!!project} onClose={onClose} title="Project quick view" className="quick-view">
    {project && <div key={project.id} className="quick-content content-enter"><div className="eyebrow">{project.project_id} · {pretty(project.data_source)} record</div><h3>{project.project_name}</h3><p><MapPin size={14}/> {project.district}, {project.state}</p><span className="badge">{pretty(project.acquisition_stage)}</span>
      {readiness && <section className="quick-readiness" aria-label="Acquisition readiness"><div><span className="eyebrow"><ShieldCheck size={13}/> ACQUISITION READINESS</span><strong>{readiness.readiness_score}/100 · {readiness.readiness_label}</strong></div><dl><div><dt>Primary blocker</dt><dd>{readiness.primary_blocker}</dd></div><div><dt>Next milestone</dt><dd>{readiness.next_milestone}</dd></div></dl><small>Transparent operational readiness logic — not ML.</small></section>}
      {readinessError && <p className="muted">Readiness unavailable in quick view: {readinessError}</p>}
      <Progress label="Compensation" value={project.compensation_completion_pct}/><Progress label="Possession" value={project.possession_pct}/><Progress label="Rehabilitation" value={project.rehabilitation_completion_pct}/>
      <dl className="quick-facts"><div><dt>Pending approvals</dt><dd>{project.pending_approvals}</dd></div><div><dt>Legal disputes</dt><dd>{project.legal_disputes}</dd></div><div><dt>Land area</dt><dd>{project.land_area} ha</dd></div><div><dt>Coordinates</dt><dd>{project.latitude}, {project.longitude}</dd></div></dl>
      <div className="quick-actions"><Link className="button primary" to={'/projects/' + project.project_id} state={{ returnTo }} onClick={onClose}>Open command center <ArrowRight size={15}/></Link><Link className="button" to={'/projects/' + project.project_id + '?tab=gis'} state={{ returnTo }} onClick={onClose}><MapPin size={15}/> Locate on map</Link></div>
      <p className="muted">Quick view shows recorded acquisition status and readiness. Predictive schedule intelligence, historical analogues and tracked interventions are available in the full project command center.</p>
    </div>}
  </Modal>;
}
