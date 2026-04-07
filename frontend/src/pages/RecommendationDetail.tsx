import React, { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Breadcrumb,
  Card,
  Col,
  Row,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import {
  ArrowLeftOutlined,
  DollarOutlined,
  LinkOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useQuery } from '@tanstack/react-query';
import { formatCurrency } from '@/utils/formatters';
import {
  CLOUD_TYPE_LABELS,
  CLOUD_TYPE_COLORS,
  RECOMMENDATION_SOURCE_LABELS,
  RECOMMENDATION_SOURCE_COLORS,
} from '@/utils/constants';
import { ROUTES } from '@/utils/routes';
import { recommendationsApi, type WellArchitectedRule, type RecommendationItem } from '@/api/recommendations';
import { useCurrentOrgId } from '@/hooks/useCurrentOrgId';

const { Title, Text, Paragraph } = Typography;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  cost: 'Cost Optimization',
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

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#cf1322',
  high: '#fa541c',
  medium: '#faad14',
  low: '#52c41a',
};

const FRAMEWORK_COLORS: Record<string, string> = {
  'AWS Well-Architected': '#FF9900',
  'Azure Well-Architected': '#0078D4',
  'GCP Architecture Framework': '#4285F4',
};

function cloudLabel(cloudType: string): string {
  return CLOUD_TYPE_LABELS[cloudType] || cloudType;
}

