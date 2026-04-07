import apiClient from './client';

export interface WellArchitectedRule {
  id: string;
  title: string;
  description: string;
  framework: string;
  pillar: string;
  severity: string;
  estimated_saving_pct: number;
  reference_url: string;
}

export interface RecommendationItem {
  id: string;
  resource_id: string;
  resource_name: string;
  cloud_type: string;
  region: string;
  saving: number;
  source_service: string;
  dismissed: boolean;
}

export interface RecommendationType {
  type: string;
  name: string;
  description: string;
  category: string;
  cloud_types: string[];
  count: number;
  saving: number;
  items: RecommendationItem[];
  rules: WellArchitectedRule[];
  source: string;
  source_cloud_account_id: string;
}

export interface RecommendationsOverview {
  total_saving: number;
  total_count: number;
  last_run: number | null;
  next_run: number | null;
  categories: Record<string, number>;
  recommendations: RecommendationType[];
}

export const recommendationsApi = {
  getOverview: (orgId: string, cloudAccountIds?: string[]) =>
    apiClient.get<RecommendationsOverview>(`/organizations/${orgId}/recommendations`, {
      params: cloudAccountIds?.length ? { cloud_account_id: cloudAccountIds } : undefined,
    }),

  getByType: (orgId: string, type: string) =>
    apiClient.get<RecommendationType>(`/organizations/${orgId}/recommendations/${type}`),

  dismiss: (orgId: string, id: string) =>
    apiClient.patch(`/organizations/${orgId}/recommendations/${id}/dismiss`),
};
