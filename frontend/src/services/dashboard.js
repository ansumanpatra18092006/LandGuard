import { api } from './api';

export function filterQuery(filters) {
  return new URLSearchParams(Object.entries(filters).filter(([, value]) => value.trim()).map(([key, value]) => [key, value.trim()]));
}

function pulseQuery(filters) {
  const query = new URLSearchParams();
  if (filters?.state?.trim()) query.set('state', filters.state.trim());
  if (filters?.district?.trim()) query.set('district', filters.district.trim());
  const value = query.toString();
  return value ? `?${value}` : '';
}

// Dashboard mode needs only the KPI summary + operational bottlenecks.
// Analytics mode requests the heavier ML/trend datasets as well. Keeping these
// paths separate prevents the dashboard cards from waiting on risk-pulse ML
// inference and 365-day trend queries.
export async function loadDashboard(filters, signal, includeAnalytics = false) {
  const query = filterQuery(filters);

  if (!includeAnalytics) {
    const [summary, indicators] = await Promise.all([
      api(`/dashboard/summary?${query}`, { signal }),
      api(`/dashboard/operational-risks?${query}`, { signal }),
    ]);
    return {
      summary, indicators,
      districts: [], stages: [], pulse: null, ledger: null,
      districtTrends: [], stateTrends: [],
    };
  }

  const trendQuery = new URLSearchParams(query);
  trendQuery.set('days', '365');
  const districtTrendQuery = new URLSearchParams(trendQuery);
  districtTrendQuery.set('group_by', 'district');
  const stateTrendQuery = new URLSearchParams(trendQuery);
  stateTrendQuery.set('group_by', 'state');

  // Start all independent analytics requests together. The previous implementation
  // waited for four base calls before starting ML/trend requests.
  const [summary, districts, stages, indicators, pulse, ledger, districtTrends, stateTrends] = await Promise.all([
    api(`/dashboard/summary?${query}`, { signal }),
    api(`/dashboard/district-summary?${query}`, { signal }),
    api(`/dashboard/stage-distribution?${query}`, { signal }),
    api(`/dashboard/operational-risks?${query}`, { signal }),
    api(`/risk-pulse${pulseQuery(filters)}`, { signal }).catch(() => null),
    api('/interventions/summary', { signal }).catch(() => null),
    api(`/dashboard/delay-trends?${districtTrendQuery}`, { signal }).catch(() => []),
    api(`/dashboard/delay-trends?${stateTrendQuery}`, { signal }).catch(() => []),
  ]);

  return { summary, districts, stages, indicators, pulse, ledger, districtTrends, stateTrends };
}
