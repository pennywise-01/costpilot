import apiClient from './client';

export interface RecRuleCondition {
  id?: string;
  type: string;
  meta_info: string | null;
}

export interface RecRuleResponse {
  id: string;
  name: string;
  description: string;
  priority: number;
  organization_id: string;
  creator_id: string;
  active: boolean;
  category: string;
  severity: string;
  action_description: string;
  saving_type: string;
  saving_value: number;
  conditions: RecRuleCondition[];
  created_at: string;
  is_builtin?: boolean;
  data_source?: string;
}

export interface RecRuleCreate {
  name: string;
  description?: string;
  category?: string;
  severity?: string;
  action_description?: string;
  saving_type?: string;
  saving_value?: number;
  conditions?: Omit<RecRuleCondition, 'id'>[];
  active?: boolean;
}

export interface RecRuleUpdate {
  name?: string;
  description?: string;
  category?: string;
  severity?: string;
  action_description?: string;
  saving_type?: string;
  saving_value?: number;
  conditions?: Omit<RecRuleCondition, 'id'>[];
  active?: boolean;
}

export const recommendationRulesApi = {
  list: (orgId: string) =>
    apiClient.get<RecRuleResponse[]>(`/organizations/${orgId}/recommendation-rules`),

  get: (ruleId: string) =>
    apiClient.get<RecRuleResponse>(`/recommendation-rules/${ruleId}`),

  create: (orgId: string, data: RecRuleCreate) =>
    apiClient.post<RecRuleResponse>(`/organizations/${orgId}/recommendation-rules`, data),

  update: (ruleId: string, data: RecRuleUpdate) =>
    apiClient.patch<RecRuleResponse>(`/recommendation-rules/${ruleId}`, data),

  delete: (ruleId: string) =>
    apiClient.delete<RecRuleResponse>(`/recommendation-rules/${ruleId}`),
};
