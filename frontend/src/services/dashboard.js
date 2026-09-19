import { api } from './api';

export function filterQuery(filters) {
  return new URLSearchParams(Object.entries(filters).filter(([, value]) => value.trim()).map(([key, value]) => [key, value.trim()]));
}

export async function loadDashboard(filters, signal) {
  const query = filterQuery(filters);
  const [summary, districts, stages, indicators] = await Promise.all(
    ['summary', 'district-summary', 'stage-distribution', 'operational-risks']
      .map(path => api(`/dashboard/${path}?${query}`, { signal })),
  );
  return { summary, districts, stages, indicators };
}
