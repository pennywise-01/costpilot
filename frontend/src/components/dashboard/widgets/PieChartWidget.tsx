import React, { useMemo } from 'react';
import { Empty } from 'antd';
import { Pie } from '@ant-design/charts';
import WidgetShell from './WidgetShell';

interface PieChartWidgetProps {
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

const CLOUD_COLORS: Record<string, string> = {
  aws_cnr: '#FF9900',
  azure_cnr: '#0078D4',
  gcp_cnr: '#4285F4',
};

const PieChartWidget: React.FC<PieChartWidgetProps> = ({
  widgetId, config, data, loading, error, editMode, onRemove, onConfigure, onRetry,
}) => {
  const chartData = useMemo(() => {
    const breakdown = (data?.breakdown as { id: string; name: string; total: number }[]) ?? [];
    return breakdown.map((b) => ({
      name: b.name,
      total: b.total,
    }));
  }, [data]);

  const pieConfig = {
    data: chartData,
    angleField: 'total',
    colorField: 'name',
    height: 250,
    radius: 0.9,
    innerRadius: 0.5,
    label: {
      type: 'inner' as const,
      offset: '-30%',
      formatter: (item: { name: string; percent: number }) => `${item.name}: ${(item.percent * 100).toFixed(0)}%`,
      style: { fontSize: 11, textAlign: 'center' as const },
    },
    color: ['#1677ff', '#722ed1', '#52c41a', '#fa8c16', '#eb2f96', '#13c2c2'],
    tooltip: {
      formatter: (datum: { name: string; total: number }) => ({
        name: datum.name,
        value: `$${datum.total.toFixed(2)}`,
      }),
    },
  };

  return (
    <WidgetShell widgetId={widgetId} config={config} loading={loading} error={error} editMode={editMode} onRemove={onRemove} onConfigure={onConfigure} onRetry={onRetry}>
      {chartData.length > 0 ? <Pie {...pieConfig} /> : <Empty description="No distribution data available" style={{ padding: '20px 0' }} />}
    </WidgetShell>
  );
};

export default PieChartWidget;
