import React, { useState, useEffect } from 'react';
import {
  Typography,
  Button,
  Card,
  Table,
  Tag,
  Progress,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  TreeSelect,
  Space,
  Row,
  Col,
  Statistic,
  message,
  Spin,
} from 'antd';
import { PlusOutlined, FundOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { formatCurrency } from '@/utils/formatters';
import { POOL_PURPOSE_LABELS } from '@/utils/constants';
import { poolsApi, Pool } from '@/api/pools';
import { useCurrentOrgId } from '@/hooks/useCurrentOrgId';

const { Title, Text } = Typography;

// Transform API Pool to table record format
interface PoolRecord {
  key: string;
  id: string;
  name: string;
  purpose: string;
  budget: number;
  spent: number;
  owner: string | null;
  children?: PoolRecord[];
}

const transformPoolToRecord = (pool: Pool): PoolRecord => ({
  key: pool.id,
  id: pool.id,
  name: pool.name,
  purpose: pool.purpose,
  budget: pool.limit,
  spent: pool.spent || 0,
  owner: pool.owner || 'Unassigned',
  children: pool.children?.map(transformPoolToRecord),
});

const purposeColors: Record<string, string> = {
  budget: 'blue',
  business_unit: 'purple',
  team: 'cyan',
  project: 'green',
  cicd: 'orange',
  mlai: 'magenta',
  asset_pool: 'gold',
};

const getProgressStatus = (percent: number): 'success' | 'normal' | 'exception' => {
  if (percent > 85) return 'exception';
  if (percent >= 60) return 'normal';
  return 'success';
};

const getProgressColor = (percent: number): string => {
  if (percent > 85) return '#ff4d4f';
  if (percent >= 60) return '#faad14';
  return '#52c41a';
};

const flattenTreeForSelect = (
  nodes: PoolRecord[],
  prefix = ''
): { title: string; value: string; key: string; children?: any[] }[] => {
  return nodes.map((node) => ({
    title: prefix ? `${prefix} / ${node.name}` : node.name,
    value: node.key,
    key: node.key,
    children: node.children ? flattenTreeForSelect(node.children, node.name) : undefined,
  }));
};

// Calculate totals from pool tree
const calculateTotals = (pools: PoolRecord[]) => {
  let totalBudget = 0;
  let totalSpent = 0;

  const traverse = (nodes: PoolRecord[]) => {
    nodes.forEach((node) => {
      totalBudget += node.budget;
      totalSpent += node.spent;
      if (node.children) {
        traverse(node.children);
      }
    });
  };

  traverse(pools);
  return { totalBudget, totalSpent, totalRemaining: totalBudget - totalSpent };
};

const Pools: React.FC = () => {
  const [modalOpen, setModalOpen] = useState(false);
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
  const [form] = Form.useForm();
  const [pools, setPools] = useState<PoolRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const orgId = useCurrentOrgId();

  // Fetch pools from API
  const fetchPools = async () => {
    if (!orgId) return;
    setLoading(true);
    try {
      const response = await poolsApi.list(orgId);
      const records = response.data.map(transformPoolToRecord);
      setPools(records);
      // Auto-expand root pools
      if (records.length > 0) {
        setExpandedKeys(records.map((p) => p.key));
      }
    } catch (error) {
      message.error('Failed to load pools');
      console.error('Error loading pools:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPools();
  }, [orgId]);

  const { totalBudget, totalSpent, totalRemaining } = calculateTotals(pools);

  const columns: ColumnsType<PoolRecord> = [
    {
      title: 'Pool Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: 'Purpose',
      dataIndex: 'purpose',
      key: 'purpose',
      width: 140,
      render: (purpose: string) => (
        <Tag color={purposeColors[purpose] || 'default'}>
          {POOL_PURPOSE_LABELS[purpose] || purpose}
        </Tag>
      ),
    },
    {
      title: 'Budget',
      dataIndex: 'budget',
      key: 'budget',
      width: 140,
      align: 'right',
      render: (val: number) => <Text strong>{formatCurrency(val)}</Text>,
    },
    {
      title: 'Spent',
      dataIndex: 'spent',
      key: 'spent',
      width: 140,
      align: 'right',
      render: (val: number) => formatCurrency(val),
    },
    {
      title: 'Remaining',
      key: 'remaining',
      width: 140,
      align: 'right',
      render: (_: unknown, record: PoolRecord) => {
        const remaining = record.budget - record.spent;
        return (
          <Text type={remaining < 0 ? 'danger' : undefined}>
            {formatCurrency(remaining)}
          </Text>
        );
      },
    },
    {
      title: 'Utilization',
      key: 'utilization',
      width: 200,
      render: (_: unknown, record: PoolRecord) => {
        const percent = record.budget > 0 ? Math.round((record.spent / record.budget) * 100) : 0;
        return (
          <Space direction="vertical" size={0} style={{ width: '100%' }}>
            <Progress
              percent={percent}
              size="small"
              status={getProgressStatus(percent)}
              strokeColor={getProgressColor(percent)}
              format={(p) => `${p}%`}
            />
          </Space>
        );
      },
    },
    {
      title: 'Owner',
      dataIndex: 'owner',
      key: 'owner',
      width: 150,
    },
  ];

  const handleCreatePool = async () => {
    if (!orgId) return;
    try {
      const values = await form.validateFields();
      setCreating(true);
      await poolsApi.create(orgId, {
        name: values.name,
        limit: values.limit,
        purpose: values.purpose,
        parent_id: values.parent,
      });
      message.success(`Pool "${values.name}" created successfully`);
      form.resetFields();
      setModalOpen(false);
      // Refresh pools list
      fetchPools();
    } catch (error) {
      message.error('Failed to create pool');
      console.error('Error creating pool:', error);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          <FundOutlined style={{ marginRight: 8 }} />
          Pools
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          Create Pool
        </Button>
      </div>

      <Card style={{ marginBottom: 24 }}>
        <Row gutter={24}>
          <Col span={8}>
            <Statistic
              title="Total Budget"
              value={totalBudget}
              formatter={(val) => formatCurrency(val as number)}
              valueStyle={{ color: '#1677ff' }}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="Total Spent"
              value={totalSpent}
              formatter={(val) => formatCurrency(val as number)}
              valueStyle={{ color: '#722ed1' }}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="Remaining"
              value={totalRemaining}
              formatter={(val) => formatCurrency(val as number)}
              valueStyle={{ color: totalRemaining < 0 ? '#ff4d4f' : '#52c41a' }}
            />
          </Col>
        </Row>
      </Card>

      <Card>
        <Spin spinning={loading}>
          <Table<PoolRecord>
            columns={columns}
            dataSource={pools}
            expandable={{
              expandedRowKeys: expandedKeys,
              onExpandedRowsChange: (keys) => setExpandedKeys(keys as React.Key[]),
            }}
            pagination={false}
            size="middle"
            rowKey="key"
            locale={{ emptyText: 'No pools found. Create your first pool to get started.' }}
          />
        </Spin>
      </Card>

      <Modal
        title="Create Pool"
        open={modalOpen}
        onOk={handleCreatePool}
        onCancel={() => {
          form.resetFields();
          setModalOpen(false);
        }}
        okText="Create"
        width={520}
        confirmLoading={creating}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="Pool Name"
            rules={[{ required: true, message: 'Please enter a pool name' }]}
          >
            <Input placeholder="e.g., Development Team" />
          </Form.Item>
          <Form.Item
            name="limit"
            label="Budget Limit"
            rules={[{ required: true, message: 'Please enter a budget limit' }]}
          >
            <InputNumber
              style={{ width: '100%' }}
              min={0}
              formatter={(value) => `$ ${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
              parser={(value) => Number(value?.replace(/\$\s?|(,*)/g, '') || 0) as 0}
              placeholder="10,000"
            />
          </Form.Item>
          <Form.Item
            name="purpose"
            label="Purpose"
            rules={[{ required: true, message: 'Please select a purpose' }]}
          >
            <Select placeholder="Select purpose">
              {Object.entries(POOL_PURPOSE_LABELS).map(([value, label]) => (
                <Select.Option key={value} value={value}>
                  {label}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="parent" label="Parent Pool">
            <TreeSelect
              treeData={flattenTreeForSelect(pools)}
              placeholder="Select parent pool (optional)"
              allowClear
              treeDefaultExpandAll
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Pools;
