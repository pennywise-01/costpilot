import apiClient from './client';

export interface CloudAccount {
  id: string;
  name: string;
  type: string;
  organization_id: string;
  auto_import: boolean;
  last_import_at: number | null;
  account_id: string;
  process_recommendations: boolean;
  created_at: string;
}

export interface CloudAccountWithLiveData extends CloudAccount {
  monthly_cost?: number;
  forecast?: number;
  last_month_cost?: number;
  resources_count?: number;
  data_source?: 'live' | 'cache' | 'unavailable';
  cached_at?: string;
}

export interface CloudAccountResource {
  id: string;
  name: string;
  resource_type: string;
  region: string;
  state: string;
  daily_cost: number;
  tags: Record<string, string>;
}

export interface CloudAccountCostHistory {
  date: string;
  cost: number;
}

export type IamTier = 'billing' | 'advisor' | 'config';

export interface AwsPolicyDocument {
  Version: string;
  Statement: Array<{
    Sid?: string;
    Effect: string;
    Action: string[];
    Resource: string;
  }>;
}

export interface AwsTrustPolicyDocument {
  Version: string;
  Statement: Array<{
    Effect: string;
    Principal: { AWS: string };
    Action: string;
    Condition?: { StringEquals?: { 'sts:ExternalId'?: string } };
  }>;
}

export interface AwsPolicyBundle {
  Policy: AwsPolicyDocument;
  TrustPolicy: AwsTrustPolicyDocument;
}

export interface AzureGcpPolicy {
  cloud: 'azure' | 'gcp';
  roles: string[];
  instructions: string;
}

export interface IamPolicyResponse {
  cloud: string;
  tiers: IamTier[];
  policy: AwsPolicyDocument | AwsPolicyBundle | AzureGcpPolicy;
}

export const cloudAccountsApi = {
  /**
   * List all cloud accounts (DB data only, no live cloud API calls)
   * Fast - returns cached data without hitting cloud provider APIs
   */
  list: (orgId: string) =>
    apiClient.get<CloudAccount[]>(`/organizations/${orgId}/cloud-accounts`),

  /**
   * Get a single cloud account (DB data only)
   */
  get: (id: string) =>
    apiClient.get<CloudAccount>(`/cloud-accounts/${id}`),

  /**
   * Get live data for a specific cloud account (with caching)
   * This fetches real-time data from cloud provider including costs and resource counts
   * Results are cached for 5 minutes to prevent rate limiting
   */
  getLiveData: (id: string, forceRefresh = false) =>
    apiClient.get<CloudAccountWithLiveData>(`/cloud-accounts/${id}/live-data`, {
      params: { force_refresh: forceRefresh },
    }),

  create: (orgId: string, data: { name: string; type: string; config: Record<string, string> }) =>
    apiClient.post<CloudAccount>(`/organizations/${orgId}/cloud-accounts`, data),

  update: (id: string, data: Partial<Pick<CloudAccount, 'name' | 'auto_import' | 'process_recommendations'>>) =>
    apiClient.patch<CloudAccount>(`/cloud-accounts/${id}`, data),

  delete: (id: string) =>
    apiClient.delete(`/cloud-accounts/${id}`),

  /**
   * Get resources for a cloud account (live fetch from cloud provider)
   * Use sparingly - prefer getLiveData() which includes cached resource counts
   */
  getResources: (id: string, limit = 50) =>
    apiClient.get<CloudAccountResource[]>(`/cloud-accounts/${id}/resources`, { params: { limit } }),

  /**
   * Get cost history for a cloud account (live fetch from cloud provider)
   * Use sparingly - prefer getLiveData() which includes cached cost summary
   */
  getCostHistory: (id: string, days = 30) =>
    apiClient.get<CloudAccountCostHistory[]>(`/cloud-accounts/${id}/cost-history`, { params: { days } }),

  /**
   * Generate the IAM policy JSON CostPilot needs on a cloud account.
   * Used by the onboarding wizard's "View required IAM policy" button.
   */
  getIamPolicy: (params: {
    cloud: 'aws' | 'azure' | 'gcp';
    tiers: IamTier[];
    trust_principal?: string;
    external_id?: string;
  }) =>
    apiClient.get<IamPolicyResponse>('/cloud-accounts/iam-policy', {
      params: {
        cloud: params.cloud,
        tiers: params.tiers.join(','),
        trust_principal: params.trust_principal,
        external_id: params.external_id,
      },
    }),
};
