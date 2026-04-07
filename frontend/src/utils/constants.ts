export const CLOUD_TYPE_LABELS: Record<string, string> = {
  aws_cnr: 'Amazon Web Services',
  azure_cnr: 'Microsoft Azure',
  azure_tenant: 'Azure Tenant',
  gcp_cnr: 'Google Cloud Platform',
  gcp_tenant: 'GCP Tenant',
  alibaba_cnr: 'Alibaba Cloud',
  kubernetes_cnr: 'Kubernetes',
  environment: 'Environment',
  nebius: 'Nebius',
  databricks: 'Databricks',
};

export const CLOUD_TYPE_COLORS: Record<string, string> = {
  aws_cnr: '#FF9900',
  azure_cnr: '#0078D4',
  gcp_cnr: '#4285F4',
  alibaba_cnr: '#FF6A00',
  kubernetes_cnr: '#326CE5',
  nebius: '#5C2D91',
  databricks: '#FF3621',
  environment: '#52c41a',
};

export const POOL_PURPOSE_LABELS: Record<string, string> = {
  budget: 'Budget',
  business_unit: 'Business Unit',
  team: 'Team',
  project: 'Project',
  cicd: 'CI/CD',
  mlai: 'ML/AI',
  asset_pool: 'Asset Pool',
};

export const RECOMMENDATION_CATEGORIES = {
  ALL: 'all',
  COST: 'cost',
  SECURITY: 'security',
} as const;

export const RECOMMENDATION_SOURCE_LABELS: Record<string, string> = {
  builtin: 'Built-in',
  custom_rule: 'Custom Rule',
  csp_native: 'CSP Native',
};

export const RECOMMENDATION_SOURCE_COLORS: Record<string, string> = {
  builtin: '#1677ff',
  custom_rule: '#722ed1',
  csp_native: '#13c2c2',
};