function cloudColor(cloudType: string): string {
  return CLOUD_TYPE_COLORS[cloudType] || '#888';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const RecommendationDetail: React.FC = () => {
  const { type } = useParams<{ type: string }>();
  const navigate = useNavigate();
  const orgId = useCurrentOrgId();
  const [expandedRules, setExpandedRules] = useState<Set<string>>(new Set());

  const { data: rec, isLoading } = useQuery({
    queryKey: ['recommendation-detail', orgId, type],
    queryFn: async () => {
      const res = await recommendationsApi.getByType(orgId, type!);
      return res.data;
    },
    enabled: !!type,
  });

  const rules = rec?.rules ?? [];

  const totalEstimatedSaving = useMemo(() => {
    if (!rec || rec.saving === 0) return 0;
    const avgPct = rules.length > 0
      ? rules.reduce((s, r) => s + r.estimated_saving_pct, 0) / rules.length
      : 0;
    return Math.round((rec.saving * avgPct) / 100);
  }, [rec, rules]);

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!type || !rec) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Title level={4}>Recommendation type not found</Title>
        <a onClick={() => navigate(ROUTES.RECOMMENDATIONS)}>Back to Recommendations</a>
      </div>
    );
  }

  const toggleRule = (id: string) => {
    setExpandedRules((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const columns: ColumnsType<WellArchitectedRule> = [
    {
      title: 'Rule',
      dataIndex: 'title',
      key: 'title',
      render: (text: string, rule) => (
        <a
          onClick={() => toggleRule(rule.id)}
          style={{ fontWeight: 500 }}
        >
          {text}
        </a>
      ),
    },
    {
      title: 'Framework',
      dataIndex: 'framework',
      key: 'framework',
      width: 200,
      render: (fw: string) => (
        <Tag color={FRAMEWORK_COLORS[fw] || '#888'}>{fw}</Tag>
      ),
    },
    {
      title: 'Pillar',
      dataIndex: 'pillar',
      key: 'pillar',
      width: 160,
    },
    {
      title: 'Severity',
      dataIndex: 'severity',
      key: 'severity',
      width: 100,
      render: (sev: string) => (
        <Tag
          color={SEVERITY_COLORS[sev] || '#888'}
          style={{ textTransform: 'capitalize' }}
        >
          {sev}
        </Tag>
      ),
    },
    {
      title: 'Est. Saving',
      dataIndex: 'estimated_saving_pct',
      key: 'saving',
      width: 120,
      align: 'right',
      render: (pct: number) =>
        pct > 0 ? (
          <Text style={{ color: '#3f8600', fontWeight: 600 }}>~{pct}%</Text>
        ) : (
          <Text type="secondary">N/A</Text>
        ),
    },
    {
      title: 'Reference',
      dataIndex: 'reference_url',
      key: 'reference',
      width: 100,
      align: 'center',
      render: (url: string) =>
        url ? (
          <a href={url} target="_blank" rel="noopener noreferrer">
            <LinkOutlined /> Docs
          </a>
        ) : null,
    },
  ];

  return (
    <div>
      {/* Breadcrumb */}
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          {
            title: (
              <a onClick={() => navigate(ROUTES.RECOMMENDATIONS)}>
                <ArrowLeftOutlined style={{ marginRight: 4 }} />
                Recommendations
              </a>
            ),
          },
          { title: rec.name },
        ]}
      />

      {/* Header card */}
      <Card style={{ marginBottom: 24 }}>
        <Row gutter={24} align="middle">
          <Col flex="auto">
            <Title level={3} style={{ margin: 0, marginBottom: 8 }}>
              <SafetyCertificateOutlined style={{ marginRight: 8 }} />
              {rec.name}
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 12, maxWidth: 700 }}>
              {rec.description}
            </Paragraph>
            <Space size={8} wrap>
              <Tag color={CATEGORY_COLORS[rec.category] || 'default'}>
                {CATEGORY_LABELS[rec.category] || rec.category}
              </Tag>
              <Tag
                color={RECOMMENDATION_SOURCE_COLORS[rec.source] || '#888'}
              >
                {RECOMMENDATION_SOURCE_LABELS[rec.source] || rec.source}
              </Tag>
              {rec.cloud_types.map((ct) => (
                <Tag
                  key={ct}
                  style={{
                    borderColor: cloudColor(ct),
                    color: cloudColor(ct),
                    background: 'transparent',
                  }}
                >
                  {cloudLabel(ct)}
                </Tag>
              ))}
            </Space>
          </Col>
          <Col>
            <Space size={32}>
              <Statistic title="Affected Resources" value={rec.count} />
              {rec.saving > 0 ? (
                <Statistic
                  title="Est. Monthly Savings"
                  value={rec.saving}
                  prefix={<DollarOutlined />}
                  valueStyle={{ color: '#3f8600', fontWeight: 600 }}
                />
              ) : (
                <Statistic title="Est. Monthly Savings" value="N/A" />
              )}
              {totalEstimatedSaving > 0 && (
                <Statistic
                  title="Projected After Rules"
                  value={totalEstimatedSaving}
                  prefix={<DollarOutlined />}
                  valueStyle={{ color: '#3f8600', fontWeight: 600 }}
                  suffix="/mo"
                />
              )}
            </Space>
          </Col>
        </Row>
      </Card>

      {/* Rules table */}
      {rules.length > 0 && (
        <Card
          title={`Well-Architected Framework Rules (${rules.length})`}
          styles={{ body: { padding: 0 } }}
        >
          <Table<WellArchitectedRule>
            dataSource={rules}
            columns={columns}
            rowKey="id"
            pagination={false}
            expandable={{
              expandedRowKeys: Array.from(expandedRules),
              onExpand: (expanded, record) => toggleRule(record.id),
              expandedRowRender: (rule) => (
                <div style={{ padding: '8px 16px' }}>
                  <Paragraph style={{ marginBottom: 8 }}>{rule.description}</Paragraph>
                  {rule.estimated_saving_pct > 0 && rec.saving > 0 && (
                    <Text type="secondary">
                      Applying this rule could save approximately{' '}
                      <Text strong style={{ color: '#3f8600' }}>
                        {formatCurrency(Math.round((rec.saving * rule.estimated_saving_pct) / 100))}/mo
                      </Text>{' '}
                      ({rule.estimated_saving_pct}% of current spend on affected resources).
                    </Text>
                  )}
                  {rule.estimated_saving_pct === 0 && (
                    <Text type="secondary">
                      This is a security best practice with no direct cost savings, but reduces risk exposure.
                    </Text>
                  )}
                </div>
              ),
            }}
          />
        </Card>
      )}

      {/* Affected Resources Table */}
      {rec.items && rec.items.length > 0 && (
        <Card
          title={`Affected Resources (${rec.items.length})`}
          style={{ marginTop: 24 }}
          styles={{ body: { padding: 0 } }}
        >
          <Table<RecommendationItem>
            dataSource={rec.items}
            rowKey="id"
            pagination={false}
            columns={[
              {
                title: 'Resource Name',
                dataIndex: 'resource_name',
                key: 'resource_name',
                render: (name: string, item: RecommendationItem) => (
                  <Space direction="vertical" size={0}>
                    <Text strong>{name || 'N/A'}</Text>
                    {item.resource_id && (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {item.resource_id.length > 60
                          ? `...${item.resource_id.slice(-60)}`
                          : item.resource_id}
                      </Text>
                    )}
                  </Space>
                ),
              },
              {
                title: 'Cloud',
                dataIndex: 'cloud_type',
                key: 'cloud_type',
                width: 100,
                render: (ct: string) => (
                  <Tag style={{ borderColor: cloudColor(ct), color: cloudColor(ct), background: 'transparent' }}>
                    {cloudLabel(ct)}
                  </Tag>
                ),
              },
              {
                title: 'Region',
                dataIndex: 'region',
                key: 'region',
                width: 120,
                render: (region: string) => region || 'N/A',
              },
              {
                title: 'Est. Savings',
                dataIndex: 'saving',
                key: 'saving',
                width: 120,
                align: 'right',
                render: (saving: number) =>
                  saving > 0 ? (
                    <Text style={{ color: '#3f8600', fontWeight: 600 }}>
                      {formatCurrency(saving)}/mo
                    </Text>
                  ) : (
                    <Text type="secondary">N/A</Text>
                  ),
              },
              {
                title: 'Status',
                dataIndex: 'dismissed',
                key: 'dismissed',
                width: 100,
                align: 'center',
                render: (dismissed: boolean) =>
                  dismissed ? (
                    <Tag color="default">Dismissed</Tag>
                  ) : (
                    <Tag color="processing">Active</Tag>
                  ),
              },
            ]}
          />
        </Card>
      )}
    </div>
  );
};

export default RecommendationDetail;
