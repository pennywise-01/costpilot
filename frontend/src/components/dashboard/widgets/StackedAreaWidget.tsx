import React, { useMemo } from 'react';
import { Empty } from 'antd';
import { Area } from '@ant-design/charts';
import dayjs from 'dayjs';
import WidgetShell from './WidgetShell';

interface StackedAreaWidgetProps {
  widgetId: string;
  config: { type: string; metric: string; title?: string; dateRange?: number; [key: string]: unknown };
  data?: Record<string, unknown>;
  loading?: boolean;
  error?: string | null;
  editMode?: boolean;
  onRemove?: () => void;
  onConfigure?: () => void;
  onRetry?: () => void;
}

const StackedAreaWidget: React.FC<StackedAreaWidgetProps> = ({
  widgetId, config, data, loading, error, editMode, onRemove, onConfigure, onRetry,
}) => {
  const chartData = useMemo(() => {
    const breakdown = (data?.breakdown as {
      id: string; name: string; daily_breakdown: { date: string; cost: number }[];
    }[]) ?? [];
    const rows: { date: string; cost: number; name: string }[] = [];
    for (const item of breakdown) {
      for (const d of item.daily_breakdown ?? []) {
        rows.push({ date: dayjs(d.date).format('MMM DD'), cost: d.cost, name: item.name });
      }
    }
    return rows;
  }, [data]);

  const areaConfig = {
    data: chartData,
    xField: 'date',
    yField: 'cost',
    seriesField: 'name',
    height: 250,
    smooth: true,
    isStack: true,
    color: ['#1677ff', '#722ed1', '#52c41a', '#fa8c16', '#eb2f96', '#13c2c2'],
    xAxis: { tickCount: 8, label: { style: { fontSize: 11 } } },
    yAxis: { label: { formatter: (v: string) => `$${v}`, style: { fontSize: 11 } } },
    tooltip: {
      formatter: (datum: { name: string; cost: number }) => ({
        name: datum.name,
        value: `$${datum.cost.toFixed(2)}`,
      }),
    },
  };

  return (
    <WidgetShell widgetId={widgetId} config={config} loading={loading} error={error} editMode={editMode} onRemove={onRemove} onConfigure={onConfigure} onRetry={onRetry}>
      {chartData.length > 0 ? <Area {...areaConfig} /> : <Empty description="No trend data available" style={{ padding: '20px 0' }} />}
    </WidgetShell>
  );
};

export default StackedAreaWidget;
