import React, { useMemo } from 'react';
import { Empty, Typography, Space, Progress, Tooltip } from 'antd';
import { DollarOutlined, WarningOutlined, CheckCircleOutlined } from '@ant-design/icons';
import WidgetShell from './WidgetShell';

const { Text } = Typography;

interface BudgetGaugeWidgetProps {
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

const BudgetGaugeWidget: React.FC<BudgetGaugeWidgetProps> = ({
  widgetId, config, data, loading, error, editMode, onRemove, onConfigure, onRetry,
}) => {
  const { budget, spent, forecast, percentUsed, percentForecast, status } = useMemo(() => {
    const b = (data?.budget as number) ?? 0;
    const s = (data?.spent as number) ?? 0;
    const f = (data?.forecast as number) ?? 0;
    const pct = b > 0 ? Math.round((s / b) * 100) : 0;
    const pctForecast = b > 0 ? Math.round((f / b) * 100) : 0;
    let st: 'healthy' | 'warning' | 'danger' = 'healthy';
    if (pctForecast > 100) st = 'danger';
    else if (pctForecast > 80) st = 'warning';
    return { budget: b, spent: s, forecast: f, percentUsed: pct, percentForecast: pctForecast, status: st };
  }, [data]);

  const strokeColor = status === 'danger' ? '#f5222d' : status === 'warning' ? '#fa8c16' : '#52c41a';

  if (budget === 0) {
    return (
      <WidgetShell widgetId={widgetId} config={config} loading={loading} error={error} editMode={editMode} onRemove={onRemove} onConfigure={onConfigure} onRetry={onRetry}>
        <Empty description="No budget set. Configure a budget pool to see gauge." style={{ padding: '20px 0' }} />
      </WidgetShell>
    );
  }

  return (
    <WidgetShell widgetId={widgetId} config={config} loading={loading} error={error} editMode={editMode} onRemove={onRemove} onConfigure={onConfigure} onRetry={onRetry}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'center', gap: 8 }}>
        <Progress
          type="dashboard"
          percent={Math.min(percentUsed, 100)}
          strokeColor={strokeColor}
          format={() => `${percentUsed}%`}
          size={160}
          gapDegree={30}
          gapPosition="bottom"
        />
        <Space size={4} style={{ marginTop: 4 }}>
          {status === 'danger' ? (
            <WarningOutlined style={{ color: '#f5222d' }} />
          ) : (
            <CheckCircleOutlined style={{ color: strokeColor }} />
          )}
          <Text type={status === 'danger' ? 'danger' : 'secondary'} style={{ fontSize: 13 }}>
            {status === 'danger'
              ? `Over budget! Forecast: $${forecast.toFixed(0)}`
              : status === 'warning'
                ? `Forecast at ${percentForecast}% of budget`
                : `${percentForecast}% forecast usage`}
          </Text>
        </Space>
        <Space size={24} style={{ marginTop: 8 }}>
          <Tooltip title="Spent this month">
            <Space size={4}>
              <DollarOutlined style={{ color: '#1677ff' }} />
              <Text strong style={{ fontSize: 16 }}>${spent.toFixed(0)}</Text>
              <Text type="secondary" style={{ fontSize: 11 }}>spent</Text>
            </Space>
          </Tooltip>
          <Tooltip title="Monthly budget">
            <Space size={4}>
              <Text type="secondary" style={{ fontSize: 16 }}>${budget.toFixed(0)}</Text>
              <Text type="secondary" style={{ fontSize: 11 }}>budget</Text>
            </Space>
          </Tooltip>
        </Space>
      </div>
    </WidgetShell>
  );
};

export default BudgetGaugeWidget;
