import { useCallback, useEffect, useState, type FC } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Progress,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  App,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DownloadOutlined, PlayCircleOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { useCurrentOrgId } from '@/hooks/useCurrentOrgId';
import {
  exportsApi,
  type ExportDataType,
  type ExportFormat,
  type ExportJob,
  type ExportStatus,
} from '@/api/exports';

const { Title, Text } = Typography;

const DATA_TYPE_OPTIONS: { label: string; value: ExportDataType }[] = [
  { label: 'Expenses', value: 'expenses' },
  { label: 'Resources', value: 'resources' },
  { label: 'Recommendations', value: 'recommendations' },
];

const FORMAT_OPTIONS: { label: string; value: ExportFormat }[] = [
  { label: 'CSV', value: 'csv' },
  { label: 'JSON', value: 'json' },
  { label: 'Parquet', value: 'parquet' },
  { label: 'Excel', value: 'excel' },
];

const STATUS_COLORS: Record<ExportStatus, string> = {
  pending: 'default',
  queued: 'processing',
  processing: 'processing',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
  expired: 'default',
};

const Exports: FC = () => {
  const orgId = useCurrentOrgId();
  const { message } = App.useApp();
  const [jobs, setJobs] = useState<ExportJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [actionLoadingById, setActionLoadingById] = useState<Record<string, boolean>>({});
  const [form] = Form.useForm();

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const response = await exportsApi.listExports(orgId, 1, 50);
      setJobs(response.items);
    } catch (error) {
      message.error('Failed to load export jobs');
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  const hasRunningJobs = jobs.some((job: ExportJob) => job.status === 'queued' || job.status === 'processing');

  useEffect(() => {
    if (!hasRunningJobs) {
      return;
    }

    const intervalId = window.setInterval(() => {
      fetchJobs();
    }, 3000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [hasRunningJobs, fetchJobs]);

  const withActionLoading = async (jobId: string, action: () => Promise<void>) => {
    setActionLoadingById((prev: Record<string, boolean>) => ({ ...prev, [jobId]: true }));
    try {
      await action();
    } finally {
      setActionLoadingById((prev: Record<string, boolean>) => ({ ...prev, [jobId]: false }));
    }
  };

  const handleCreate = async () => {
    const values = await form.validateFields();
    setCreating(true);
    try {
      await exportsApi.createExport(orgId, {
        name: values.name,
        data_type: values.data_type,
        format: values.format,
      });
      message.success('Export job created');
      setCreateModalOpen(false);
      form.resetFields();
      await fetchJobs();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || 'Failed to create export job');
    } finally {
      setCreating(false);
    }
  };

  const handleExecute = async (job: ExportJob) => {
    await withActionLoading(job.id, async () => {
      try {
        setJobs((prev: ExportJob[]) =>
          prev.map((item: ExportJob) =>
            item.id === job.id
              ? {
                  ...item,
                  status: 'processing',
                  progress_percent: item.progress_percent > 0 ? item.progress_percent : 5,
                  error_message: null,
                }
              : item,
          ),
        );

        const updatedJob = await exportsApi.executeExport(orgId, job.id);
        setJobs((prev: ExportJob[]) =>
          prev.map((item: ExportJob) => (item.id === updatedJob.id ? updatedJob : item)),
        );

        if (updatedJob.status === 'failed') {
          message.error(updatedJob.error_message || 'Export execution failed');
        } else if (updatedJob.status === 'completed') {
          message.success('Export completed');
        } else {
          message.success('Export started');
        }

        await fetchJobs();
      } catch (error: any) {
        message.error(error?.response?.data?.detail || 'Failed to execute export');
      }
    });
  };

  const handleDownload = async (job: ExportJob) => {
    await withActionLoading(job.id, async () => {
      try {
        const result = await exportsApi.downloadExportFile(orgId, job.id);
        const blobUrl = window.URL.createObjectURL(result.blob);
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = result.filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => {
          window.URL.revokeObjectURL(blobUrl);
        }, 1000);
        message.success('Download started');
      } catch (error: any) {
        message.error(error?.response?.data?.detail || 'Failed to download export file');
      }
    });
  };

  const columns: ColumnsType<ExportJob> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (value: string) => <Text strong>{value}</Text>,
    },
    {
      title: 'Data Type',
      dataIndex: 'data_type',
      key: 'data_type',
      render: (value: string) => value.replace('_', ' '),
    },
    {
      title: 'Format',
      dataIndex: 'format',
      key: 'format',
      render: (value: string) => value.toUpperCase(),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (value: ExportStatus) => <Tag color={STATUS_COLORS[value]}>{value.toUpperCase()}</Tag>,
    },
    {
      title: 'Progress',
      dataIndex: 'progress_percent',
      key: 'progress_percent',
      width: 160,
      render: (value: number, record: ExportJob) => {
        if (record.status === 'failed') {
          return <Text type="danger" title={record.error_message || undefined}>Failed</Text>;
        }

        const percent = record.status === 'processing' && value === 0 ? 5 : value;
        return <Progress percent={percent} size="small" status={record.status === 'processing' ? 'active' : undefined} />;
      },
    },
    {
      title: 'Records',
      dataIndex: 'record_count',
      key: 'record_count',
      render: (value: number | null) => value ?? '-',
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value: string) => new Date(value).toLocaleString(),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 220,
      render: (_: unknown, record: ExportJob) => (
        <Space>
          {(record.status === 'pending' || record.status === 'queued' || record.status === 'failed') && (
            <Button
              icon={<PlayCircleOutlined />}
              size="small"
              loading={!!actionLoadingById[record.id]}
              onClick={() => handleExecute(record)}
            >
              Run
            </Button>
          )}
          {record.status === 'completed' && (
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              size="small"
              loading={!!actionLoadingById[record.id]}
              onClick={() => handleDownload(record)}
            >
              Download
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={3} style={{ marginBottom: 4 }}>
            Data Export
          </Title>
          <Text type="secondary">
            Create and run export jobs for expenses, resources, and recommendations.
          </Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchJobs}>
            Refresh
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
            New Export
          </Button>
        </Space>
      </div>

      <Card>
        <Table<ExportJob>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={jobs}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      <Modal
        title="Create Export Job"
        open={createModalOpen}
        onCancel={() => {
          setCreateModalOpen(false);
          if (createModalOpen) {
            form.resetFields();
          }
        }}
        onOk={handleCreate}
        okText="Create"
        confirmLoading={creating}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            data_type: 'expenses',
            format: 'csv',
          }}
        >
          <Form.Item name="name" label="Job Name" rules={[{ required: true, message: 'Job name is required' }]}>
            <Input placeholder="e.g. Monthly FinOps Report" maxLength={256} />
          </Form.Item>
          <Form.Item name="data_type" label="Data Type" rules={[{ required: true }]}>
            <Select options={DATA_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="format" label="Format" rules={[{ required: true }]}>
            <Select options={FORMAT_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Exports;
