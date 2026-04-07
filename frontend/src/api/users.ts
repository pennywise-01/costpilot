import apiClient from './client';
import type { Employee } from './organizations';

export const usersApi = {
  listEmployees: (orgId: string) =>
    apiClient.get<Employee[]>(`/organizations/${orgId}/employees`),

  inviteEmployee: (orgId: string, data: { email: string; name?: string }) =>
    apiClient.post<Employee>(`/organizations/${orgId}/employees/invite`, data),
};
