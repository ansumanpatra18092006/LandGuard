export const filterKeys = ['search','state','district','project_type','acquisition_stage','indicator'];
export const indicatorLabels = {
  pending_approvals: 'Pending approvals', legal_disputes: 'Legal disputes',
  compensation_lag: 'Compensation lag', possession_lag: 'Possession lag', slow_response: 'Slow response',
};
export const sortOptions = [
  { value: 'project_id', label: 'Project ID' },
  { value: 'project_name', label: 'Project name' },
  { value: 'state', label: 'State' },
  { value: 'district', label: 'District' },
  { value: 'project_type', label: 'Project type' },
  { value: 'acquisition_stage', label: 'Acquisition stage' },
  { value: 'compensation_completion_pct', label: 'Compensation %' },
  { value: 'possession_pct', label: 'Possession %' },
  { value: 'rehabilitation_completion_pct', label: 'Rehabilitation %' },
  { value: 'pending_approvals', label: 'Pending approvals' },
  { value: 'legal_disputes', label: 'Legal disputes' },
  { value: 'stakeholder_response_days', label: 'Response time' },
  { value: 'elapsed_acquisition_days', label: 'Elapsed duration' },
];
export const sortLabels = Object.fromEntries(sortOptions.map(({ value, label }) => [value, label]));
// Numeric/progress fields read better sorted highest-first by default; identifiers and names read better A→Z.
const descByDefault = new Set(['compensation_completion_pct','possession_pct','rehabilitation_completion_pct','pending_approvals','legal_disputes','stakeholder_response_days','elapsed_acquisition_days']);
export const defaultSortDir = field => descByDefault.has(field) ? 'desc' : 'asc';
export const pageSizeOptions = [6, 12, 24];
export function safeReturnTo(value) {
  if (typeof value !== 'string') return '/projects';
  const path = value.split('?')[0];
  return ['/dashboard', '/projects', '/analytics', '/map'].includes(path) ? value : '/projects';
}
export function scopeLabel(url) {
  const query = new URLSearchParams(url.split('?')[1] || '');
  const page = url.split('?')[0] === '/dashboard' ? 'Dashboard' : url.startsWith('/analytics') ? 'Analytics' : 'Projects';
  return [page, query.get('state'), query.get('district'), query.get('acquisition_stage')?.toLowerCase(), indicatorLabels[query.get('indicator')], query.get('search')].filter(Boolean).join(' · ');
}
