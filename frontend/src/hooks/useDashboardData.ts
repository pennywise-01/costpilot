import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { dashboardsApi, type DashboardDetail, type WidgetDataRequest } from '@/api/dashboards';
import { useCurrentOrgId } from '@/hooks/useCurrentOrgId';

export const useDashboardData = (dashboard: DashboardDetail | null) => {
  const orgId = useCurrentOrgId();

  // Deduplicate by (type, metric, JSON-serialized params) before hitting the API
  const widgetRequests: WidgetDataRequest[] = useMemo(() => {
    if (!dashboard) return [];
    const seen = new Set<string>();
    return Object.values(dashboard.widget_config).reduce<WidgetDataRequest[]>((acc, w) => {
      const key = `${w.type}:${w.metric}:${JSON.stringify(w.params ?? {})}`;
      if (!seen.has(key)) {
        seen.add(key);
        acc.push({ type: w.type, metric: w.metric, params: w.params ?? {} });
      }
      return acc;
    }, []);
  }, [dashboard]);

  return useQuery({
    queryKey: ['dashboard-data', orgId, dashboard?.id, widgetRequests],
    queryFn: () => dashboardsApi.postWidgetData(orgId, widgetRequests).then((r) => r.data),
    enabled: !!dashboard && widgetRequests.length > 0,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
};
