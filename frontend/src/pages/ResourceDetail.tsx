import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Typography,
  Card,
  Breadcrumb,
  Badge,
  Tag,
  Descriptions,
  Space,
  List,
  Row,
  Col,
  Spin,
  Empty,
  message,
} from 'antd';
import {
  HomeOutlined,
  BulbOutlined,
  DollarOutlined,
  TagsOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Area } from '@ant-design/charts';
import { formatCurrency } from '@/utils/formatters';
import { CLOUD_TYPE_LABELS, CLOUD_TYPE_COLORS } from '@/utils/constants';
import { resourcesApi, ResourceDetail as ResourceDetailType } from '@/api/resources';

const { Title, Text } = Typography;

const recommendationIcons: Record<string, React.ReactNode> = {
  rightsizing: <ThunderboltOutlined style={{ color: '#faad14' }} />,
  rightsizing_instances: <ThunderboltOutlined style={{ color: '#faad14' }} />,
  reserved: <DollarOutlined style={{ color: '#52c41a' }} />,
  delete: <BulbOutlined style={{ color: '#ff4d4f' }} />,
  obsolete_instances: <BulbOutlined style={{ color: '#ff4d4f' }} />,
};

const formatTimestamp = (ts: number | undefined): string => {
  if (!ts) return '-';
  const date = new Date(ts * 1000);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

const ResourceDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [resource, setResource] = useState<ResourceDetailType | null>(null);

  useEffect(() => {
    const fetchResource = async () => {
      if (!id) return;
      
      setLoading(true);
      try {
        const decodedId = decodeURIComponent(id);
        const response = await resourcesApi.get(decodedId);
        setResource(response.data);
      } catch (error) {
        console.error('Failed to fetch resource:', error);
        message.error('Failed to load resource details');
      } finally {
        setLoading(false);
      }
    };
    
    fetchResource();
  }, [id]);

  const chartConfig = useMemo(() => {
    if (!resource) return null;
    
    const expenseData = resource.daily_expenses || [];
    const cloudColor = CLOUD_TYPE_COLORS[resource.cloud_type || ''] || '#1677ff';
    
    return {
      data: expenseData,
      xField: 'date',
      yField: 'cost',
      smooth: true,
      style: {
        fill: `linear-gradient(-90deg, ${cloudColor}33 0%, ${cloudColor}05 100%)`,
        stroke: cloudColor,
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
  }, [resource]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" tip="Loading resource details..." />
      </div>
    );
  }

  if (!resource) {
    return (
      <div>
        <Breadcrumb
          style={{ marginBottom: 16 }}
          items={[
            {
              title: (
                <span onClick={() => navigate('/resources')} style={{ cursor: 'pointer' }}>
                  <HomeOutlined style={{ marginRight: 4 }} />
                  Resources
                </span>
              ),
            },
            { title: 'Not Found' },
          ]}
        />
        <Card>
          <Empty description="Resource not found" />
        </Card>
      </div>
    );
  }

  const cloudType = resource.cloud_type || 'aws_cnr';
  const recommendations = (resource.recommendations || []).map((rec: Record<string, unknown>) => ({
    type: (rec.type as string) || 'rightsizing',
    name: (rec.name as string) || 'Recommendation',
    description: (rec.description as string) || '',
    saving: (rec.saving as number) || 0,
  }));

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          {
            title: (
              <span onClick={() => navigate('/resources')} style={{ cursor: 'pointer' }}>
                <HomeOutlined style={{ marginRight: 4 }} />
                Resources
              </span>
            ),
          },
          { title: resource.name },
        ]}
      />

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>{resource.name}</Title>
        <Tag color={CLOUD_TYPE_COLORS[cloudType]}>
          {CLOUD_TYPE_LABELS[cloudType] || cloudType}
        </Tag>
        <Badge status={resource.active ? 'success' : 'default'} text={resource.active ? 'Active' : 'Inactive'} />
      </div>

      <Card style={{ marginBottom: 24 }}>
        <Descriptions column={{ xs: 1, sm: 2, md: 3 }} size="small" bordered>
          <Descriptions.Item label="Cloud Resource ID">
            <Text copyable style={{ fontFamily: 'monospace', fontSize: 12 }}>
              {resource.cloud_resource_id}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="Type">
            <Tag>{resource.resource_type || 'Unknown'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Region">{resource.region || '-'}</Descriptions.Item>
          <Descriptions.Item label="Cloud Account">{resource.cloud_account_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="Pool">
            {resource.pool_name ? <Tag color="blue">{resource.pool_name}</Tag> : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Owner">{resource.owner_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="First Seen">{formatTimestamp(resource.first_seen)}</Descriptions.Item>
          <Descriptions.Item label="Last Seen">{formatTimestamp(resource.last_seen)}</Descriptions.Item>
          <Descriptions.Item label="Total Cost">
            <Text strong style={{ color: '#1677ff' }}>{formatCurrency(resource.total_cost)}</Text>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="Daily Expenses (Last 30 Days)" style={{ marginBottom: 24 }}>
        {chartConfig && resource.daily_expenses && resource.daily_expenses.length > 0 ? (
          <Area {...chartConfig} />
        ) : (
          <Empty description="No cost data available. Cost attribution requires AWS Cost Explorer with resource-level tags enabled." />
        )}
      </Card>

      <Row gutter={24}>
        <Col xs={24} lg={14}>
          <Card
            title={
              <Space>
                <BulbOutlined />
                <span>Recommendations</span>
              </Space>
            }
            style={{ marginBottom: 24 }}
          >
            {recommendations.length > 0 ? (
              <List
                dataSource={recommendations}
                renderItem={(item) => (
                  <List.Item
                    extra={
                      item.saving > 0 ? (
                        <Text strong style={{ color: '#52c41a', whiteSpace: 'nowrap' }}>
                          Save {formatCurrency(item.saving)}/mo
                        </Text>
                      ) : null
                    }
                  >
                    <List.Item.Meta
                      avatar={recommendationIcons[item.type] || <BulbOutlined />}
                      title={item.name}
                      description={item.description}
                    />
                  </List.Item>
                )}
              />
            ) : (
              <Text type="secondary">No recommendations at this time.</Text>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card
            title={
              <Space>
                <TagsOutlined />
                <span>Tags</span>
              </Space>
            }
            style={{ marginBottom: 24 }}
          >
            {resource.tags && Object.keys(resource.tags).length > 0 ? (
              <Space size={[8, 8]} wrap>
                {Object.entries(resource.tags).map(([key, value]) => (
                  <Tag key={key} color="geekblue" style={{ fontSize: 13 }}>
                    {key}: {value}
                  </Tag>
                ))}
              </Space>
            ) : (
              <Text type="secondary">No tags</Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default ResourceDetailPage;
