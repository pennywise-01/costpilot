import apiClient from './client';

export interface Resource {
  id: string;
  name: string;
  cloud_resource_id: string;
  resource_type?: string;
  cloud_account_id?: string;
  cloud_account_name?: string;
  cloud_type?: string;
  region?: string;
  pool_id?: string;
  pool_name?: string;
  owner_id?: string;
  owner_name?: string;
  tags: Record<string, string>;
  first_seen?: number;
  last_seen?: number;
  total_cost: number;
  daily_cost: number;
  active: boolean;
}

export interface ResourceListResponse {
  resources: Resource[];
  total_count: number;
  limit: number;
  offset: number;
}

export interface ResourceDetail extends Resource {
  meta: Record<string, unknown>;
  recommendations: Record<string, unknown>[];
  daily_expenses: { date: string; cost: number }[];
}

export const resourcesApi = {
  list: (orgId: string, params: {
    limit?: number;
    offset?: number;
    cloud_type?: string;
    region?: string;
    pool_id?: string;
    owner_id?: string;
  }) =>
    apiClient.get<ResourceListResponse>(`/organizations/${orgId}/resources`, { params }),

  get: (id: string) =>
    apiClient.get<ResourceDetail>(`/resources/${id}`),
};
