import React, { useEffect, useState } from 'react';
import {
  Modal,
  Table,
  Tag,
  Space,
  Button,
  Spin,
  Empty,
  message,
  Typography,
  Tabs,
  Timeline,
} from 'antd';
import {
  ReloadOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import { useCurrentOrgId } from '../../hooks/useCurrentOrgId';
import { schedulerApi } from '../../api/scheduler';
import type { SchedulerConfig, SchedulerRun, SchedulerLog } from '../../types/scheduler';
import { STATUS_COLORS, STATUS_LABELS, LOG_LEVEL_COLORS } from '../../types/scheduler';

const { Text, Title } = Typography;
const { TabPane } = Tabs;

interface SchedulerRunsModalProps {
  scheduler: SchedulerConfig;
  visible: boolean;
  onClose: () => void;
}

const SchedulerRunsModal: React.FC<SchedulerRunsModalProps> = ({
  scheduler,
  visible,
  onClose,
}) => {
  const orgId = useCurrentOrgId();
  const [runs, setRuns] = useState<SchedulerRun[]>([]);
  const [logs, setLogs] = useState<SchedulerLog[]>([]);
  const [selectedRun, setSelectedRun] = useState<SchedulerRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [logsLoading, setLogsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('runs');

  const fetchRuns = async () => {
    if (!orgId) return;
    setLoading(true);
    try {
      const response = await schedulerApi.listSchedulerRuns(orgId, scheduler.id, 0, 50);
      setRuns(response.items);
    } catch (error) {
      message.error('Failed to load runs');
    } finally {
      setLoading(false);
    }
  };

  const fetchLogs = async (runId: string) => {
    if (!orgId) return;
    setLogsLoading(true);
    try {
      const response = await schedulerApi.listSchedulerLogs(orgId, scheduler.id, runId, 0, 100);
      setLogs(response.items);
    } catch (error) {
      message.error('Failed to load logs');
    } finally {
      setLogsLoading(false);
    }
  };

  useEffect(() => {
    if (visible) {
      fetchRuns();
      setSelectedRun(null);
      setLogs([]);
      setActiveTab('runs');
    }
  }, [visible, scheduler.id]);

  const handleViewLogs = (run: SchedulerRun) => {
    setSelectedRun(run);
    fetchLogs(run.id);
    setActiveTab('logs');
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <ClockCircleOutlined />;
      case 'running':
        return <LoadingOutlined spin />;
      case 'completed':
        return <CheckCircleOutlined style={{ color: 'green' }} />;
      case 'failed':
        return <CloseCircleOutlined style={{ color: 'red' }} />;
      case 'partial':
        return <ExclamationCircleOutlined style={{ color: 'orange' }} />;
      default:
        return null;
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-';
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  };

  const runsColumns = [
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag icon={getStatusIcon(status)} color={STATUS_COLORS[status as keyof typeof STATUS_COLORS]}>
          {STATUS_LABELS[status as keyof typeof STATUS_LABELS]}
        </Tag>
      ),
    },
    {
      title: 'Started',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: 'Duration',
      key: 'duration',
      render: (_: unknown, record: SchedulerRun) => formatDuration(record.duration_seconds),
    },
    {
      title: 'Trigger',
      dataIndex: 'trigger_type',
      key: 'trigger_type',
      render: (type: string) => (
        <Tag color={type === 'manual' ? 'blue' : 'default'}>
          {type.charAt(0).toUpperCase() + type.slice(1)}
        </Tag>
      ),
    },
    {
      title: 'Results',
      key: 'results',
      render: (_: unknown, record: SchedulerRun) => (
        <Space size="small">
          {record.collected_expenses && (
            <Tag color="blue" style={{ fontSize: 11 }}>
              Exp: {record.expenses_records}
            </Tag>
          )}
          {record.collected_resources && (
            <Tag color="green" style={{ fontSize: 11 }}>
              Res: {record.resources_records}
            </Tag>
          )}
          {record.collected_recommendations && (
            <Tag color="purple" style={{ fontSize: 11 }}>
              Rec: {record.recommendations_records}
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: SchedulerRun) => (
        <Button size="small" onClick={() => handleViewLogs(record)}>
          View Logs
        </Button>
      ),
    },
  ];

  return (
    <Modal
      title={`Run History - ${scheduler.name}`}
      open={visible}
      onCancel={onClose}
      footer={[
        <Button key="close" onClick={onClose}>
          Close
        </Button>,
      ]}
      width={900}
      bodyStyle={{ padding: '0 24px 24px' }}
    >
      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <TabPane tab="Runs" key="runs">
          <Space style={{ marginBottom: 16 }}>
            <Button icon={<ReloadOutlined />} onClick={fetchRuns} loading={loading}>
              Refresh
            </Button>
          </Space>

          <Spin spinning={loading}>
            {runs.length > 0 ? (
              <Table
                columns={runsColumns}
                dataSource={runs}
                rowKey="id"
                pagination={{ pageSize: 10 }}
                size="small"
              />
            ) : (
              <Empty description="No runs yet" />
            )}
          </Spin>
        </TabPane>

        <TabPane tab="Logs" key="logs" disabled={!selectedRun}>
          {selectedRun && (
            <>
              <div style={{ marginBottom: 16 }}>
                <Button onClick={() => setActiveTab('runs')} style={{ marginBottom: 8 }}>
                  ← Back to Runs
                </Button>
                <Title level={5}>
                  Logs for Run on {new Date(selectedRun.started_at).toLocaleString()}
                </Title>
                <Space>
                  <Tag color={STATUS_COLORS[selectedRun.status as keyof typeof STATUS_COLORS]}>
                    {STATUS_LABELS[selectedRun.status as keyof typeof STATUS_LABELS]}
                  </Tag>
                  {selectedRun.error_message && (
                    <Text type="danger">Error: {selectedRun.error_message}</Text>
                  )}
                </Space>
              </div>

              <Spin spinning={logsLoading}>
                {logs.length > 0 ? (
                  <Timeline mode="left">
                    {logs.map((log) => (
                      <Timeline.Item
                        key={log.id}
                        color={LOG_LEVEL_COLORS[log.level as keyof typeof LOG_LEVEL_COLORS]}
                        label={new Date(log.logged_at).toLocaleTimeString()}
                      >
                        <Space direction="vertical" size={0}>
                          <Text strong style={{ color: LOG_LEVEL_COLORS[log.level as keyof typeof LOG_LEVEL_COLORS] }}>
                            [{log.level.toUpperCase()}]
                            {log.data_type && ` ${log.data_type}`}
                          </Text>
                          <Text>{log.message}</Text>
                          {log.cloud_account_name && (
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              Account: {log.cloud_account_name}
                            </Text>
                          )}
                        </Space>
                      </Timeline.Item>
                    ))}
                  </Timeline>
                ) : (
                  <Empty description="No logs for this run" />
                )}
              </Spin>
            </>
          )}
        </TabPane>
      </Tabs>
    </Modal>
  );
};

export default SchedulerRunsModal;
