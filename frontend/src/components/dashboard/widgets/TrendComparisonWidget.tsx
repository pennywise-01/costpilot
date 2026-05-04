import React, { useMemo } from 'react';
import { Empty } from 'antd';
import { Column } from '@ant-design/charts';
import WidgetShell from './WidgetShell';

interface TrendComparisonWidgetProps {
  widgetId: string;
  config: { type: string; metric: string; title?: string; groupBy?: string; [key: string]: unknown };
  data?: Record<string, unknown>;
  loading?: boolean;
  error?: string | null;
  editMode?: boolean;
  onRemove?: () => void;
  onConfigure?: () => void;
  onRetry?: () => void;
}

const TrendComparisonWidget: React.FC<TrendComparisonWidgetProps> = ({
  widgetId, config, data, loading, error, editMode, onRemove, onConfigure, onRetry,
}) => {
  const chartData = useMemo(() => {
    const breakdown = (data?.breakdown as {
      id: string; name: string; total: number; previous_total: number;
    }[]) ?? [];
    const rows: { name: string; period: string; total: number }[] = [];
    for (const item of breakdown) {
      rows.push({ name: item.name, period: 'This Month', total: item.total });
      rows.push({ name: item.name, period: 'Last Month', total: item.previous_total ?? 0 });
    }
    return rows;
  }, [data]);

  const columnConfig = {
    data: chartData,
    xField: 'name',
    yField: 'total',
    seriesField: 'period',
    isGroup: true,
    autoFit: true,
    height: 250,
    color: ['#1677ff', '#bfbfbf'],
    label: {
      position: 'middle' as const,
      formatter: (item: { total: number }) => `$${item.total.toFixed(0)}`,
      style: { fill: '#fff', fontSize: 10 },
    },
    xAxis: { label: { style: { fontSize: 11 } } },
    yAxis: { label: { formatter: (v: string) => `$${v}`, style: { fontSize: 11 } } },
    tooltip: {
      formatter: (datum: { name: string; period: string; total: number }) => ({
        name: datum.period,
        value: `$${datum.total.toFixed(2)}`,
      }),
    },
    legend: { position: 'top' as const },
  };

  return (
    <WidgetShell widgetId={widgetId} config={config} loading={loading} error={error} editMode={editMode} onRemove={onRemove} onConfigure={onConfigure} onRetry={onRetry}>
      {chartData.length > 0 ? <Column {...columnConfig} /> : <Empty description="No comparison data available" style={{ padding: '20px 0' }} />}
    </WidgetShell>
  );
};

export default TrendComparisonWidget;
