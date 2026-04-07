export type ScheduleType = 'interval' | 'cron' | 'once';
export type SchedulerStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'partial';
export type LogLevel = 'debug' | 'info' | 'warning' | 'error';
export type TriggerType = 'scheduled' | 'manual' | 'api';

export interface SchedulerConfig {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  
  // Data types to collect
  collect_expenses: boolean;
  collect_resources: boolean;
  collect_recommendations: boolean;
  
  // Schedule configuration
  schedule_type: ScheduleType;
  interval_minutes?: number;
  cron_expression?: string;
  
  // Timing options
  timezone: string;
  start_date?: string;
  end_date?: string;
  
  // Status
  is_enabled: boolean;
  last_run_at?: string;
  next_run_at?: string;
  consecutive_failures: number;
  max_consecutive_failures: number;
  
  // Audit
  created_at: string;
  updated_at: string;
  created_by: string;
}

export interface SchedulerConfigCreate {
  name: string;
  description?: string;
  collect_expenses?: boolean;
  collect_resources?: boolean;
  collect_recommendations?: boolean;
  schedule_type?: ScheduleType;
  interval_minutes?: number;
  cron_expression?: string;
  timezone?: string;
  start_date?: string;
  end_date?: string;
  is_enabled?: boolean;
  max_consecutive_failures?: number;
}

export interface SchedulerConfigUpdate {
  name?: string;
  description?: string;
  collect_expenses?: boolean;
  collect_resources?: boolean;
  collect_recommendations?: boolean;
  schedule_type?: ScheduleType;
  interval_minutes?: number;
  cron_expression?: string;
  timezone?: string;
  start_date?: string;
  end_date?: string;
  is_enabled?: boolean;
  max_consecutive_failures?: number;
}

export interface SchedulerRun {
  id: string;
  scheduler_config_id: string;
  organization_id: string;
  
  // Execution timing
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  status: SchedulerStatus;
  
  // What was collected
  collected_expenses: boolean;
  collected_resources: boolean;
  collected_recommendations: boolean;
  
  // Status per data type
  expenses_status?: string;
  resources_status?: string;
  recommendations_status?: string;
  
  // Record counts
  expenses_records: number;
  resources_records: number;
  recommendations_records: number;
  
  // Error information
  error_message?: string;
  error_details?: Record<string, unknown>;
  
  // Trigger information
  trigger_type: TriggerType;
  triggered_by?: string;
}

export interface SchedulerLog {
  id: string;
  scheduler_run_id: string;
  logged_at: string;
  level: LogLevel;
  message: string;
  data_type?: string;
  cloud_account_id?: string;
  cloud_account_name?: string;
  details?: Record<string, unknown>;
}

export interface SchedulerConfigListResponse {
  items: SchedulerConfig[];
  total: number;
}

export interface SchedulerRunListResponse {
  items: SchedulerRun[];
  total: number;
  page: number;
  page_size: number;
}

export interface SchedulerLogListResponse {
  items: SchedulerLog[];
  total: number;
  page: number;
  page_size: number;
}

export interface SchedulerStats {
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  partial_runs: number;
  avg_duration_seconds?: number;
  last_run_status?: string;
  last_run_at?: string;
}

export interface SchedulerStatsResponse {
  scheduler_id: string;
  stats: SchedulerStats;
}

export interface OrganizationSchedulerStats {
  total_schedulers: number;
  active_schedulers: number;
  inactive_schedulers: number;
  total_runs_today: number;
  successful_runs_today: number;
  failed_runs_today: number;
  upcoming_runs: Array<{
    scheduler_id: string;
    scheduler_name: string;
    next_run_at: string;
  }>;
}

export interface ManualTriggerRequest {
  collect_expenses?: boolean;
  collect_resources?: boolean;
  collect_recommendations?: boolean;
}

export interface ManualTriggerResponse {
  success: boolean;
  run_id?: string;
  message: string;
}

export interface ToggleSchedulerRequest {
  is_enabled: boolean;
}

export interface ToggleSchedulerResponse {
  success: boolean;
  is_enabled: boolean;
  message: string;
}

export const SCHEDULE_TYPE_OPTIONS: { value: ScheduleType; label: string; description: string }[] = [
  { value: 'interval', label: 'Interval', description: 'Run at regular intervals (e.g., every 30 minutes)' },
  { value: 'cron', label: 'Cron', description: 'Use cron expressions for complex schedules' },
  { value: 'once', label: 'One-time', description: 'Run once at a specific date/time' },
];

export const COMMON_INTERVALS = [
  { value: 5, label: '5 minutes' },
  { value: 15, label: '15 minutes' },
  { value: 30, label: '30 minutes' },
  { value: 60, label: '1 hour' },
  { value: 360, label: '6 hours' },
  { value: 720, label: '12 hours' },
  { value: 1440, label: '1 day' },
  { value: 10080, label: '1 week' },
];

export const COMMON_CRON_EXPRESSIONS = [
  { value: '0 * * * *', label: 'Every hour' },
  { value: '0 */6 * * *', label: 'Every 6 hours' },
  { value: '0 0 * * *', label: 'Daily at midnight' },
  { value: '0 9 * * 1-5', label: 'Weekdays at 9 AM' },
  { value: '0 0 * * 0', label: 'Weekly on Sunday' },
  { value: '0 0 1 * *', label: 'Monthly on 1st' },
];

export const TIMEZONE_OPTIONS = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Asia/Singapore',
  'Asia/Dubai',
  'Australia/Sydney',
  'Pacific/Auckland',
];

export const STATUS_COLORS: Record<SchedulerStatus, string> = {
  pending: 'gold',
  running: 'blue',
  completed: 'green',
  failed: 'red',
  cancelled: 'gray',
  partial: 'orange',
};

export const STATUS_LABELS: Record<SchedulerStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
  partial: 'Partial',
};

export const LOG_LEVEL_COLORS: Record<LogLevel, string> = {
  debug: 'gray',
  info: 'blue',
  warning: 'orange',
  error: 'red',
};
