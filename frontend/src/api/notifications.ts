import apiClient from './client';

export interface NotificationPrefItem {
  notification_type: string;
  enabled: boolean;
  recipients: string[];
}

export interface NotificationPrefResponse {
  id: string;
  notification_type: string;
  enabled: boolean;
  recipients: string[];
}

export interface NotificationPreferencesResponse {
  preferences: NotificationPrefResponse[];
}

export interface NotificationLogResponse {
  id: string;
  notification_type: string;
  recipient_email: string;
  subject: string;
  sent_at: string | null;
  error: string | null;
  created_at: string;
}

export interface NotificationLogsResponse {
  logs: NotificationLogResponse[];
  total: number;
}

export const notificationsApi = {
  getPreferences: (orgId: string) =>
    apiClient.get<NotificationPreferencesResponse>(`/organizations/${orgId}/notifications/preferences`),

  savePreferences: (orgId: string, preferences: NotificationPrefItem[]) =>
    apiClient.put<NotificationPreferencesResponse>(`/organizations/${orgId}/notifications/preferences`, {
      preferences,
    }),

  getHistory: (orgId: string, limit = 50, offset = 0) =>
    apiClient.get<NotificationLogsResponse>(`/organizations/${orgId}/notifications/history`, {
      params: { limit, offset },
    }),

  sendTest: (orgId: string, notification_type: string) =>
    apiClient.post<NotificationLogResponse>(`/organizations/${orgId}/notifications/test`, {
      notification_type,
    }),
};
