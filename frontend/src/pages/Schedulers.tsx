import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  Table,
  Tag,
  Space,
  Popconfirm,
  Switch,
  Typography,
  Row,
  Col,
  Statistic,
  Tooltip,
  Badge,
  Empty,
  Spin,
  message,
  Modal,
} from 'antd';
import {
  PlusOutlined,
  PlayCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  HistoryOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { useCurrentOrgId } from '../hooks/useCurrentOrgId';
import { schedulerApi } from '../api/scheduler';
import type {
  SchedulerConfig,
  OrganizationSchedulerStats,
  ScheduleType,
} from '../types/scheduler';
import {
  SCHEDULE_TYPE_OPTIONS,
  STATUS_COLORS,
  STATUS_LABELS,
} from '../types/scheduler';
import SchedulerForm from '../components/scheduler/SchedulerForm';
import SchedulerRunsModal from '../components/scheduler/SchedulerRunsModal';

const { Title, Text } = Typography;

const Schedulers: React.FC = () => {
  const navigate = useNavigate();
  const orgId = useCurrentOrgId();
  const [schedulers, setSchedulers] = useState<SchedulerConfig[]>([]);
  const [stats, setStats] = useState<OrganizationSchedulerStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [formVisible, setFormVisible] = useState(false);
  const [editingScheduler, setEditingScheduler] = useState<SchedulerConfig | null>(null);
  const [runsModalVisible, setRunsModalVisible] = useState(false);
  const [selectedScheduler, setSelectedScheduler] = useState<SchedulerConfig | null>(null);

  const fetchData = async () => {
    if (!orgId) return;
    setLoading(true);
    try {
      const [schedulersRes, statsRes] = await Promise.all([
        schedulerApi.listSchedulers(orgId),
        schedulerApi.getOrganizationSchedulerStats(orgId),
      ]);
      setSchedulers(schedulersRes.items);
      setStats(statsRes);
    } catch (error) {
      message.error('Failed to load schedulers');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [orgId]);

  const handleToggle = async (scheduler: SchedulerConfig) => {
    if (!orgId) return;
    try {
      await schedulerApi.toggleScheduler(orgId, scheduler.id, !scheduler.is_enabled);
      message.success(`Scheduler ${scheduler.is_enabled ? 'disabled' : 'enabled'} successfully`);
      fetchData();
    } catch (error) {
      message.error('Failed to toggle scheduler');
    }
  };

  const handleDelete = async (scheduler: SchedulerConfig) => {
    if (!orgId) return;
    try {
      await schedulerApi.deleteScheduler(orgId, scheduler.id);
      message.success('Scheduler deleted successfully');
      fetchData();
    } catch (error) {
      message.error('Failed to delete scheduler');
    }
  };

  const handleTrigger = async (scheduler: SchedulerConfig) => {
    if (!orgId) return;
    try {
      const result = await schedulerApi.triggerScheduler(orgId, scheduler.id);
      if (result.success) {
        message.success('Manual run started successfully');
      } else {
        message.warning(result.message);
      }
    } catch (error) {
      message.error('Failed to trigger scheduler');
    }
  };

  const handleEdit = (scheduler: SchedulerConfig) => {
    setEditingScheduler(scheduler);
    setFormVisible(true);
  };

  const handleCreate = () => {
    setEditingScheduler(null);
    setFormVisible(true);
  };

  const handleFormSuccess = () => {
    setFormVisible(false);
    setEditingScheduler(null);
    fetchData();
  };

  const handleViewRuns = (scheduler: SchedulerConfig) => {
    setSelectedScheduler(scheduler);
    setRunsModalVisible(true);
  };

  const getScheduleLabel = (scheduler: SchedulerConfig) => {
    switch (scheduler.schedule_type) {
      case 'interval':
        return scheduler.interval_minutes
          ? `Every ${scheduler.interval_minutes} minutes`
          : 'Interval not set';
      case 'cron':
        return scheduler.cron_expression || 'Cron not set';
      case 'once':
        return scheduler.start_date
          ? `Once at ${new Date(scheduler.start_date).toLocaleString()}`
          : 'One-time not scheduled';
      default:
        return 'Unknown';
    }
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: SchedulerConfig) => (
        <Space direction="vertical" size={0}>
          <Text strong>{name}</Text>
          {record.description && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {record.description}
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: SchedulerConfig) => (
        <Space>
          <Badge
            status={record.is_enabled ? 'success' : 'default'}
            text={record.is_enabled ? 'Enabled' : 'Disabled'}
          />
          {record.consecutive_failures > 0 && (
            <Tooltip title={`${record.consecutive_failures} consecutive failures`}>
              <ExclamationCircleOutlined style={{ color: 'orange' }} />
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: 'Schedule',
      key: 'schedule',
      render: (_: unknown, record: SchedulerConfig) => (
        <Space direction="vertical" size={0}>
          <Tag>{SCHEDULE_TYPE_OPTIONS.find((o) => o.value === record.schedule_type)?.label}</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {getScheduleLabel(record)}
          </Text>
        </Space>
      ),
    },
    {
      title: 'Data Types',
      key: 'dataTypes',
      render: (_: unknown, record: SchedulerConfig) => (
        <Space>
          {record.collect_expenses && <Tag color="blue">Expenses</Tag>}
          {record.collect_resources && <Tag color="green">Resources</Tag>}
          {record.collect_recommendations && <Tag color="purple">Recommendations</Tag>}
        </Space>
      ),
    },
    {
      title: 'Last Run',
      key: 'lastRun',
      render: (_: unknown, record: SchedulerConfig) => (
        <Text type="secondary">
          {record.last_run_at
            ? new Date(record.last_run_at).toLocaleString()
            : 'Never'}
        </Text>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 250,
      render: (_: unknown, record: SchedulerConfig) => (
        <Space>
          <Tooltip title="Toggle Enable/Disable">
            <Switch
              checked={record.is_enabled}
              onChange={() => handleToggle(record)}
              size="small"
            />
          </Tooltip>
          <Tooltip title="Manual Trigger">
            <Button
              icon={<PlayCircleOutlined />}
              size="small"
              onClick={() => handleTrigger(record)}
              disabled={!record.is_enabled}
            />
          </Tooltip>
          <Tooltip title="View Runs">
            <Button
              icon={<HistoryOutlined />}
              size="small"
              onClick={() => handleViewRuns(record)}
            />
          </Tooltip>
          <Tooltip title="Edit">
            <Button
              icon={<EditOutlined />}
              size="small"
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          <Popconfirm
            title="Delete Scheduler"
            description="Are you sure you want to delete this scheduler?"
            onConfirm={() => handleDelete(record)}
            okText="Yes"
            cancelText="No"
          >
            <Button icon={<DeleteOutlined />} size="small" danger />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={2}>Data Collection Schedulers</Title>
          <Text type="secondary">
            Configure automated data collection from your cloud providers
          </Text>
        </Col>
        <Col>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleCreate}
          >
            Create Scheduler
          </Button>
        </Col>
      </Row>

      {stats && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={4}>
            <Card>
              <Statistic
                title="Total Schedulers"
                value={stats.total_schedulers}
                prefix={<ClockCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={4}>
            <Card>
              <Statistic
                title="Active"
                value={stats.active_schedulers}
                valueStyle={{ color: '#3f8600' }}
                prefix={<CheckCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={4}>
            <Card>
              <Statistic
                title="Inactive"
                value={stats.inactive_schedulers}
                valueStyle={{ color: '#cf1322' }}
                prefix={<CloseCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={4}>
            <Card>
              <Statistic
                title="Runs Today"
                value={stats.total_runs_today}
                suffix={`/ ${stats.successful_runs_today} OK`}
              />
            </Card>
          </Col>
        </Row>
      )}

      <Card>
        <Spin spinning={loading}>
          {schedulers.length > 0 ? (
            <Table
              columns={columns}
              dataSource={schedulers}
              rowKey="id"
              pagination={{ pageSize: 10 }}
            />
          ) : (
            <Empty
              description="No schedulers configured"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            >
              <Button type="primary" onClick={handleCreate}>
                Create Your First Scheduler
              </Button>
            </Empty>
          )}
        </Spin>
      </Card>

      <Modal
        title={editingScheduler ? 'Edit Scheduler' : 'Create Scheduler'}
        open={formVisible}
        onCancel={() => {
          setFormVisible(false);
          setEditingScheduler(null);
        }}
        footer={null}
        width={700}
      >
        <SchedulerForm
          scheduler={editingScheduler}
          onSuccess={handleFormSuccess}
          onCancel={() => {
            setFormVisible(false);
            setEditingScheduler(null);
          }}
        />
      </Modal>

      {selectedScheduler && (
        <SchedulerRunsModal
          scheduler={selectedScheduler}
          visible={runsModalVisible}
          onClose={() => {
            setRunsModalVisible(false);
            setSelectedScheduler(null);
          }}
        />
      )}
    </div>
  );
};

export default Schedulers;
