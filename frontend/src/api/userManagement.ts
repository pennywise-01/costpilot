import apiClient from './client';
import type { Role } from './rbac';

export interface Permission {
  action: string;
  resource_type: string;
  granted_via_role?: string;
  granted_via_abac: boolean;
}

export interface RoleSummary {
  id: string;
  name: string;
  description: string;
}

export interface UserActivitySummary {
  last_login: string | null;
  login_count_30d: number;
  actions_count_30d: number;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  status: 'pending' | 'active' | 'suspended' | 'deactivated' | 'locked';
  is_active: boolean;
  last_login: string | null;
  roles: RoleSummary[];
  department: string | null;
  job_title: string | null;
  joined_at: string | null;
  created_at: string;
}

export interface UserDetail extends User {
  preferences: Record<string, any> | null;
  activity_summary: UserActivitySummary;
  permissions: Permission[];
}

export interface UserFilters {
  status?: string;
  role_id?: string;
  department?: string;
  search?: string;
  page?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface PaginatedUsers {
  items: User[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface UserInviteRequest {
  email: string;
  role_id: string;
  department?: string;
  job_title?: string;
  message?: string;
}

export interface UserInviteBulkRequest {
  invitations: UserInviteRequest[];
}

export interface UserInviteResponse {
  id: string;
  email: string;
  status: string;
  error?: string;
  invitation_token?: string;
  expires_at: string;
}

export interface BulkInviteResponse {
  total: number;
  successful: number;
  failed: number;
  results: UserInviteResponse[];
}

export interface InvitationAcceptData {
  display_name: string;
  password: string;
}

export interface InvitationDetail {
  token: string;
  email: string;
  organization_name: string;
  invited_by_name: string;
  role_name: string | null;
  expires_at: string;
  is_valid: boolean;
}

export interface UserUpdateRequest {
  display_name?: string;
  department?: string;
  job_title?: string;
  is_active?: boolean;
}

export interface UserStatusUpdateRequest {
  status: string;
  reason?: string;
}

export interface UserRoleUpdateRequest {
  role_ids: string[];
  action: 'assign' | 'revoke' | 'replace';
  reason?: string;
  expires_at?: string;
}

export interface UserRoleAssignment {
  id: string;
  user_id: string;
  role_id: string;
  role: RoleSummary;
  organization_id: string;
  assigned_by: string | null;
  assigned_at: string;
  expires_at: string | null;
}

export interface ActivityLogEntry {
  id: string;
  user_id: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  metadata: Record<string, any> | null;
  created_at: string;
}

export interface ActivityLogFilter {
  action?: string;
  resource_type?: string;
  from_date?: string;
  to_date?: string;
}

export interface ActivityLogResponse {
  items: ActivityLogEntry[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface EffectivePermissionsResponse {
  user_id: string;
  organization_id: string;
  roles: RoleSummary[];
  permissions: Permission[];
  abac_policies: any[];
  calculated_at: string;
}

export const userManagementApi = {
  // User listing and details
  listUsers: (orgId: string, filters: UserFilters = {}) =>
    apiClient.get<PaginatedUsers>(`/organizations/${orgId}/users`, { params: filters }),

  getUser: (orgId: string, userId: string) =>
    apiClient.get<UserDetail>(`/organizations/${orgId}/users/${userId}`),

  updateUser: (orgId: string, userId: string, data: UserUpdateRequest) =>
    apiClient.patch<User>(`/organizations/${orgId}/users/${userId}`, data),

  // User status management
  suspendUser: (orgId: string, userId: string, data: UserStatusUpdateRequest) =>
    apiClient.post<User>(`/organizations/${orgId}/users/${userId}/suspend`, data),

  activateUser: (orgId: string, userId: string) =>
    apiClient.post<User>(`/organizations/${orgId}/users/${userId}/activate`),

  removeUser: (orgId: string, userId: string) =>
    apiClient.delete<void>(`/organizations/${orgId}/users/${userId}`),

  resetPassword: (orgId: string, userId: string, newPassword: string) =>
    apiClient.post<User>(`/organizations/${orgId}/users/${userId}/reset-password`, { new_password: newPassword }),

  // Invitations
  inviteUser: (orgId: string, data: UserInviteRequest) =>
    apiClient.post<UserInviteResponse>(`/organizations/${orgId}/users/invite`, data),

  inviteBulk: (orgId: string, data: UserInviteBulkRequest) =>
    apiClient.post<BulkInviteResponse>(`/organizations/${orgId}/users/invite-bulk`, data),

  getInvitation: (token: string) =>
    apiClient.get<InvitationDetail>(`/invitations/${token}`),

  acceptInvitation: (token: string, data: InvitationAcceptData) =>
    apiClient.post<{ access_token: string; token_type: string; user: any }>(
      `/invitations/${token}/accept`,
      data
    ),

  // Role management
  getUserRoles: (orgId: string, userId: string) =>
    apiClient.get<UserRoleAssignment[]>(`/organizations/${orgId}/users/${userId}/roles`),

  updateUserRoles: (orgId: string, userId: string, data: UserRoleUpdateRequest) =>
    apiClient.patch<UserRoleAssignment[]>(`/organizations/${orgId}/users/${userId}/roles`, data),

  // Permissions
  getUserPermissions: (orgId: string, userId: string) =>
    apiClient.get<EffectivePermissionsResponse>(`/organizations/${orgId}/users/${userId}/permissions`),

  // Activity logs
  getUserActivity: (orgId: string, userId: string, filters: ActivityLogFilter & { page?: number; limit?: number } = {}) =>
    apiClient.get<ActivityLogResponse>(`/organizations/${orgId}/users/${userId}/activity`, { params: filters }),

  getOrganizationActivity: (orgId: string, filters: ActivityLogFilter & { page?: number; limit?: number } = {}) =>
    apiClient.get<ActivityLogResponse>(`/organizations/${orgId}/activity`, { params: filters }),
};
