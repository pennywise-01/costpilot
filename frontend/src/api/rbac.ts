import apiClient from './client';

export interface Permission {
  id: string;
  action: string;
  resource_type: string;
}

export interface Role {
  id: string;
  name: string;
  description: string;
  organization_id: string;
  is_default: boolean;
  permissions: Permission[];
  created_at: string;
  updated_at: string;
}

export interface UserRoleAssignment {
  id: string;
  user_id: string;
  role_id: string;
  organization_id: string;
  role: Role;
  created_at: string;
}

export interface ABACPolicy {
  id: string;
  name: string;
  description: string;
  organization_id: string;
  resource_type: string;
  action: string;
  attribute_key: string;
  operator: string;
  attribute_value: string;
  effect_allow: boolean;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AccessReview {
  id: string;
  organization_id: string;
  user_id: string;
  reviewer_id: string;
  role_id: string;
  status: 'pending' | 'approved' | 'revoked';
  notes: string;
  role: Role;
  created_at: string;
  updated_at: string;
}

export interface SSOConfig {
  id: string;
  organization_id: string;
  provider: string;
  issuer_url: string;
  client_id: string;
  metadata_url: string;
  enabled: boolean;
  auto_provision_roles: boolean;
  default_role_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface RBACOverview {
  total_roles: number;
  total_assignments: number;
  total_abac_policies: number;
  pending_reviews: number;
  sso_configs: SSOConfig[];
  roles: Role[];
}

export interface PermissionCheckResult {
  allowed: boolean;
  matched_roles: string[];
  matched_policies: string[];
}

export const rbacApi = {
  // Overview
  getOverview: (orgId: string) =>
    apiClient.get<RBACOverview>(`/enterprise/${orgId}/rbac`),

  // Roles
  listRoles: (orgId: string) =>
    apiClient.get<Role[]>(`/enterprise/${orgId}/rbac/roles`),

  createRole: (orgId: string, data: { name: string; description?: string; permissions?: { action: string; resource_type: string }[]; is_default?: boolean }) =>
    apiClient.post<Role>(`/enterprise/${orgId}/rbac/roles`, data),

  updateRole: (orgId: string, roleId: string, data: { name?: string; description?: string; permissions?: { action: string; resource_type: string }[]; is_default?: boolean }) =>
    apiClient.patch<Role>(`/enterprise/${orgId}/rbac/roles/${roleId}`, data),

  deleteRole: (orgId: string, roleId: string) =>
    apiClient.delete(`/enterprise/${orgId}/rbac/roles/${roleId}`),

  // Assignments
  listAssignments: (orgId: string, userId?: string) =>
    apiClient.get<UserRoleAssignment[]>(`/enterprise/${orgId}/rbac/assignments`, { params: userId ? { user_id: userId } : {} }),

  assignRole: (orgId: string, data: { user_id: string; role_id: string }) =>
    apiClient.post<UserRoleAssignment>(`/enterprise/${orgId}/rbac/assignments`, data),

  revokeAssignment: (orgId: string, assignmentId: string) =>
    apiClient.delete(`/enterprise/${orgId}/rbac/assignments/${assignmentId}`),

  // ABAC Policies
  listPolicies: (orgId: string) =>
    apiClient.get<ABACPolicy[]>(`/enterprise/${orgId}/rbac/policies`),

  createPolicy: (orgId: string, data: { name: string; description?: string; resource_type: string; action: string; attribute_key: string; operator: string; attribute_value: string; effect_allow?: boolean; active?: boolean }) =>
    apiClient.post<ABACPolicy>(`/enterprise/${orgId}/rbac/policies`, data),

  updatePolicy: (orgId: string, policyId: string, data: Partial<ABACPolicy>) =>
    apiClient.patch<ABACPolicy>(`/enterprise/${orgId}/rbac/policies/${policyId}`, data),

  deletePolicy: (orgId: string, policyId: string) =>
    apiClient.delete(`/enterprise/${orgId}/rbac/policies/${policyId}`),

  // Access Reviews
  listReviews: (orgId: string, status?: string) =>
    apiClient.get<AccessReview[]>(`/enterprise/${orgId}/rbac/reviews`, { params: status ? { status } : {} }),

  createReview: (orgId: string, data: { user_id: string; role_id: string; notes?: string }) =>
    apiClient.post<AccessReview>(`/enterprise/${orgId}/rbac/reviews`, data),

  decideReview: (orgId: string, reviewId: string, data: { status: 'approved' | 'revoked'; notes?: string }) =>
    apiClient.patch<AccessReview>(`/enterprise/${orgId}/rbac/reviews/${reviewId}`, data),

  // Permission Check
  checkPermission: (orgId: string, data: { user_id: string; action: string; resource_type: string; resource_attributes?: Record<string, string> }) =>
    apiClient.post<PermissionCheckResult>(`/enterprise/${orgId}/rbac/check`, data),

  // SSO Configs
  listSSOConfigs: (orgId: string) =>
    apiClient.get<SSOConfig[]>(`/enterprise/${orgId}/rbac/sso`),

  createSSOConfig: (orgId: string, data: { provider: string; issuer_url: string; client_id?: string; metadata_url?: string; enabled?: boolean; auto_provision_roles?: boolean; default_role_id?: string | null }) =>
    apiClient.post<SSOConfig>(`/enterprise/${orgId}/rbac/sso`, data),

  updateSSOConfig: (orgId: string, configId: string, data: Partial<SSOConfig>) =>
    apiClient.patch<SSOConfig>(`/enterprise/${orgId}/rbac/sso/${configId}`, data),

  deleteSSOConfig: (orgId: string, configId: string) =>
    apiClient.delete(`/enterprise/${orgId}/rbac/sso/${configId}`),
};
