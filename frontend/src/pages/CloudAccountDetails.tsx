import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Typography,
  Card,
  Row,
  Col,
  Breadcrumb,
  Badge,
  Switch,
  Table,
  Tag,
  Descriptions,
  Spin,
  Empty,
} from 'antd';
import { HomeOutlined } from '@ant-design/icons';
import { Area } from '@ant-design/charts';
import type { ColumnsType } from 'antd/es/table';
import { useQuery } from '@tanstack/react-query';
import { formatCurrency } from '@/utils/formatters';
import { CLOUD_TYPE_LABELS, CLOUD_TYPE_COLORS } from '@/utils/constants';
import { cloudAccountsApi, type CloudAccountResource, type CloudAccountCostHistory } from '@/api/cloudAccounts';

const { Title, Text } = Typography;

interface ResourceRow {
  key: string;
  name: string;
  type: string;
  region: string;
  dailyCost: number;
}

const resourceColumns: ColumnsType<ResourceRow> = [
  {
    title: 'Name',
    dataIndex: 'name',
    key: 'name',
    render: (name: string) => <Text strong>{name}</Text>,
  },
  {
    title: 'Type',
    dataIndex: 'type',
    key: 'type',
    render: (type: string) => <Tag>{type}</Tag>,
  },
  {
    title: 'Region',
    dataIndex: 'region',
    key: 'region',
  },
  {
    title: 'Daily Cost',
    dataIndex: 'dailyCost',
    key: 'dailyCost',
    align: 'right',
    sorter: (a, b) => a.dailyCost - b.dailyCost,
    defaultSortOrder: 'descend',
    render: (val: number) => <Text strong>{formatCurrency(val)}</Text>,
  },
];

const CloudAccountDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: account, isLoading } = useQuery({
    queryKey: ['cloud-account', id],
    queryFn: async () => {
      const res = await cloudAccountsApi.get(id!);
      return res.data;
    },
    enabled: !!id,
  });

  const { data: resources = [], isLoading: resourcesLoading } = useQuery({
    queryKey: ['cloud-account-resources', id],
    queryFn: async () => {
      const res = await cloudAccountsApi.getResources(id!, 50);
      return res.data;
    },
    enabled: !!id,
  });

  const { data: costHistory = [], isLoading: costHistoryLoading } = useQuery({
    queryKey: ['cloud-account-cost-history', id],
    queryFn: async () => {
      const res = await cloudAccountsApi.getCostHistory(id!, 30);
      return res.data;
    },
    enabled: !!id,
  });

  if (isLoading || !account) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  const lastImportLabel = account.last_import_at
    ? new Date(account.last_import_at * 1000).toLocaleString()
    : 'Never';

  // Transform resources for the table
  const tableData: ResourceRow[] = resources.map((r: CloudAccountResource, idx: number) => ({
    key: r.id || String(idx),
    name: r.name,
    type: r.resource_type,
    region: r.region,
    dailyCost: r.daily_cost || 0,
  }));

  // Transform cost history for the chart
  const chartData = costHistory.map((d: CloudAccountCostHistory) => ({
    date: d.date,
    cost: d.cost,
  }));

  const chartConfig = {
    data: chartData,
    xField: 'date',
    yField: 'cost',
    smooth: true,
    style: {
      fill: `linear-gradient(-90deg, ${CLOUD_TYPE_COLORS[account.type] || '#1677ff'}33 0%, ${CLOUD_TYPE_COLORS[account.type] || '#1677ff'}05 100%)`,
      stroke: CLOUD_TYPE_COLORS[account.type] || '#1677ff',
    },
    axis: {
      x: {
        labelFormatter: (val: string) => {
          const d = new Date(val);
          return `${d.getMonth() + 1}/${d.getDate()}`;
        },
      },
      y: {
        labelFormatter: (val: number) => `$${val}`,
      },
    },
    tooltip: {
      channel: 'y',
      valueFormatter: (val: number) => formatCurrency(val),
    },
    height: 300,
  };

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          {
            title: (
              <span onClick={() => navigate('/cloud-accounts')} style={{ cursor: 'pointer' }}>
                <HomeOutlined style={{ marginRight: 4 }} />
                Data Sources
              </span>
            ),
          },
          { title: account.name },
        ]}
      />

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <div
          style={{
            width: 14,
            height: 14,
            borderRadius: '50%',
            backgroundColor: CLOUD_TYPE_COLORS[account.type] || '#999',
          }}
        />
        <Title level={3} style={{ margin: 0 }}>{account.name}</Title>
        <Badge status="success" text="Active" />
      </div>

      <Card style={{ marginBottom: 24 }}>
        <Descriptions column={4} size="small">
          <Descriptions.Item label="Account ID">
            <Text copyable style={{ fontFamily: 'monospace' }}>
              {account.account_id || account.id}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="Type">
            <Tag color={CLOUD_TYPE_COLORS[account.type]}>
              {CLOUD_TYPE_LABELS[account.type]}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Last Import">
            {lastImportLabel}
          </Descriptions.Item>
          <Descriptions.Item label="Auto Import">
            <Switch defaultChecked={account.auto_import} size="small" />
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Row gutter={24}>
        <Col span={24}>
          <Card title="Cost Over Time (Last 30 Days)" style={{ marginBottom: 24 }}>
            {costHistoryLoading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
                <Spin />
              </div>
            ) : chartData.length > 0 ? (
              <Area {...chartConfig} />
            ) : (
              <Empty
                description="No cost data available yet. Cost data will appear after AWS Cost Explorer syncs."
                style={{ padding: '40px 0' }}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Card title="Top Resources">
        {resourcesLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
            <Spin />
          </div>
        ) : tableData.length > 0 ? (
          <Table<ResourceRow>
            columns={resourceColumns}
            dataSource={tableData}
            pagination={false}
            size="middle"
            rowKey="key"
          />
        ) : (
          <Empty
            description="No resources discovered yet. Resources will appear after AWS account sync."
            style={{ padding: '40px 0' }}
          />
        )}
      </Card>
    </div>
  );
};

export default CloudAccountDetails;
