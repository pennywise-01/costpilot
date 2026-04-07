import apiClient from './client';

export interface Pool {
  id: string;
  name: string;
  limit: number;
  organization_id: string;
  parent_id: string | null;
  purpose: string;
  default_owner_id: string | null;
  created_at: string;
  children: Pool[];
  // Real-time calculated fields from backend
  spent: number;
  owner: string | null;
}

export interface PoolPolicy {
  id: string;
  type: string;
  limit: number;
  active: boolean;
  pool_id: string;
  created_at: string;
}

export const poolsApi = {
  list: (orgId: string) =>
    apiClient.get<Pool[]>(`/organizations/${orgId}/pools`),

  get: (id: string) =>
    apiClient.get<Pool>(`/pools/${id}`),

  create: (orgId: string, data: { name: string; limit?: number; parent_id?: string; purpose?: string }) =>
    apiClient.post<Pool>(`/organizations/${orgId}/pools`, data),

  update: (id: string, data: Partial<Pick<Pool, 'name' | 'limit' | 'default_owner_id' | 'purpose'>>) =>
    apiClient.patch<Pool>(`/pools/${id}`, data),

  delete: (id: string) =>
    apiClient.delete(`/pools/${id}`),

  listPolicies: (id: string) =>
    apiClient.get<PoolPolicy[]>(`/pools/${id}/policies`),

  createPolicy: (id: string, data: { type: string; limit: number; active?: boolean }) =>
    apiClient.post<PoolPolicy>(`/pools/${id}/policies`, data),
};
