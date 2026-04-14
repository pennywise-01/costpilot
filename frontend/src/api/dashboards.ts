import apiClient from './client';

// --- Types ---

export interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  maxW?: number;
  maxH?: number;
  static?: boolean;
}

export interface WidgetConfigEntry {
  type: string;
  metric: string;
  title?: string;
  color?: string;
  icon?: string;
  dateRange?: number;
  groupBy?: string;
  smooth?: boolean;
  params?: Record<string, unknown>;
}

export interface DashboardListItem {
  id: string;
  name: string;
  slug: string;
  is_default: boolean;
  updated_by: string;
  updated_at: string;
}

export interface DashboardDetail {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  is_default: boolean;
  layout_config: LayoutItem[];
  previous_layout_config: LayoutItem[] | null;
  widget_config: Record<string, WidgetConfigEntry>;
  version: number;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export interface WidgetDataRequest {
  type: string;
  metric: string;
  params?: Record<string, unknown>;
}

export interface BatchWidgetDataResponse {
  data: Record<string, unknown>;
  errors: Record<string, string>;
  meta: {
    data_source: string;
    freshness: string;
    generated_at: string;
  };
}

// --- API ---

export const dashboardsApi = {
  list: (orgId: string) =>
    apiClient.get<DashboardListItem[]>(`/organizations/${orgId}/dashboards`),

  get: (orgId: string, dashboardId: string) =>
    apiClient.get<DashboardDetail>(`/organizations/${orgId}/dashboards/${dashboardId}`),

  create: (orgId: string, data: { name: string; template_dashboard_id?: string }) =>
    apiClient.post<DashboardDetail>(`/organizations/${orgId}/dashboards`, data),

  update: (orgId: string, dashboardId: string, data: {
    name?: string;
    layout_config?: LayoutItem[];
    widget_config?: Record<string, WidgetConfigEntry>;
    version: number;
  }) =>
    apiClient.put<DashboardDetail>(`/organizations/${orgId}/dashboards/${dashboardId}`, data),

  delete: (orgId: string, dashboardId: string) =>
    apiClient.delete(`/organizations/${orgId}/dashboards/${dashboardId}`),

  setDefault: (orgId: string, dashboardId: string) =>
    apiClient.put<DashboardDetail>(`/organizations/${orgId}/dashboards/${dashboardId}/set-default`),

  revert: (orgId: string, dashboardId: string) =>
    apiClient.post<DashboardDetail>(`/organizations/${orgId}/dashboards/${dashboardId}/revert`),

  duplicate: (orgId: string, dashboardId: string, name: string) =>
    apiClient.post<DashboardDetail>(`/organizations/${orgId}/dashboards/${dashboardId}/duplicate`, { name }),

  postWidgetData: (orgId: string, widgets: WidgetDataRequest[]) =>
    apiClient.post<BatchWidgetDataResponse>(
      `/organizations/${orgId}/dashboards/widgets/data`,
      { widgets },
    ),
};
