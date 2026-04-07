import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Typography,
  Table,
  Tag,
  Row,
  Col,
  Select,
  Input,
  Badge,
  Card,
  Space,
  Spin,
  Empty,
  message,
} from 'antd';
import { AppstoreOutlined } from '@ant-design/icons';
import type { ColumnsType, TableProps } from 'antd/es/table';
import { formatCurrency } from '@/utils/formatters';
import { CLOUD_TYPE_COLORS } from '@/utils/constants';
import { resourcesApi, Resource } from '@/api/resources';
import { useOrgStore } from '@/store/orgStore';

const { Title, Text } = Typography;

interface ResourceRecord {
  key: string;
  id: string;
  name: string;
  cloudResourceId: string;
  type: string;
  cloud: string;
  region: string;
  owner: string;
  pool: string;
  dailyCost: number;
  tags: Record<string, string>;
}

const cloudOptions = [
  { label: 'AWS', value: 'aws_cnr' },
  { label: 'Azure', value: 'azure_cnr' },
  { label: 'GCP', value: 'gcp_cnr' },
];

const Resources: React.FC = () => {
  const navigate = useNavigate();
  const currentOrg = useOrgStore((s) => s.currentOrg);
  const [loading, setLoading] = useState(true);
  const [resources, setResources] = useState<Resource[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 15 });
  const [filters, setFilters] = useState<{
    cloud?: string;
    region?: string;
    pool?: string;
    owner?: string;
    search?: string;
  }>({});

  useEffect(() => {
    const fetchResources = async () => {
      if (!currentOrg?.id) return;
      
      setLoading(true);
      try {
        const response = await resourcesApi.list(currentOrg.id, {
          limit: 500, // Fetch all resources for client-side filtering
          offset: 0,
          cloud_type: filters.cloud,
          region: filters.region,
        });
        setResources(response.data.resources);
        setTotalCount(response.data.total_count);
      } catch (error) {
        console.error('Failed to fetch resources:', error);
        message.error('Failed to load resources');
      } finally {
        setLoading(false);
      }
    };
    
    fetchResources();
  }, [currentOrg?.id, filters.cloud, filters.region]);

  // Convert API resources to table format
  const tableData: ResourceRecord[] = useMemo(() => {
    return resources.map((r) => ({
      key: r.id,
      id: r.id,
      name: r.name,
      cloudResourceId: r.cloud_resource_id,
      type: r.resource_type || 'Unknown',
      cloud: r.cloud_type || 'aws_cnr',
      region: r.region || 'unknown',
      owner: r.owner_name || '-',
      pool: r.pool_name || '-',
      dailyCost: r.daily_cost,
      tags: r.tags || {},
    }));
  }, [resources]);

  // Client-side filtering for search and other filters
  const filteredResources = useMemo(() => {
    return tableData.filter((r) => {
      if (filters.pool && r.pool !== filters.pool) return false;
      if (filters.owner && r.owner !== filters.owner) return false;
      if (filters.search) {
        const s = filters.search.toLowerCase();
        if (
          !r.name.toLowerCase().includes(s) &&
          !r.cloudResourceId.toLowerCase().includes(s) &&
          !r.type.toLowerCase().includes(s)
        ) {
          return false;
        }
      }
      return true;
    });
  }, [tableData, filters.pool, filters.owner, filters.search]);

  // Extract unique values for filter dropdowns
  const regionOptions = useMemo(() => {
    const regions = [...new Set(resources.map(r => r.region).filter(Boolean))];
    return regions.map(r => ({ label: r!, value: r! }));
  }, [resources]);

  const columns: ColumnsType<ResourceRecord> = [
    {
      title: 'Resource Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: ResourceRecord) => (
        <Space>
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: CLOUD_TYPE_COLORS[record.cloud] || '#999',
              flexShrink: 0,
            }}
          />
          <Text strong>{name}</Text>
        </Space>
      ),
    },
    {
      title: 'Cloud Resource ID',
      dataIndex: 'cloudResourceId',
      key: 'cloudResourceId',
      width: 200,
      ellipsis: true,
      render: (val: string) => (
        <Text style={{ fontFamily: 'monospace', fontSize: 11 }} type="secondary">
          {val}
        </Text>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: 160,
      render: (type: string) => <Tag>{type}</Tag>,
    },
    {
      title: 'Cloud',
      dataIndex: 'cloud',
      key: 'cloud',
      width: 100,
      render: (cloud: string) => (
        <Tag color={CLOUD_TYPE_COLORS[cloud]}>
          {cloud === 'aws_cnr' ? 'AWS' : cloud === 'azure_cnr' ? 'Azure' : cloud === 'gcp_cnr' ? 'GCP' : 'K8s'}
        </Tag>
      ),
    },
    {
      title: 'Region',
      dataIndex: 'region',
      key: 'region',
      width: 120,
    },
    {
      title: 'Owner',
      dataIndex: 'owner',
      key: 'owner',
      width: 130,
    },
    {
      title: 'Pool',
      dataIndex: 'pool',
      key: 'pool',
      width: 110,
      render: (pool: string) => <Tag color="blue">{pool}</Tag>,
    },
    {
      title: 'Daily Cost',
      dataIndex: 'dailyCost',
      key: 'dailyCost',
      width: 120,
      align: 'right',
      sorter: (a, b) => a.dailyCost - b.dailyCost,
      defaultSortOrder: 'descend',
      render: (val: number) => <Text strong>{formatCurrency(val)}</Text>,
    },
    {
      title: 'Tags',
      dataIndex: 'tags',
      key: 'tags',
      width: 180,
      ellipsis: true,
      render: (tags: Record<string, string>) => {
        const entries = Object.entries(tags);
        const displayed = entries.slice(0, 2);
        const remaining = entries.length - 2;
        return (
          <Space size={2} wrap>
            {displayed.map(([k, v]) => (
              <Tag key={k} style={{ fontSize: 11 }}>
                {k}={v}
              </Tag>
            ))}
            {remaining > 0 && (
              <Tag style={{ fontSize: 11 }}>+{remaining}</Tag>
            )}
          </Space>
        );
      },
    },
  ];

  const handleTableChange: TableProps<ResourceRecord>['onChange'] = (newPagination) => {
    if (newPagination.current) {
      setPagination(prev => ({ ...prev, current: newPagination.current! }));
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" tip="Loading resources..." />
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Space>
          <Title level={3} style={{ margin: 0 }}>
            <AppstoreOutlined style={{ marginRight: 8 }} />
            Resources
          </Title>
          <Badge
            count={`${filteredResources.length} resource${filteredResources.length !== 1 ? 's' : ''}`}
            style={{ backgroundColor: '#f0f0f0', color: '#666', fontSize: 12 }}
          />
        </Space>
      </div>

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={12}>
          <Col flex="1">
            <Select
              placeholder="Cloud Type"
              allowClear
              style={{ width: '100%' }}
              options={cloudOptions}
              value={filters.cloud}
              onChange={(val) => setFilters((f) => ({ ...f, cloud: val }))}
            />
          </Col>
          <Col flex="1">
            <Select
              placeholder="Region"
              allowClear
              style={{ width: '100%' }}
              options={regionOptions}
              value={filters.region}
              onChange={(val) => setFilters((f) => ({ ...f, region: val }))}
            />
          </Col>
          <Col flex="2">
            <Input.Search
              placeholder="Search resources by name, ID, or type..."
              allowClear
              onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
            />
          </Col>
        </Row>
      </Card>

      <Card>
        {filteredResources.length === 0 ? (
          <Empty
            description={
              resources.length === 0
                ? "No resources found. Connect a cloud account to discover resources."
                : "No resources match your filters."
            }
          />
        ) : (
          <Table<ResourceRecord>
            columns={columns}
            dataSource={filteredResources}
            rowKey="key"
            size="middle"
            onChange={handleTableChange}
            onRow={(record) => ({
              onClick: () => navigate(`/resources/${encodeURIComponent(record.id)}`),
              style: { cursor: 'pointer' },
            })}
            pagination={{
              total: filteredResources.length,
              pageSize: pagination.pageSize,
              current: pagination.current,
              showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} resources`,
              showSizeChanger: true,
              pageSizeOptions: ['15', '30', '50', '100'],
              onShowSizeChange: (_, size) => setPagination({ current: 1, pageSize: size }),
            }}
            scroll={{ x: 1200 }}
          />
        )}
      </Card>
    </div>
  );
};

export default Resources;
