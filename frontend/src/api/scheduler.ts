import api from './client';
import type {
  ManualTriggerRequest,
  ManualTriggerResponse,
  OrganizationSchedulerStats,
  SchedulerConfig,
  SchedulerConfigCreate,
  SchedulerConfigListResponse,
  SchedulerConfigUpdate,
  SchedulerLogListResponse,
  SchedulerRunListResponse,
  SchedulerStatsResponse,
  ToggleSchedulerRequest,
  ToggleSchedulerResponse,
} from '../types/scheduler';

const BASE_PATH = '/organizations';

export const schedulerApi = {
  // Scheduler Config CRUD
  async listSchedulers(
    orgId: string,
    skip: number = 0,
    limit: number = 100
  ): Promise<SchedulerConfigListResponse> {
    const response = await api.get<SchedulerConfigListResponse>(
      `${BASE_PATH}/${orgId}/schedulers`,
      { params: { skip, limit } }
    );
    return response.data;
  },

  async getScheduler(orgId: string, schedulerId: string): Promise<SchedulerConfig> {
    const response = await api.get<SchedulerConfig>(
      `${BASE_PATH}/${orgId}/schedulers/${schedulerId}`
    );
    return response.data;
  },

  async createScheduler(
    orgId: string,
    data: SchedulerConfigCreate
  ): Promise<SchedulerConfig> {
    const response = await api.post<SchedulerConfig>(
      `${BASE_PATH}/${orgId}/schedulers`,
      data
    );
    return response.data;
  },

  async updateScheduler(
    orgId: string,
    schedulerId: string,
    data: SchedulerConfigUpdate
  ): Promise<SchedulerConfig> {
    const response = await api.patch<SchedulerConfig>(
      `${BASE_PATH}/${orgId}/schedulers/${schedulerId}`,
      data
    );
    return response.data;
  },

  async deleteScheduler(orgId: string, schedulerId: string): Promise<void> {
    await api.delete(`${BASE_PATH}/${orgId}/schedulers/${schedulerId}`);
  },

  // Scheduler Control
  async toggleScheduler(
    orgId: string,
    schedulerId: string,
    isEnabled: boolean
  ): Promise<ToggleSchedulerResponse> {
    const response = await api.post<ToggleSchedulerResponse>(
      `${BASE_PATH}/${orgId}/schedulers/${schedulerId}/toggle`,
      { is_enabled: isEnabled }
    );
    return response.data;
  },

  async triggerScheduler(
    orgId: string,
    schedulerId: string,
    overrides?: ManualTriggerRequest
  ): Promise<ManualTriggerResponse> {
    const response = await api.post<ManualTriggerResponse>(
      `${BASE_PATH}/${orgId}/schedulers/${schedulerId}/trigger`,
      overrides || {}
    );
    return response.data;
  },

  // Statistics
  async getSchedulerStats(
    orgId: string,
    schedulerId: string
  ): Promise<SchedulerStatsResponse> {
    const response = await api.get<SchedulerStatsResponse>(
      `${BASE_PATH}/${orgId}/schedulers/${schedulerId}/stats`
    );
    return response.data;
  },

  async getOrganizationSchedulerStats(
    orgId: string
  ): Promise<OrganizationSchedulerStats> {
    const response = await api.get<OrganizationSchedulerStats>(
      `${BASE_PATH}/${orgId}/scheduler-stats`
    );
    return response.data;
  },

  // Run History
  async listSchedulerRuns(
    orgId: string,
    schedulerId: string,
    skip: number = 0,
    limit: number = 50,
    status?: string
  ): Promise<SchedulerRunListResponse> {
    const response = await api.get<SchedulerRunListResponse>(
      `${BASE_PATH}/${orgId}/schedulers/${schedulerId}/runs`,
      { params: { skip, limit, status } }
    );
    return response.data;
  },

  // Logs
  async listSchedulerLogs(
    orgId: string,
    schedulerId: string,
    runId: string,
    skip: number = 0,
    limit: number = 100,
    level?: string,
    dataType?: string
  ): Promise<SchedulerLogListResponse> {
    const response = await api.get<SchedulerLogListResponse>(
      `${BASE_PATH}/${orgId}/schedulers/${schedulerId}/runs/${runId}/logs`,
      { params: { skip, limit, level, data_type: dataType } }
    );
    return response.data;
  },
};

export default schedulerApi;
