import React, { useMemo } from 'react';
import { Empty, Typography } from 'antd';
import { Area } from '@ant-design/charts';
import dayjs from 'dayjs';
import WidgetShell from './WidgetShell';

const { Text } = Typography;

interface AreaChartWidgetProps {
  widgetId: string;
  config: { type: string; metric: string; title?: string; dateRange?: number; smooth?: boolean; [key: string]: unknown };
  data?: Record<string, unknown>;
  loading?: boolean;
  error?: string | null;
  editMode?: boolean;
  onRemove?: () => void;
  onConfigure?: () => void;
  onRetry?: () => void;
}

const AreaChartWidget: React.FC<AreaChartWidgetProps> = ({
  widgetId, config, data, loading, error, editMode, onRemove, onConfigure, onRetry,
}) => {
  const chartData = useMemo(() => {
    const dailyTotals = (data?.daily_totals as { date: string; cost: number }[]) ?? [];
    return dailyTotals.map((d) => ({
      date: dayjs(d.date).format('MMM DD'),
      cost: d.cost,
    }));
  }, [data]);

  const smooth = config.smooth ?? true;

  const areaConfig = {
    data: chartData,
    xField: 'date',
    yField: 'cost',
    smooth,
    height: 250,
    color: '#1677ff',
    areaStyle: { fill: 'l(270) 0:#ffffff 0.5:#d6e4ff 1:#1677ff' },
    line: { style: { lineWidth: 2 } },
    xAxis: { tickCount: 8, label: { style: { fontSize: 11 } } },
    yAxis: { label: { formatter: (v: string) => `$${v}`, style: { fontSize: 11 } } },
    tooltip: {
      formatter: (datum: { date: string; cost: number }) => ({
        name: 'Daily Cost',
        value: `$${datum.cost.toFixed(2)}`,
      }),
    },
    animation: { appear: { animation: 'wave-in', duration: 1200 } },
  };

  return (
    <WidgetShell widgetId={widgetId} config={config} loading={loading} error={error} editMode={editMode} onRemove={onRemove} onConfigure={onConfigure} onRetry={onRetry}>
      {chartData.length > 0 ? <Area {...areaConfig} /> : <Empty description="No cost data available" style={{ padding: '20px 0' }} />}
    </WidgetShell>
  );
};

export default AreaChartWidget;
