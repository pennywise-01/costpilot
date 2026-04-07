import apiClient from './client';

export interface ExpenseSummary {
  this_month_total: number;
  last_month_total: number;
  this_month_forecast: number;
  change_percent: number;
  // Cache metadata
  data_source?: 'cache' | 'live' | 'stale' | 'uninitialized';
  cached_at?: string;
  expires_at?: string;
  cache_age_hours?: number;
}

export interface DailyExpense {
  date: string;
  cost: number;
}

export interface BreakdownItem {
  id: string;
  name: string;
  type?: string;
  total: number;
  previous_total: number;
  daily_breakdown: DailyExpense[];
}

export interface ExpenseBreakdown {
  total: number;
  previous_total: number;
  start_date: string;
  end_date: string;
  breakdown: BreakdownItem[];
  daily_totals: DailyExpense[];
}

export interface CleanExpense {
  resource_id: string;
  resource_name: string;
  resource_type?: string;
  cloud_account_id?: string;
  cloud_account_name?: string;
  cloud_type?: string;
  region?: string;
  owner_name?: string;
  pool_name?: string;
  cost: number;
}

// Cache status response
export interface CacheStatus {
  status: 'healthy' | 'stale' | 'expired' | 'error' | 'uninitialized';
  last_updated: string | null;
  next_update: string | null;
  accounts_cached: number;
  accounts_total: number;
  is_refreshing: boolean;
  last_error: string | null;
}

// Cache refresh response
export interface CacheRefreshResponse {
  status: 'refreshing' | 'skipped' | 'error';
  message: string;
  estimated_completion: string | null;
  refresh_id: string | null;
}

export const expensesApi = {
  getSummary: (orgId: string) =>
    apiClient.get<ExpenseSummary>(`/organizations/${orgId}/expenses/summary`),

  getBreakdown: (orgId: string, params: { start_date?: string; end_date?: string; group_by?: string }) =>
    apiClient.get<ExpenseBreakdown>(`/organizations/${orgId}/expenses/breakdown`, { params }),

  getCleanExpenses: (orgId: string, params: { limit?: number; offset?: number }) =>
    apiClient.get<CleanExpense[]>(`/organizations/${orgId}/expenses/clean`, { params }),

  // Cache management endpoints
  getCacheStatus: (orgId: string) =>
    apiClient.get<CacheStatus>(`/organizations/${orgId}/expenses/cache-status`),

  refreshCache: (orgId: string, force = false) =>
    apiClient.post<CacheRefreshResponse>(`/organizations/${orgId}/expenses/refresh`, { force }),
};
