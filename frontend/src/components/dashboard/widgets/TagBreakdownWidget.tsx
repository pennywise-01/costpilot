import React, { useMemo } from 'react';
import { Empty, Typography, Space, Tag } from 'antd';
import { Treemap } from '@ant-design/charts';
import WidgetShell from './WidgetShell';

const { Text } = Typography;

interface TagBreakdownWidgetProps {
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

const TagBreakdownWidget: React.FC<TagBreakdownWidgetProps> = ({
  widgetId, config, data, loading, error, editMode, onRemove, onConfigure, onRetry,
}) => {
  const { chartData, topTags } = useMemo(() => {
    const breakdown = (data?.breakdown as {
      id: string; name: string; total: number; type: string;
    }[]) ?? [];
    const total = breakdown.reduce((s, b) => s + b.total, 0) || 1;
    const treeData = {
      name: 'All Tags',
      children: breakdown.slice(0, 20).map((b) => ({
        name: b.name,
        value: b.total,
        pct: ((b.total / total) * 100).toFixed(1),
      })),
    };
    const top = breakdown.slice(0, 5).map((b) => ({
      name: b.name,
      total: b.total,
      pct: ((b.total / total) * 100).toFixed(1),
    }));
    return { chartData: treeData, topTags: top };
  }, [data]);

  const treemapConfig = {
    data: chartData,
    colorField: 'name',
    autoFit: true,
    height: 200,
    color: ['#1677ff', '#722ed1', '#52c41a', '#fa8c16', '#eb2f96', '#13c2c2', '#2f54eb', '#f5222d'],
    tooltip: {
      formatter: (datum: { name: string; value: number; pct: string }) => ({
        name: datum.name,
        value: `$${datum.value.toFixed(2)} (${datum.pct}%)`,
      }),
    },
    legend: false,
  };

  return (
    <WidgetShell widgetId={widgetId} config={config} loading={loading} error={error} editMode={editMode} onRemove={onRemove} onConfigure={onConfigure} onRetry={onRetry}>
      {topTags.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Treemap {...treemapConfig} />
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {topTags.map((t) => (
              <Tag key={t.name} style={{ margin: 0 }}>
                {t.name}: <Text strong style={{ fontSize: 12 }}>${t.total.toFixed(0)}</Text>
                <Text type="secondary" style={{ fontSize: 10, marginLeft: 4 }}>({t.pct}%)</Text>
              </Tag>
            ))}
          </div>
        </div>
      ) : (
        <Empty description="No tag breakdown data available" style={{ padding: '20px 0' }} />
      )}
    </WidgetShell>
  );
};

export default TagBreakdownWidget;
