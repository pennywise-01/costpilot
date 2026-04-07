import apiClient from './client';

export type ExportDataType = 'expenses' | 'resources' | 'recommendations';
export type ExportFormat = 'csv' | 'json' | 'parquet' | 'excel';
export type ExportStatus =
  | 'pending'
  | 'queued'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'expired';

export interface ExportColumn {
  name: string;
  label: string;
  type?: string;
  format?: string | null;
  width?: number | null;
}

export interface ExportJob {
  id: string;
  organization_id: string;
  template_id: string | null;
  name: string;
  data_type: ExportDataType;
  format: ExportFormat;
  columns: ExportColumn[];
  filters: Record<string, unknown>;
  date_range_start: string | null;
  date_range_end: string | null;
  group_by: string[] | null;
  sort_by: string | null;
  sort_order: 'asc' | 'desc' | null;
  status: ExportStatus;
  progress_percent: number;
  record_count: number | null;
  file_size_bytes: number | null;
  file_url: string | null;
  error_message: string | null;
  created_by: string;
  started_at: string | null;
  completed_at: string | null;
  expires_at: string | null;
  is_scheduled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExportJobListResponse {
  items: ExportJob[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface ExportJobCreateRequest {
  name: string;
  data_type: ExportDataType;
  format: ExportFormat;
  columns?: ExportColumn[];
  filters?: Record<string, unknown>;
}

export interface ExportDownloadResponse {
  download_url: string;
  expires_in_seconds: number;
  filename: string;
  file_size_bytes: number | null;
}

export interface ExportFileDownloadResult {
  blob: Blob;
  filename: string;
  contentType: string;
}

const BASE_PATH = '/enterprise/organizations';

function extractFilenameFromContentDisposition(
  contentDisposition?: string,
  fallbackFilename: string = 'export.csv',
): string {
  if (!contentDisposition) {
    return fallbackFilename;
  }

  const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(contentDisposition);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const asciiMatch = /filename="?([^";]+)"?/i.exec(contentDisposition);
  if (asciiMatch?.[1]) {
    return asciiMatch[1];
  }

  return fallbackFilename;
}

export const exportsApi = {
  listExports: async (
    orgId: string,
    page: number = 1,
    limit: number = 20,
    status?: ExportStatus,
    dataType?: ExportDataType,
  ): Promise<ExportJobListResponse> => {
    const response = await apiClient.get<ExportJobListResponse>(
      `${BASE_PATH}/${orgId}/exports`,
      { params: { page, limit, status, data_type: dataType } },
    );
    return response.data;
  },

  createExport: async (
    orgId: string,
    data: ExportJobCreateRequest,
  ): Promise<ExportJob> => {
    const response = await apiClient.post<ExportJob>(`${BASE_PATH}/${orgId}/exports`, {
      columns: [],
      filters: {},
      ...data,
    });
    return response.data;
  },

  executeExport: async (orgId: string, jobId: string): Promise<ExportJob> => {
    const response = await apiClient.post<ExportJob>(
      `${BASE_PATH}/${orgId}/exports/${jobId}/execute`,
    );
    return response.data;
  },

  getDownloadInfo: async (orgId: string, jobId: string): Promise<ExportDownloadResponse> => {
    const response = await apiClient.get<ExportDownloadResponse>(
      `${BASE_PATH}/${orgId}/exports/${jobId}/download`,
    );
    return response.data;
  },

  downloadExportFile: async (orgId: string, jobId: string): Promise<ExportFileDownloadResult> => {
    const response = await apiClient.get<Blob>(
      `${BASE_PATH}/${orgId}/exports/${jobId}/file`,
      { responseType: 'blob' },
    );

    const contentDisposition = response.headers['content-disposition'] as string | undefined;
    const filename = extractFilenameFromContentDisposition(
      contentDisposition,
      `export_${jobId}.csv`,
    );

    return {
      blob: response.data,
      filename,
      contentType: (response.headers['content-type'] as string | undefined) || 'application/octet-stream',
    };
  },
};
