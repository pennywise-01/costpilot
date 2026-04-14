import React, { useMemo } from 'react';
import { Progress, Space, Tag, Typography, Divider, Empty } from 'antd';
import WidgetShell from './WidgetShell';

const { Text, Title } = Typography;

const CATEGORY_COLORS: Record<string, string> = {
  cost: '#1677ff',
  security: '#fa8c16',
};

const CATEGORY_LABELS: Record<string, string> = {
  cost: 'Cost Optimization',
  security: 'Security',
};

interface ProgressListWidgetProps {
  widgetId: string;
  config: { type: string; metric: string; title?: string; [key: string]: unknown };
  data?: Record<string, unknown>;
  loading?: boolean;
  error?: string | null;
  editMode?: boolean;
  onRemove?: () => void;
  onConfigure?: () => void;
  onRetry?: () => void;
}

const ProgressListWidget: React.FC<ProgressListWidgetProps> = ({
  widgetId, config, data, loading, error, editMode, onRemove, onConfigure, onRetry,
}) => {
  const metric = config.metric || 'recommendation_categories';

  const items = useMemo(() => {
    if (metric === 'recommendation_categories') {
      const categories = (data?.categories as Record<string, number>) ?? {};
      const recs = (data?.recommendations as { category: string; count: number; saving: number }[]) ?? [];
      const totalSaving = (data?.total_saving as number) ?? 0;

      const byCategory: Record<string, { items: number; savings: number }> = {};
      for (const rec of recs) {
        const cat = rec.category;
        if (!byCategory[cat]) byCategory[cat] = { items: 0, savings: 0 };
        byCategory[cat].items += rec.count;
        byCategory[cat].savings += rec.saving;
      }

      return Object.entries(byCategory).map(([cat, d]) => ({
        label: CATEGORY_LABELS[cat] || cat,
        items: d.items,
        savings: Math.round(d.savings),
        color: CATEGORY_COLORS[cat] || '#888',
        proportion: totalSaving > 0 ? Math.round((d.savings / totalSaving) * 100) : 0,
      }));
    }

    if (metric === 'pool_status') {
      const pools = (data?.pools as { id: string; name: string; limit: number; purpose?: string }[]) ?? [];
      return pools.map((p) => ({
        label: p.name,
        items: 0,
        savings: 0,
        color: '#1677ff',
        proportion: 0,
      }));
    }

    return [];
  }, [data, metric]);

  const totalSavings = items.reduce((sum, i) => sum + i.savings, 0);

  return (
    <WidgetShell widgetId={widgetId} config={config} loading={loading} error={error} editMode={editMode} onRemove={onRemove} onConfigure={onConfigure} onRetry={onRetry}>
      {items.length > 0 ? (
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          {metric === 'recommendation_categories' && totalSavings > 0 && (
            <div style={{ textAlign: 'center', padding: '4px 0 8px' }}>
              <Text type="secondary" style={{ fontSize: 13 }}>Total Potential Savings</Text>
              <Title level={3} style={{ color: '#52c41a', margin: '2px 0 0', fontWeight: 700 }}>
                ${totalSavings.toLocaleString()}/mo
              </Title>
            </div>
          )}
          {items.map((item) => (
            <div key={item.label}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <Space size={8}>
                  <Text strong style={{ fontSize: 14 }}>{item.label}</Text>
                  {item.items > 0 && (
                    <Tag style={{ borderRadius: 10, fontSize: 11, lineHeight: '18px', padding: '0 8px' }}>
                      {item.items} items
                    </Tag>
                  )}
                </Space>
                {item.savings > 0 && (
                  <Text strong style={{ color: '#52c41a', fontSize: 14 }}>
                    ${item.savings.toLocaleString()}
                  </Text>
                )}
              </div>
              <Progress
                percent={item.proportion}
                strokeColor={item.color}
                trailColor="#f0f0f0"
                showInfo={false}
                strokeLinecap="round"
                size={['100%', 10]}
              />
            </div>
          ))}
        </Space>
      ) : (
        <Empty description="No data available" style={{ padding: '20px 0' }} />
      )}
    </WidgetShell>
  );
};

export default ProgressListWidget;
