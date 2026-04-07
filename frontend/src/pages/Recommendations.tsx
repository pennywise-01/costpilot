import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Card,
  Col,
  Input,
  Row,
  Segmented,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
  Badge,
} from 'antd';
import {
  BulbOutlined,
  DollarOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { formatCurrency } from '@/utils/formatters';
import { CLOUD_TYPE_COLORS, RECOMMENDATION_SOURCE_LABELS, RECOMMENDATION_SOURCE_COLORS } from '@/utils/constants';
import { ROUTES } from '@/utils/routes';
import { recommendationsApi, type RecommendationsOverview } from '@/api/recommendations';
import { useCurrentOrgId } from '@/hooks/useCurrentOrgId';

const { Title, Text } = Typography;

type Category = 'All' | 'Cost' | 'Security' | 'Reliability' | 'Performance' | 'Operational Excellence';

const CATEGORY_LABELS: Record<string, string> = {
  cost: 'Cost',
  security: 'Security',
  reliability: 'Reliability',
  performance: 'Performance',
  operational_excellence: 'Operational Excellence',
};

const CATEGORY_COLORS: Record<string, string> = {
  cost: 'blue',
  security: 'red',
  reliability: 'green',
  performance: 'purple',
  operational_excellence: 'orange',
};
type SourceFilter = 'all' | 'builtin' | 'custom_rule' | 'csp_native';

const CLOUD_FILTERS: { key: string; label: string; color: string }[] = [
  { key: 'aws_cnr', label: 'AWS', color: CLOUD_TYPE_COLORS.aws_cnr },
  { key: 'azure_cnr', label: 'Azure', color: CLOUD_TYPE_COLORS.azure_cnr },
  { key: 'gcp_cnr', label: 'GCP', color: CLOUD_TYPE_COLORS.gcp_cnr },
];

const Recommendations: React.FC = () => {
  const navigate = useNavigate();
  const orgId = useCurrentOrgId();
  const [category, setCategory] = useState<Category>('All');
  const [source, setSource] = useState<SourceFilter>('all');
  const [search, setSearch] = useState('');
  const [selectedClouds, setSelectedClouds] = useState<Set<string>>(
    new Set(['aws_cnr', 'azure_cnr', 'gcp_cnr']),
  );

  const { data: overview, isLoading } = useQuery({
    queryKey: ['recommendations', orgId],
    queryFn: async () => {
      const res = await recommendationsApi.getOverview(orgId);
      return res.data;
    },
  });

  const recommendations = overview?.recommendations ?? [];

  const toggleCloud = (cloud: string) => {
    setSelectedClouds((prev) => {
      const next = new Set(prev);
      if (next.has(cloud)) {
        if (next.size === 1) return prev;
        next.delete(cloud);
      } else {
        next.add(cloud);
      }
      return next;
    });
  };

  const filtered = useMemo(() => {
    return recommendations.filter((rec) => {
      if (category === 'Cost' && rec.category !== 'cost') return false;
      if (category === 'Security' && rec.category !== 'security') return false;
      if (category === 'Reliability' && rec.category !== 'reliability') return false;
      if (category === 'Performance' && rec.category !== 'performance') return false;
      if (category === 'Operational Excellence' && rec.category !== 'operational_excellence') return false;

      if (source !== 'all' && rec.source !== source) return false;

      if (search && !rec.name.toLowerCase().includes(search.toLowerCase())) return false;

      const matchesCloud = rec.cloud_types.some((ct) => selectedClouds.has(ct));
      if (!matchesCloud) return false;

      return true;
    });
  }, [recommendations, category, source, search, selectedClouds]);

  const totalSavings = overview?.total_saving ?? 0;

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 24,
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div>
          <Title level={3} style={{ margin: 0 }}>
            <SafetyCertificateOutlined style={{ marginRight: 8 }} />
            Recommendations
          </Title>
        </div>
        <Space size={24} align="start" wrap>
          <Statistic
            title="Potential Monthly Savings"
            value={totalSavings}
            prefix={<DollarOutlined />}
            valueStyle={{ color: '#3f8600', fontWeight: 600 }}
          />
          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button
                icon={<SettingOutlined />}
                onClick={() => navigate(ROUTES.RECOMMENDATION_RULES)}
              >
                Manage Rules
              </Button>
              <Button disabled icon={<SyncOutlined />}>
                Force Check
              </Button>
            </Space>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {overview?.last_run
                ? `Last checked: ${new Date(overview.last_run * 1000).toLocaleString()}`
                : 'Last checked: never'}
            </Text>
          </div>
        </Space>
      </div>

      {/* Filter bar */}
      <Card style={{ marginBottom: 24 }} styles={{ body: { padding: '16px 24px' } }}>
        <Space size={16} wrap style={{ width: '100%' }}>
          <Segmented
            options={['All', 'Cost', 'Security', 'Reliability', 'Performance', 'Operational Excellence']}
            value={category}
            onChange={(val) => setCategory(val as Category)}
          />
          <Segmented
            options={[
              { value: 'all', label: 'All Sources' },
              { value: 'builtin', label: 'Built-in' },
              { value: 'custom_rule', label: 'Custom Rules' },
              { value: 'csp_native', label: 'CSP Native' },
            ]}
            value={source}
            onChange={(val) => setSource(val as SourceFilter)}
          />
          <Input.Search
            placeholder="Search recommendations..."
            allowClear
            style={{ width: 260 }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onSearch={(val) => setSearch(val)}
          />
          <Space size={8}>
            {CLOUD_FILTERS.map((cf) => (
              <Tag.CheckableTag
                key={cf.key}
                checked={selectedClouds.has(cf.key)}
                onChange={() => toggleCloud(cf.key)}
                style={{
                  borderColor: cf.color,
                  color: selectedClouds.has(cf.key) ? '#fff' : cf.color,
                  backgroundColor: selectedClouds.has(cf.key) ? cf.color : 'transparent',
                  padding: '2px 10px',
                  fontSize: 13,
                  cursor: 'pointer',
                  border: `1px solid ${cf.color}`,
                  borderRadius: 4,
                }}
              >
                {cf.label}
              </Tag.CheckableTag>
            ))}
          </Space>
        </Space>
      </Card>

      {/* Recommendation cards grid */}
      <Row gutter={[16, 16]}>
        {filtered.map((rec) => (
          <Col xs={24} sm={12} lg={8} key={rec.type}>
            <Card
              hoverable
              onClick={() => {
                navigate(`/recommendations/${rec.type}`);
              }}
              style={{
                height: '100%',
                transition: 'box-shadow 0.3s ease',
                cursor: 'pointer',
              }}
              styles={{ body: { padding: '20px 24px' } }}
            >
              {/* Title row */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 12,
                }}
              >
                <Text strong style={{ fontSize: 15 }}>
                  {rec.name}
                </Text>
                <Space size={4}>
                  <Tag
                    color={RECOMMENDATION_SOURCE_COLORS[rec.source] || '#888'}
                    style={{ fontSize: 11, margin: 0 }}
                  >
                    {RECOMMENDATION_SOURCE_LABELS[rec.source] || rec.source}
                  </Tag>
                  <Tag color={CATEGORY_COLORS[rec.category] || 'default'}>
                    {CATEGORY_LABELS[rec.category] || rec.category}
                  </Tag>
                </Space>
              </div>

              {/* Stats */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 12,
                }}
              >
                <Badge
                  count={`${rec.count} resource${rec.count !== 1 ? 's' : ''}`}
                  style={{
                    backgroundColor: '#f0f0f0',
                    color: '#595959',
                    fontSize: 12,
                    fontWeight: 500,
                    boxShadow: 'none',
                  }}
                />
                {rec.saving > 0 ? (
                  <Text style={{ color: '#3f8600', fontWeight: 600, fontSize: 14 }}>
                    Save {formatCurrency(rec.saving)}/mo
                  </Text>
                ) : (
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    No direct savings
                  </Text>
                )}
              </div>

              {/* Supported clouds */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {rec.cloud_types.map((ct) => {
                  const cf = CLOUD_FILTERS.find((f) => f.key === ct);
                  return (
                    <Tag
                      key={ct}
                      style={{
                        margin: 0,
                        fontSize: 11,
                        borderColor: cf?.color || '#888',
                        color: cf?.color || '#888',
                        background: 'transparent',
                      }}
                    >
                      {cf?.label || ct}
                    </Tag>
                  );
                })}
              </div>
            </Card>
          </Col>
        ))}

        {filtered.length === 0 && (
          <Col span={24}>
            <Card>
              <div style={{ textAlign: 'center', padding: '40px 0' }}>
                <BulbOutlined style={{ fontSize: 40, color: '#bfbfbf', marginBottom: 12 }} />
                <br />
                <Text type="secondary">No recommendations match your filters.</Text>
              </div>
            </Card>
          </Col>
        )}
      </Row>
    </div>
  );
};

export default Recommendations;
