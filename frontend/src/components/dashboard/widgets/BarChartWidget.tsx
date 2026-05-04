import React, { useMemo } from 'react';
import { Empty } from 'antd';
import { Column } from '@ant-design/charts';
import WidgetShell from './WidgetShell';

interface BarChartWidgetProps {
  widgetId: string;
  config: { type: string; metric: string; title?: string; dateRange?: number; groupBy?: string; [key: string]: unknown };
  data?: Record<string, unknown>;
  loading?: boolean;
  error?: string | null;
  editMode?: boolean;
  onRemove?: () => void;
  onConfigure?: () => void;
  onRetry?: () => void;
}

const BarChartWidget: React.FC<BarChartWidgetProps> = ({
  widgetId, config, data, loading, error, editMode, onRemove, onConfigure, onRetry,
}) => {
  const chartData = useMemo(() => {
    const breakdown = (data?.breakdown as { id: string; name: string; total: number }[]) ?? [];
    return breakdown.map((b) => ({
      name: b.name,
      total: b.total,
    }));
  }, [data]);

  const columnConfig = {
    data: chartData,
    xField: 'name',
    yField: 'total',
    autoFit: true,
    height: 250,
    color: '#1677ff',
    label: {
      position: 'middle' as const,
      formatter: (item: { total: number }) => `$${item.total.toFixed(0)}`,
      style: { fill: '#fff', fontSize: 11 },
    },
    xAxis: { label: { style: { fontSize: 11 } } },
    yAxis: { label: { formatter: (v: string) => `$${v}`, style: { fontSize: 11 } } },
    tooltip: {
      formatter: (datum: { name: string; total: number }) => ({
        name: datum.name,
        value: `$${datum.total.toFixed(2)}`,
      }),
    },
  };

  return (
    <WidgetShell widgetId={widgetId} config={config} loading={loading} error={error} editMode={editMode} onRemove={onRemove} onConfigure={onConfigure} onRetry={onRetry}>
      {chartData.length > 0 ? <Column {...columnConfig} /> : <Empty description="No breakdown data available" style={{ padding: '20px 0' }} />}
    </WidgetShell>
  );
};

export default BarChartWidget;
