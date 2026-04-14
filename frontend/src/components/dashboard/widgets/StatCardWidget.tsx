import React from 'react';
import { Statistic, Typography } from 'antd';
import {
  DollarOutlined,
  FundOutlined,
  CalendarOutlined,
  ThunderboltOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  CloudServerOutlined,
  HddOutlined,
  BulbOutlined,
} from '@ant-design/icons';
import WidgetShell from './WidgetShell';

const { Text } = Typography;

const ICON_MAP: Record<string, React.ReactNode> = {
  DollarOutlined: <DollarOutlined />,
  FundOutlined: <FundOutlined />,
  CalendarOutlined: <CalendarOutlined />,
  ThunderboltOutlined: <ThunderboltOutlined />,
  CloudServerOutlined: <CloudServerOutlined />,
  HddOutlined: <HddOutlined />,
  BulbOutlined: <BulbOutlined />,
};

const METRIC_LABELS: Record<string, string> = {
  monthly_spend: 'Monthly Spend',
  last_month_spend: 'Last Month',
  forecast: 'Forecast',
  change_percent: 'Change %',
  potential_savings: 'Potential Savings',
  recommendation_count: 'Recommendations',
  cloud_account_count: 'Cloud Accounts',
  resource_count: 'Resources',
};

interface StatCardWidgetProps {
  widgetId: string;
  config: {
    type: string;
    metric: string;
    title?: string;
    color?: string;
    icon?: string;
    [key: string]: unknown;
  };
  data?: Record<string, unknown>;
  loading?: boolean;
  error?: string | null;
  editMode?: boolean;
  onRemove?: () => void;
  onConfigure?: () => void;
  onRetry?: () => void;
}

const StatCardWidget: React.FC<StatCardWidgetProps> = ({
  widgetId,
  config,
  data,
  loading,
  error,
  editMode,
  onRemove,
  onConfigure,
  onRetry,
}) => {
  const metric = config.metric || 'monthly_spend';
  const color = config.color || '#1677ff';
  const icon = ICON_MAP[config.icon || ''] || <DollarOutlined />;
  const value = (data?.value as number) ?? 0;
  const changePercent = (data?.change_percent as number) ?? undefined;
  const title = config.title || METRIC_LABELS[metric] || metric;

  const isCurrency = ['monthly_spend', 'last_month_spend', 'forecast', 'potential_savings'].includes(metric);
  const isPercent = metric === 'change_percent';

  return (
    <WidgetShell
      widgetId={widgetId}
      config={config}
      loading={loading}
      error={error}
      editMode={editMode}
      onRemove={onRemove}
      onConfigure={onConfigure}
      onRetry={onRetry}
    >
      <Statistic
        title={<Text type="secondary" style={{ fontSize: 13 }}>{title}</Text>}
        value={isPercent ? Math.abs(value) : value}
        precision={isCurrency ? 2 : isPercent ? 1 : 0}
        prefix={
          <span style={{
            color,
            backgroundColor: color + '18',
            padding: 8,
            borderRadius: 8,
            fontSize: 18,
            marginRight: 4,
          }}>
            {icon}
          </span>
        }
        formatter={(v) => {
          const num = Number(v);
          if (isCurrency) {
            return (
              <span>
                ${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                {changePercent !== undefined && (
                  <span style={{
                    fontSize: 13,
                    marginLeft: 8,
                    color: changePercent >= 0 ? '#ff4d4f' : '#52c41a',
                    fontWeight: 500,
                  }}>
                    {changePercent >= 0 ? <ArrowUpOutlined style={{ fontSize: 11 }} /> : <ArrowDownOutlined style={{ fontSize: 11 }} />}
                    {' '}{Math.abs(changePercent).toFixed(1)}%
                  </span>
                )}
              </span>
            );
          }
          if (isPercent) {
            return (
              <span>
                {num.toFixed(1)}%
                {value >= 0 ? <ArrowUpOutlined style={{ fontSize: 11, marginLeft: 4, color: '#ff4d4f' }} /> : <ArrowDownOutlined style={{ fontSize: 11, marginLeft: 4, color: '#52c41a' }} />}
              </span>
            );
          }
          return <span>{num.toLocaleString()}</span>;
        }}
      />
    </WidgetShell>
  );
};

export default StatCardWidget;
