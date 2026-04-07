import apiClient from './client';

export interface Organization {
  id: string;
  name: string;
  currency: string;
  pool_id: string | null;
  is_demo: boolean;
  disabled: boolean;
  created_at: string;
  role: string;
}

export interface Employee {
  id: string;
  name: string;
  organization_id: string;
  auth_user_id: string;
  role: string;
  created_at: string;
}

export const organizationsApi = {
  list: () =>
    apiClient.get<Organization[]>('/organizations'),

  get: (id: string) =>
    apiClient.get<Organization>(`/organizations/${id}`),

  create: (data: { name: string; currency?: string }) =>
    apiClient.post<Organization>('/organizations', data),

  update: (id: string, data: Partial<Pick<Organization, 'name' | 'currency' | 'disabled'>>) =>
    apiClient.patch<Organization>(`/organizations/${id}`, data),

  delete: (id: string) =>
    apiClient.delete(`/organizations/${id}`),

  listEmployees: (orgId: string) =>
    apiClient.get<Employee[]>(`/organizations/${orgId}/employees`),

  inviteEmployee: (orgId: string, data: { email: string; name?: string }) =>
    apiClient.post<Employee>(`/organizations/${orgId}/employees/invite`, data),
};
